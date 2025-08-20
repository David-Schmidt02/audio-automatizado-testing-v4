import threading
import signal
import sys
import os
import socket
import threading
import json

from utils import log_buffer_sizes_periodically
from rtp_server import udp_listener_fixed_jitter
from client_manager import clients_lock, clients
from metadata import channel_map

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import METADATA_PORT, LISTEN_IP, HEADLESS

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


def metadata_listener(ip, port):
    global HEADLESS
    import json
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    log(f"🎧 Listening for CHANNEL NAME on {LISTEN_IP}:{port}", "INFO")
    while True:
        data, addr = sock.recvfrom(1024)
        try:
            msg = json.loads(data.decode())
            if msg.get("cmd") == "GET_DISPLAY_NUM":
                if HEADLESS:
                    display_num = len(channel_map) + 10
                    sock.sendto(str(display_num).encode(), addr)
                    log(f"🖥️ Display solicitado por {addr}, asignado: {display_num}", "INFO")
            # Si es metadata normal
            elif "ssrc" in msg and "channel" in msg:
                ssrc = str(msg['ssrc'])
                channel = msg['channel']
                channel_map[ssrc] = channel
                log(f"📡 Metadata received: {ssrc} -> {channel}", "INFO")
                # (Opcional) puedes responder algo si lo necesitas
            else:
                log(f"❌ Mensaje JSON no reconocido: {msg}", "ERROR")
        except Exception:
            # Si no es JSON, loguea el mensaje crudo
            log(f"❌ Mensaje no JSON recibido: {data}", "ERROR")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    metadata_thread = threading.Thread(target=metadata_listener, args=(LISTEN_IP, METADATA_PORT,), daemon=True)
    metadata_thread.start()

    log_buffer_size_thread = threading.Thread(target=log_buffer_sizes_periodically, daemon=True)
    log_buffer_size_thread.start()

    listener_thread = threading.Thread(target=udp_listener_fixed_jitter, daemon=True)
    listener_thread.start()

    # Mantener el programa vivo esperando señal para cerrar
    signal.pause()
