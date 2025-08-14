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

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log

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
    log("⚠️ Selenium no disponible - sin control de ads automático", "WARNING")

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

    log("\n🛑 Received shutdown signal. Cleaning up...", "WARNING")

    # Señalar a todos los hilos que paren
    stop_event.set()
    
    # Cerrar Selenium driver
    if selenium_driver:
        log("🔥 Closing Selenium driver...", "INFO")
        try:
            selenium_driver.quit()
        except Exception as e:
            log(f"⚠️ Error closing Selenium: {e}", "ERROR")

    # Terminar Firefox
    if firefox_process:
        log("🔥 Terminating Firefox...", "INFO")
        try:
            firefox_process.terminate()
            firefox_process.wait(timeout=5)
        except Exception as e:
            log(f"⚠️ Failed to terminate Firefox: {e}", "ERROR")
            try:
                firefox_process.kill()
            except:
                pass
    
    # Limpiar perfil temporal de Firefox
    if firefox_profile_dir and os.path.exists(firefox_profile_dir):
        try:
            import shutil
            shutil.rmtree(firefox_profile_dir)
            log(f"🗑️ Perfil Firefox eliminado: {firefox_profile_dir}", "INFO")
        except Exception as e:
            log(f"⚠️ Error eliminando perfil Firefox: {e}", "ERROR")

    # Esperar a que termine el hilo de grabación
    if recording_thread and recording_thread.is_alive():
        log("🔥 Waiting for recording thread to finish...", "INFO")
        recording_thread.join(timeout=10)
    
    # Esperar a que termine el hilo de control de ads
    if ad_control_thread and ad_control_thread.is_alive():
        log("🔥 Waiting for ad control thread to finish...", "INFO")
        ad_control_thread.join(timeout=5)
    
    # Descargar módulo PulseAudio
    if module_id:
        log(f"🎧 Unloading PulseAudio module: {module_id}", "INFO")
        try:
            subprocess.run(["pactl", "unload-module", module_id], check=True)
        except Exception as e:
            log(f"⚠️ Failed to unload PulseAudio module: {e}", "ERROR")

    log("✅ Cleanup complete. Exiting.", "INFO")


def signal_handler(sig, frame):
    """Handler para señales de sistema."""
    cleanup()
    sys.exit(0)


def create_pulse_sink():
    """Crea un sink PulseAudio único - siguiendo patrón Go."""
    global sink_name, module_id
    
    # Generar nombre único
    sink_name = f"simple-audio-{random.randint(10000, 99999)}"
    log(f"🎧 Creating PulseAudio sink: {sink_name}", "INFO")

    try:
        # Crear sink
        result = subprocess.run([
            "pactl", "load-module", "module-null-sink", 
            f"sink_name={sink_name}"
        ], capture_output=True, text=True, check=True)
        
        module_id = result.stdout.strip()
        log(f"✅ PulseAudio sink created with module ID: {module_id}", "INFO")

        # Esperar inicialización como en Go
        log("⏳ Waiting for PulseAudio sink to initialize...", "INFO")
        time.sleep(2)
        
        return sink_name
        
    except subprocess.CalledProcessError as e:
        log(f"❌ Failed to create PulseAudio sink: {e}", "ERROR")
        log("Make sure PulseAudio is running.", "ERROR")
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
        log(f"📁 Perfil Firefox creado: {firefox_profile_dir}", "INFO")
        return firefox_profile_dir
    except Exception as e:
        log(f"❌ Error creando perfil: {e}", "ERROR")
        return None


def launch_firefox(url, sink_name, profile_dir=None):
    """Lanza Firefox con el sink preconfigurado y perfil ya creado."""
    global firefox_process

    log(f"🚀 Launching Firefox with URL: {url}", "INFO")

    # Usar el perfil recibido como parámetro (creado en main)
    if not profile_dir:
        log("⚠️ Usando perfil por defecto (sin autoplay optimizado)", "WARNING")
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

        log("✅ Firefox launched with preconfigured audio sink and autoplay", "INFO")
        return True
        
    except Exception as e:
        log(f"❌ Failed to start Firefox: {e}", "ERROR")
        return False


