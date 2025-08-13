import socket
import threading
import signal
import sys
import time
import wave
import struct
from collections import defaultdict
from rtp import RTP 

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

def create_wav_file(addr_str, payload):
    name_wav = f"record-{time.strftime('%Y%m%d-%H%M%S')}-{addr_str}.wav"
    with wave.open(name_wav,"wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)

        for paquete_rtp in payload:
            wf.writeframes(paquete_rtp)

def obtener_datos(sock):
    paquetes = {}
    sequence_number = 0

    while len(paquetes) < 6000:
        data, addr = sock.recvfrom(1600)
        rtp_packet = RTP().fromBytearray(data)
        paquetes[sequence_number] = rtp_packet
        sequence_number += 1
    return paquetes, addr

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    print(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}")
    print("🔊 Saving incoming audio streams to .wav files...")

    while True:
        try:
            #data, addr = sock.recvfrom(1600)
            data,addr = obtener_datos(sock)
            addr_str = f"{addr[0]}:{addr[1]}"

            # Parse RTP packet manualmente
            rtp_info = RTP().fromBytearray(data)

            payload = rtp_info.payload
            create_wav_file(addr_str, payload) # Escribimos wavs de 2 minutos

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
