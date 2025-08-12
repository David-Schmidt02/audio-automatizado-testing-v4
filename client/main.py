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
from start_firefox import clean_and_create_selenium_profile, configuracion_firefox, open_firefox_and_play_video
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

parec_proc = None
module_index = None
profile_dir = None
identificador = None
driver = None
service = Service(GeckoDriverManager().install())

def get_audio_streams_for_firefox(firefox_pid):
    """Obtiene todos los streams de audio asociados a un PID específico de Firefox"""
    try:
        streams_output = subprocess.check_output(["pactl", "list", "short", "sink-inputs"])
        firefox_streams = []
        for line in streams_output.decode().split('\n'):
            if line.strip() and str(firefox_pid) in line:
                stream_index = line.split('\t')[0]
                firefox_streams.append(stream_index)
                log(f"Stream encontrado para Firefox PID {firefox_pid}: {stream_index}", "DEBUG")
        return firefox_streams
    except Exception as e:
        log(f"Error obteniendo streams de Firefox: {e}", "ERROR")
        return []

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

def move_firefox_to_sink(firefox_pid, sink_name):
    """Mueve el audio de Firefox específico al sink específico"""
    streams = get_audio_streams_for_firefox(firefox_pid)
    moved_count = 0
    
    for stream_index in streams:
        try:
            subprocess.run(["pactl", "move-sink-input", stream_index, sink_name], check=True)
            log(f"✅ Stream {stream_index} movido a sink {sink_name}", "SUCCESS")
            moved_count += 1
        except subprocess.CalledProcessError as e:
            log(f"Error moviendo stream {stream_index}: {e}", "ERROR")
    
    if moved_count > 0:
        log(f"Total streams movidos: {moved_count}", "SUCCESS")
        return True
    else:
        log(f"No se pudieron mover streams para Firefox PID {firefox_pid}", "WARN")
        return False

def create_null_sink():
    global identificador
    identificador = random.randint(0, 100000)
    sink_name = f"rtp-stream-{identificador}"
    log(f"Creando PulseAudio sink: {sink_name}", "INFO")
    
    try:
        output = subprocess.check_output([
            "pactl", "load-module", "module-null-sink", f"sink_name={sink_name}"
        ])
        module_index = output.decode().strip()
        log(f"Módulo creado con índice: {module_index}", "SUCCESS")
        
        # Verificar que el sink fue creado listando los sinks disponibles
        time.sleep(1)  # Esperar un poco para que se inicialice
        try:
            sinks_output = subprocess.check_output(["pactl", "list", "short", "sinks"])
            sinks_list = sinks_output.decode().strip()
            log(f"Sinks disponibles:\n{sinks_list}", "DEBUG")
            
            # Verificar si nuestro sink está en la lista
            if sink_name in sinks_list:
                log(f"✅ Sink '{sink_name}' creado y disponible", "SUCCESS")
            else:
                log(f"⚠️ Sink '{sink_name}' no aparece en la lista de sinks", "WARN")
            
            # Verificar también el monitor correspondiente
            sources_output = subprocess.check_output(["pactl", "list", "short", "sources"])
            sources_list = sources_output.decode().strip()
            monitor_name = f"{sink_name}.monitor"
            
            if monitor_name in sources_list:
                log(f"✅ Monitor '{monitor_name}' disponible", "SUCCESS")
                # Extraer el índice del monitor para uso futuro
                for line in sources_list.split('\n'):
                    if monitor_name in line:
                        monitor_index = line.split('\t')[0]
                        log(f"Monitor index: {monitor_index}", "DEBUG")
                        break
            else:
                log(f"⚠️ Monitor '{monitor_name}' no encontrado", "WARN")
                
        except Exception as e:
            log(f"Error verificando sinks: {e}", "ERROR")
            
        return sink_name, module_index
        
    except subprocess.CalledProcessError as e:
        log(f"Error ejecutando pactl load-module: {e}", "ERROR")
        log(f"Código de salida: {e.returncode}", "ERROR")
        log(f"Salida stderr: {e.stderr}", "ERROR")
        raise
    except Exception as e:
        log(f"Error inesperado creando sink: {e}", "ERROR")
        raise

