import os
import sys
import signal
import time
import random
import subprocess
import socket
import threading
import struct
import shutil
import psutil
from pathlib import Path
from start_firefox import clean_and_create_selenium_profile, configuracion_firefox, open_firefox_and_get_pid, move_firefox_audio_to_sink, load_video_and_configure
from youtube_js_utils import YouTubeJSUtils, get_youtube_player_state, activate_youtube_video, force_youtube_audio_refresh
# Importaciones para Selenium
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

from logger_client import log

# Parámetros
SAMPLE_RATE = 48000 # Frecuencia de muestreo, determina la calidad del audio
CHANNELS = 1 # Número de canales de audio
BIT_DEPTH = 16 # Profundidad de bits por muestra
PAYLOAD_TYPE_L16 = 96 # Tipo de carga útil para audio lineal de 16 bits
RTP_CLOCK_RATE = 48000 # Frecuencia de reloj RTP
MTU = 1500 # Unidad máxima de transmisión

# Identificadores para PulseAudio
module_id = None # ID del módulo creado
sink_index = None # Índice del sink creado
pulse_device = None # Dispositivo PulseAudio del monitor del sink

identificador = None # Identificador del sink creado -> Revisar si es necesario

parec_proc = None # Proceso parec
profile_dir = None # Directorio del perfil de Firefox para esta instancia 

# Configuración de Selenium
driver = None # Controlador de Firefox
service = Service(GeckoDriverManager().install()) # Servicio de GeckoDriver
firefox_pid = None # PID del proceso de Firefox

def verify_audio_capture(sink_name, timeout=10):
    """Verifica que el sink monitor está capturando audio"""
    monitor_device = f"{sink_name}.monitor"
    log(f"Verificando captura de audio en {monitor_device}...", "INFO")
    
    try:
        # Comando para verificar si hay audio fluyendo en el monitor
        cmd = [
            "pactl", "list", "sources", "short"
        ]
        
        sources_output = subprocess.check_output(cmd)
        sources_text = sources_output.decode()
        
        if monitor_device in sources_text:
            log(f"✅ Monitor {monitor_device} disponible", "SUCCESS")
            
            # Verificar si hay actividad de audio
            detailed_cmd = ["pactl", "list", "sources"]
            detailed_output = subprocess.check_output(detailed_cmd)
            detailed_text = detailed_output.decode()
            
            # Buscar información del monitor específico
            if monitor_device in detailed_text:
                log(f"✅ Monitor {monitor_device} operativo", "SUCCESS")
                return True
            else:
                log(f"⚠️ Monitor {monitor_device} no encontrado en listado detallado", "WARN")
                return False
        else:
            log(f"❌ Monitor {monitor_device} no disponible", "ERROR")
            return False
            
    except Exception as e:
        log(f"Error verificando captura de audio: {e}", "ERROR")
        return False

#-----------------------------------------------------------------------------------------------------------------#

# 1.2 - Verifica el monitor del sink creado
def verify_monitor_creation(monitor_name):
    log(f"Verificando creación de monitor: {monitor_name}", "INFO")
    try:
        sources_output = subprocess.check_output(["pactl", "list", "short", "sources"])
        sources_list = sources_output.decode().strip()
        log(f"Monitores disponibles:\n{sources_list}", "DEBUG")

        if monitor_name in sources_list:
            log(f"✅ Monitor '{monitor_name}' creado y disponible", "SUCCESS")
        else:
            log(f"⚠️ Monitor '{monitor_name}' no aparece en la lista de monitores", "WARN")

    except Exception as e:
        log(f"Error verificando monitores: {e}", "ERROR")

# 1.1 -Verifica la creacion del sink
def verify_sink_creation(sink_name):
    log(f"Verificando creación de sink: {sink_name}", "INFO")
    try:
        sinks_output = subprocess.check_output(["pactl", "list", "short", "sinks"])
        sinks_list = sinks_output.decode().strip()
        log(f"Sinks disponibles:\n{sinks_list}", "DEBUG")

        if sink_name in sinks_list:
            log(f"✅ Sink '{sink_name}' creado y disponible", "SUCCESS")
        else:
            log(f"⚠️ Sink '{sink_name}' no aparece en la lista de sinks", "WARN")

    except Exception as e:
        log(f"Error verificando sinks: {e}", "ERROR")
    verify_monitor_creation(f"{sink_name}.monitor")

