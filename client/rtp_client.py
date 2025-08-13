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

DEST_IP = "172.21.100.130"  # De momento la IP de destino es la misma que la IP del cliente
DEST_PORT = 6001
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

FRAME_SIZE = 160  # Samples por paquete
SAMPLE_RATE = 48000  # 48kHz

CHANNELS = 1  # Mono
SAMPLE_FORMAT = "int16"

SSRC = None  # SSRC 


def send_pcm_to_server(wav_path, id_instance):
    global SSRC
    global sock
    # Asegurar que SSRC tiene un valor válido
    SSRC = id_instance
    sequence_number = 0

    log(f"Sending audio file: {wav_path} with SSRC: {SSRC}", "INFO")

    with wave.open(wav_path, "rb") as wf:
        while True:
            frame = wf.readframes(FRAME_SIZE)
            if not frame:
                break
            
            # Crear paquete RTP con el frame de audio
            rtp_packet = create_rtp_packet(bytearray(frame), sequence_number)
            sock.sendto(rtp_packet.toBytearray(), (DEST_IP, DEST_PORT))
            sequence_number += 1
            
            # Opcional: agregar pequeña pausa para simular timing real
            time.sleep(FRAME_SIZE / SAMPLE_RATE)

    log(f"Finished sending {sequence_number} packets for file: {wav_path}", "INFO")


def send_rtp_to_server(wav_path):
    global SSRC
    sequence_number = 0
    global sock

    log(f"Sending audio file: {wav_path} with SSRC: {SSRC}", "INFO")
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
    
    log(f"Payload type: {type(payload)}, length: {len(payload)}", "DEBUG")
    
    rtp_packet = RTP(
        version=2,  # Usar valor directo 2
        payloadType=PayloadType.DYNAMIC_96,  # Usar PayloadType enum
        sequenceNumber=sequence_number,      # camelCase
        timestamp=int(time.time() * SAMPLE_RATE) % 2**32,
        ssrc=SSRC,
        payload=payload
    )
    return rtp_packet



