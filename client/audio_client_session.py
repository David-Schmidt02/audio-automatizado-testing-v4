
import os
import random
import subprocess
import sys
import tempfile
import threading
import time

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

from my_logger import log
from config import BUFFER_SIZE


class AudioClientSession:
    def __init__(self, id_instance):
        self.sink_name = None
        self.module_id = None
        self.navegador_process = None
        self.recording_thread = None

        self.navegador_profile_dir = None
        self.id_instance = id_instance
        self.output_dir = None
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

    def create_firefox_profile_for_snap(self):
        """Crea un directorio de perfil de Firefox en ~/snap/firefox/common/."""
        base_dir = os.path.expanduser("~/snap/firefox/common/.mozilla/firefox/")
        os.makedirs(base_dir, exist_ok=True)
        # Nombre único para el perfil
        profile_name = f"firefox-autoplay-{random.randint(10000, 99999)}"
        self.firefox_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.firefox_profile_dir, exist_ok=True)

    def create_firefox_profile_for_classic(self):
        """Crea un directorio de perfil de Firefox en ~/.mozilla/firefox/."""
        base_dir = os.path.expanduser("~/.mozilla/firefox/")
        os.makedirs(base_dir, exist_ok=True)
        # Nombre único para el perfil
        profile_name = f"firefox-autoplay-{random.randint(10000, 99999)}"
        self.firefox_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.firefox_profile_dir, exist_ok=True)

    def create_firefox_profile(self):
        """Crea un directorio temporal para el perfil de Firefox."""
        # self.create_firefox_profile_for_classic() -> Se debe desinstalar la version snap e instalar la classic
        self.create_firefox_profile_for_snap()
        prefs_js = os.path.join(self.firefox_profile_dir, "prefs.js")
        
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
            log(f"📁 Perfil Firefox creado: {self.navegador_profile_dir}", "INFO")
            return self.navegador_profile_dir
        except Exception as e:
            self.navegador_profile_dir = None
            log(f"❌ Error creando perfil: {e}", "ERROR")
            return None

    def launch_firefox(self, url, display_num):
        """Lanza Firefox con el sink preconfigurado y perfil ya creado."""

        log(f"🚀 Launching Firefox with URL: {url}", "INFO")

        # Usar el perfil recibido como parámetro (creado en main)
        if not self.navegador_profile_dir:
            log("⚠️ Usando perfil por defecto (sin autoplay optimizado)", "WARNING")
            profile_args = []
        else:
            profile_args = ["--profile", self.navegador_profile_dir]
        
        # Configurar variables de entorno
        env = os.environ.copy()
        env["PULSE_SINK"] = self.sink_name
        env["DISPLAY"] = display_num

        try:
            # Lanzar Firefox con sink preconfigurado y perfil optimizado
            cmd = ["firefox", "--headless", "--new-instance", "--new-window"] + profile_args + [url]

            self.navegador_process = subprocess.Popen(cmd, env=env)

            log("✅ Firefox launched with preconfigured audio sink and autoplay", "INFO")
            return True
            
        except Exception as e:
            log(f"❌ Failed to start Firefox: {e}", "ERROR")
            return False

    def create_chrome_profile(self):
        """Crea un directorio de perfil de Chrome en ~/.config/chromium-browser/ con nombre único."""
        base_dir = os.path.expanduser("~/.config/chromium-browser/")
        os.makedirs(base_dir, exist_ok=True)
        profile_name = f"chrome-profile-{random.randint(10000, 99999)}"
        self.chrome_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.chrome_profile_dir, exist_ok=True)
        log(f"📁 Perfil Chrome creado: {self.chrome_profile_dir}", "INFO")
        return self.chrome_profile_dir

    def launch_chrome(self, url, display):
        """Lanza Google Chrome en modo headless usando el perfil creado y el display indicado."""
        log(f"🚀 Launching Chrome with URL: {url}", "INFO")
        if not hasattr(self, 'chrome_profile_dir') or not self.chrome_profile_dir:
            log("⚠️ Usando perfil por defecto de Chrome", "WARNING")
            profile_args = []
        else:
            profile_args = [f"--user-data-dir={self.chrome_profile_dir}"]

        env = os.environ.copy()
        env["PULSE_SINK"] = self.sink_name
        env["DISPLAY"] = display

        cmd = [
            "google-chrome", "--headless", "--no-sandbox", "--disable-gpu",
            "--window-size=1920,1080",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--mute-audio",
            "--disable-extensions"
        ] + profile_args + [url]

        try:
            self.browser_process = subprocess.Popen(cmd, env=env)
            log("✅ Chrome launched with preconfigured audio sink and headless mode", "INFO")
            return True
        except Exception as e:
            log(f"❌ Failed to start Chrome: {e}", "ERROR")
            return False

    def cerrar_navegador(self):
        """Cierra el proceso de navegador (Chrome/Chromium/Firefox) si está en ejecución."""
        if hasattr(self, 'browser_process') and self.browser_process:
            log("🔥 Terminating navegador...", "INFO")
            try:
                self.browser_process.terminate()
                try:
                    self.browser_process.communicate(timeout=5)
                except Exception:
                    pass
            except Exception as e:
                log(f"⚠️ Failed to terminate navegador: {e}", "ERROR")
                try:
                    self.browser_process.kill()
                except Exception:
                    pass
        
    def limpiar_perfil_navegador(self):
        if self.navegador_profile_dir and os.path.exists(self.navegador_profile_dir):
            try:
                import shutil
                shutil.rmtree(self.navegador_profile_dir)
                log(f"🗑️ Perfil Navegador eliminado: {self.navegador_profile_dir}", "INFO")
            except Exception as e:
                log(f"⚠️ Error eliminando perfil Navegador: {e}", "ERROR")

    def cleanup(self):
        """Limpieza de recursos al finalizar."""
        global output_dir

        log("\n🛑 Received shutdown signal. Cleaning up...", "WARNING")

        # Señalar a todos los hilos que paren
        self.stop_event.set()

        # Cerrar Navegador
        self.cerrar_navegador()

        # Limpiar perfil temporal de Navegador
        self.limpiar_perfil_navegador()

        # Esperar a que termine el hilo de grabación
        if self.recording_thread and self.recording_thread.is_alive():
            log("🔥 Waiting for recording thread to finish...", "INFO")
            self.recording_thread.join(timeout=10)

        # Descargar módulo PulseAudio
        if self.module_id:
            log(f"🎧 Unloading PulseAudio module: {self.module_id}", "INFO")
            try:
                subprocess.run(["pactl", "unload-module", self.module_id], check=True)
            except Exception as e:
                log(f"⚠️ Failed to unload PulseAudio module: {e}", "ERROR")

        log("✅ Cleanup complete. Exiting.", "INFO")