# 1 - Se crea el Sink de audio con un id único 
def create_null_sink():
    global identificador
    global module_id
    global pulse_device
    identificador = random.randint(0, 100000)
    sink_name = f"rtp-stream-{identificador}"
    log(f"Creando PulseAudio sink: {sink_name}", "INFO")
    
    try:
        # Al ejecutar pactl load-module module-null-sink "sink_name = "rtp-stream-{identificador}" se crea el sink
        output = subprocess.check_output([
            "pactl", "load-module", "module-null-sink", f"sink_name={sink_name}"
        ])
        # Obtenemos el id del módulo del sink creado -> sirve para descargarlo/limpiarlo despues
        module_id = output.decode().strip()
        log(f"Módulo creado con id: {module_id}", "SUCCESS")

        # Verificar que el sink fue creado listando los sinks disponibles
        time.sleep(2)  # Esperar un poco para que se inicialice
        verify_sink_creation(sink_name) # Tambien verifica el monitor dentro
        pulse_device = f"{sink_name}.monitor"
        return sink_name, module_id
        
    except subprocess.CalledProcessError as e:
        log(f"Error ejecutando pactl load-module: {e}", "ERROR")
        log(f"Código de salida: {e.returncode}", "ERROR")
        log(f"Salida stderr: {e.stderr}", "ERROR")
        raise
    except Exception as e:
        log(f"Error inesperado creando sink: {e}", "ERROR")
        raise

#-----------------------------------------------------------------------------------------------------------------#

# 2 - Se crea el perfil de Firefox, se configura Firefox y se lo lanza
def launch_firefox(url, sink_name):
    global identificador
    global profile_dir
    global driver
    global service
    global firefox_pid

    profile_dir = clean_and_create_selenium_profile(identificador) # 2.1 Se crea un perfil temporal para Firefox con un identificador único que puede utilizar selenium
    # Configuración de Firefox
    firefox_options = Options()
    firefox_options = configuracion_firefox(firefox_options) # 2.2 Configuraciones adicionales para el perfil de firefox
    profile = FirefoxProfile(profile_directory=profile_dir)
    firefox_options.profile = profile
    # Iniciar el navegador
    driver, firefox_pid = open_firefox_and_get_pid(firefox_options, service) # 2.3 Inicia Firefox y retorna su PID

    if firefox_pid:
        # Mover audio de Firefox al sink
        move_firefox_audio_to_sink(firefox_pid, sink_name) # 2.4 Movemos el stream de esta instancia de firefox al sink creado
        # Cargar URL y configurar JS
        load_video_and_configure(driver, url) # 2.5 Cargar la URL y configurar el JavaScript
    else:
        log("No se pudo iniciar Firefox correctamente", "ERROR")

#-----------------------------------------------------------------------------------------------------------------#

# 3.1 - Verificación del estado de JavaScript, utilizando la clase YouTubeJSUtils
def verificar_estado_javascript(driver):
    state = get_youtube_player_state(driver)
    if not state or not state.get('hasVideo'):
        log("No hay video cargado", "WARN")
        return False
    if state.get('videoError'):
        log(f"Error en video: {state['videoError']}", "ERROR")
        force_youtube_audio_refresh(driver)
        # Lógica para manejar error de video
        return False
    if state.get('videoEnded'):
        log("Video terminado", "WARN")
        force_youtube_audio_refresh(driver)
        # Lógica para manejar video terminado
        return False
    if state.get('videoPaused'):
        log("Video pausado, intentando reactivar...", "WARN")
        activate_youtube_video(driver)
        time.sleep(1)
        # Revisar si logró reactivar
        return YouTubeJSUtils.is_video_playing(driver)
    if state.get('videoReadyState', 0) < 3:
        log("Video no listo para reproducir", "WARN")
        return False
    return True
