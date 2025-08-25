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
SSRC = None
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

SEQUENCE_NUMBER = 0  # Número de secuencia para RTP


def send_rtp_stream_to_server (data, id_instance):
    """
    Envía un bloque de audio PCM/WAV en tiempo real al servidor RTP.
    """
    global SSRC
    global sock
    global SEQUENCE_NUMBER
    SSRC = id_instance

    total_len = len(data)
    offset = 0
    frame_bytes = FRAME_SIZE * 2  # 2 bytes por muestra (int16)

    while offset < total_len:
        frame = data[offset:offset + frame_bytes]
        if not frame:
            break
        rtp_packet = create_rtp_packet(bytearray(frame), SEQUENCE_NUMBER)
        sock.sendto(rtp_packet.toBytearray(), (DEST_IP, DEST_PORT))
        if SEQUENCE_NUMBER % 100 == 0:
            log_and_save(f"📤 Enviado paquete seq {SEQUENCE_NUMBER} (raw stream)", "DEBUG", SSRC)
        SEQUENCE_NUMBER = (SEQUENCE_NUMBER + 1) % 65536
        offset += frame_bytes


def create_rtp_packet(payload, sequence_number):
    global SSRC
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
        ssrc=SSRC,
        payload=payload
    )
    return rtp_packet



