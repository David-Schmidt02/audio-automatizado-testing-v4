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
from my_logger import log_and_save
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
ssrc = None

def signal_handler(sig, frame):
    if not shutdown_event.is_set():
        log_and_save("🛑 Received shutdown signal. Cleaning up...", "WARN", ssrc)
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
    log_and_save(f"📡 Enviando metadata: {msg}", "INFO", ssrc)
    sock.sendto(msg.encode(), (DEST_IP, METADATA_PORT))
    sock.close()


def return_display_number(ssrc):
    import socket
    import json
    msg = json.dumps({"cmd": "GET_DISPLAY_NUM", "ssrc": ssrc})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(msg.encode(), (DEST_IP, NUM_DISPLAY_PORT))
    log_and_save(f"🖥️ Display solicitado por el cliente: {ssrc}", "INFO", ssrc)
    try:
        data, _ = sock.recvfrom(1024)  # Espera la respuesta del servidor
        display_num = int(data.decode())
        log_and_save(f"✅ Display asignado por el servidor: :{display_num}", "INFO", ssrc)
        display_str = f":{display_num}"
        sock.close()
        return display_str
    except socket.timeout:
        log_and_save("❌ No se recibió respuesta del servidor para el display", "ERROR", ssrc)
        sock.close()
        return None


def monitor_browser_process(browser_process, max_ram_mb=500, max_runtime_sec=7200):
    import psutil
    start_time = time.time()
    try:
        p = psutil.Process(browser_process.pid)
        log_and_save("🔍 Iniciando monitor de uso de RAM del navegador...", "INFO", ssrc)
    except Exception:
        log_and_save("❌ Error al obtener el proceso del navegador", "ERROR", ssrc)
        return  # Proceso ya terminó

    while not shutdown_event.is_set():
        try:
            ram_mb = p.memory_info().rss / 1024 / 1024
            if ram_mb > max_ram_mb - 20 or (time.time() - start_time) > max_runtime_sec - 15:
                log_and_save(f"🛑 Navegador cerca del límite de RAM ({ram_mb:.1f} MB) o tiempo. Relanzando script...", "WARN", ssrc)
                log_and_save(f"Memoria al finalizar: {ram_mb:.1f} MB", "INFO", ssrc)
                shutdown_reason['auto'] = True
                shutdown_event.set()
                break
            time.sleep(10)
        except psutil.NoSuchProcess:
            log_and_save("❌ El proceso del navegador ya no existe.", "WARN", ssrc)
            shutdown_event.set()
            break  # El navegador ya terminó


def levantar_script_misma_terminal():
    # Relanzamiento en la misma ventana:
    import os
    import sys
    args = [sys.executable] + sys.argv
    log_and_save(f"[RELAUNCH] Relanzando en la misma terminal: {' '.join(args)}", "INFO", ssrc)
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


def minimizar_ventana_por_id(window_id, delay=5):
    """
    Minimiza la ventana asociada a un ID específico que contenga el nombre del canal en el título.
    Si no encuentra ninguna, minimiza la primera ventana encontrada como fallback. Solo Linux con xdotool.
    """
    import time
    import subprocess
    import platform
    time.sleep(delay)
    so = platform.system()
    if so == 'Linux':
        try:
            subprocess.run(['xdotool', 'windowminimize', window_id], check=True)
            log_and_save(f"Ventana minimizada: {window_id}", "INFO", ssrc)
        except Exception as e:
            log_and_save(f"No se pudo minimizar la ventana {window_id}: {e}", "WARN", ssrc)
    else:
        log_and_save("Minimizar por ID solo implementado en Linux con xdotool.", "INFO", ssrc)


