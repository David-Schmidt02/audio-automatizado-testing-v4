import os
import sys
import signal
import time
import threading
import subprocess

import random

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import DEST_IP, DEST_PORT, METADATA_PORT, XVFB_DISPLAY, HEADLESS, NUM_DISPLAY_PORT

from client.audio_client_session import AudioClientSession
from navigator_manager import Navigator
from xvfb_manager import start_xvfb, stop_xvfb

audio_client_session = None
navigator_manager = None

def signal_handler(sig, frame):
    audio_client_session.cleanup()
    navigator_manager.cleanup()
    sys.exit(0)

def obtain_display_num(ssrc):
    pass

def extract_channel_name(url):
    import re
    match = re.search(r'youtube\.com/@([^/]+)', url)
    return match.group(1) if match else "unknown"

def send_channel_metadata(channel_name, ssrc):
    import socket
    import json
    msg = json.dumps({"ssrc": ssrc, "channel": str(channel_name)})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    log(f"📡 Enviando metadata: {msg}", "INFO")
    sock.sendto(msg.encode(), (DEST_IP, METADATA_PORT))
    sock.close()


def return_display_number(ssrc):
    import socket
    import json
    msg = json.dumps({"cmd": "GET_DISPLAY_NUM", "ssrc": ssrc})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)  # 5 segundos de espera
    sock.sendto(msg.encode(), (DEST_IP, NUM_DISPLAY_PORT))
    log(f"🖥️ Display solicitado por {ssrc}", "INFO")
    try:
        data, _ = sock.recvfrom(1024)  # Espera la respuesta del servidor
        display_num = int(data.decode())
        log(f"✅ Display asignado por el servidor: :{display_num}", "INFO")
        display_str = f":{display_num}"
        sock.close()
        return display_str
    except socket.timeout:
        log("❌ No se recibió respuesta del servidor para el display", "ERROR")
        sock.close()
        return None


def main():
    """Función principal."""
    global audio_client_session, navigator_manager, XVFB_DISPLAY, HEADLESS

    # 1. Validar argumentos de línea de comandos
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <URL> <Navegador> <Headless>")
        print(f"\nExample: {sys.argv[0]} 'https://www.youtube.com/@todonoticias/live' 'Firefox/Chrome/Chromium' True")
        sys.exit(1)

    url = sys.argv[1]
    navigator_name = sys.argv[2]
    headless = sys.argv[3].lower() == 'true'
    HEADLESS = headless

    # Variables globales para cleanup
    id_instance = random.randint(1000, 100000)

    # Controlador de sesión de audio
    audio_client_session = AudioClientSession(id_instance)

    # Configurar señales para cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 2. Crear sink PulseAudio único
    sink_name = audio_client_session.create_pulse_sink()
    if not sink_name:
        audio_client_session.cleanup()
        sys.exit(1)

    # 2.1 Crear el manager de browser
    # Manager del navegador
    navigator_manager = Navigator(navigator_name, sink_name, headless)

    # 3. Crear perfil del Navegador (con autoplay)
    navigator_profile_dir = navigator_manager.create_navigator_profile()
    if not navigator_profile_dir:
        audio_client_session.cleanup()
        navigator_manager.cleanup()
        sys.exit(1)

    # 3.1 Crear Display de XVFB con el numero asignado por el servidor
    # 3.1 Además obtener el nombre del canal para crear la carpeta con su nombre
    channel_name = extract_channel_name(url)
    send_channel_metadata(channel_name, id_instance)
    log(f"✅ Canal extraído: {channel_name}", "INFO")
    if HEADLESS:
        log(f"MODO SOLICITADO: {HEADLESS}")
        XVFB_DISPLAY = return_display_number(id_instance)
        log(f"✅ Variable de entorno DISPLAY configurada: {XVFB_DISPLAY}", "INFO")
        xvfb_proc = start_xvfb(XVFB_DISPLAY)
        if not xvfb_proc:
            audio_client_session.cleanup()
            navigator_manager.cleanup()
            stop_xvfb(xvfb_proc)
            sys.exit(1)

    # 4. Lanzar Navegador con sink preconfigurado y perfil optimizado
    navigator_process = navigator_manager.launch_navigator(url, XVFB_DISPLAY)
    log(f"Proceso de navegador: {navigator_process}", "INFO")

    if not navigator_process:
        audio_client_session.cleanup()
        navigator_manager.cleanup()
        stop_xvfb(xvfb_proc)
        sys.exit(1)

    # 5. Esperar un poco para que Chrome inicie y luego configurar control de ads
    print(f"⏳ Esperando que {navigator_name} se inicie completamente...")
    time.sleep(5)


    # 6. Iniciar captura y grabación de audio
    print("🎵 Iniciando captura de audio...")
    audio_client_session.start_audio_recording(sink_name)
    
    print("🎯 System initialized successfully!")
    print("Press Ctrl+C to stop...")
    
    # 7. Esperar señal de shutdown
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    audio_client_session.cleanup()
    navigator_manager.cleanup()
    stop_xvfb(xvfb_proc)

if __name__ == "__main__":
    main()
