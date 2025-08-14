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

FRAME_SIZE = 160  # Samples por paquete
SAMPLE_RATE = 48000
SAMPLE_FORMAT = "int16"

CHANNELS = 1  # Mono

clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

def create_wav_file(addr_str, payload_list):
    name_wav = f"record-{time.strftime('%Y%m%d-%H%M%S')}-{addr_str.replace(':', '_')}.wav"
    print(f"💾 Creating WAV file: {name_wav} with {len(payload_list)} packets")
    
    with wave.open(name_wav, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)

        for payload in payload_list:
            if isinstance(payload, bytearray):
                wf.writeframes(payload)
            else:
                wf.writeframes(bytearray(payload))

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    print(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}")
    print("🔊 Saving incoming audio streams to .wav files...")

    client_packets = defaultdict(list)  # ssrc -> lista de (timestamp, payload)
    client_buffers = defaultdict(dict)  # ssrc -> {seq_num: (timestamp, payload)}
    client_next_seq = defaultdict(int)  # ssrc -> próximo sequence number esperado

    REORDER_BATCH = 50
    WAV_PACKETS = 1440  # Aproximadamente 30 segundos

    while True:
        try:
            data, addr = sock.recvfrom(1600)
            addr_str = f"{addr[0]}:{addr[1]}"

            try:
                rtp_packet = RTP()
                rtp_packet.fromBytearray(bytearray(data))
            except Exception as e:
                log(f"Error parsing RTP packet: {e}", "ERROR")
                continue

            client_id = str(rtp_packet.ssrc)
            seq_num = rtp_packet.sequenceNumber
            timestamp = rtp_packet.timestamp

            # Guardar en buffer temporal para reordenar por timestamp cada REORDER_BATCH
            client_packets[client_id].append((timestamp, rtp_packet.payload))

            # Cada REORDER_BATCH paquetes, reordenar por timestamp y agregar al buffer de audio
            if len(client_packets[client_id]) >= REORDER_BATCH:
                # Ordenar por timestamp
                client_packets[client_id].sort(key=lambda x: x[0])
                # Extraer solo los payloads ordenados
                ordered_payloads = [payload for ts, payload in client_packets[client_id]]
                # Guardar en buffer de audio definitivo
                if client_id not in client_buffers:
                    client_buffers[client_id] = []
                client_buffers[client_id].extend(ordered_payloads)
                # Limpiar el batch temporal
                client_packets[client_id] = []

                # Si hay suficientes para un archivo WAV (~30s)
                if len(client_buffers[client_id]) >= WAV_PACKETS:
                    create_wav_file(client_id, client_buffers[client_id][:WAV_PACKETS])
                    client_buffers[client_id] = client_buffers[client_id][WAV_PACKETS:]

        except Exception as e:
            if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                break
            print(f"Error receiving or processing packet: {e}")

    sock.close()
    
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
