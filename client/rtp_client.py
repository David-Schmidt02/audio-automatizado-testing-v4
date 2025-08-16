import socket
import struct
import time
import wave
import os
import sys
from rtp import RTP, PayloadType

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log


# Configuración RTP
RTP_VERSION = 2
PAYLOAD_TYPE = 96
SSRC = None

DEST_IP = "192.168.0.82"  # De momento la IP de destino es la misma que la IP del cliente
DEST_PORT = 6001
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

FRAME_SIZE = 960  # Samples por paquete
SAMPLE_RATE = 48000  # 48kHz

CHANNELS = 1  # Mono
SAMPLE_FORMAT = "int16"

SSRC = None  # SSRC 
SEQUENCE_NUMBER = 0  # Número de secuencia para RTP


def send_pcm_to_server(data, id_instance):
    """
    Envía un bloque de audio PCM/WAV en tiempo real al servidor RTP.
    """
    global SSRC
    global sock
    global SEQUENCE_NUMBER
    SSRC = id_instance

    total_len = len(data)
    #log(f"Sending raw audio stream ({total_len} bytes) with SSRC: {SSRC}", "INFO")
    offset = 0
    frame_bytes = FRAME_SIZE * 2  # 2 bytes por muestra (int16)

    while offset < total_len:
        frame = data[offset:offset + frame_bytes]
        if not frame:
            break
        rtp_packet = create_rtp_packet(bytearray(frame), SEQUENCE_NUMBER)
        sock.sendto(rtp_packet.toBytearray(), (DEST_IP, DEST_PORT))
        if SEQUENCE_NUMBER % 100 == 0:
            log(f"📤 Enviado paquete seq {SEQUENCE_NUMBER} (raw stream)", "DEBUG")
        SEQUENCE_NUMBER = (SEQUENCE_NUMBER + 1) % 65536
        offset += frame_bytes

def send_rtp_to_server(wav_path):
    global SSRC
    sequence_number = 0
    global sock

    #log(f"Sending audio file: {wav_path} with SSRC: {SSRC}", "INFO")
    with wave.open(wav_path, "rb") as wf:
        while True:
            frame = wf.readframes(FRAME_SIZE)
            if not frame:
                break
            rtp_packet = create_rtp_packet(frame, sequence_number)
            sock.sendto(rtp_packet.toBytearray(), (DEST_IP, DEST_PORT))
            sequence_number += 1


def create_rtp_packet(payload, sequence_number):
    global SSRC
    #log(f"Creating RTP packet with sequence number: {sequence_number}", "DEBUG")

    # Asegurar que payload es bytearray
    if not isinstance(payload, bytearray):
        payload = bytearray(payload)
    
    #log(f"Payload type: {type(payload)}, length: {len(payload)}", "DEBUG")
    
    # Usar timestamp basado en samples, no en tiempo real
    timestamp = sequence_number * FRAME_SIZE  # Timestamp basado en samples procesados
    
    rtp_packet = RTP(
        version=2,  # Usar valor directo 2
        payloadType=PayloadType.DYNAMIC_96,  # Usar PayloadType enum
        sequenceNumber=sequence_number,      # camelCase
        timestamp=timestamp % 2**32,         # Timestamp predecible basado en samples
        ssrc=SSRC,
        payload=payload
    )
    return rtp_packet



