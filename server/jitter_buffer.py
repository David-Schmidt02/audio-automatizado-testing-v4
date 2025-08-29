import os
import sys
import time

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import JITTER_BUFFER_SIZE, MAX_WAIT, FRAME_SIZE, JITTER_BUFFER_SIZE


import time

class JitterBuffer:
    def __init__(self, prefill_min=10, max_wait=0.5):
        self.buffer = {}  # seq_num -> (timestamp, payload)
        self.prefill_min = prefill_min
        self.prefill_done = False
        self.max_wait = max_wait
        self.last_seq_time = None  # (seq_num, time.time())
        self.expected_timestamp = None

    def add_packet(self, seq_num, timestamp, payload):
        self.buffer[seq_num] = (timestamp, payload)
        # Opcional: actualizar expected_timestamp si es el primer paquete
        if self.expected_timestamp is None:
            self.expected_timestamp = timestamp

    def ready_to_consume(self):
        if not self.prefill_done and len(self.buffer) >= self.prefill_min:
            self.prefill_done = True
        return self.prefill_done

    def pop_next(self, next_seq):
        now = time.time()
        # Si el paquete esperado está, lo devolvemos
        if next_seq in self.buffer:
            timestamp, payload = self.buffer.pop(next_seq)
            self.last_seq_time = (next_seq, now)
            self.expected_timestamp = timestamp  # Actualiza el timestamp esperado
            return {"payload": payload, "is_silence": False}
        # Si no está, pero ya esperamos suficiente, insertamos silencio
        elif self.last_seq_time and (now - self.last_seq_time[1]) > self.max_wait:
            # Avanzamos secuencia y timestamp esperado
            self.last_seq_time = (next_seq, now)
            if self.expected_timestamp is not None:
                self.expected_timestamp += 960  # Ejemplo: 20ms a 48kHz = 960 samples
            silence = b'\x00' * 2 * 960  # 2 bytes por sample, 960 samples (ajusta según tu frame)
            return {"payload": silence, "is_silence": True}
        else:
            return None  # Esperar más

    def get_size(self):
        return len(self.buffer)

    # Opcional: descartar paquetes muy viejos según timestamp
    def discard_old(self, current_timestamp):
        to_remove = [seq for seq, (ts, _) in self.buffer.items() if ts < current_timestamp - 10 * 960]
        for seq in to_remove:
            del self.buffer[seq]

# --- Jitter buffer configurable ---

def check_prefill(buffer, prefill_done, client_id):
    """
    Verifica si el pre-llenado del jitter buffer ha sido completado.
    """
    if not prefill_done and len(buffer) > 0:
        log(f"[JitterBuffer] Cliente {client_id}: pre-llenado completado con {len(buffer)} paquetes", "INFO")
        return True
    return prefill_done
