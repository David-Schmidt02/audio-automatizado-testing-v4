from collections import defaultdict
import gc

clients = defaultdict() # client_id -> dict con 'wavefile', 'lock', 'buffer', 'next_seq', 'last_time'

import socket
import threading
import signal
import sys
import os
import time
import wave
from collections import defaultdict
from rtp import RTP 

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import BUFFER_SIZE, SAMPLE_RATE, CHANNELS, LISTEN_IP, LISTEN_PORT

clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

INACTIVITY_TIMEOUT = 5  # segundos de inactividad para cerrar WAV

# Contador de paquetes fuera de orden por cliente
out_of_order_count = {}

def create_wav_file(client_id):
    """Crea un WAV nuevo para el cliente en un directorio propio dentro de 'records'."""
    base_dir = "records"
    client_dir = os.path.join(base_dir, str(client_id))
    os.makedirs(client_dir, exist_ok=True)
    name_wav = os.path.join(client_dir, f"record-{time.strftime('%Y%m%d-%H%M%S')}-{client_id}.wav")
    wf = wave.open(name_wav, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    log(f"💾 [Cliente {client_id}] WAV abierto: {name_wav}", "INFO")
    return wf


MAX_WAIT = 0.08
# --- Jitter buffer configurable ---
def log_jitter(client_id, buffer, next_seq):
    """
    Registra la información de jitter para un cliente específico.
    """
    if buffer:
        min_seq = min(buffer.keys())
        jitter = (min_seq - next_seq) % 65536
        log(f"[Jitter] Cliente {client_id}: jitter acumulado = {jitter} (next_seq={next_seq}, min_seq={min_seq}, buffer={sorted(buffer.keys())})", "DEBUG")

def check_prefill(buffer, jitter_buffer_size, prefill_done, client_id):
    """
    Verifica si el pre-llenado del jitter buffer ha sido completado.
    """
    if not prefill_done:
        if len(buffer) >= jitter_buffer_size:
            log(f"[JitterBuffer] Cliente {client_id}: pre-llenado completado con {len(buffer)} paquetes", "INFO")
            return True
    return prefill_done

def handle_inactivity(client, client_id):
    """
    Maneja la inactividad de un cliente, cerrando su archivo WAV si ha estado inactivo durante más de INACTIVITY_TIMEOUT segundos.
    """
    if not client['buffer'] and time.time() - client['last_time'] > INACTIVITY_TIMEOUT:
        try:
            client['wavefile'].close()
            log(f"[Worker] Cliente {client_id} inactivo por {INACTIVITY_TIMEOUT}s, WAV cerrado y recursos liberados.", "INFO")
        except Exception as e:
            log(f"[Worker] Error cerrando WAV de cliente {client_id}: {e}", "ERROR")
        with clients_lock:
            clients.pop(client_id, None)
        return True
    return False

def process_buffer(client, client_id, jitter_buffer_size):
    """
    Procesa el buffer de un cliente, escribiendo los paquetes en su archivo WAV.
    """
    buffer = client['buffer']
    next_seq = client['next_seq']
    while buffer:
        if next_seq in buffer:
            payload = buffer.pop(next_seq)
            client['wavefile'].writeframes(payload)
            client['next_seq'] = next_seq = (next_seq + 1) % 65536
            client['last_time'] = time.time()
        else:
            if len(buffer) >= jitter_buffer_size and time.time() - client['last_time'] > MAX_WAIT:
                min_seq = min(buffer.keys())
                log(f"[JitterBuffer] Timeout o lag, saltando de seq={next_seq} a seq={min_seq} (buffer: {sorted(buffer.keys())})", "WARN")
                client['next_seq'] = next_seq = min_seq
                client['last_time'] = time.time()
            else:
                break

def iniciar_worker_cliente(client_id, jitter_buffer_size):
    """Hilo que procesa paquetes en orden y escribe en WAV usando jitter buffer real."""
    log(f"[Worker] Iniciado para cliente con SSRC: {client_id}", "INFO")
    client = clients[client_id]
    prefill_done = False
    while True:
        with client['lock']:
            buffer = client['buffer']
            next_seq = client['next_seq']

            log_jitter(client_id, buffer, next_seq)

            # Prefill del jitter buffer
            prefill_done = check_prefill(buffer, jitter_buffer_size, prefill_done, client_id)
            if not prefill_done:
                if handle_inactivity(client, client_id):
                    break
                time.sleep(0.01)
                continue

            # Procesar buffer
            process_buffer(client, client_id, jitter_buffer_size)

            # Cierre por inactividad
            if handle_inactivity(client, client_id):
                break

        time.sleep(0.01)

def shutdown_handler(signum, frame):
    log("\n🛑 Shutting down server...", "WARNING")

    with clients_lock:
        log("💾 Closing all WAV files...", "INFO")
        for client_id, client in clients.items():
            try:
                client['wavefile'].close()
                log(f"Closed WAV for client {client_id}", "INFO")
            except Exception as e:
                log(f"Error closing WAV file for client {client_id}: {e}", "ERROR")

    log("✅ Cleanup complete.", "INFO")
    sys.exit(0)

# Log periódico del tamaño de buffers de todos los clientes

def log_buffer_sizes_periodically():
    while True:
        with clients_lock:
            for client_id, client in clients.items():
                buffer_size = len(client['buffer'])
                log(f"[Buffer] Cliente {client_id}: tamaño del buffer = {buffer_size}", "DEBUG")
        # Log de objetos grandes en memoria (debug)
        all_objs = gc.get_objects()
        wav_count = sum(1 for o in all_objs if hasattr(o, 'writeframes'))
        log(f"[Mem] Objetos tipo wave abiertos: {wav_count}", "DEBUG")
        time.sleep(30)

# Lanzar el log periódico en un hilo aparte
threading.Thread(target=log_buffer_sizes_periodically, daemon=True).start()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    JITTER_BUFFER_SIZE = 20  # Cambia este valor si quieres otro tamaño

    def parse_rtp_packet(data):
        try:
            rtp_packet = RTP()
            rtp_packet.fromBytearray(bytearray(data))
            return rtp_packet
        except Exception as e:
            log(f"Error parsing RTP packet: {e}", "ERROR")
            return None

    def get_or_create_client(client_id, seq_num):
        with clients_lock:
            if client_id not in clients:
                clients[client_id] = {
                    'wavefile': create_wav_file(client_id),
                    'lock': threading.Lock(),
                    'buffer': dict(),
                    'next_seq': seq_num,
                    'last_time': time.time(),
                }
                t = threading.Thread(target=iniciar_worker_cliente, args=(client_id, JITTER_BUFFER_SIZE), daemon=True)
                t.start()
        return clients[client_id]

    def handle_rtp_packet(client, seq_num, payload):
        with client['lock']:
            if seq_num in client['buffer']:
                log(f"[RTP] Paquete fuera de orden para cliente {client['wavefile'].name}: seq={seq_num} ya recibido", "WARNING")
                return False
            client['buffer'][seq_num] = payload
            client['last_time'] = time.time()
            return True

    def udp_listener_fixed_jitter():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1<<20)
        sock.bind((LISTEN_IP, LISTEN_PORT))
        log(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}", "INFO")
        log("🔊 Saving incoming audio streams to .wav files...", "INFO")
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                rtp_packet = parse_rtp_packet(data)
                if not rtp_packet:
                    continue
                client_id = str(rtp_packet.ssrc)
                seq_num = rtp_packet.sequenceNumber
                client = get_or_create_client(client_id, seq_num)
                handle_rtp_packet(client, seq_num, rtp_packet.payload)
            except Exception as e:
                if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                    break
                print(f"Error receiving or processing packet: {e}")
        sock.close()

    listener_thread = threading.Thread(target=udp_listener_fixed_jitter, daemon=True)
    listener_thread.start()

    # Mantener el programa vivo esperando señal para cerrar
    signal.pause()
