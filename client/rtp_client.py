import socket
import os
import sys
from rtp import RTP, PayloadType

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log_and_save
from config import FRAME_SIZE, RTP_VERSION, DEST_IP, DEST_PORT
# PAYLOAD_TYPE termina sobreescribiendose con el de la clase de la libreria rtp
# Configuración RTP

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_rtp_stream_to_server(data, ssrc, sequence_number):
    total_len = len(data)
    offset = 0
    frame_bytes = FRAME_SIZE * 2
    while offset < total_len:
        frame = data[offset:offset + frame_bytes]
        if not frame:
            break
        rtp_packet = create_rtp_packet(bytearray(frame), sequence_number, ssrc)
        sock.sendto(rtp_packet.toBytearray(), (DEST_IP, DEST_PORT))
        if sequence_number % 100 == 0:
            log_and_save(f"📤 Enviado paquete seq {sequence_number} (raw stream)", "DEBUG", ssrc)
        sequence_number = (sequence_number + 1) % 65536
        offset += frame_bytes
    return sequence_number


def create_rtp_packet(payload, sequence_number, ssrc):
    # Asegurar que payload es bytearray
    if not isinstance(payload, bytearray):
        payload = bytearray(payload)
    
    # Usar timestamp basado en samples, no en tiempo real
    timestamp = sequence_number * FRAME_SIZE  # Timestamp basado en samples procesados
    
    rtp_packet = RTP(
        version=RTP_VERSION,  # Usar valor directo 2
        payloadType=PayloadType.DYNAMIC_96,  # Usar PayloadType enum
        sequenceNumber=sequence_number,      # camelCase
        timestamp=timestamp % 2**32,         # Timestamp predecible basado en samples
        ssrc=ssrc,
        payload=payload
    )
    return rtp_packet



