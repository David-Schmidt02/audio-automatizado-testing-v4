import os
import socket
import sys
import time

from rtp import RTP

from client_manager import get_or_create_client

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log    
from config import BUFFER_SIZE, LISTEN_IP, LISTEN_PORT, SAMPLE_RATE, FRAME_SIZE

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

    
def handle_rtp_packet(client, seq_num, payload, rtp_timestamp, arrival_mon):
    """
    Maneja un paquete RTP recibido de un cliente.
    Ahora almacena información completa del paquete incluyendo timestamps.
    """
    with client['lock']:
        if seq_num in client['buffer']:
            log(f"[RTP] Paquete fuera de orden para cliente {client['wavefile'].name}: seq={seq_num} ya recibido", "WARN")
            return False
            
        # Almacenar tupla con información completa del paquete
        client['buffer'][seq_num] = {
            'payload': payload,
            'rtp_timestamp': rtp_timestamp,
            'arrival_mon': arrival_mon
        }
        client['last_time'] = time.time()
        
        # Actualizar estadísticas de jitter usando RFC3550
        update_jitter_stats(client, rtp_timestamp, arrival_mon)
        
        # Actualizar next_seq de forma más inteligente
        update_next_sequence(client, seq_num)
        
        # Log para diagnosticar el llenado del buffer
        keys = sorted(client['buffer'].keys())
        buffer_str = f"{keys[:5]} ... {keys[-5:]}" if len(keys) > 10 else str(keys)
        log(f"[RTP][Buffer] Cliente {client['wavefile'].name}: len(buffer)={len(client['buffer'])}, seq agregada={seq_num}, rtp_ts={rtp_timestamp}, buffer={buffer_str}", "DEBUG")
        return True


def update_jitter_stats(client, rtp_timestamp, arrival_mon):
    """
    Actualiza las estadísticas de jitter según RFC3550.
    """
    if 'jitter_state' not in client:
        client['jitter_state'] = {
            'last_rtp_ts': rtp_timestamp,
            'last_arrival': arrival_mon,
            'jitter': 0.0
        }
        return
        
    jitter_state = client['jitter_state']
    
    # Calcular diferencias de tiempo
    rtp_diff = (rtp_timestamp - jitter_state['last_rtp_ts']) % (2**32)
    arrival_diff = arrival_mon - jitter_state['last_arrival']
    
    # Convertir RTP timestamp difference a milisegundos
    rtp_diff_ms = (rtp_diff * 1000.0) / SAMPLE_RATE
    arrival_diff_ms = arrival_diff * 1000.0
    
    # Calcular jitter incremental según RFC3550
    d = abs(arrival_diff_ms - rtp_diff_ms)
    jitter_state['jitter'] += (d - jitter_state['jitter']) / 16.0
    
    # Actualizar estado
    jitter_state['last_rtp_ts'] = rtp_timestamp
    jitter_state['last_arrival'] = arrival_mon
    
    # Log ocasional de jitter
    if hasattr(client, '_last_jitter_log'):
        if arrival_mon - client._last_jitter_log > 5.0:  # Cada 5 segundos
            log(f"[Jitter] Cliente {client['wavefile'].name}: jitter={jitter_state['jitter']:.2f}ms", "DEBUG")
            client._last_jitter_log = arrival_mon
    else:
        client._last_jitter_log = arrival_mon


def update_next_sequence(client, seq_num):
    """
    Actualiza next_seq de forma más inteligente que simplemente usar min(buffer.keys()).
    """
    if not client['buffer']:
        return
        
    # Solo actualizar next_seq si está muy desalineado o si es una secuencia inicial
    current_next = client['next_seq']
    min_seq = min(client['buffer'].keys())
    
    # Calcular distancia módulo 65536
    distance_to_min = (min_seq - current_next) % 65536
    distance_to_current = (seq_num - current_next) % 65536
    
    # Si la distancia es muy grande, probablemente hay un problema
    if distance_to_min > 32768:  # Más de la mitad del espacio de secuencias
        distance_to_min = 65536 - distance_to_min
        
    # Solo corregir si la diferencia es significativa
    if distance_to_min > 10:  # Threshold configurabile
        log(f"[RTP][Buffer] Corrigiendo next_seq de {current_next} a {min_seq} (distancia: {distance_to_min}, buffer: {sorted(client['buffer'].keys())[:10]})", "INFO")
        client['next_seq'] = min_seq


def udp_listener_fixed_jitter():
    """
    Escucha paquetes UDP y los procesa como flujos de audio RTP.
    Ahora captura timestamps de llegada usando time.monotonic().
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
            # Capturar timestamp de llegada inmediatamente después de recibir
            data, addr = sock.recvfrom(BUFFER_SIZE)
            arrival_mon = time.monotonic()  # Timestamp monotónico de llegada
            
            rtp_packet = parse_rtp_packet(data)
            if not rtp_packet:
                continue
                
            client_id = str(rtp_packet.ssrc)
            seq_num = rtp_packet.sequenceNumber
            rtp_timestamp = rtp_packet.timestamp
            
            # Log de instrumentación para debugging
            log(f"[UDP][Recv] SSRC={client_id}, seq={seq_num}, rtp_ts={rtp_timestamp}, arrival={arrival_mon:.6f}", "DEBUG")
            
            client = get_or_create_client(client_id, seq_num) # De crear u obtener el cliente se encarga client_manager.py
            handle_rtp_packet(client, seq_num, rtp_packet.payload, rtp_timestamp, arrival_mon)
            
        except Exception as e:
            if isinstance(e, OSError) and str(e) == 'Bad file descriptor':
                break
            print(f"Error receiving or processing packet: {e}")
    sock.close()