import threading
import signal
import sys
import os

from utils import log_buffer_sizes_periodically
from rtp_server import udp_listener_fixed_jitter
from client_manager import clients_lock, clients

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log

def shutdown_handler(signum, frame):
    log("\n🛑 Shutting down server...", "WARNING")

    with clients_lock:
        log("💾 Closing all WAV files...", "INFO")
        for client_id, client in clients.items():
            try:
                client['wavefile'].close()
                log(f"Closed WAV for client {client_id}", "INFO")
            except Exception as e:
                log(f"Error closing WAV file for client {client_id}: {e}", "ERROR")

    log("✅ Cleanup complete.", "INFO")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    log_buffer_size_thread = threading.Thread(target=log_buffer_sizes_periodically, daemon=True)
    log_buffer_size_thread.start()

    listener_thread = threading.Thread(target=udp_listener_fixed_jitter, daemon=True)
    listener_thread.start()

    # Mantener el programa vivo esperando señal para cerrar
    signal.pause()
