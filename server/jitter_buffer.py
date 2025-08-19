import os
import sys


parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import JITTER_BUFFER_SIZE, MAX_WAIT

# --- Jitter buffer configurable ---
def log_jitter(client_id, buffer, next_seq):
    """
    Registra la información de jitter para un cliente específico.
    """
    if buffer:
        min_seq = min(buffer.keys())
        jitter = (min_seq - next_seq) % 65536
        log(f"[Jitter] Cliente {client_id}: jitter acumulado = {jitter} (next_seq={next_seq}, min_seq={min_seq}, buffer={sorted(buffer.keys())})", "DEBUG")


def check_prefill(buffer, prefill_done, client_id):
    """
    Verifica si el pre-llenado del jitter buffer ha sido completado.
    """
    if not prefill_done:
        if len(buffer) >= JITTER_BUFFER_SIZE:
            log(f"[JitterBuffer] Cliente {client_id}: pre-llenado completado con {len(buffer)} paquetes", "INFO")
            return True
    return prefill_done
