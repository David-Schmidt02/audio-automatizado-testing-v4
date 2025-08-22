import os
import sys
import time

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import JITTER_BUFFER_SIZE, MAX_WAIT
_last_jitter_log = {}


# --- Jitter buffer configurable ---
def log_jitter(client_id, buffer, next_seq):
    if buffer:
        min_seq = min(buffer.keys())
        jitter = (min_seq - next_seq) % 65536
        now = time.time()
        last = _last_jitter_log.get(client_id, 0)
        if now - last > 1:  # Loguea como máximo una vez por segundo por cliente
            keys = sorted(buffer.keys())
            buffer_str = f"{keys[:5]} ... {keys[-5:]}" if len(keys) > 10 else str(keys)
            log(f"[Jitter] Cliente {client_id}: jitter acumulado = {jitter} (next_seq={next_seq}, min_seq={min_seq}, buffer={buffer_str}, size={len(keys)})", "DEBUG")
            _last_jitter_log[client_id] = now


def check_prefill(buffer, prefill_done, client_id):
    """
    Verifica si el pre-llenado del jitter buffer ha sido completado.
    """
    if not prefill_done:
        if len(buffer) >= JITTER_BUFFER_SIZE:
            log(f"[JitterBuffer] Cliente {client_id}: pre-llenado completado con {len(buffer)} paquetes", "INFO")
            return True
    return prefill_done
