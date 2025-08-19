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

    
def handle_rtp_packet(client, seq_num, payload):
    """
    Maneja un paquete RTP recibido de un cliente.
    """
    with client['lock']:
        if seq_num in client['buffer']:
            log(f"[RTP] Paquete fuera de orden para cliente {client['wavefile'].name}: seq={seq_num} ya recibido", "WARNING")
            return False
        client['buffer'][seq_num] = payload
        client['last_time'] = time.time()
        return True


def udp_listener_fixed_jitter():
    """
    Escucha paquetes UDP y los procesa como flujos de audio RTP.
    """
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
            client = get_or_create_client(client_id, seq_num) # De crear u obtener el cliente se encarga client_manager.py
            handle_rtp_packet(client, seq_num, rtp_packet.payload)
        except Exception as e:
            if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                break
            print(f"Error receiving or processing packet: {e}")
    sock.close()