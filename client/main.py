import os
import sys
import signal
import time
import threading
import subprocess
import threading

import random

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import DEST_IP, DEST_PORT, METADATA_PORT, XVFB_DISPLAY, NUM_DISPLAY_PORT

from client.audio_client_session import AudioClientSession
from navigator_manager import Navigator
from xvfb_manager import Xvfb_manager


audio_client_session = None
navigator_manager = None
xvfb_manager = None
HEADLESS = False
shutdown_event = threading.Event()
# Variable para distinguir si el shutdown fue por relanzamiento automático o por señal del usuario
shutdown_reason = {'auto': False, 'sigint': False}

def signal_handler(sig, frame):
    if not shutdown_event.is_set():
        log("🛑 Received shutdown signal. Cleaning up...", "WARN")
        shutdown_reason['sigint'] = True
        shutdown_event.set()

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
    sock.sendto(msg.encode(), (DEST_IP, NUM_DISPLAY_PORT))
    log(f"🖥️ Display solicitado por el cliente: {ssrc}", "INFO")
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


def monitor_browser_process(browser_process, max_ram_mb=500, max_runtime_sec=7200):
    import psutil
    start_time = time.time()
    try:
        p = psutil.Process(browser_process.pid)
        log("🔍 Iniciando monitor de uso de RAM del navegador...", "INFO")
    except Exception:
        log("❌ Error al obtener el proceso del navegador", "ERROR")
        return  # Proceso ya terminó

    while not shutdown_event.is_set():
        try:
            ram_mb = p.memory_info().rss / 1024 / 1024
            if ram_mb > max_ram_mb - 20 or (time.time() - start_time) > max_runtime_sec - 15:
                log(f"🛑 Navegador cerca del límite de RAM ({ram_mb:.1f} MB) o tiempo. Relanzando script...", "WARN")
                log(f"Memoria al finalizar: {ram_mb:.1f} MB", "INFO")
                shutdown_reason['auto'] = True
                shutdown_event.set()
                break
            time.sleep(10)
        except psutil.NoSuchProcess:
            log("❌ El proceso del navegador ya no existe.", "WARN")
            shutdown_event.set()
            break  # El navegador ya terminó


def levantar_script_nueva_terminal():
    # Relanzamiento en la misma ventana:
    import os
    import sys
    args = [sys.executable] + sys.argv
    log(f"[RELAUNCH] Relanzando en la misma terminal: {' '.join(args)}", "INFO")
    time.sleep(2)
    os.execv(sys.executable, args)

def print_subprocess_tree(pid):
    import psutil
    try:
        parent = psutil.Process(pid)
        print(f"Proceso principal: {parent.pid} - {parent.name()}")
        for child in parent.children(recursive=True):
            print(f"  Hijo: {child.pid} - {child.name()}")
    except Exception as e:
        print(f"Error: {e}")

def minimizar_ventana_por_pid(pid, delay=5):
    import platform
    """
    Minimiza la ventana asociada a un PID específico después de 'delay' segundos (solo Linux con xdotool).
    """
    import time
    import subprocess
    time.sleep(delay)
    print_subprocess_tree(pid)
    so = platform.system()
    if so == 'Linux':
        try:
            # Busca la ventana por PID y la minimiza
            subprocess.run(['xdotool', 'search', '--pid', str(pid), 'windowminimize'], check=True)
        except Exception as e:
            log(f"No se pudo minimizar la ventana del navegador (PID {pid}): {e}", "WARN")
    else:
        log("Minimizar por PID solo implementado en Linux con xdotool.", "INFO")
    return

def main():
    """Función principal."""
    global audio_client_session, navigator_manager, xvfb_manager, XVFB_DISPLAY, HEADLESS

    # 1. Validar argumentos de línea de comandos
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <URL> <Navegador> <Headless>")
        print(f"\nExample: {sys.argv[0]} 'https://www.youtube.com/@todonoticias/live' 'Firefox/Chrome/Chromium' True")
        sys.exit(1)

    url = sys.argv[1]
    navigator_name = sys.argv[2]
    headless = sys.argv[3].lower() == 'true'
    if headless:
        HEADLESS = True

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
    time.sleep(1)  # Esperar un poco para que el servidor procese la metadata
    log(f"✅ Canal extraído: {channel_name}", "INFO")
    if headless:
        XVFB_DISPLAY = return_display_number(id_instance)
        if not XVFB_DISPLAY:
            log("❌ No se pudo obtener el número de display", "ERROR")
            audio_client_session.cleanup()
            navigator_manager.cleanup()
            sys.exit(1)
        else:
            log(f"✅ Variable de entorno DISPLAY configurada: {XVFB_DISPLAY}", "INFO")

        xvfb_manager = Xvfb_manager(XVFB_DISPLAY) 
        xvfb_process = xvfb_manager.start_xvfb()

        if not xvfb_process:
            audio_client_session.cleanup()
            navigator_manager.cleanup()
            xvfb_manager.stop_xvfb()
            sys.exit(1)


    # 4. Lanzar Navegador con sink preconfigurado y perfil optimizado
    navigator_process = navigator_manager.launch_navigator(url, XVFB_DISPLAY)
    log(f"Proceso de navegador: {navigator_process}", "INFO")

    # Minimizar la ventana del navegador tras 5 segundos (solo Linux con xdotool)
    if navigator_process:
        threading.Thread(target=minimizar_ventana_por_pid, args=(navigator_process.pid, 5), daemon=True).start()

    if not navigator_process:
        audio_client_session.cleanup()
        navigator_manager.cleanup()
        if headless:
            xvfb_manager.stop_xvfb()
        sys.exit(1)

    # 5. Esperar un poco para que Chrome inicie y luego configurar control de ads
    log(f"⏳ Esperando que {navigator_name} se inicie completamente...", "INFO")
    time.sleep(5)


    # 6. Iniciar captura y grabación de audio
    log("🎵 Iniciando captura de audio...", "INFO")
    thread_audio_capture = audio_client_session.start_audio_recording(sink_name)
    

    # 6.1 Iniciar Hilo que controla los mb del browser
    log("🔍 Iniciando monitor de uso de RAM del navegador...", "INFO")
    thread_monitor_browser = threading.Thread(target=monitor_browser_process, args=(navigator_process, 1000, 300))
    thread_monitor_browser.start()

    log("🎯 System initialized successfully!", "INFO")
    log("Press Ctrl+C to stop...", "INFO")
    

    # 7. Esperar señal de shutdown
    try:
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_reason['sigint'] = True
        shutdown_event.set()

    # Cleanup solo una vez, fuera del bucle
    if not thread_monitor_browser.is_alive():
        log("❌ El navegador ya se cerró por timeout o por consumo de RAM. Saliendo...", "WARN")
    else:
        log("🛑 Shutdown solicitado por el usuario o señal externa. Cerrando programas...", "INFO")

    if audio_client_session:
        log("Cerrando audio_client_session...", "INFO")
        audio_client_session.cleanup()
    if navigator_manager:
        log("Cerrando navigator_manager...", "INFO")
        navigator_manager.cleanup()
    if HEADLESS and xvfb_manager:
        log("Cerrando xvfb_manager...", "INFO")
        xvfb_manager.stop_xvfb()
    log("✅ Todos los programas cerrados. Saliendo...", "INFO")

    # Si el shutdown fue por RAM/tiempo (no por Ctrl+C), relanzar
    if shutdown_reason['auto'] and not shutdown_reason['sigint']:
        levantar_script_nueva_terminal()

    # Forzar salida de todos los hilos y procesos hijos
    os._exit(0)

if __name__ == "__main__":
    main()
