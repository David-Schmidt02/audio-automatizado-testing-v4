from collections import defaultdict
import queue

buffers = defaultdict(lambda: queue.Queue())         # Almacena paquetes RTP por cliente (SSRC)
expected_seq = defaultdict(lambda: None)             # Guarda el número de secuencia esperado por cliente

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

LISTEN_IP = "172.21.100.130" # Debe ser la de la misma máquina Host 192.168.0.....
LISTEN_PORT = 6001

FRAME_SIZE = 160  # Samples por paquete
SAMPLE_RATE = 48000
SAMPLE_FORMAT = "int16"

CHANNELS = 1  # Mono

clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

def create_wav_file(client_id):
    """Crea un WAV nuevo para el cliente."""
    name_wav = f"record-{time.strftime('%Y%m%d-%H%M%S')}-{client_id}.wav"
    wf = wave.open(name_wav, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    print(f"💾 [Cliente {client_id}] WAV abierto: {name_wav}")
    return wf

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    print(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}")
    print("🔊 Saving incoming audio streams to .wav files...")
    
    while True:
        try:
            data, addr = sock.recvfrom(1600)
            try:
                rtp_packet = RTP()
                rtp_packet.fromBytearray(bytearray(data))
            except Exception as e:
                log(f"Error parsing RTP packet: {e}", "ERROR")
                continue
            
            # Usar SSRC como identificador único del cliente
            client_id = str(rtp_packet.ssrc)
            seq_num = rtp_packet.sequenceNumber
            
            # Bloqueamos el dict de los clientes y si es un cliente nuevo, creamos su estructura y lanzamos un worker por cliente
            with clients_lock: # Bloquea el acceso al dict de clientes porque se puede crear uno
                if client_id not in clients:
                    # Inicializar estructura del cliente
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
                if seq_num in client['buffer']:
                    # Evitar duplicados
                    continue
                client['buffer'][seq_num] = rtp_packet.payload
                client['last_time'] = time.time()

        except Exception as e:
            if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                break
            print(f"Error receiving or processing packet: {e}")
    sock.close()

MAX_WAIT = 0.2

def iniciar_worker_cliente(client_id):
    """Hilo que procesa paquetes en orden y escribe en WAV."""
    print(f"[Worker] Iniciado para cliente con SSRC: {client_id}")
    client = clients[client_id]
    while True:
        with client['lock']: # Si el worker entra antes que el listener al lock, no hace nada debido a que su buffer se encuentra vacio
            buffer = client['buffer']
            next_seq = client['next_seq']

            # Procesar paquetes en orden
            while next_seq in buffer:
                payload = buffer.pop(next_seq)
                client['wavefile'].writeframes(payload)
                client['next_seq'] = next_seq = (next_seq + 1) % 65536
                client['last_time'] = time.time()

        # Timeout: saltar paquetes perdidos
        with client['lock']:
            if buffer and time.time() - client['last_time'] > MAX_WAIT:
                min_seq = min(buffer.keys())
                print(f"[Worker] Timeout cliente {client_id}, saltando paquete {next_seq}")
                client['next_seq'] = next_seq = min_seq
                client['last_time'] = time.time()

        time.sleep(0.01)  # evitar busy wait

def shutdown_handler(signum, frame):
    print("\n🛑 Shutting down server...")

    with clients_lock:
        print("💾 Closing all WAV files...")
        for addr, client in clients.items():
            try:
                client['wavefile'].close()
                print(f"Closed file: {client['filename']}")
            except Exception as e:
                print(f"Error closing WAV file for {addr}: {e}")

    print("✅ Cleanup complete.")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

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