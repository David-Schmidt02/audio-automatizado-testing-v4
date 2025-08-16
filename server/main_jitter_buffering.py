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

INACTIVITY_TIMEOUT = 5  # segundos de inactividad para cerrar WAV

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
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1<<20)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    log(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}", "INFO")
    log("🔊 Saving incoming audio streams to .wav files...", "INFO")
    
    while True:
        try:
            #data, addr = sock.recvfrom(1600)
            data, addr = sock.recvfrom(4096)
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
                    'last_time': time.time(),
                    'rtp_clock': SAMPLE_RATE,          # para PCM: clock = sample rate
                    'frame_samples_guess': FRAME_SIZE, # fallback inicial
                    'expected_play_time': None,        # se setea tras prefill
                    'last_ts': None,                   # último timestamp RTP usado
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
                #client['buffer'][seq_num] = rtp_packet.payload
                client['buffer'][seq_num] = (rtp_packet.timestamp, rtp_packet.payload)
                client['last_time'] = time.time()

        except Exception as e:
            if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                break
            print(f"Error receiving or processing packet: {e}")
    sock.close()

MAX_WAIT = 0.1


def iniciar_worker_cliente(client_id, jitter_buffer_size_packets):
    """
    Worker por cliente que programa la escritura usando el timestamp RTP.
    jitter_buffer_size_packets: prefill en paquetes (p.ej. 60 => ~60*frame_ms).
    """
    log(f"[Worker] Iniciado para cliente con SSRC: {client_id}", "INFO")
    client = clients[client_id]
    prefill_done = False

    # Helpers locales para no estar mirando globals todo el tiempo
    BYTES_PER_SAMPLE = 2 * CHANNELS
    rtp_clock = client.get('rtp_clock', SAMPLE_RATE)

    # Para estimar tamaño de frame por TS (por si cambia FRAME_SIZE del emisor)
    ts_deltas = []

    while True:
        # ----------- BLOQUE CORTO BAJO LOCK: tomar lo necesario -----------
        with client['lock']:
            buffer = client['buffer']
            next_seq = client['next_seq']
            wf = client['wavefile']

            # Inactividad => cerrar
            if not buffer and time.time() - client['last_time'] > INACTIVITY_TIMEOUT:
                try:
                    wf.close()
                    log(f"[Worker] Cliente {client_id} inactivo {INACTIVITY_TIMEOUT}s, WAV cerrado.", "INFO")
                except Exception as e:
                    log(f"[Worker] Error cerrando WAV de cliente {client_id}: {e}", "ERROR")
                with clients_lock:
                    clients.pop(client_id, None)
                break

            # Prefill por paquetes (simple): esperamos a tener jitter_buffer_size_packets
            if not prefill_done:
                if len(buffer) >= jitter_buffer_size_packets:
                    prefill_done = True
                    # mapeamos el tiempo "real" a TS del primer paquete a reproducir
                    client['expected_play_time'] = time.time()
                    client['last_ts'] = None  # se setea al primer paquete real
                    log(f"[JitterBuffer] Cliente {client_id}: pre-llenado con {len(buffer)} paquetes", "INFO")
                else:
                    # no hay suficiente prefill aún
                    pass

            # Si ya hay prefill, intentamos tomar el paquete esperado
            pkt = None
            if prefill_done and next_seq in buffer:
                pkt = buffer.pop(next_seq)  # (ts, payload)
                client['next_seq'] = (next_seq + 1) % 65536
                client['last_time'] = time.time()

        # ------------------- FUERA DEL LOCK: procesar pkt -------------------
        if not prefill_done:
            time.sleep(0.005)
            continue

        if pkt is None:
            # No está el paquete esperado aún.
            # Política simple: si estamos muy atrasados respecto a expected_play_time, avanzamos (silencio).
            now = time.time()
            if client['expected_play_time'] is not None and (now - client['expected_play_time']) > MAX_WAIT:
                # Estimar duración de frame para “llenar” el hueco con silencio
                frame_samples = estimate_frame_samples(client, ts_deltas, rtp_clock)
                silence = b'\x00' * (frame_samples * BYTES_PER_SAMPLE)
                try:
                    wf.writeframes(silence)
                except Exception as e:
                    log(f"[Worker] Error escribiendo silencio WAV cliente {client_id}: {e}", "ERROR")
                # Avanzamos expected_play_time
                client['expected_play_time'] = now
                # También avanzamos last_ts “virtualmente”
                if client['last_ts'] is None:
                    client['last_ts'] = 0
                client['last_ts'] = (client['last_ts'] + frame_samples) % (1<<32)
            else:
                time.sleep(0.001)
            continue

        # Tenemos un paquete real
        ts, payload = pkt

        # Estimar frame_samples a partir de TS consecutivos
        if client['last_ts'] is not None:
            delta_ts = (ts - client['last_ts']) & 0xFFFFFFFF
            if 0 < delta_ts < rtp_clock * 0.25:  # ignora saltos demasiado grandes
                ts_deltas.append(delta_ts)
                if len(ts_deltas) > 50:
                    ts_deltas.pop(0)
        frame_samples = estimate_frame_samples(client, ts_deltas, rtp_clock)

        # Programar la salida respecto del clock del emisor
        if client['expected_play_time'] is None:
            client['expected_play_time'] = time.time()

        # ¿Estamos adelantados o atrasados?
        # “Tiempo ideal” para este frame: avanzar frame_samples/rtp_clock desde expected_play_time
        ideal_next_time = client['expected_play_time'] + (frame_samples / float(rtp_clock))
        now = time.time()
        drift = ideal_next_time - now

        # Si vamos adelantados, esperamos; si vamos atrasados mucho, escribimos y reseteamos
        if drift > 0:
            time.sleep(drift)
            client['expected_play_time'] = ideal_next_time
        else:
            # Atraso: no dormimos; si el atraso es muy grande, reanclamos el reloj
            if -drift > MAX_WAIT:
                client['expected_play_time'] = now

        # Escribimos el frame
        try:
            wf.writeframes(payload)
        except Exception as e:
            log(f"[Worker] Error escribiendo WAV cliente {client_id}: {e}", "ERROR")

        # Actualizamos TS
        client['last_ts'] = ts


