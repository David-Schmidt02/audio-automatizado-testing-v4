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

def move_firefox_audio_to_sink(pid, sink_name):
    """Mueve el audio del proceso de Firefox a un sink específico."""
    if pid is None:
        log("PID no disponible, no se puede mover el audio", "ERROR")
        return False
    try:
        # Aquí usas pactl para mover el stream al sink
        subprocess.run(["pactl", "move-sink-input", str(pid), sink_name], check=True)
        log(f"Audio del PID {pid} movido a sink '{sink_name}'", "SUCCESS")
        return True
    except Exception as e:
        log(f"Error moviendo audio al sink: {e}", "ERROR")
        return False

def load_video_and_configure(driver, video_url):
    """Navega a la URL, salta anuncios y ejecuta configuración JS."""
    log(f"Navegando a: {video_url}")
    driver.get(video_url)

    skip_ads(driver, timeout=60) # Se saltan las publicidades, si las hubiera
    try:
        script_js = obtener_path_js('live_stream_video.js')
        driver.execute_script(script_js)
        log("JavaScript de configuración ejecutado", "SUCCESS")
    except Exception as e:
        log(f"Error ejecutando JavaScript: {e}", "ERROR")

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