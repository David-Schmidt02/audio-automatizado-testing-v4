import os
import socket
import sys
import time

from rtp import RTP

from client_manager import get_or_create_client

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log    
from config import BUFFER_SIZE, LISTEN_IP, LISTEN_PORT

def parse_rtp_packet(data):
    """
    Analiza un paquete RTP y devuelve un objeto RTP.
    """
    try:
        rtp_packet = RTP()
        rtp_packet.fromBytearray(bytearray(data))
        return rtp_packet
    except Exception as e:
        log(f"Error parsing RTP packet: {e}", "ERROR")
        return None


def udp_listener_jitter():
    """
    Escucha paquetes UDP y los procesa como flujos de audio RTP.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Aumentar el buffer UDP a 8 MB para soportar más tráfico simultáneo
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8<<20)
    actual_buf = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    log(f"[UDP] Buffer de recepción configurado: {actual_buf // (1024*1024)} MB", "INFO")
    sock.bind((LISTEN_IP, LISTEN_PORT))
    log(f"🎧 Listening for RTP audio on {LISTEN_IP}:{LISTEN_PORT}", "INFO")
    log("🔊 Saving incoming audio streams to .wav files...", "INFO")
    while True:
        try:
            data, addr = sock.recvfrom(8192)
            rtp_packet = parse_rtp_packet(data)
            if rtp_packet.sequenceNumber % 100 == 0:
                log(f"[UDP] Paquete clave recibido de {addr}, seq={rtp_packet.sequenceNumber}", "INFO")
            if not rtp_packet:
                continue
            client_id = str(rtp_packet.ssrc)
            seq_num = rtp_packet.sequenceNumber
            client = get_or_create_client(client_id, seq_num)

            jitter_buffer = client['jitter_buffer']
            jitter_buffer.add_packet(seq_num, rtp_packet.timestamp, rtp_packet.payload)

            #handle_rtp_packet(client, client_id, seq_num, rtp_packet.payload)
        except Exception as e:
            if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                break
            print(f"Error receiving or processing packet: {e}")
    sock.close()