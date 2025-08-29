import os
import sys
import threading
import time
import gc

from jitter_buffer import JitterBuffer
from metadata import channel_map

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import SAMPLE_RATE, CHANNELS, INACTIVITY_TIMEOUT, JITTER_BUFFER_SIZE, WAV_SEGMENT_SECONDS


clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

def create_wav_file(ssrc, wav_index = 0):
    import wave
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



def start_worker_client(ssrc):
    log(f"[Worker] Iniciado para cliente con SSRC: {ssrc}", "INFO")
    client = clients[ssrc]
    jitter_buffer = client['jitter_buffer']

    while True:
        with client['lock']:
            # Esperar a que el jitter buffer tenga prefill suficiente
            if not jitter_buffer.ready_to_consume():
                if handle_inactivity(client, ssrc):
                    break
                time.sleep(0.005)
                continue


            # Procesar todos los paquetes listos en orden
            next_seq = client['next_seq']
            while True:
                packet = jitter_buffer.pop_next(next_seq)
                if packet is None:
                    break
                now = time.time()
                # Lógica de segmentación WAV por tiempo
                if now - client['wav_start_time'] >= WAV_SEGMENT_SECONDS:
                    client['wavefile'].close()
                    client['wavefile'] = None
                    gc.collect()
                    client['wav_index'] += 1
                    client['wavefile'] = create_wav_file(ssrc, wav_index=client['wav_index'])
                    client['wav_start_time'] = time.time()
                    log(f"[Segmentación] Nuevo archivo WAV para {ssrc}, segmento {client['wav_index']}", "INFO")

                client['wavefile'].writeframes(packet["payload"])
                if not packet.get("is_silence", False):
                    client['last_time'] = now
                next_seq = (next_seq + 1) % 65536
            client['next_seq'] = next_seq

            if handle_inactivity(client, ssrc):
                break

        time.sleep(0.005)
    log(f"[Worker] Terminando para cliente con SSRC: {ssrc}", "WARN")

def get_or_create_client(ssrc, seq_num):
    client = clients.get(ssrc)
    if client is not None:
        return client
    with clients_lock:
        clients[ssrc] = {
            'jitter_buffer': JitterBuffer(prefill_min=JITTER_BUFFER_SIZE),
            'wavefile': create_wav_file(ssrc, wav_index=0),
            'lock': threading.Lock(),
            'next_seq': seq_num,
            'last_time': time.time(),
            'wav_start_time': time.time(),  # Marca el inicio del archivo actual
            'wav_index': 0,                 # Contador de archivos para ese cliente
        }
        log(f"[Init] Cliente nuevo {ssrc}: next_seq inicializado en {seq_num}", "INFO")
        t = threading.Thread(target=start_worker_client, args=(ssrc,), daemon=True)
        t.start()
    return clients[ssrc]
