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


def cleanup():
    """Limpieza de recursos al finalizar - siguiendo patrón Go."""
    global sink_name, module_id, firefox_process, recording_thread, selenium_driver, ad_control_thread
    
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


def launch_firefox(url, sink_name):
    """Lanza Firefox con el sink preconfigurado - siguiendo patrón Go."""
    global firefox_process
    
    print(f"🚀 Launching Firefox with URL: {url}")
    
    # Configurar variables de entorno como en Go
    env = os.environ.copy()
    env["PULSE_SINK"] = sink_name
    
    try:
        # Lanzar Firefox con sink preconfigurado
        firefox_process = subprocess.Popen([
            "firefox",
            "--new-instance", 
            "--new-window",
            url
        ], env=env)
        
        print("✅ Firefox launched with preconfigured audio sink")
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
        firefox_options.add_argument("--autoplay")  # Habilitar autoplay
        
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


def record_audio_chunks(pulse_device, interval=15, output_dir="records"):
    """Graba chunks de audio de duración específica usando ffmpeg."""
    print(f"🎵 Starting audio recording: {interval}s chunks in '{output_dir}' directory")
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    chunk_number = 1
    
    while not stop_event.is_set():
        try:
            # Crear nombre de archivo con timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"audio_chunk_{timestamp}_{chunk_number:03d}.wav"
            full_path = os.path.join(output_dir, output_file)
            
            print(f"🎵 Recording: {output_file}")
            
            # Comando ffmpeg para grabar exactamente el intervalo especificado
            cmd = [
                "ffmpeg",
                "-y",  # Sobrescribir archivo si existe
                "-f", "pulse",
                "-i", pulse_device,
                "-t", str(interval),  # Duración
                "-acodec", "pcm_s16le",
                "-ar", "48000",
                "-ac", "1",
                "-loglevel", "error",  # Solo mostrar errores
                full_path
            ]
            
            # Ejecutar ffmpeg y esperar a que termine
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Verificar que el archivo se creó y tiene contenido
                if os.path.exists(full_path) and os.path.getsize(full_path) > 1000:
                    print(f"✅ Recording completed: {output_file}")
                else:
                    print(f"⚠️ File created but very small: {output_file}")
            else:
                print(f"❌ FFmpeg error: {result.stderr.strip()}")
            
            chunk_number += 1
            
        except Exception as e:
            print(f"❌ Error recording audio: {e}")
            if not stop_event.is_set():
                time.sleep(5)  # Esperar antes de reintentar


def start_audio_recording(pulse_device):
    """Inicia el hilo de grabación de audio."""
    global recording_thread
    
    pulse_device_monitor = f"{pulse_device}.monitor"
    print(f"🎤 Starting audio capture from PulseAudio source: {pulse_device_monitor}")
    
    recording_thread = threading.Thread(
        target=record_audio_chunks, 
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