def estimate_frame_samples(client, ts_deltas, rtp_clock):
    """
    Devuelve cuántas muestras hay por frame.
    - Si hay deltas de TS, usa la mediana (robusto al ruido).
    - Si no, cae al frame_samples_guess inicial.
    """
    if ts_deltas:
        sorted_d = sorted(ts_deltas)
        median = sorted_d[len(sorted_d)//2]
        # Redondeo a múltiplos “comunes” para estabilidad (480/960/1920)
        common = [240, 320, 480, 960, 1920]
        closest = min(common, key=lambda x: abs(x - median))
        client['frame_samples_guess'] = closest
        return closest
    return client.get('frame_samples_guess', 960)


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

    JITTER_BUFFER_SIZE = 60  # Cambia este valor si quieres otro tamaño

    def udp_listener_fixed_jitter():
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
                        'rtp_clock': SAMPLE_RATE,          # para PCM: clock = sample rate
                        'frame_samples_guess': FRAME_SIZE, # fallback inicial
                        'expected_play_time': None,        # se setea tras prefill
                        'last_ts': None,                   # último timestamp RTP usado
                    }
                        t = threading.Thread(target=iniciar_worker_cliente, args=(client_id, JITTER_BUFFER_SIZE), daemon=True)
                        t.start()
                client = clients[client_id]
                with client['lock']:
                    if seq_num in client['buffer']:
                        out_of_order_count[client_id] += 1
                        log(f"[RTP] Paquete fuera de orden para cliente {client_id}: seq={seq_num} (total fuera de orden: {out_of_order_count[client_id]})", "WARN")
                        continue
                    #client['buffer'][seq_num] = rtp_packet.payload
                    client['buffer'][seq_num] = (rtp_packet.timestamp, rtp_packet.payload)
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