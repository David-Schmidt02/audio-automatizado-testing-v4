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

    client_packets = defaultdict(list)  # addr_str -> lista de payloads
    
    while True:
        try:
            data, addr = sock.recvfrom(1600)
            addr_str = f"{addr[0]}:{addr[1]}"
            
            #log(f"Received {len(data)} bytes from {addr_str}", "DEBUG")
            
            # Parse RTP packet
            try:
                rtp_packet = RTP()
                rtp_packet.fromBytearray(bytearray(data))  # Sin () - método estático
                #log(f"Successfully parsed RTP packet, payload length: {len(rtp_packet.payload)}", "DEBUG")
            except Exception as e:
                log(f"Error parsing RTP packet: {e}", "ERROR")
                continue
            
            # Agregar payload a la lista del cliente
            client_packets[addr_str].append(rtp_packet.payload)
            
            # Crear archivo WAV cada 240 paquetes (aprox 5 segundos)
            if len(client_packets[addr_str]) >= 240:
                create_wav_file(addr_str, client_packets[addr_str])
                client_packets[addr_str] = []  # Reset lista

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
