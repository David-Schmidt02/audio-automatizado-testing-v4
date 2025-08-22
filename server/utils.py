
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
        wave_objs = [o for o in all_objs if hasattr(o, 'writeframes')]
        # Solo contar los wave que realmente están abiertos
        wave_open = [w for w in wave_objs if not (getattr(w, '_file', None) is None or getattr(w, 'closed', False))]
        wav_count = len(wave_open)
        log(f"[Mem] Objetos tipo wave abiertos: {wav_count}", "WARN")
        # Log extra: mostrar id y estado de cerrado de cada objeto wave
        for i, w in enumerate(wave_objs):
            closed = getattr(w, '_file', None) is None or getattr(w, 'closed', False)
            log(f"[Mem][wave] id={id(w)} cerrado={closed} repr={repr(w)}", "DEBUG")
            if closed:
                referrers = gc.get_referrers(w)
                log(f"[Mem][wave] id={id(w)} REFERENCIADO POR: {[type(r) for r in referrers]}", "DEBUG")
                # Si quieres ver más detalle:
                for ref in referrers:
                    log(f"    Ref: {repr(ref)[:200]}", "DEBUG")

        log(" ---------------------------"*3, "WARN")
        for w in wave_open:
            print(f"Referencias a wave id={id(w)}:")
            refs = gc.get_referrers(w)
            for ref in refs:
                print(f"  - {type(ref)}: {repr(ref)[:200]}")

        time.sleep(30)