def main():
    """Función principal."""
    global audio_client_session, navigator_manager, xvfb_manager, XVFB_DISPLAY, HEADLESS, ssrc

    # 1. Validar argumentos de línea de comandos
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <URL> <Navegador> <Headless>")
        print(f"\nExample: {sys.argv[0]} 'https://www.youtube.com/@todonoticias/live' 'Chrome/Chromium' True")
        sys.exit(1)

    url = sys.argv[1]
    navigator_name = sys.argv[2]
    headless = sys.argv[3].lower() == 'true'
    if headless:
        HEADLESS = True

    # Variables globales para cleanup
    id_instance = random.randint(10000, 100000)

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
    navigator_manager = Navigator(navigator_name, sink_name, headless, id_instance)
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
    log_and_save(f"✅ Canal extraído: {channel_name}", "INFO", id_instance)
    if headless:
        XVFB_DISPLAY = return_display_number(id_instance)
        if not XVFB_DISPLAY:
            log_and_save("❌ No se pudo obtener el número de display", "ERROR", id_instance)
            audio_client_session.cleanup()
            navigator_manager.cleanup()
            sys.exit(1)
        else:
            log_and_save(f"✅ Variable de entorno DISPLAY configurada: {XVFB_DISPLAY}", "INFO", id_instance)

        xvfb_manager = Xvfb_manager(XVFB_DISPLAY) 
        xvfb_process = xvfb_manager.start_xvfb()

        if not xvfb_process:
            audio_client_session.cleanup()
            navigator_manager.cleanup()
            xvfb_manager.stop_xvfb()
            sys.exit(1)


    # 4. Lanzar Navegador con sink preconfigurado y perfil optimizado
    navigator_process = navigator_manager.launch_navigator(url, XVFB_DISPLAY)
    log_and_save(f"Proceso de navegador: {navigator_process}", "INFO", id_instance)

    time.sleep(10)  # darle tiempo a que se abra la ventana
    result = subprocess.run(
        ["xdotool", "getactivewindow"],
        capture_output=True, text=True
    )
    window_id = result.stdout.strip()

    # Minimizar la ventana del navegador tras 5 segundos (solo Linux con xdotool)
    if navigator_process and window_id:
        threading.Thread(target=minimizar_ventana_por_id, args=(window_id, 5), daemon=True).start()
    else:
        log_and_save("❌ No se pudo obtener el ID de la ventana", "ERROR", id_instance)
    
    log_and_save(f"ID de ventana obtenida: {window_id}", "INFO", id_instance)
    if not navigator_process:
        audio_client_session.cleanup()
        navigator_manager.cleanup()
        if headless:
            xvfb_manager.stop_xvfb()
        sys.exit(1)

    # 5. Esperar un poco para que Chrome inicie y luego configurar control de ads
    log_and_save(f"⏳ Esperando que {navigator_name} se inicie completamente...", "INFO", id_instance)
    time.sleep(5)

    # 6. Iniciar captura y grabación de audio
    log_and_save("🎵 Iniciando captura de audio...", "INFO", id_instance)
    thread_audio_capture = audio_client_session.start_audio_recording(sink_name)
    

    # 6.1 Iniciar Hilo que controla los mb del browser
    log_and_save("🔍 Iniciando monitor de uso de RAM del navegador...", "INFO", id_instance)
    thread_monitor_browser = threading.Thread(target=monitor_browser_process, args=(navigator_process, 1000, 3600))
    thread_monitor_browser.start()

    log_and_save("🎯 System initialized successfully!", "INFO", id_instance)
    log_and_save("Press Ctrl+C to stop...", "INFO", id_instance)

    # 7. Esperar señal de shutdown
    try:
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_reason['sigint'] = True
        shutdown_event.set()

    # Cleanup solo una vez, fuera del bucle
    if not thread_monitor_browser.is_alive():
        log_and_save("❌ El navegador ya se cerró por timeout o por consumo de RAM. Saliendo...", "WARN", id_instance)
    else:
        log_and_save("🛑 Shutdown solicitado por el usuario o señal externa. Cerrando programas...", "INFO", id_instance)

    if audio_client_session:
        log_and_save("Cerrando audio_client_session...", "INFO", id_instance)
        audio_client_session.cleanup()
    if navigator_manager:
        log_and_save("Cerrando navigator_manager...", "INFO", id_instance)
        navigator_manager.cleanup()
    if HEADLESS and xvfb_manager:
        log_and_save("Cerrando xvfb_manager...", "INFO", id_instance)
        xvfb_manager.stop_xvfb()
    log_and_save("✅ Todos los programas cerrados. Saliendo...", "INFO", id_instance)
    # Si el shutdown fue por RAM/tiempo (no por Ctrl+C), relanzar
    if shutdown_reason['auto'] and not shutdown_reason['sigint']:
        levantar_script_misma_terminal()

    # Forzar salida de todos los hilos y procesos hijos
    os._exit(0)

if __name__ == "__main__":
    main()