def setup_selenium_driver(url, profile_dir=None):
    """Configura Selenium driver para control de ads usando perfil existente."""
    global selenium_driver
    
    if not SELENIUM_AVAILABLE:
        log("⚠️ Selenium no disponible - omitiendo control de ads", "WARNING")
        return None
    
    try:
        log("🎯 Configurando Selenium para control de ads...", "INFO")

        # Configurar opciones de Firefox para Selenium
        firefox_options = Options()
        firefox_options.add_argument("--width=1280")
        firefox_options.add_argument("--height=720")
        
        # Si hay un perfil, usarlo (evita crear nueva ventana)
        if profile_dir:
            firefox_options.add_argument(f"--profile={profile_dir}")
        
        # Configurar preferencias para autoplay y audio
        firefox_options.set_preference("media.autoplay.default", 0)  # 0 = permitir autoplay
        firefox_options.set_preference("media.autoplay.blocking_policy", 0)  # No bloquear autoplay
        firefox_options.set_preference("media.volume_scale", "1.0")  # Volumen máximo
        firefox_options.set_preference("dom.webnotifications.enabled", False)  # Sin notificaciones
        firefox_options.set_preference("media.navigator.permission.disabled", True)  # Sin permisos de medios
        
        # Inicializar driver
        selenium_driver = webdriver.Firefox(options=firefox_options)

        log("🌐 Abriendo URL con Selenium...", "INFO")
        selenium_driver.get(url)

        log("✅ Selenium driver configurado exitosamente", "INFO")
        return selenium_driver
        
    except Exception as e:
        log(f"❌ Error configurando Selenium: {e}", "ERROR")
        log("🔄 Continuando sin control automático de ads...", "WARNING")
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
    log("🎯 Iniciando control automático de ads...", "INFO")
    
    # Fase 1: Control intensivo primeros 60 segundos
    log("🚀 Fase intensiva: buscando ads cada 5 segundos...", "INFO")
    start_time = time.time()
    intensive_duration = 60  # 60 segundos
    
    while not stop_event.is_set() and (time.time() - start_time) < intensive_duration:
        if skip_ads(driver):
            log("🎯 Ad detectado y saltado en fase intensiva", "INFO")
        time.sleep(5)
    
    # Fase 2: Control esporádico cada 2 minutos
    log("⏱️ Cambiando a fase esporádica: verificación cada 2 minutos...", "INFO")

    while not stop_event.is_set():
        time.sleep(60)  # Cada 2 minutos
        if skip_ads(driver):
            log("🎯 Ad detectado y saltado en fase esporádica", "INFO")

    log("🛑 Control de ads terminado", "INFO")


def start_ad_control(url, profile_dir=None):
    """Inicia el sistema de control de ads con Selenium usando perfil existente."""
    global ad_control_thread
    
    # Configurar Selenium driver con el mismo perfil
    driver = setup_selenium_driver(url, profile_dir)
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
            "-f", "wav",      # O el formato que acepte tu servidor
            "-loglevel", "error",
            "pipe:1"
        ]

        log(f"🚀 Starting ffmpeg streaming...", "INFO")

        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as process:
            while not stop_event.is_set():
                data = process.stdout.read(4096)
                if not data:
                    break
                try:
                    send_pcm_to_server(data, id_instance) 
                except Exception as e:
                    log(f"⚠️ Error enviando audio: {e}", "ERROR")
                    break

            if process.poll() is None:
                log("🛑 Stopping FFmpeg...", "INFO")
                process.terminate()
                process.wait(timeout=5)

    except Exception as e:
        log(f"❌ Error in continuous streaming: {e}", "ERROR")



def start_audio_recording(pulse_device):
    """Inicia el hilo de grabación de audio."""
    global recording_thread
    
    pulse_device_monitor = f"{pulse_device}.monitor"
    log(f"🎤 Starting audio capture from PulseAudio source: {pulse_device_monitor}", "INFO")

    recording_thread = threading.Thread(
        target=record_audio, 
        args=(pulse_device_monitor,), 
        daemon=True
    )
    recording_thread.start()
    return recording_thread


def main():
    """Función principal."""
    
    # 1. Validar argumentos de línea de comandos
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <URL>")
        print(f"\nExample: {sys.argv[0]} 'https://www.youtube.com/@todonoticias/live'")
        sys.exit(1)
    
    url = sys.argv[1]

    global id_instance, output_dir, firefox_profile_dir
    id_instance = random.randint(1000, 100000)
    output_dir = f"records-{id_instance}"

    # Configurar señales para cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 2. Crear sink PulseAudio único
    sink_name = create_pulse_sink()
    if not sink_name:
        sys.exit(1)
    
    # 3. Crear perfil de Firefox con autoplay habilitado (solo una vez)
    firefox_profile_dir = create_firefox_profile_with_autoplay()
    if not firefox_profile_dir:
        log("⚠️ Usando perfil por defecto (sin autoplay optimizado)", "WARNING")
    
    # 4. Lanzar Firefox con sink preconfigurado y perfil optimizado
    if not launch_firefox(url, sink_name, firefox_profile_dir):
        cleanup()
        sys.exit(1)
    
    # 5. Esperar un poco para que Firefox inicie y luego configurar control de ads
    print("⏳ Esperando que Firefox se inicie completamente...")
    time.sleep(5)
    
    # 6. Iniciar control de ads con Selenium usando el mismo perfil
    print("🎯 Iniciando sistema de control de ads...")
    # TEMPORALMENTE DESHABILITADO - Selenium abre nueva ventana
    # if start_ad_control(url, firefox_profile_dir):
    #     print("✅ Control de ads configurado")
    # else:
    #     print("⚠️ Continuando sin control automático de ads")
    print("⚠️ Control automático de ads deshabilitado (para evitar segunda ventana)")
    
    # 7. Iniciar captura y grabación de audio
    start_audio_recording(sink_name)
    
    print("🎯 System initialized successfully!")
    print("🎵 Recording 15-second audio chunks to 'records/' directory")
    print("Press Ctrl+C to stop...")
    
    # 8. Esperar señal de shutdown
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    cleanup()


if __name__ == "__main__":
    main()
