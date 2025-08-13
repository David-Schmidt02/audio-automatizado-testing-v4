#!/usr/bin/env python3
"""
Sistema de audio automatizado simplificado - Análogo al script de Go
Captura audio de YouTube live streams y guarda chunks de 15 segundos.
Sigue exactamente el patrón del script Go para máxima simplicidad.
"""

import os
import sys
import signal
import time
import threading
import subprocess
import random
from rtp_client import send_pcm_to_server

# Importaciones para Selenium (control de ads)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    from selenium.common.exceptions import NoSuchElementException, TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium no disponible - sin control de ads automático")

# Variable global para parar hilos
stop_event = threading.Event()

# Variables globales para cleanup
sink_name = None
module_id = None
firefox_process = None
recording_thread = None
selenium_driver = None
ad_control_thread = None
firefox_profile_dir = None
id_instance = None
output_dir = None

def cleanup():
    """Limpieza de recursos al finalizar - siguiendo patrón Go."""
    global sink_name, module_id, firefox_process, recording_thread, selenium_driver, ad_control_thread, firefox_profile_dir
    
    print("\n🛑 Received shutdown signal. Cleaning up...")
    
    # Señalar a todos los hilos que paren
    stop_event.set()
    
    # Cerrar Selenium driver
    if selenium_driver:
        print("🔥 Closing Selenium driver...")
        try:
            selenium_driver.quit()
        except Exception as e:
            print(f"⚠️ Error closing Selenium: {e}")
    
    # Terminar Firefox
    if firefox_process:
        print("🔥 Terminating Firefox...")
        try:
            firefox_process.terminate()
            firefox_process.wait(timeout=5)
        except Exception as e:
            print(f"⚠️ Failed to terminate Firefox: {e}")
            try:
                firefox_process.kill()
            except:
                pass
    
    # Limpiar perfil temporal de Firefox
    if firefox_profile_dir and os.path.exists(firefox_profile_dir):
        try:
            import shutil
            shutil.rmtree(firefox_profile_dir)
            print(f"🗑️ Perfil Firefox eliminado: {firefox_profile_dir}")
        except Exception as e:
            print(f"⚠️ Error eliminando perfil Firefox: {e}")
    
    # Esperar a que termine el hilo de grabación
    if recording_thread and recording_thread.is_alive():
        print("🔥 Waiting for recording thread to finish...")
        recording_thread.join(timeout=10)
    
    # Esperar a que termine el hilo de control de ads
    if ad_control_thread and ad_control_thread.is_alive():
        print("🔥 Waiting for ad control thread to finish...")
        ad_control_thread.join(timeout=5)
    
    # Descargar módulo PulseAudio
    if module_id:
        print(f"🎧 Unloading PulseAudio module: {module_id}")
        try:
            subprocess.run(["pactl", "unload-module", module_id], check=True)
        except Exception as e:
            print(f"⚠️ Failed to unload PulseAudio module: {e}")
    
    print("✅ Cleanup complete. Exiting.")


def signal_handler(sig, frame):
    """Handler para señales de sistema."""
    cleanup()
    sys.exit(0)


def create_pulse_sink():
    """Crea un sink PulseAudio único - siguiendo patrón Go."""
    global sink_name, module_id
    
    # Generar nombre único
    sink_name = f"simple-audio-{random.randint(10000, 99999)}"
    print(f"🎧 Creating PulseAudio sink: {sink_name}")
    
    try:
        # Crear sink
        result = subprocess.run([
            "pactl", "load-module", "module-null-sink", 
            f"sink_name={sink_name}"
        ], capture_output=True, text=True, check=True)
        
        module_id = result.stdout.strip()
        print(f"✅ PulseAudio sink created with module ID: {module_id}")
        
        # Esperar inicialización como en Go
        print("⏳ Waiting for PulseAudio sink to initialize...")
        time.sleep(2)
        
        return sink_name
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create PulseAudio sink: {e}")
        print("Make sure PulseAudio is running.")
        return None


def create_firefox_profile_with_autoplay():
    """Crea un perfil temporal de Firefox con autoplay habilitado."""
    import tempfile
    global firefox_profile_dir
    
    # Crear directorio temporal para el perfil
    firefox_profile_dir = tempfile.mkdtemp(prefix="firefox-autoplay-")
    
    # Crear archivo de preferencias
    prefs_js = os.path.join(firefox_profile_dir, "prefs.js")
    
    preferences = [
        '// Configuración optimizada para autoplay y captura de audio',
        'user_pref("media.autoplay.default", 0);',  # 0 = permitir autoplay
        'user_pref("media.autoplay.blocking_policy", 0);',  # No bloquear autoplay
        'user_pref("media.volume_scale", "1.0");',  # Volumen máximo
        'user_pref("dom.webnotifications.enabled", false);',  # Sin notificaciones
        'user_pref("app.update.enabled", false);',  # Sin actualizaciones
        'user_pref("browser.startup.homepage_override.mstone", "ignore");',  # Sin página de bienvenida
        'user_pref("toolkit.startup.max_resumed_crashes", -1);',  # No mostrar recuperación
        'user_pref("media.navigator.permission.disabled", true);',  # Sin permisos de medios
        'user_pref("media.gmp-gmpopenh264.enabled", true);',  # Habilitar H264
    ]
    
    try:
        with open(prefs_js, 'w', encoding='utf-8') as f:
            f.write('\n'.join(preferences))
        print(f"📁 Perfil Firefox creado: {firefox_profile_dir}")
        return firefox_profile_dir
    except Exception as e:
        print(f"❌ Error creando perfil: {e}")
        return None


