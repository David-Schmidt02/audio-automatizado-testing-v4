import time
import os
import sys
import subprocess
import time
import re
import shutil
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_client import log
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile


def clean_and_create_selenium_profile(identificador):
    """
    Crea un perfil de Firefox limpio con configuraciones fijas.
    """
    profile_dir = os.path.expanduser(f"~/.mozilla/firefox/selenium-vm-profile-{identificador}")
    
    # Borrar perfil viejo si existe
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            log(f"Perfil antiguo eliminado: {profile_dir}", "INFO")
        except Exception as e:
            log(f"Error eliminando perfil antiguo: {e}", "ERROR")
    
    os.makedirs(profile_dir, exist_ok=True)
    
    prefs_file = os.path.join(profile_dir, "prefs.js")
    prefs_content = '''// Configuraciones fijas para Selenium
user_pref("browser.startup.homepage", "about:blank");
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("toolkit.startup.max_resumed_crashes", -1);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("app.update.enabled", false);
user_pref("app.update.auto", false);
user_pref("extensions.update.enabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("media.cubeb.backend", "pulse");
user_pref("dom.webdriver.enabled", false);
user_pref("useAutomationExtension", false);
user_pref("browser.tabs.remote.autostart", false);
user_pref("browser.tabs.remote.autostart.2", false);
user_pref("layers.acceleration.disabled", true);
user_pref("general.useragent.override", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0");
'''
    with open(prefs_file, 'w') as f:
        f.write(prefs_content)
    
    log("Perfil nuevo creado y listo para usar", "SUCCESS")
    log(f"🦊 Perfil temporal: {profile_dir}", "INFO")
    return profile_dir

def configuracion_firefox(options):
    """
    Configuraciones dinámicas o ajustables.
    """
    # Permitir autoplay de video/sonido
    options.set_preference("media.autoplay.default", 0)
    options.set_preference("media.autoplay.allow-muted", True)
    options.set_preference("media.block-autoplay-until-in-foreground", False)

    # Desactivar notificaciones
    options.set_preference("dom.webnotifications.enabled", False)
    options.set_preference("dom.push.enabled", False)

    return options

def obtener_path_js(path_script):
    js_path = os.path.join(os.path.dirname(__file__), path_script)
    with open(js_path, 'r', encoding='utf-8') as js_file:
            script_js = js_file.read()
    return script_js
   
def open_firefox_and_get_pid(firefox_options, service):
    """Inicia Firefox y retorna el driver + PID del proceso."""
    log("Iniciando Firefox con Selenium (solo arranque)...", "INFO")
    driver = webdriver.Firefox(service=service, options=firefox_options)
    # Obtener el PID principal de Firefox
    try:
        pid = driver.service.process.pid
        log(f"Firefox iniciado con PID: {pid}", "SUCCESS")
    except Exception as e:
        log(f"No se pudo obtener PID de Firefox: {e}", "ERROR")
        pid = None

    return driver, pid

def debug_audio_streams():
    """Función de debug para mostrar todos los streams de audio activos."""
    try:
        result = subprocess.run(["pactl", "list", "sink-inputs"], 
                              capture_output=True, text=True, check=True)
        
        log("=== DEBUG: Streams de audio activos ===", "DEBUG")
        log(result.stdout, "DEBUG")
        log("=== Fin DEBUG ===", "DEBUG")
        
        # También mostrar la versión corta
        short_result = subprocess.run(["pactl", "list", "short", "sink-inputs"], 
                                    capture_output=True, text=True, check=True)
        log("=== Streams cortos ===", "DEBUG")
        log(short_result.stdout, "DEBUG")
        
    except Exception as e:
        log(f"Error en debug de streams: {e}", "ERROR")

