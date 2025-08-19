import os
import sys
import threading
import time
import wave

from jitter_buffer import log_jitter, check_prefill

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import SAMPLE_RATE, CHANNELS, INACTIVITY_TIMEOUT, MAX_WAIT, JITTER_BUFFER_SIZE

clients_lock = threading.Lock()
clients = dict()  # addr_str -> dict con 'wavefile' y 'lock'

def create_wav_file(client_id):
    """Crea un WAV nuevo para el cliente en un directorio propio dentro de 'records'."""
    base_dir = "records"
    client_dir = os.path.join(base_dir, str(client_id))
    os.makedirs(client_dir, exist_ok=True)
    name_wav = os.path.join(client_dir, f"record-{time.strftime('%Y%m%d-%H%M%S')}-{client_id}.wav")
    wf = wave.open(name_wav, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    log(f"💾 [Cliente {client_id}] WAV abierto: {name_wav}", "INFO")
    return wf


def handle_inactivity(client, client_id):
    """
    Maneja la inactividad de un cliente, cerrando su archivo WAV si ha estado inactivo durante más de INACTIVITY_TIMEOUT segundos.
    """
    if not client['buffer'] and time.time() - client['last_time'] > INACTIVITY_TIMEOUT:
        try:
            client['wavefile'].close()
            log(f"[Worker] Cliente {client_id} inactivo por {INACTIVITY_TIMEOUT}s, WAV cerrado y recursos liberados.", "INFO")
        except Exception as e:
            log(f"[Worker] Error cerrando WAV de cliente {client_id}: {e}", "ERROR")
        with clients_lock:
            clients.pop(client_id, None)
        return True
    return False


def process_buffer(client):
    """
    Procesa el buffer de un cliente, escribiendo los paquetes en su archivo WAV.
    """
    buffer = client['buffer']
    next_seq = client['next_seq']
    while buffer:
        if next_seq in buffer:
            payload = buffer.pop(next_seq)
            client['wavefile'].writeframes(payload)
            client['next_seq'] = next_seq = (next_seq + 1) % 65536
            client['last_time'] = time.time()
        else:
            if len(buffer) >= JITTER_BUFFER_SIZE and time.time() - client['last_time'] > MAX_WAIT:
                min_seq = min(buffer.keys())
                log(f"[JitterBuffer] Timeout o lag, saltando de seq={next_seq} a seq={min_seq} (buffer: {sorted(buffer.keys())})", "WARN")
                client['next_seq'] = next_seq = min_seq
                client['last_time'] = time.time()
            else:
                break


def start_worker_client(client_id):
    """Hilo que procesa paquetes en orden y escribe en WAV usando jitter buffer real."""
    log(f"[Worker] Iniciado para cliente con SSRC: {client_id}", "INFO")
    client = clients[client_id]
    prefill_done = False
    while True:
        with client['lock']:
            buffer = client['buffer']
            next_seq = client['next_seq']

            log_jitter(client_id, buffer, next_seq)

            # Prefill del jitter buffer
            prefill_done = check_prefill(buffer, prefill_done,client_id)
            if not prefill_done:
                if handle_inactivity(client, client_id):
                    break
                time.sleep(0.01)
                continue

            # Procesar buffer
            process_buffer(client, client_id)

            # Cierre por inactividad
            if handle_inactivity(client, client_id):
                break

        time.sleep(0.01)


def get_or_create_client(client_id, seq_num):
        with clients_lock:
            if client_id not in clients:
                clients[client_id] = {
                    'wavefile': create_wav_file(client_id),
                    'lock': threading.Lock(),
                    'buffer': dict(),
                    'next_seq': seq_num,
                    'last_time': time.time(),
                }
                t = threading.Thread(target=start_worker_client, args=(client_id,), daemon=True)
                t.start()
        return clients[client_id]