def launch_firefox(url, sink_name):
    """Lanza Firefox con el sink preconfigurado y autoplay habilitado."""
    global firefox_process
    
    print(f"🚀 Launching Firefox with URL: {url}")
    
    # Crear perfil con autoplay habilitado
    profile_dir = create_firefox_profile_with_autoplay()
    if not profile_dir:
        print("⚠️ Usando perfil por defecto (sin autoplay optimizado)")
        profile_args = []
    else:
        profile_args = ["--profile", profile_dir]
    
    # Configurar variables de entorno como en Go
    env = os.environ.copy()
    env["PULSE_SINK"] = sink_name
    
    try:
        # Lanzar Firefox con sink preconfigurado y perfil optimizado
        cmd = ["firefox", "--new-instance", "--new-window"] + profile_args + [url]
        
        firefox_process = subprocess.Popen(cmd, env=env)
        
        print("✅ Firefox launched with preconfigured audio sink and autoplay")
        return True
        
    except Exception as e:
        print(f"❌ Failed to start Firefox: {e}")
        return False


def setup_selenium_driver(url):
    """Configura Selenium driver para control de ads."""
    global selenium_driver
    
    if not SELENIUM_AVAILABLE:
        print("⚠️ Selenium no disponible - omitiendo control de ads")
        return None
    
    try:
        print("🎯 Configurando Selenium para control de ads...")
        
        # Configurar opciones de Firefox para Selenium
        firefox_options = Options()
        firefox_options.add_argument("--width=1280")
        firefox_options.add_argument("--height=720")
        
        # Configurar preferencias para autoplay y audio
        firefox_options.set_preference("media.autoplay.default", 0)  # 0 = permitir autoplay
        firefox_options.set_preference("media.autoplay.blocking_policy", 0)  # No bloquear autoplay
        firefox_options.set_preference("media.volume_scale", "1.0")  # Volumen máximo
        firefox_options.set_preference("dom.webnotifications.enabled", False)  # Sin notificaciones
        firefox_options.set_preference("media.navigator.permission.disabled", True)  # Sin permisos de medios
        
        # Inicializar driver
        selenium_driver = webdriver.Firefox(options=firefox_options)
        
        print("🌐 Abriendo URL con Selenium...")
        selenium_driver.get(url)
        
        print("✅ Selenium driver configurado exitosamente")
        return selenium_driver
        
    except Exception as e:
        print(f"❌ Error configurando Selenium: {e}")
        print("🔄 Continuando sin control automático de ads...")
        return None


def skip_ads(driver):
    """Intenta saltar ads de YouTube."""
    if not driver:
        return False
    
    ad_selectors = [
        "button[aria-label*='Skip']",
        "button[aria-label*='Omitir']", 
        ".ytp-ad-skip-button",
        ".ytp-skip-ad-button",
        "button[class*='skip']",
        ".ytp-ad-skip-button-modern",
        ".videoAdUiSkipButton"
    ]
    
    try:
        for selector in ad_selectors:
            try:
                skip_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for button in skip_buttons:
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        print("✅ Ad skipped")
                        return True
            except:
                continue
        return False
        
    except Exception as e:
        print(f"⚠️ Error buscando ads: {e}")
        return False


def ad_control_worker(driver):
    """Hilo worker para control de ads - intensivo al inicio, esporádico después."""
    print("🎯 Iniciando control automático de ads...")
    
    # Fase 1: Control intensivo primeros 60 segundos
    print("🚀 Fase intensiva: buscando ads cada 5 segundos...")
    start_time = time.time()
    intensive_duration = 60  # 60 segundos
    
    while not stop_event.is_set() and (time.time() - start_time) < intensive_duration:
        if skip_ads(driver):
            print("🎯 Ad detectado y saltado en fase intensiva")
        time.sleep(5)
    
    # Fase 2: Control esporádico cada 2 minutos
    print("⏱️ Cambiando a fase esporádica: verificación cada 2 minutos...")
    
    while not stop_event.is_set():
        time.sleep(60)  # Cada 2 minutos
        if skip_ads(driver):
            print("🎯 Ad detectado y saltado en fase esporádica")
    
    print("🛑 Control de ads terminado")


def start_ad_control(url):
    """Inicia el sistema de control de ads con Selenium."""
    global ad_control_thread
    
    # Configurar Selenium driver
    driver = setup_selenium_driver(url)
    if not driver:
        return False
    
    # Iniciar hilo de control de ads
    ad_control_thread = threading.Thread(
        target=ad_control_worker, 
        args=(driver,), 
        daemon=True
    )
    ad_control_thread.start()
    
    print("✅ Sistema de control de ads iniciado")
    return True


