import time
import os
import sys
import subprocess
import time
import re
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
    Crea un nuevo profile de selenium para firefox
    """
    profile_dir = os.path.expanduser("~/.mozilla/firefox/selenium-vm-profile" + f"-{identificador}")
    if os.path.exists(profile_dir):
        import shutil
        try:
            shutil.rmtree(profile_dir)
            log(f"Perfil antiguo eliminado: {profile_dir}", "INFO")
        except Exception as e:
            log(f"Error eliminando perfil antiguo: {e}", "ERROR")
    os.makedirs(profile_dir, exist_ok=True)
    prefs_file = os.path.join(profile_dir, "prefs.js")
    prefs_content = '''// Configuraciones automáticas para Selenium en VM con GUI
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
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.allow-muted", true);
user_pref("media.block-autoplay-until-in-foreground", false);
user_pref("dom.webdriver.enabled", false);
user_pref("useAutomationExtension", false);
user_pref("browser.tabs.remote.autostart", false);
user_pref("browser.tabs.remote.autostart.2", false);
user_pref("layers.acceleration.disabled", true);
user_pref("dom.webnotifications.enabled", false);
user_pref("dom.push.enabled", false);
user_pref("general.useragent.override", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0");
'''
    with open(prefs_file, 'w') as f:
        f.write(prefs_content)
    log("Perfil nuevo creado y listo para usar", "SUCCESS")
    return profile_dir

def verificar_estado_javascript(driver):
    """Verifica si los scripts JavaScript están funcionando correctamente"""
    try:
        # Verificar el estado del video y los event listeners
        estado = driver.execute_script("""
            var video = document.querySelector('video');
            if (!video) return {error: 'No video element found'};
            
            // Verificar propiedades del video
            var videoState = {
                exists: true,
                muted: video.muted,
                volume: video.volume,
                paused: video.paused,
                ended: video.ended,
                duration: video.duration,
                currentTime: video.currentTime,
                isLive: video.duration === Infinity || isNaN(video.duration),
                readyState: video.readyState
            };
            
            // Verificar si nuestros event listeners están activos
            var hasCustomPause = video.pause !== HTMLVideoElement.prototype.pause;
            videoState.customPauseActive = hasCustomPause;
            
            // Verificar eventos de visibilidad
            var hasVisibilityListener = document.hasOwnProperty('visibilityListeners');
            videoState.visibilityListenerActive = hasVisibilityListener;
            
            return videoState;
        """)
        
        if 'error' in estado:
            log(f"Error en verificación JS: {estado['error']}", "ERROR")
            return False
            
        log(f"Estado del video: Muted={estado.get('muted')}, Volume={estado.get('volume')}, Paused={estado.get('paused')}, Live={estado.get('isLive')}", "INFO")
        log(f"Custom pause interceptor activo: {estado.get('customPauseActive')}", "DEBUG")
        
        return True
        
    except Exception as e:
        log(f"Error verificando JavaScript: {e}", "ERROR")
        return False

def obtener_path_js(path_script):
    js_path = os.path.join(os.path.dirname(__file__), path_script)
    with open(js_path, 'r', encoding='utf-8') as js_file:
            script_js = js_file.read()
    return script_js
   
def configuracion_firefox(firefox_options):
    # Configuracion esencial de autplay para videos
    firefox_options.set_preference("media.autoplay.default", 0)  # 0 = Allow autoplay
    firefox_options.set_preference("media.autoplay.allow-muted", True)
    firefox_options.set_preference("media.block-autoplay-until-in-foreground", False)
    
    # Deshabilitar notificaciones que puedan interrumpir
    firefox_options.set_preference("dom.webnotifications.enabled", False)
    firefox_options.set_preference("dom.push.enabled", False)

    # Fuerza a Firefox a utilizar PulseAudio
    firefox_options.set_preference("media.cubeb.backend", "pulse")
    
    # Configurar User-Agent de Ubuntu Firefox real
    firefox_options.set_preference("general.useragent.override", 
                                 "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0")
    
    # Configuraciones anti-detección mínimas
    firefox_options.set_preference("dom.webdriver.enabled", False) # Ya no se le indica a los navegadores el webdriver de selenium
    
    # Para VM: desactivar algunas optimizaciones que pueden causar problemas
    firefox_options.set_preference("browser.tabs.remote.autostart", False)
    firefox_options.set_preference("browser.tabs.remote.autostart.2", False)

    return firefox_options

def found_sinks(output, firefox_pid):
    # Buscar sink-inputs de Firefox y comparar con el sink deseado
    firefox_sink_inputs = []
    current_input = None
    current_sink = None
    current_pid = None
    in_properties = False
    
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Sink Input #"):
            current_input = line.split("#")[1].strip()
            current_sink = None
            current_pid = None
            in_properties = False
        elif line.startswith("Sink:"):
            # Extraer nombre del sink actual: Sink: rtp-stream-12345
            current_sink = line.split(":")[1].strip()
        elif line.startswith("Properties:"):
            in_properties = True
        elif in_properties and current_input and "application.process.id" in line:
            # Extraer PID: application.process.id = "12345"
            try:
                pid_str = line.split("=")[1].strip().strip('"')
                current_pid = int(pid_str)
            except:
                current_pid = None
        elif in_properties and current_input and "application.name" in line and "Firefox" in line:
            # Verificar si es nuestro proceso de Firefox específico
            if current_pid == firefox_pid:
                firefox_sink_inputs.append({
                    'input_id': current_input,
                    'current_sink': current_sink,
                    'pid': current_pid
                })
                log(f"Firefox PID {current_pid}: Sink-input {current_input} en sink '{current_sink}'", "INFO")
            elif current_pid is None:
                # Fallback: si no podemos obtener PID, incluir todos los Firefox
                firefox_sink_inputs.append({
                    'input_id': current_input,
                    'current_sink': current_sink,
                    'pid': 'unknown'
                })
                log(f"Firefox (PID desconocido): Sink-input {current_input} en sink '{current_sink}'", "INFO")
    return firefox_sink_inputs

def move_audio_to_sink(driver, sink_name):
    log(f"Moviendo streams de audio de esta instancia Firefox al sink: {sink_name}", "INFO")
    
    # Obtener el PID del proceso de Firefox específico
    try:
        firefox_pid = driver.service.process.pid
        log(f"PID de Firefox de este cliente: {firefox_pid}", "INFO")
    except Exception as e:
        log(f"Error obteniendo PID de Firefox: {e}", "ERROR")
        return driver
    
    # Listar los sink-inputs actuales
    try:
        output = subprocess.check_output(["pactl", "list", "sink-inputs"], text=True)
        
        if not output.strip():
            log("No hay streams de audio activos en este momento", "WARN")
            return driver
            
        log("Buscando streams de audio de Firefox...", "INFO")
        firefox_sink_inputs = found_sinks(output, firefox_pid)
        
        if not firefox_sink_inputs:
            log(f"No se encontraron streams para Firefox PID {firefox_pid}", "WARN")
            log("Esto es normal si el video aún no ha iniciado audio", "INFO")
            return driver
        
        # Mover cada stream encontrado al sink deseado
        for sink_info in firefox_sink_inputs:
            input_id = sink_info['input_id']
            current_sink = sink_info['current_sink']
            
            if current_sink == sink_name:
                log(f"Stream {input_id} ya está en el sink correcto '{sink_name}'", "SUCCESS")
            else:
                log(f"Moviendo stream {input_id} de '{current_sink}' a '{sink_name}'", "INFO")
                try:
                    subprocess.run(["pactl", "move-sink-input", input_id, sink_name], check=True)
                    log(f"Stream {input_id} movido exitosamente a '{sink_name}'", "SUCCESS")
                except Exception as e:
                    log(f"Error moviendo stream {input_id}: {e}", "ERROR")
                    
    except Exception as e:
        log(f"Error listando sink-inputs: {e}", "ERROR")
    
    return driver

def open_firefox_and_play_video(firefox_options, video_url, sink_name, service):
    log("Iniciando Firefox con Selenium para LIVE STREAM...")
    log("VERSIÓN DE start_firefox.py: v2.0 - Con verificación de JavaScript", "DEBUG")
    driver = webdriver.Firefox(service=service, options=firefox_options)

    # Ejecutar script para ocultar mejor que somos un bot
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    log(f"Navegando a live stream: {video_url}")
    driver.get(video_url)

    skip_ads(driver, timeout=60)

    log("Configurando live stream para grabación continua en Firefox...")
    try:
        script_js = obtener_path_js('live_stream_video.js')
        log(f"JavaScript cargado: {len(script_js)} caracteres", "DEBUG")
        
        # Ejecutar el script y verificar si se ejecutó correctamente
        result = driver.execute_script(script_js)
        log("Script JavaScript ejecutado exitosamente", "SUCCESS")
        
        # Verificar que el video existe y está configurado
        video_check = driver.execute_script("""
            var video = document.querySelector('video');
            if (video) {
                return {
                    found: true,
                    muted: video.muted,
                    volume: video.volume,
                    paused: video.paused,
                    duration: video.duration,
                    currentTime: video.currentTime
                };
            }
            return {found: false};
        """)
        
        if video_check and video_check.get('found'):
            log(f"Video encontrado y configurado: muted={video_check.get('muted')}, volume={video_check.get('volume')}, paused={video_check.get('paused')}", "SUCCESS")
        else:
            log("Advertencia: No se encontró elemento video en la página", "WARN")
            
    except Exception as e:
        log(f"Error ejecutando JavaScript: {e}", "ERROR")
    
    # Esperar un poco para que el video inicie y genere audio
    log("Esperando que el video inicie reproducción de audio...", "INFO")
    time.sleep(5)
    
    # Verificar que el JavaScript está funcionando
    if verificar_estado_javascript(driver):
        log("JavaScript funcionando correctamente", "SUCCESS")
    else:
        log("Problema con JavaScript, reintentando configuración...", "WARN")
        try:
            # Reintentar la ejecución del script
            script_js = obtener_path_js('live_stream_video.js')
            driver.execute_script(script_js)
            time.sleep(2)
            verificar_estado_javascript(driver)
        except Exception as e:
            log(f"Error en reintento de JavaScript: {e}", "ERROR")
    
    # Ahora mover el audio específico de esta instancia al sink
    driver = move_audio_to_sink(driver, sink_name)

    log("Firefox iniciado y live stream configurado", "SUCCESS")
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