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

# Global RTP timestamp tracker - separate from sequence number
_rtp_timestamp_trackers = {}

def send_rtp_stream_to_server(data, ssrc, sequence_number):
    total_len = len(data)
    offset = 0
    frame_bytes = FRAME_SIZE * 2  # 2 bytes per sample for 16-bit audio
    
    # Initialize RTP timestamp tracker for this SSRC if not exists
    if ssrc not in _rtp_timestamp_trackers:
        _rtp_timestamp_trackers[ssrc] = 0
        
    while offset < total_len:
        frame = data[offset:offset + frame_bytes]
        if not frame:
            break
            
        # Get current RTP timestamp for this SSRC
        rtp_timestamp = _rtp_timestamp_trackers[ssrc]
        
        rtp_packet = create_rtp_packet(bytearray(frame), sequence_number, ssrc, rtp_timestamp)
        sock.sendto(rtp_packet.toBytearray(), (DEST_IP, DEST_PORT))
        
        if sequence_number % 100 == 0:
            log_and_save(f"📤 Enviado paquete seq={sequence_number}, rtp_ts={rtp_timestamp} (raw stream)", "DEBUG", ssrc)
            
        # Increment sequence number and RTP timestamp
        sequence_number = (sequence_number + 1) % 65536
        _rtp_timestamp_trackers[ssrc] = (rtp_timestamp + FRAME_SIZE) % (2**32)
        offset += frame_bytes
        
    return sequence_number


def create_rtp_packet(payload, sequence_number, ssrc, rtp_timestamp):
    # Asegurar que payload es bytearray
    if not isinstance(payload, bytearray):
        payload = bytearray(payload)
    
    # Usar el rtp_timestamp proporcionado en lugar de calcularlo desde sequence_number
    # Esto garantiza que el timestamp RTP sea consistente independientemente del batching
    
    rtp_packet = RTP(
        version=RTP_VERSION,  # Usar valor directo 2
        payloadType=PayloadType.DYNAMIC_96,  # Usar PayloadType enum
        sequenceNumber=sequence_number,      # camelCase
        timestamp=rtp_timestamp % (2**32),   # Timestamp basado en samples incrementales
        ssrc=ssrc,
        payload=payload
    )
    return rtp_packet



