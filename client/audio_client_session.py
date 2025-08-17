
import os
import random
import subprocess
import sys
import tempfile
import threading
import time

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

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

from my_logger import log
from config import BUFFER_SIZE


class AudioClientSession:
    def __init__(self, id_instance):
        self.sink_name = None
        self.module_id = None
        self.firefox_process = None
        self.recording_thread = None
        self.selenium_driver = None
        self.ad_control_thread = None
        self.firefox_profile_dir = None
        self.id_instance = id_instance
        self.output_dir = None
        self.options = None
        self.service = None
        self.ad_control_thread = None
        self.stop_event = threading.Event()

    def create_pulse_sink(self):
        """Crea un sink de audio único."""
        self.sink_name = f"audio-sink-{random.randint(10000, 99999)}"
        log(f"🎧 Creating audio sink: {self.sink_name}", "INFO")

        try:
            result = subprocess.run([
                "pactl", "load-module", "module-null-sink",
                f"sink_name={self.sink_name}"
            ], capture_output=True, text=True, check=True)

            self.module_id = result.stdout.strip()
            log(f"✅ Audio sink created with module ID: {self.module_id}", "INFO")

            return self.sink_name

        except subprocess.CalledProcessError as e:
            log(f"❌ Failed to create audio sink: {e}", "ERROR")
            return None

    def create_firefox_profile(self):
        """Crea un directorio temporal para el perfil de Firefox."""
        self.firefox_profile_dir = tempfile.mkdtemp(prefix="firefox-autoplay-")
        log(f"📁 Perfil Firefox creado: {self.firefox_profile_dir}", "INFO")
        return self.firefox_profile_dir

    def create_firefox_options(self):
        """Crea las opciones de Firefox para Selenium."""
        options = Options()
        options.add_argument("--width=1280")
        options.add_argument("--height=720")
        options.set_preference("media.autoplay.default", 0)  # 0 = permitir autoplay
        options.set_preference("media.autoplay.blocking_policy", 0)  # No bloquear autoplay
        options.set_preference("media.volume_scale", "1.0")  # Volumen máximo
        options.set_preference("dom.webnotifications.enabled", False)  # Sin notificaciones
        options.set_preference("media.navigator.permission.disabled", True)  # Sin permisos de medios

        return options

    def launch_firefox(self, url):
        """Lanza Firefox con el sink preconfigurado y perfil ya creado -> Desde Selenium."""
    
        log(f"🚀 Launching Firefox with URL: {url}", "INFO")

        # Configurar las opciones
        self.options = self.create_firefox_options()

        # Configurar variables de entorno
        env = os.environ.copy()
        env["PULSE_SINK"] = self.sink_name

        try:
            # Definir servicio con entorno modificado
            self.service = Service(
                executable_path="/usr/bin/geckodriver",
                env=env
            )

            # Lanzar Firefox controlado por Selenium
            selenium_driver = self.create_selenium_driver()
            log("🌐 Abriendo URL con Selenium...", "INFO")
            selenium_driver.get(url)

            log("✅ Firefox launched with preconfigured audio sink and Selenium", "INFO")
            return True

        except Exception as e:
            log(f"❌ Failed to start Firefox: {e}", "ERROR")
            return False

    def create_selenium_driver(self):
        """Configura Selenium driver para controlar Firefox."""
        
        if not SELENIUM_AVAILABLE:
            log("⚠️ Selenium no disponible - omitiendo control de ads", "WARNING")
            return None
        
        try:
            # Inicializar driver
            log("🌐 Iniciando Selenium WebDriver con Firefox...", "INFO")
            selenium_driver = webdriver.Firefox(service=self.service, options=self.options)

            log("✅ Selenium driver configurado exitosamente", "INFO")
            return selenium_driver
            
        except Exception as e:
            log(f"❌ Error configurando Selenium: {e}", "ERROR")
            log("🔄 Continuando sin control automático de ads...", "WARNING")
            return None
    
    def skip_ads(self):
        """Intenta saltar ads de YouTube."""
        
        ad_selectors = [
            "button[aria-label*='Skip']",
            "button[aria-label*='Omitir']", 
            ".ytp-ad-skip-button",
            ".ytp-skip-ad-button",
            "button[class*='skip']",
            ".ytp-ad-skip-button-modern",
            ".videoAdUiSkipButton"
        ]
        
        for selector in ad_selectors:
            try:
                skip_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for button in skip_buttons:
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        print("✅ Ad skipped")
                        return True
            except:
                continue
        return False


    def ads_control_worker(self):
        """Hilo worker para control de ads - intensivo al inicio, esporádico después."""
        log("🎯 Iniciando control automático de ads...", "INFO")
        
        # Fase 1: Control intensivo primeros 60 segundos
        log("🚀 Fase intensiva: buscando ads cada 5 segundos...", "INFO")
        start_time = time.time()
        intensive_duration = 60  # 60 segundos

        while not self.stop_event.is_set() and (time.time() - start_time) < intensive_duration:
            if self.skip_ads():
                log("🎯 Ad detectado y saltado en fase intensiva", "INFO")
            time.sleep(5)
        
        # Fase 2: Control esporádico cada 2 minutos
        log("⏱️ Cambiando a fase esporádica: verificación cada 2 minutos...", "INFO")

        while not self.stop_event.is_set():
            time.sleep(60)  # Cada 2 minutos
            if self.skip_ads():
                log("🎯 Ad detectado y saltado en fase esporádica", "INFO")

        log("🛑 Control de ads terminado", "INFO")

    def start_thread_ads_control(self):
        """Inicia el sistema de control de ads con Selenium usando perfil existente."""
        
        # Iniciar hilo de control de ads
        self.ad_control_thread = threading.Thread(
            target=self.ads_control_worker,
            args=(self.selenium_driver,),
            daemon=True
        )
        self.ad_control_thread.start()

        print("✅ Sistema de control de ads iniciado")
        return True

    def cleanup(self):
        """Limpieza de recursos al finalizar - siguiendo patrón Go."""
        global output_dir

        log("\n🛑 Received shutdown signal. Cleaning up...", "WARNING")

        # Señalar a todos los hilos que paren
        self.stop_event.set()

        # Cerrar Selenium driver y Firefox
        if self.selenium_driver:
            log("🔥 Closing Selenium driver and Firefox...", "INFO")
            try:
                self.selenium_driver.quit()
            except Exception as e:
                log(f"⚠️ Error closing: {e}", "ERROR")

        # Limpiar perfil temporal de Firefox
        if self.firefox_profile_dir and os.path.exists(self.firefox_profile_dir):
            try:
                import shutil
                shutil.rmtree(self.firefox_profile_dir)
                log(f"🗑️ Perfil Firefox eliminado: {self.firefox_profile_dir}", "INFO")
            except Exception as e:
                log(f"⚠️ Error eliminando perfil Firefox: {e}", "ERROR")

        # Esperar a que termine el hilo de grabación
        if self.recording_thread and self.recording_thread.is_alive():
            log("🔥 Waiting for recording thread to finish...", "INFO")
            self.recording_thread.join(timeout=10)

        # Esperar a que termine el hilo de control de ads
        if self.ad_control_thread and self.ad_control_thread.is_alive():
            log("🔥 Waiting for ad control thread to finish...", "INFO")
            self.ad_control_thread.join(timeout=5)

        # Descargar módulo PulseAudio
        if self.module_id:
            log(f"🎧 Unloading PulseAudio module: {self.module_id}", "INFO")
            try:
                subprocess.run(["pactl", "unload-module", self.module_id], check=True)
            except Exception as e:
                log(f"⚠️ Failed to unload PulseAudio module: {e}", "ERROR")

        log("✅ Cleanup complete. Exiting.", "INFO")


    # Puedes agregar métodos para inicializar cada recurso, lanzar Firefox, etc.