def find_firefox_streams_alternative(pid):
    """Método alternativo para encontrar streams de Firefox usando múltiples enfoques."""
    firefox_streams = []
    
    try:
        # Método 1: Buscar por PID en la información detallada
        result = subprocess.run(["pactl", "list", "sink-inputs"], 
                              capture_output=True, text=True, check=True)
        
        output = result.stdout
        
        # Buscar todos los Sink Input #
        import re
        stream_blocks = re.split(r'Sink Input #(\d+)', output)
        
        for i in range(1, len(stream_blocks), 2):
            stream_id = stream_blocks[i]
            stream_info = stream_blocks[i + 1]
            
            # Buscar el PID en múltiples formatos
            pid_patterns = [
                f'application.process.id = "{pid}"',
                f'application.process.id = {pid}',
                f'application.process.id="{pid}"',
                f'application.process.id={pid}'
            ]
            
            for pattern in pid_patterns:
                if pattern in stream_info:
                    log(f"Stream {stream_id} encontrado para PID {pid} (método PID)", "DEBUG")
                    firefox_streams.append(stream_id)
                    break
        
        # Método 2: Buscar por nombre de aplicación "Firefox"
        firefox_patterns = [
            'application.name = "Firefox"',
            'application.name = Firefox',
            'media.name = "Firefox"'
        ]
        
        for i in range(1, len(stream_blocks), 2):
            stream_id = stream_blocks[i]
            stream_info = stream_blocks[i + 1]
            
            if stream_id not in firefox_streams:  # No duplicar
                for pattern in firefox_patterns:
                    if pattern in stream_info:
                        log(f"Stream {stream_id} encontrado por nombre Firefox", "DEBUG")
                        firefox_streams.append(stream_id)
                        break
        
        return list(set(firefox_streams))  # Eliminar duplicados
        
    except Exception as e:
        log(f"Error en búsqueda alternativa de streams: {e}", "ERROR")
        return []

def move_firefox_audio_to_sink(pid, sink_name):
    """Mueve el audio del proceso de Firefox a un sink específico."""
    log(f"Intentando mover audio del PID {pid} al sink {sink_name}", "INFO")
    
    # Primero intentar método alternativo más robusto
    firefox_streams = find_firefox_streams_alternative(pid)
    
    if not firefox_streams:
        log(f"No se encontraron streams para PID {pid} con método alternativo", "WARN")
        return False
    
    moved_count = 0
    for stream_id in firefox_streams:
        try:
            log(f"Intentando mover stream {stream_id}...", "DEBUG")
            subprocess.run(["pactl", "move-sink-input", stream_id, sink_name], check=True)
            log(f"✅ Stream {stream_id} movido exitosamente a '{sink_name}'", "SUCCESS")
            moved_count += 1
        except subprocess.CalledProcessError as e:
            log(f"❌ Error moviendo stream {stream_id}: {e}", "ERROR")
            continue
    
    if moved_count > 0:
        log(f"🎵 Total streams movidos: {moved_count}/{len(firefox_streams)}", "SUCCESS")
        return True
    else:
        log("❌ No se pudo mover ningún stream", "ERROR")
        return False

def load_video_and_configure(driver, video_url):
    """Navega a la URL, salta anuncios y ejecuta configuración JS."""
    log(f"Navegando a: {video_url}")
    driver.get(video_url)

    skip_ads(driver, timeout=60) # Se saltan las publicidades, si las hubiera
    
    # Esperar un poco para que el video inicie
    log("Esperando que el video inicie reproducción...", "INFO")
    time.sleep(5)
    
    try:
        script_js = obtener_path_js('live_stream_video.js')
        driver.execute_script(script_js)
        log("JavaScript de configuración ejecutado", "SUCCESS")
    except Exception as e:
        log(f"Error ejecutando JavaScript: {e}", "ERROR")

    # Esperar un poco más para que se genere audio
    time.sleep(3)
    
    # Debug: mostrar streams disponibles
    debug_audio_streams()

    return driver

def skip_ads(driver, timeout=60):
    log("Intentando saltar anuncios (si aparecen)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Intentar varios selectores para botones de saltar anuncio
            skip_selectors = [
                ".ytp-ad-skip-button",
                ".ytp-skip-ad-button", 
                "[aria-label*='Skip']",
                "[aria-label*='Omitir']",
                ".skip-button",
                "#skip-button"
            ]
            
            for selector in skip_selectors:
                try:
                    skip_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    log("Botón 'Saltar anuncio' encontrado. Haciendo clic...", "SUCCESS")
                    skip_button.click()
                    time.sleep(2)
                    break
                except TimeoutException:
                    continue
            else:
                # Si no encontró ningún botón, salir del bucle principal
                break
                
        except TimeoutException:
            break
    log("Proceso de saltar anuncios finalizado", "SUCCESS")