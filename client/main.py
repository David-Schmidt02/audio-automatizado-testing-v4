import os
import sys
import signal
import time
import threading
import subprocess

import random
from rtp_client import send_rtp_stream_to_server 

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import BUFFER_SIZE, DEST_IP, DEST_PORT, METADATA_PORT

from client.audio_client_session import AudioClientSession

# Variables globales para cleanup
id_instance = random.randint(1000, 100000)

# Controlador de sesión de audio
audio_client_session = AudioClientSession(id_instance)


def signal_handler(sig, frame):
    audio_client_session.cleanup()
    sys.exit(0)


def record_audio(pulse_device):
    """Graba y envía un stream continuo de audio usando ffmpeg sin segmentación."""
    log("🎵 Starting continuous audio streaming (sin segmentación)", "INFO")

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "pulse",
            "-i", pulse_device,
            "-acodec", "pcm_s16le",
            "-ar", "48000",
            "-ac", "1",
            "-f", "s16le",     # ⚠️ NO "wav"
            "-loglevel", "error",
            "pipe:1"
        ]

        log(f"🚀 Starting ffmpeg streaming...", "INFO")

        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            try:
                while not audio_client_session.stop_event.is_set():
                    data = process.stdout.read(BUFFER_SIZE)
                    if not data:
                        break
                    try:
                        send_rtp_stream_to_server (data, id_instance)
                    except Exception as e:
                        log(f"⚠️ Error enviando audio: {e}", "ERROR")
                        break

                if process.poll() is None:
                    log("🛑 Stopping FFmpeg...", "INFO")
                    process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except Exception:
                        pass
            except Exception as e:
                log(f"❌ Error in continuous streaming: {e}", "ERROR")
    except Exception as e:
        log(f"❌ Error in continuous streaming: {e}", "ERROR")


def start_audio_recording(pulse_device):
    """Inicia el hilo de grabación de audio."""
    global recording_thread
    
    pulse_device_monitor = f"{pulse_device}.monitor"
    log(f"🎤 Starting audio capture from PulseAudio source: {pulse_device_monitor}", "INFO")
    audio_client_session.recording_thread = threading.Thread(
        target=record_audio, 
        args=(pulse_device_monitor,), 
        daemon=True
    )
    audio_client_session.recording_thread.start()
    return audio_client_session.recording_thread

def extract_channel_name(url):
    import re
    match = re.search(r'youtube\\.com/@([^/]+)', url)
    return match.group(1) if match else "unknown"

def send_channel_metadata(channel_name, ssrc):
    import socket
    import json
    msg = json.dumps({"ssrc": ssrc, "channel": channel_name})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(msg.encode(), (DEST_IP, METADATA_PORT))
    sock.close()
    
def main():
    """Función principal."""
    
    # 1. Validar argumentos de línea de comandos
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <URL>")
        print(f"\nExample: {sys.argv[0]} 'https://www.youtube.com/@todonoticias/live'")
        sys.exit(1)

    url = sys.argv[1]

    global id_instance

    # Configurar señales para cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 2. Crear sink PulseAudio único
    sink_name = audio_client_session.create_pulse_sink()
    if not sink_name:
        audio_client_session.cleanup()
        sys.exit(1)
    
    # 3. Crear perfil de Firefox con autoplay habilitado (solo una vez)
    firefox_profile_dir = audio_client_session.create_firefox_profile()
    if not firefox_profile_dir:
        audio_client_session.cleanup()
        log("⚠️ Usando perfil por defecto (sin autoplay optimizado)", "WARNING")
    
    # 4. Lanzar Firefox con sink preconfigurado y perfil optimizado
    if not audio_client_session.launch_firefox(url):
        audio_client_session.cleanup()
        sys.exit(1)
    
    # 5. Esperar un poco para que Firefox inicie y luego configurar control de ads
    print("⏳ Esperando que Firefox se inicie completamente...")
    time.sleep(5)
    
    # 6. Iniciar control de ads con Selenium usando el mismo perfil
    print("🎯 Iniciando sistema de control de ads...")
    print("⚠️ Control automático de ads deshabilitado (para evitar segunda ventana)")
    
    # 6.1 Prueba para crear una carpeta con el nombre del canal previamente
    channel_name = extract_channel_name(url)
    send_channel_metadata(channel_name, id_instance)

    # 7. Iniciar captura y grabación de audio
    start_audio_recording(sink_name)
    
    print("🎯 System initialized successfully!")
    print("Press Ctrl+C to stop...")
    
    # 8. Esperar señal de shutdown
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    audio_client_session.cleanup()


if __name__ == "__main__":
    main()