# 3 - Monitoreo del estado de JavaScript
def monitor_javascript_health(driver, interval=30):
    if not driver:
        return

    def check_js_health():
        while True:
            try:
                if verificar_estado_javascript(driver):
                    log("JavaScript health check: OK", "DEBUG")
                else:
                    log("JavaScript health check: PROBLEMA DETECTADO", "WARN")
                    # Aquí podrías usar force_youtube_audio_refresh(driver) o estrategias similares

            except Exception as e:
                log(f"Error en health check: {e}", "ERROR")
                break

            time.sleep(interval)

    health_thread = threading.Thread(target=check_js_health, daemon=True)
    health_thread.start()
    return health_thread

#-----------------------------------------------------------------------------------------------------------------#

def start_parec_and_stream(destination, pulse_device):
    global parec_proc
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    host, port = destination.split(":")
    port = int(port)
    udp_addr = (host, port)

    parec_cmd = [
        "parec",
        "--format=s16be",
        f"--rate={SAMPLE_RATE}",
        f"--channels={CHANNELS}",
        f"--device={pulse_device}"
    ]

    parec_proc = subprocess.Popen(
        parec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Tamaño de frame de 20ms
    buffer_size = (SAMPLE_RATE // 50) * CHANNELS * (BIT_DEPTH // 8)

    ssrc = random.randint(0, (1 << 32) - 1)
    seq_num = random.randint(0, 65535)
    timestamp = 0

    def rtp_header(payload_type, seq, ts, ssrc):
        v_p_x_cc = 0x80
        m_pt = payload_type & 0x7F
        return struct.pack("!BBHII", v_p_x_cc, m_pt, seq, ts, ssrc)

    def stream_audio():
        nonlocal seq_num, timestamp
        while True:
            data = parec_proc.stdout.read(buffer_size)
            if not data:
                break
            timestamp += RTP_CLOCK_RATE // 50
            header = rtp_header(PAYLOAD_TYPE_L16, seq_num, timestamp, ssrc)
            seq_num = (seq_num + 1) % 65536
            packet = header + data
            udp_sock.sendto(packet, udp_addr)

    threading.Thread(target=stream_audio, daemon=True).start()

    return parec_proc

def cleanup():
    global driver, parec_proc, module_id, profile_dir
    
    print("\n🛑 Limpiando...")
    try:
        if driver:
            driver.quit()
            print("Driver de Firefox cerrado")
    except Exception as e:
        print(f"Error cerrando driver: {e}")

    try:
        if parec_proc and parec_proc.poll() is None:
            parec_proc.kill()
            print("Proceso parec terminado")
    except Exception as e:
        print(f"Error terminando proceso parec: {e}")

    try:
        if module_id:
            subprocess.run(["pactl", "unload-module", module_id], check=True)
            print(f"Módulo PulseAudio {module_id} descargado")
    except Exception as e:
        print(f"Error descargando módulo PulseAudio: {e}")

    try:
        if profile_dir and os.path.exists(profile_dir):
            shutil.rmtree(profile_dir)
            print(f"Perfil temporal eliminado: {profile_dir}")
    except Exception as e:
        print(f"Error eliminando perfil temporal: {e}")

    print("✅ Limpieza completa.")


def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

def main():
    global parec_proc, module_id, pulse_device

    if len(sys.argv) != 3:
        print(f"Uso: {sys.argv[0]} <URL> <host:puerto>")
        sys.exit(1)

    url = sys.argv[1]
    destination = sys.argv[2]

    sink_name, module_id = create_null_sink()
    time.sleep(2)  # esperar inicialización sink

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    launch_firefox(url, sink_name)

    # Iniciar monitoreo de JavaScript
    if driver:
        log("Iniciando monitoreo de JavaScript...", "INFO")
        monitor_javascript_health(driver, interval=15)  # Verificar cada 15 segundos

    # Verificar que el audio se está capturando correctamente
    if verify_audio_capture(sink_name):
        log("Audio capture verificado correctamente", "SUCCESS")
    else:
        log("Advertencia: No se pudo verificar la captura de audio", "WARN")
    
    parec_proc = start_parec_and_stream(destination, pulse_device)

    # Esperar señales
    signal.pause()

if __name__ == "__main__":
    main()