def record_audio(pulse_device, segment_time = 5):
    """Graba un stream continuo dividido automáticamente en múltiples archivos usando ffmpeg segment."""
    print(f"🎵 Starting continuous audio recording with {segment_time}s segments")

    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Template para nombres de archivo - %03d será reemplazado por 001, 002, 003, etc.
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_template = os.path.join(output_dir, f"audio_chunk_{timestamp}_%03d.wav")
        
        print(f"🎵 Recording continuous stream to: {output_template}")
        
        # Comando ffmpeg para stream continuo con segmentación automática
        cmd = [
            "ffmpeg",
            "-y",  # Sobrescribir si existe
            "-f", "pulse",
            "-i", pulse_device,
            "-acodec", "pcm_s16le",
            "-ar", "48000",
            "-ac", "1",
            "-f", "segment",
            "-segment_time", str(segment_time),  # Duración de cada segmento
            "-reset_timestamps", "1",  # Resetear timestamps en cada segmento
            "-segment_format", "wav",  # Formato de cada segmento
            "-loglevel", "error",  # Solo mostrar errores
            output_template
        ]
        
        print(f"🚀 Starting continuous recording...")
        
        # Ejecutar ffmpeg en modo continuo (no esperar a que termine)
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
        
        # Monitorear el proceso en un hilo separado
        def monitor_ffmpeg():
            while not stop_event.is_set() and process.poll() is None:
                time.sleep(1)
                
                # Buscar archivos nuevos y enviarlos por RTP
                try:
                    for filename in os.listdir(output_dir):
                        if filename.startswith(f"audio_chunk_{timestamp}") and filename.endswith(".wav"):
                            file_path = os.path.join(output_dir, filename)
                            # Solo procesar archivos que no estén siendo escritos
                            if os.path.getsize(file_path) > 1000:
                                try:
                                    send_pcm_to_server(file_path)
                                    print(f"📡 Enviado por RTP: {filename}")
                                except Exception as rtp_error:
                                    print(f"⚠️ Error enviando {filename}: {rtp_error}")
                except Exception as e:
                    print(f"⚠️ Error monitoreando archivos: {e}")
        
        # Iniciar monitoreo en hilo separado
        monitor_thread = threading.Thread(target=monitor_ffmpeg, daemon=True)
        monitor_thread.start()
        
        # Esperar hasta que se detenga
        while not stop_event.is_set():
            if process.poll() is not None:
                print("⚠️ FFmpeg process terminated unexpectedly")
                break
            time.sleep(1)
        
        # Terminar proceso FFmpeg si sigue ejecutándose
        if process.poll() is None:
            print("🛑 Stopping FFmpeg...")
            process.terminate()
            process.wait(timeout=5)
            
    except Exception as e:
        print(f"❌ Error in continuous recording: {e}")


def start_audio_recording(pulse_device):
    """Inicia el hilo de grabación de audio."""
    global recording_thread
    
    pulse_device_monitor = f"{pulse_device}.monitor"
    print(f"🎤 Starting audio capture from PulseAudio source: {pulse_device_monitor}")
    
    recording_thread = threading.Thread(
        target=record_audio, 
        args=(pulse_device_monitor,), 
        daemon=True
    )
    recording_thread.start()
    return recording_thread


def main():
    """Función principal siguiendo exactamente el patrón del script Go."""
    
    # 1. Validar argumentos de línea de comandos
    """if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <URL>")
        print(f"\nExample: {sys.argv[0]} 'https://www.youtube.com/@todonoticias/live'")
        sys.exit(1)
    
    url = sys.argv[1]"""
    url = "https://www.youtube.com/@todonoticias/live"

    global id_instance, output_dir
    id_instance = random.randint(1000, 100000)
    output_dir = f"records-{id_instance}"

    # Configurar señales para cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 2. Crear sink PulseAudio único
    sink_name = create_pulse_sink()
    if not sink_name:
        sys.exit(1)
    
    # 3. Lanzar Firefox con sink preconfigurado
    if not launch_firefox(url, sink_name):
        cleanup()
        sys.exit(1)
    
    # 3.5. Esperar un poco para que Firefox inicie y luego configurar control de ads
    print("⏳ Esperando que Firefox se inicie completamente...")
    time.sleep(5)
    
    # Iniciar control de ads con Selenium (opcional)
    print("🎯 Iniciando sistema de control de ads...")
    if start_ad_control(url):
        print("✅ Control de ads configurado")
    else:
        print("⚠️ Continuando sin control automático de ads")
    
    # 4. Iniciar captura y grabación de audio
    start_audio_recording(sink_name)
    
    print("🎯 System initialized successfully!")
    print("🎵 Recording 15-second audio chunks to 'records/' directory")
    print("Press Ctrl+C to stop...")
    
    # 5. Esperar señal de shutdown
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    cleanup()


if __name__ == "__main__":
    main()
