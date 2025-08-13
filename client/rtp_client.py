import socket
import struct
import time
import wave
import os
from rtp import RTP, PayloadType

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
    SSRC = id_instance
    with wave.open(wav_path, "rb") as wf:
        while True:
            frame = wf.readframes(FRAME_SIZE)
            if not frame:
                break
            sock.sendto(frame, (DEST_IP, DEST_PORT))
            # Por ahora lo mandamos tal cual como PCM luego podríamos modificarlo para codificar y mandar como RTP


def send_rtp_to_server(wav_path):
    sequence_number = 0
    global sock
    with wave.open(wav_path, "rb") as wf:
        while True:
            frame = wf.readframes(FRAME_SIZE)
            if not frame:
                break
            rtp_packet = create_rtp_packet(frame, sequence_number)
            sock.sendto(rtp_packet.toBytearray(), (DEST_IP, DEST_PORT))
            sequence_number += 1


def create_rtp_packet(payload, sequence_number):
    rtp_packet = RTP(
        version=RTP_VERSION,
        payload_type=PAYLOAD_TYPE,
        sequence_number=sequence_number,
        ssrc=SSRC,
        timestamp=int(time.time() * SAMPLE_RATE) % 2**32,
        payload=payload
    )
    return rtp_packet




