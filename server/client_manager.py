import os
import sys
import threading
import time
import wave
import gc

from jitter_buffer import log_jitter, check_prefill
from metadata import channel_map

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import SAMPLE_RATE, CHANNELS, INACTIVITY_TIMEOUT, MAX_WAIT, JITTER_BUFFER_SIZE, WAV_SEGMENT_SECONDS

clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

def create_wav_file(ssrc, wav_index = 0):
    """Crea un WAV nuevo para el cliente en un directorio propio dentro de 'records'."""
    base_dir = "records"
    # Obtener el nombre del canal desde channel_map, o usar el ssrc si no existe
    channel_name = channel_map.get(str(ssrc), str(ssrc))
    client_dir = os.path.join(base_dir, channel_name)
    if not os.path.exists(client_dir):
        os.makedirs(client_dir)
        log(f"📂 Creando directorio para canal: {channel_name}", "ERROR")
    name_wav = os.path.join(client_dir, f"record-{time.strftime('%Y%m%d-%H%M%S')}-{ssrc}-{channel_name}-{wav_index}.wav")
    wf = wave.open(name_wav, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    log(f"💾 [Cliente {ssrc}] WAV abierto: {name_wav}", "INFO")
    return wf


def handle_inactivity(client, ssrc):
    """
    Maneja la inactividad de un cliente, cerrando su archivo WAV si ha estado inactivo durante más de INACTIVITY_TIMEOUT segundos.
    """
    # Cerrar el cliente si no se han procesado paquetes en INACTIVITY_TIMEOUT segundos,
    # aunque el buffer no esté vacío (para evitar clientes zombies)
    if time.time() - client['last_time'] > INACTIVITY_TIMEOUT:
        try:
            client['wavefile'].close()
            client['wavefile'] = None  # Eliminar referencia para liberar memoria
            gc.collect()  # Forzar recolección de basura
            log(f"[Worker] Cliente {ssrc} inactivo por {INACTIVITY_TIMEOUT}s, WAV cerrado y recursos liberados.", "INFO")
        except Exception as e:
            log(f"[Worker] Error cerrando WAV de cliente {ssrc}: {e}", "ERROR")
        with clients_lock:
            clients.pop(ssrc, None)
        return True
    return False


def process_buffer(client, ssrc):
    buffer = client['buffer']
    next_seq = client['next_seq']
    while buffer:
        # Log de huecos en la secuencia si hay más de un paquete
        if len(buffer) > 1:
            keys = sorted(buffer.keys())
            gaps = [b - a for a, b in zip(keys[:-1], keys[1:])]
            if any(g > 1 for g in gaps):
                log(f"[JitterBuffer][GAP] Cliente {ssrc}: Secuencias en buffer: {keys}, huecos: {[i for i, g in enumerate(gaps) if g > 1]}", "WARN")
        # Verificar si hay que segmentar el archivo
        if time.time() - client['wav_start_time'] >= WAV_SEGMENT_SECONDS:
            client['wavefile'].close()
            client['wavefile'] = None
            gc.collect()
            client['wav_index'] += 1
            client['wavefile'] = create_wav_file(ssrc, wav_index=client['wav_index'])
            client['wav_start_time'] = time.time()
            log(f"[Segmentación] Nuevo archivo WAV para {ssrc}, segmento {client['wav_index']}", "INFO")
            
        if next_seq in buffer:
            # Extraer payload del nuevo formato de buffer
            packet_info = buffer.pop(next_seq)
            if isinstance(packet_info, dict):
                payload = packet_info['payload']
                rtp_ts = packet_info.get('rtp_timestamp', 0)
                arrival = packet_info.get('arrival_mon', 0)
                log(f"[Buffer][Process] Procesando seq={next_seq}, rtp_ts={rtp_ts}, arrival={arrival:.6f}", "DEBUG")
            else:
                # Compatibilidad con formato anterior (solo payload)
                payload = packet_info
                
            client['wavefile'].writeframes(payload)
            client['next_seq'] = next_seq = (next_seq + 1) % 65536
            client['last_time'] = time.time()
            client['fill_packets'] += 1
        else:
            # Mejorar la lógica de timeout/salto con ordenamiento modular
            if len(buffer) >= JITTER_BUFFER_SIZE and time.time() - client['last_time'] > MAX_WAIT:
                # Encontrar la secuencia más cercana a next_seq en orden modular
                next_candidate = find_next_sequence_modular(buffer.keys(), next_seq)
                log(f"[JitterBuffer] Timeout o lag, saltando de seq={next_seq} a seq={next_candidate} (buffer: {sorted(buffer.keys())})", "WARN")
                client['next_seq'] = next_seq = next_candidate
                client['last_time'] = time.time()
            else:
                break


def find_next_sequence_modular(buffer_keys, current_next):
    """
    Encuentra la siguiente secuencia más apropiada usando aritmética modular.
    """
    if not buffer_keys:
        return current_next
        
    keys = list(buffer_keys)
    
    # Calcular distancias modulares desde current_next
    distances = []
    for key in keys:
        distance = (key - current_next) % 65536
        if distance > 32768:  # Si está en la segunda mitad, es hacia atrás
            distance = distance - 65536
        distances.append((abs(distance), key))
    
    # Ordenar por distancia y tomar el más cercano
    distances.sort()
    return distances[0][1]


def start_worker_client(ssrc):
    """Hilo que procesa paquetes en orden y escribe en WAV usando jitter buffer real."""
    log(f"[Worker] Iniciado para cliente con SSRC: {ssrc}", "INFO")
    client = clients[ssrc]
    prefill_done = False
    while True:
        with client['lock']:
            buffer = client['buffer']
            next_seq = client['next_seq']

            log_jitter(ssrc, buffer, next_seq)

            # Prefill del jitter buffer
            prefill_done = check_prefill(buffer, prefill_done,ssrc)
            if not prefill_done:
                if handle_inactivity(client, ssrc):
                    break
                time.sleep(0.01)
                continue

            # Procesar buffer
            process_buffer(client, ssrc)

            # Cierre por inactividad
            if handle_inactivity(client, ssrc):
                break

        time.sleep(0.01)


def get_or_create_client(ssrc, seq_num):
    client = clients.get(ssrc)
    if client is not None:
        return client
    with clients_lock:
        # Obtener el nombre del canal desde channel_map
        channel_name = channel_map.get(str(ssrc), f"client_{ssrc}")
        
        clients[ssrc] = {
            'wavefile': create_wav_file(ssrc, wav_index=0),
            'lock': threading.Lock(),
            'buffer': dict(),
            'next_seq': seq_num,
            'last_time': time.time(),
            'wav_start_time': time.time(),  # Marca el inicio del archivo actual
            'wav_index': 0,                 # Contador de archivos para ese cliente
            'name': channel_name,           # Nombre del canal
            'fill_packets': 0,              # Contador de paquetes recibidos
            'jitter_state': None,           # Se inicializa en handle_rtp_packet
        }
        log(f"[Init] Cliente nuevo {ssrc} ({channel_name}): next_seq inicializado en {seq_num}", "INFO")
        t = threading.Thread(target=start_worker_client, args=(ssrc,), daemon=True)
        t.start()
    return clients[ssrc]
