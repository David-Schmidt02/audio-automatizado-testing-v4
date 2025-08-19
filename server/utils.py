
import gc
import os
import sys
import time

from client_manager import clients, clients_lock

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log

def log_buffer_sizes_periodically():
    while True:
        with clients_lock:
            for client_id, client in clients.items():
                buffer_size = len(client['buffer'])
                log(f"[Buffer] Cliente {client_id}: tamaño del buffer = {buffer_size}", "DEBUG")
        # Log de objetos grandes en memoria (debug)
        all_objs = gc.get_objects()
        wav_count = sum(1 for o in all_objs if hasattr(o, 'writeframes'))
        log(f"[Mem] Objetos tipo wave abiertos: {wav_count}", "DEBUG")
        time.sleep(30)