def launch_firefox(url, sink_name):
    global identificador
    global profile_dir
    global driver
    global service
    profile_dir = clean_and_create_selenium_profile(identificador)
    # Configuración de Firefox
    firefox_options = Options()
    firefox_options = configuracion_firefox(firefox_options)
    profile = FirefoxProfile(profile_directory=profile_dir)
    firefox_options.profile = profile
    # Iniciar el navegador
    driver = open_firefox_and_play_video(firefox_options, url, sink_name, service)
    
    # Obtener el PID del proceso Firefox para identificarlo
    try:
        # El driver de Selenium mantiene referencia al proceso
        firefox_pid = None
        if hasattr(driver, 'service') and hasattr(driver.service, 'process'):
            firefox_pid = driver.service.process.pid
            log(f"Firefox PID: {firefox_pid}", "DEBUG")
        
        # También puedes buscar por el perfil específico
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'firefox' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'])
                    if f"selenium-vm-profile-{identificador}" in cmdline:
                        firefox_pid = proc.info['pid']
                        log(f"Firefox encontrado por perfil - PID: {firefox_pid}", "SUCCESS")
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if firefox_pid:
            log(f"Firefox identificado - PID: {firefox_pid}, Sink: {sink_name}", "SUCCESS")
            
            # Esperar un poco para que Firefox inicie completamente y reproduzca audio
            time.sleep(3)
            
            # Mover el audio de Firefox al sink específico
            if move_firefox_to_sink(firefox_pid, sink_name):
                log(f"Audio de Firefox redirigido correctamente al sink {sink_name}", "SUCCESS")
            else:
                log(f"No se pudo redirigir audio de Firefox. Intentando método alternativo...", "WARN")
                # Método alternativo: buscar por aplicación Firefox en general
                try:
                    # Listar todos los sink-inputs y buscar por aplicación "Firefox"
                    streams_output = subprocess.check_output(["pactl", "list", "sink-inputs"])
                    streams_text = streams_output.decode()
                    
                    # Buscar índices de streams de Firefox
                    import re
                    firefox_pattern = r'Sink Input #(\d+).*?application\.name = "Firefox"'
                    matches = re.findall(firefox_pattern, streams_text, re.DOTALL | re.IGNORECASE)
                    
                    for stream_id in matches:
                        try:
                            subprocess.run(["pactl", "move-sink-input", stream_id, sink_name], check=True)
                            log(f"✅ Stream Firefox #{stream_id} movido por método alternativo", "SUCCESS")
                        except:
                            continue
                            
                except Exception as e:
                    log(f"Error en método alternativo: {e}", "ERROR")
            
            return firefox_pid
            
    except Exception as e:
        log(f"Error identificando Firefox: {e}", "WARN")
    
    print(f"🦊 Perfil temporal: {profile_dir}")
    return None

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
    global driver, parec_proc, module_index, profile_dir, identificador
    print("\n🛑 Limpiando...")
    
    if driver:
        try:
            # Intentar obtener el PID antes de cerrar para limpieza completa
            firefox_pid = None
            if identificador:
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            if 'firefox' in proc.info['name'].lower():
                                cmdline = ' '.join(proc.info['cmdline'])
                                if f"selenium-vm-profile-{identificador}" in cmdline:
                                    firefox_pid = proc.info['pid']
                                    log(f"Firefox PID encontrado para cleanup: {firefox_pid}", "DEBUG")
                                    break
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                except:
                    pass
            
            driver.quit()
            log("Driver de Firefox cerrado", "SUCCESS")
            
            # Si encontramos el PID, mostrar streams que se están cerrando
            if firefox_pid:
                try:
                    streams = get_audio_streams_for_firefox(firefox_pid)
                    if streams:
                        log(f"Streams de audio cerrados: {streams}", "DEBUG")
                except:
                    pass
                    
        except Exception as e:
            log(f"Error cerrando driver: {e}", "ERROR")
    
    if parec_proc and parec_proc.poll() is None:
        parec_proc.kill()
        log("Proceso parec terminado", "SUCCESS")
        
    if module_index:
        try:
            subprocess.run(["pactl", "unload-module", module_index], check=True)
            log(f"Módulo PulseAudio {module_index} descargado", "SUCCESS")
        except Exception as e:
            log(f"Error descargando módulo: {e}", "ERROR")
            
    if profile_dir and os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            log(f"Perfil temporal eliminado: {profile_dir}", "SUCCESS")
        except Exception as e:
            log(f"Error eliminando perfil: {e}", "ERROR")
            
    print("✅ Limpieza completa.")

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

def main():
    global parec_proc, module_index

    if len(sys.argv) != 3:
        print(f"Uso: {sys.argv[0]} <URL> <host:puerto>")
        sys.exit(1)

    url = sys.argv[1]
    destination = sys.argv[2]

    sink_name, module_index = create_null_sink()
    time.sleep(2)  # esperar inicialización sink

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    firefox_pid = launch_firefox(url, sink_name)
    pulse_device = f"{sink_name}.monitor"
    
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
