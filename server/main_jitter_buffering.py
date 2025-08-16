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
import struct
from collections import defaultdict
from rtp import RTP 

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log

# Configuración RTP
RTP_VERSION = 2
PAYLOAD_TYPE = 96

LISTEN_IP = "192.168.0.82" # Debe ser la de la misma máquina Host 192.168.0.....
LISTEN_PORT = 6001

FRAME_SIZE = 960  # Samples por paquete (aumentado para mayor buffer)
SAMPLE_RATE = 48000
SAMPLE_FORMAT = "int16"

CHANNELS = 1  # Mono

clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

INACTIVITY_TIMEOUT = 10  # segundos de inactividad para cerrar WAV

# Contador de paquetes fuera de orden por cliente
out_of_order_count = {}

def create_wav_file(client_id):
    """Crea un WAV nuevo para el cliente."""
    name_wav = f"record-{time.strftime('%Y%m%d-%H%M%S')}-{client_id}.wav"
    wf = wave.open(name_wav, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    log(f"💾 [Cliente {client_id}] WAV abierto: {name_wav}", "INFO")
    return wf

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    log(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}", "INFO")
    log("🔊 Saving incoming audio streams to .wav files...", "INFO")
    
    while True:
        try:
            data, addr = sock.recvfrom(1600)
            try:
                rtp_packet = RTP()
                rtp_packet.fromBytearray(bytearray(data))
            except Exception as e:
                log(f"Error parsing RTP packet: {e}", "ERROR")
                continue

            client_id = str(rtp_packet.ssrc)
            seq_num = rtp_packet.sequenceNumber

            # Inicializar contador de fuera de orden
            if client_id not in out_of_order_count:
                out_of_order_count[client_id] = 0

            # Bloqueamos el dict de los clientes y si es un cliente nuevo, creamos su estructura y lanzamos un worker por cliente
            with clients_lock:
                if client_id not in clients:
                    clients[client_id] = {
                        'wavefile': create_wav_file(client_id),
                        'lock': threading.Lock(),
                        'buffer': dict(),
                        'next_seq': seq_num,
                        'last_time': time.time()
                    }
                    # Lanzar worker
                    t = threading.Thread(target=iniciar_worker_cliente, args=(client_id,), daemon=True)
                    t.start()

            # Insertar paquete en buffer del cliente
            client = clients[client_id]
            with client['lock']: # Bloquea el acceso al buffer y datos de ESE cliente en particular
                # Detectar paquetes fuera de orden
                if seq_num in client['buffer']:
                    out_of_order_count[client_id] += 1
                    log(f"[RTP] Paquete fuera de orden para cliente {client_id}: seq={seq_num} (total fuera de orden: {out_of_order_count[client_id]})", "WARN")
                    continue
                client['buffer'][seq_num] = rtp_packet.payload
                client['last_time'] = time.time()

        except Exception as e:
            if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                break
            print(f"Error receiving or processing packet: {e}")
    sock.close()

MAX_WAIT = 0.08


# --- Jitter buffer configurable ---
def iniciar_worker_cliente(client_id, jitter_buffer_size):
    """Hilo que procesa paquetes en orden y escribe en WAV usando jitter buffer real."""
    log(f"[Worker] Iniciado para cliente con SSRC: {client_id}", "INFO")
    client = clients[client_id]
    prefill_done = False
    while True:
        with client['lock']:
            buffer = client['buffer']
            next_seq = client['next_seq']

            # Log del jitter acumulado (diferencia entre el esperado y el menor en buffer)
            if buffer:
                min_seq = min(buffer.keys())
                jitter = (min_seq - next_seq) % 65536
                log(f"[Jitter] Cliente {client_id}: jitter acumulado = {jitter} (next_seq={next_seq}, min_seq={min_seq}, buffer={sorted(buffer.keys())})", "DEBUG")

            # Esperar a que el buffer tenga al menos jitter_buffer_size paquetes antes de empezar a escribir
            if not prefill_done:
                if len(buffer) >= jitter_buffer_size:
                    prefill_done = True
                    log(f"[JitterBuffer] Cliente {client_id}: pre-llenado completado con {len(buffer)} paquetes", "INFO")
                else:
                    # Cierre por inactividad
                    if not buffer and time.time() - client['last_time'] > INACTIVITY_TIMEOUT:
                        try:
                            client['wavefile'].close()
                            log(f"[Worker] Cliente {client_id} inactivo por {INACTIVITY_TIMEOUT}s, WAV cerrado y recursos liberados.", "INFO")
                        except Exception as e:
                            log(f"[Worker] Error cerrando WAV de cliente {client_id}: {e}", "ERROR")
                        with clients_lock:
                            clients.pop(client_id, None)
                        break
                    time.sleep(0.01)
                    continue

            # Procesar el paquete con menor sequence number disponible (ventana deslizante)
            while buffer:
                if next_seq in buffer:
                    payload = buffer.pop(next_seq)
                    client['wavefile'].writeframes(payload)
                    client['next_seq'] = next_seq = (next_seq + 1) % 65536
                    client['last_time'] = time.time()
                else:
                    # Solo saltar si hay suficiente buffer y el timeout se cumple
                    if len(buffer) >= jitter_buffer_size and time.time() - client['last_time'] > MAX_WAIT:
                        min_seq = min(buffer.keys())
                        log(f"[JitterBuffer] Timeout o lag, saltando de seq={next_seq} a seq={min_seq} (buffer: {sorted(buffer.keys())})", "WARN")
                        client['next_seq'] = next_seq = min_seq
                        client['last_time'] = time.time()
                    else:
                        break

            # Cierre por inactividad
            if not buffer and time.time() - client['last_time'] > INACTIVITY_TIMEOUT:
                try:
                    client['wavefile'].close()
                    log(f"[Worker] Cliente {client_id} inactivo por {INACTIVITY_TIMEOUT}s, WAV cerrado y recursos liberados.", "INFO")
                except Exception as e:
                    log(f"[Worker] Error cerrando WAV de cliente {client_id}: {e}", "ERROR")
                with clients_lock:
                    clients.pop(client_id, None)
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

    def udp_listener_fixed_jitter():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1<<20)
        sock.bind((LISTEN_IP, LISTEN_PORT))
        log(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}", "INFO")
        log("🔊 Saving incoming audio streams to .wav files...", "INFO")
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                try:
                    rtp_packet = RTP()
                    rtp_packet.fromBytearray(bytearray(data))
                except Exception as e:
                    log(f"Error parsing RTP packet: {e}", "ERROR")
                    continue
                client_id = str(rtp_packet.ssrc)
                seq_num = rtp_packet.sequenceNumber
                if client_id not in out_of_order_count:
                    out_of_order_count[client_id] = 0
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
                client = clients[client_id]
                with client['lock']:
                    if seq_num in client['buffer']:
                        out_of_order_count[client_id] += 1
                        log(f"[RTP] Paquete fuera de orden para cliente {client_id}: seq={seq_num} (total fuera de orden: {out_of_order_count[client_id]})", "WARN")
                        continue
                    client['buffer'][seq_num] = rtp_packet.payload
                    client['last_time'] = time.time()
            except Exception as e:
                if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                    break
                print(f"Error receiving or processing packet: {e}")
        sock.close()

    udp_listener = udp_listener_fixed_jitter

    listener_thread = threading.Thread(target=udp_listener, daemon=True)
    listener_thread.start()

    # Mantener el programa vivo esperando señal para cerrar
    signal.pause()

"""
Cambios 
    - Escritura en tiempo real: cada paquete se escribe directamente al .wav sin esperar 240 paquetes.
    - Worker por cliente: procesa paquetes de forma independiente.
    - Buffer con lock: evita problemas de concurrencia.
    - Timeout: paquetes que no llegan se “saltan” para no acumular memoria.
    - Diccionario clients: encapsula todo por cliente (wavefile, buffer, lock, next_seq, last_time).
"""