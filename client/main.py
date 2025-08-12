"""
Sistema de audio automatizado v2.0 - Arquitectura de Managers
Captura audio de YouTube live streams usando Firefox/Selenium y lo graba en WAV.
"""

import os
import sys
import signal
import time
import threading

# Importaciones de managers
from pulse_audio_manager import PulseAudioManager
from firefox_manager import FirefoxManager
from recording_manager import RecordingManager
from youtube_js_utils import YouTubeJSUtils

from logger_client import log

# Event para controlar hilos
stop_event = threading.Event()

# Managers globales
pulse_manager = None
firefox_manager = None
recording_manager = None

def monitor_javascript_health(driver, interval=30):
    """Monitorea la salud del JavaScript periódicamente usando YouTubeJSUtils."""
    if not driver:
        return

    def check_js_health():
        while not stop_event.is_set():
            try:
                # Usar YouTubeJSUtils para verificación
                state = YouTubeJSUtils.get_player_state(driver)
                if state and state.get('hasVideo') and not state.get('videoPaused'):
                    log("JavaScript health check: OK", "DEBUG")
                else:
                    log("JavaScript health check: PROBLEMA DETECTADO", "WARN")
                    log(f"Estado: {state}", "DEBUG")
                    # Reactivar usando YouTubeJSUtils
                    YouTubeJSUtils.play_video(driver)
                    YouTubeJSUtils.configure_audio(driver, muted=False, volume=1.0)
            except Exception as e:
                log(f"Error en health check: {e}", "ERROR")
                break

            time.sleep(interval)

    health_thread = threading.Thread(target=check_js_health, daemon=True)
    health_thread.start()
    return health_thread

def monitor_youtube_activity(driver):
    """Hilo que mantiene YouTube activo continuamente."""
    while not stop_event.is_set():
        time.sleep(15)  # Cada 15 segundos
        YouTubeJSUtils.keep_youtube_active(driver)

def cleanup():
    global pulse_manager, firefox_manager, recording_manager, stop_event
    
    print("\\n🛑 Limpiando recursos...")
    
    # Señalar a todos los hilos que deben parar
    stop_event.set()
    
    # Limpiar managers en orden inverso
    try:
        if recording_manager:
            recording_manager.cleanup()
            print("✅ RecordingManager limpiado")
    except Exception as e:
        print(f"Error limpiando RecordingManager: {e}")
    
    try:
        if firefox_manager:
            firefox_manager.cleanup()
            print("✅ FirefoxManager limpiado")
    except Exception as e:
        print(f"Error limpiando FirefoxManager: {e}")
    
    try:
        if pulse_manager:
            pulse_manager.cleanup()
            print("✅ PulseAudioManager limpiado")
    except Exception as e:
        print(f"Error limpiando PulseAudioManager: {e}")

    print("✅ Limpieza completa.")

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

def main():
    global pulse_manager, firefox_manager, recording_manager, stop_event

    """
    Función principal refactorizada usando la arquitectura de managers.
    """
    
    if len(sys.argv) != 2:
        print(f"Uso: {sys.argv[0]} <URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    log("🚀 Iniciando sistema de audio automatizado v2.0", "INFO")
    log("📦 Arquitectura de Managers activada", "INFO")

    # Inicializar el evento de parada
    stop_event.clear()

    # Configurar handlers de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 1. INICIALIZAR PULSE AUDIO MANAGER
        log("🔊 Inicializando PulseAudioManager...", "INFO")
        pulse_manager = PulseAudioManager()
        
        # Crear sink de audio
        sink_name, module_id = pulse_manager.create_null_sink()
        if not sink_name:
            log("❌ Error: No se pudo crear sink de audio", "ERROR")
            return False
        
        log(f"✅ Sink de audio creado: {sink_name}", "SUCCESS")
        time.sleep(2)  # Esperar inicialización

        # 2. INICIALIZAR FIREFOX MANAGER
        log("🦊 Inicializando FirefoxManager...", "INFO")
        firefox_manager = FirefoxManager(pulse_manager)
        
        # Lanzar Firefox y configurar YouTube + Audio
        if firefox_manager.launch_and_configure(url, sink_name):
            log("✅ Firefox y YouTube configurados exitosamente", "SUCCESS")
        else:
            log("❌ Error configurando Firefox/YouTube", "ERROR")
            return False

        # Obtener driver para monitoreo
        driver = firefox_manager.get_driver()
        if not driver:
            log("❌ Error: No se pudo obtener driver de Firefox", "ERROR")
            return False

        # 3. INICIALIZAR RECORDING MANAGER
        log("🎵 Inicializando RecordingManager...", "INFO")
        pulse_device = pulse_manager.pulse_device
        recording_manager = RecordingManager(pulse_device)
        
        # Iniciar grabación WAV cada 15 segundos
        if recording_manager.start_wav_recording(interval=15):
            log("✅ Grabación WAV iniciada (cada 15 segundos)", "SUCCESS")
        else:
            log("❌ Error iniciando grabación WAV", "ERROR")

        # 4. INICIAR MONITOREO
        log("👁️ Iniciando sistemas de monitoreo...", "INFO")
        
        # Monitoreo de JavaScript
        monitor_javascript_health(driver, interval=15)
        
        # Monitoreo de actividad de YouTube
        monitor_thread = threading.Thread(target=monitor_youtube_activity, args=(driver,), daemon=True)
        monitor_thread.start()
        log("✅ Monitoreo de actividad YouTube iniciado", "SUCCESS")

        # 5. VERIFICACIONES FINALES
        log("🔍 Realizando verificaciones finales...", "INFO")
        
        # Verificar captura de audio
        if pulse_manager.verify_audio_capture(sink_name):
            log("✅ Audio capture verificado correctamente", "SUCCESS")
        else:
            log("⚠️ Advertencia: No se pudo verificar la captura de audio", "WARN")
        
        # Verificar que hay streams activos
        if pulse_manager.verify_sink_has_audio(sink_name):
            log("✅ Sink tiene streams activos", "SUCCESS")
        else:
            log("⚠️ Advertencia: Sink sin streams activos detectados", "WARN")

        # 6. SISTEMA LISTO
        log("🎉 ¡Sistema completamente configurado y operativo!", "SUCCESS")
        log("📁 Grabando archivos WAV cada 15 segundos en carpeta 'records'", "INFO")
        log("🔴 Presiona Ctrl+C para detener el sistema", "INFO")
        
        # Mostrar estado de managers
        log("📊 Estado de Managers:", "INFO")
        log(f"  PulseAudio: {pulse_manager.get_sink_info()}", "DEBUG")
        log(f"  Firefox: {firefox_manager.get_status()}", "DEBUG")
        log(f"  Recording: {recording_manager.get_status()}", "DEBUG")

        # Esperar señales (bucle principal)
        signal.pause()

    except KeyboardInterrupt:
        log("⏹️ Interrupción por usuario detectada", "INFO")
        cleanup()
    except Exception as e:
        log(f"❌ Error inesperado: {e}", "ERROR")
        cleanup()
        return False

    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
