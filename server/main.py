import socket
import threading
import signal
import sys
import time
import wave
import struct
from collections import defaultdict

def parse_rtp_packet(data):
    """
    Parsea un paquete RTP y extrae el payload de audio.
    Header RTP básico: 12 bytes
    - Byte 0: V(2bits) + P(1bit) + X(1bit) + CC(4bits)
    - Byte 1: M(1bit) + PT(7bits)
    - Bytes 2-3: Sequence number
    - Bytes 4-7: Timestamp
    - Bytes 8-11: SSRC
    """
    if len(data) < 12:
        return None
    
    # Extraer información básica del header
    version = (data[0] >> 6) & 0x3
    padding = (data[0] >> 5) & 0x1
    extension = (data[0] >> 4) & 0x1
    cc = data[0] & 0xF
    
    marker = (data[1] >> 7) & 0x1
    payload_type = data[1] & 0x7F
    
    seq_num = struct.unpack('!H', data[2:4])[0]
    timestamp = struct.unpack('!I', data[4:8])[0]
    ssrc = struct.unpack('!I', data[8:12])[0]
    
    # Calcular offset del payload
    header_length = 12 + (cc * 4)  # Header básico + CSRC
    
    # Si hay extensión, saltar el header de extensión
    if extension:
        if len(data) < header_length + 4:
            return None
        ext_length = struct.unpack('!H', data[header_length + 2:header_length + 4])[0]
        header_length += 4 + (ext_length * 4)
    
    # Extraer payload (después del header)
    if len(data) <= header_length:
        return None
        
    payload = data[header_length:]
    
    # Si hay padding, remover bytes de padding
    if padding and len(payload) > 0:
        padding_length = payload[-1]
        if padding_length <= len(payload):
            payload = payload[:-padding_length]
    
    return {
        'version': version,
        'payload_type': payload_type,
        'sequence': seq_num,
        'timestamp': timestamp,
        'ssrc': ssrc,
        'payload': payload
    }

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 6001

SAMPLE_RATE = 48000
BIT_DEPTH = 16
NUM_CHANNELS = 1

clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

def create_wav_file(addr_str):
    # Sanitize filename (replace ':' con '_')
    filename = f"{addr_str.replace(':', '_')}_{int(time.time())}.wav"
    wf = wave.open(filename, 'wb')
    wf.setnchannels(NUM_CHANNELS)
    wf.setsampwidth(BIT_DEPTH // 8)
    wf.setframerate(SAMPLE_RATE)
    print(f"✅ New client connected: {addr_str}. Saving to {filename}")
    return wf, filename

def write_audio(addr_str, payload):
    # Convert big-endian bytes to signed 16-bit samples
    # Payload length should be multiple of 2
    num_samples = len(payload) // 2
    if num_samples == 0:
        return

    fmt = ">" + "h" * num_samples  # big-endian signed short
    samples = struct.unpack(fmt, payload)

    with clients_lock:
        client = clients.get(addr_str)
        if client is None:
            # Create new WAV file for new client
            wf, filename = create_wav_file(addr_str)
            client = {'wavefile': wf, 'lock': threading.Lock(), 'filename': filename}
            clients[addr_str] = client

    # Write samples to WAV file with thread-safe lock
    with client['lock']:
        # wave.writeframes expects bytes, así que volvemos a empacar samples a bytes little-endian
        # pero WAV estándar usa little endian, convertimos:
        le_samples = struct.pack("<" + "h" * num_samples, *samples)
        client['wavefile'].writeframes(le_samples)

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    print(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}")
    print("🔊 Saving incoming audio streams to .wav files...")

    while True:
        try:
            data, addr = sock.recvfrom(1600)
            addr_str = f"{addr[0]}:{addr[1]}"

            # Parse RTP packet manualmente
            rtp_info = parse_rtp_packet(data)
            if rtp_info is None:
                print(f"Error: Paquete RTP inválido desde {addr_str}")
                continue

            # El payload es audio en PCM 16-bit BE
            payload = rtp_info['payload']
            
            # Logging opcional para debug
            # print(f"RTP from {addr_str}: PT={rtp_info['payload_type']}, seq={rtp_info['sequence']}, payload_size={len(payload)}")

            write_audio(addr_str, payload)

        except Exception as e:
            # Detect closed socket on shutdown
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
