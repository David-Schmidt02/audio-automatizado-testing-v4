import subprocess
import os
import random
import sys
import tempfile
import psutil

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

from my_logger import log

class Navigator():
    def __init__(self, name, sink_name, headless):
        self.navigator_name = name
        self.profile_path = None
        self.sink_name = sink_name
        self.headless = headless

        self.browser_process = None
        self.navigator_profile_dir = None

        self.random_id = random.randint(10000, 99999)

    def create_navigator_profile(self):
        """Crea un directorio de perfil para el navegador."""
        if self.navigator_name == "Firefox":
            return self.create_firefox_profile()
        elif self.navigator_name == "Chrome":
            return self.create_chrome_profile()
        elif self.navigator_name == "Chromium":
            return self.create_chromium_profile()
        else:
            log("❌ Navegador no soportado", "ERROR")
            return None

    def create_firefox_profile(self):
        """Crea un directorio temporal para el perfil de Firefox."""
        # Recordemos que no sirve de mucho ejecutar firefox en modo headless porque igual se procesa la visualización
        # self.create_firefox_profile_for_classic() -> Se debe desinstalar la version snap e instalar la classic
        # self.create_firefox_profile_for_snap() -> Trabaja sobre snap la version por defecto
        self.create_firefox_profile_for_classic()
        prefs_js = os.path.join(self.navigator_profile_dir, "prefs.js")
        
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
            log(f"📁 Perfil Firefox creado: {self.navigator_profile_dir}", "INFO")
            return self.navigator_profile_dir
        except Exception as e:
            self.navigator_profile_dir = None
            log(f"❌ Error creando perfil: {e}", "ERROR")
            return None
        
    def create_firefox_profile_for_snap(self):
        """Crea un directorio de perfil de Firefox en ~/snap/firefox/common/."""
        base_dir = os.path.expanduser("~/snap/firefox/common/.mozilla/firefox/")
        os.makedirs(base_dir, exist_ok=True)
        # Nombre único para el perfil
        profile_name = f"firefox-autoplay-{self.random_id}"
        self.navigator_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.navigator_profile_dir, exist_ok=True)

    def create_firefox_profile_for_classic(self):
        """Crea un directorio de perfil de Firefox en ~/.mozilla/firefox/."""
        base_dir = os.path.expanduser("~/.mozilla/firefox/")
        os.makedirs(base_dir, exist_ok=True)
        # Nombre único para el perfil
        profile_name = f"firefox-autoplay-{self.random_id}"
        self.navigator_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.navigator_profile_dir, exist_ok=True)

    def create_chrome_profile(self):
        """Crea un directorio de perfil de Google Chrome en ~/.config/google-chrome/ con nombre único."""
        base_dir = os.path.expanduser("~/.config/google-chrome/")
        os.makedirs(base_dir, exist_ok=True)
        profile_name = f"chrome-profile-{self.random_id}"
        self.navigator_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.navigator_profile_dir, exist_ok=True)
        log(f"📁 Perfil Chrome creado: {self.navigator_profile_dir}", "INFO")
        return self.navigator_profile_dir

    def create_chromium_profile(self):
        """Crea un directorio de perfil para Chromium en ~/.config/chromium/ con nombre único."""
        base_dir = os.path.expanduser("~/.config/chromium/")
        os.makedirs(base_dir, exist_ok=True)
        profile_name = f"chromium-profile-{self.random_id}"
        self.navigator_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.navigator_profile_dir, exist_ok=True)
        log(f"📁 Perfil de Chromium creado: {self.navigator_profile_dir}", "INFO")
        return self.navigator_profile_dir

    def launch_navigator(self, url, display_num):
        """Lanza el navegador especificado con el sink preconfigurado y perfil ya creado."""
        log(f"🚀 Launching {self.navigator_name} with URL: {url}", "INFO")

        # Variables de entorno
        env = os.environ.copy()
        env["PULSE_SINK"] = self.sink_name
        if display_num:
            env["DISPLAY"] = display_num
        try:
            if self.navigator_name == "Firefox":
                self.browser_process = self.launch_firefox(url, env)
            elif self.navigator_name == "Chrome":
                self.browser_process = self.launch_chrome(url, env)
            elif self.navigator_name == "Chromium":
                self.browser_process = self.launch_chromium(url, env)
            log(f"✅ {self.navigator_name} launched with preconfigured audio sink and autoplay", "INFO")
            return self.browser_process
        except Exception as e:
            log(f"❌ Error lanzando {self.navigator_name}: {e}", "ERROR")
            return None

    def launch_firefox(self, url, env):
        """Lanza Firefox con el sink preconfigurado y perfil ya creado."""
        profile_args = ["--profile", self.navigator_profile_dir]
        # Lanzar Firefox con sink preconfigurado y perfil optimizado
        cmd = ["firefox", "--new-instance", "--new-window"] + profile_args + [url]
        if self.headless:
            cmd.insert(1, "--headless")
        return subprocess.Popen(cmd, env=env)

    def launch_chrome(self, url, env):
        """Lanza Google Chrome en modo headless usando el perfil creado y el display indicado."""
        profile_args = [f"--user-data-dir={self.navigator_profile_dir}"]
        cmd = [
                "google-chrome", 
                #"--disable-gpu",  # Si hay problemas con la GPU
                "--window-size=1920,1080",
                "--incognito",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=ChromeWhatsNewUI,Translate,BackgroundNetworking",
                "--disable-sync",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-translate", 
                "--disable-infobars",
                "--disable-signin-promo",
                "--disable-software-rasterizer",  # Mejor que --enable-unsafe-swiftshader
                "--disable-dev-shm-usage",  # Útil en entornos limitados (Docker/Linux)
            ] + profile_args + [url]
        if self.headless:
            cmd.insert(1, "--headless")
        return subprocess.Popen(cmd, env=env)

    def launch_chromium(self, url, env):
        """Lanza Chromium en modo headless usando el perfil creado y el display indicado."""
        profile_args = [f"--user-data-dir={self.navigator_profile_dir}"]
        cmd = [ "chromium",
                #"--disable-gpu",  # No hace falta con la aceleración 3D desactivada
                "--window-size=1920,1080",
                "--incognito",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=ChromeWhatsNewUI,Translate,BackgroundNetworking,Sync",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-translate", 
                "--disable-infobars",
                "--disable-signin-promo",
                "--disable-accelerated-video-decode",  # Desactiva render de video
                "--blink-settings=videoDisabled=true",  # Otra forma de desactivar video
                "--disable-dev-shm-usage",  # Útil en entornos limitados (VM/Linux)
                "--single-process",  # Reduce cantidad de procesos renderer
                #"--no-zygote",       # Evita procesos zombie
                #"--no-sandbox"
            ] + profile_args + [url]
        """
        if self.headless:
            cmd.insert(1, "--headless")"""
        return subprocess.Popen(cmd, env=env)


    def cerrar_navegador(self):
        """Cierra el proceso de navegador (Chrome/Chromium/Firefox) y sus hijos si están en ejecución."""
        if hasattr(self, 'browser_process') and self.browser_process:
            log("🔥 Terminating navegador...", "INFO")
            try:
                # Intentar terminar el proceso principal
                self.browser_process.terminate()
                try:
                    self.browser_process.communicate(timeout=5)
                except Exception:
                    pass
                # Intentar terminar procesos hijos si existen (requiere psutil)
                parent = psutil.Process(self.browser_process.pid)
                children = parent.children(recursive=True)
                if not children:
                    log("No child processes found to terminate.", "WARN")
                else:
                    try:
                        for child in children:
                            log(f"⚠️ Killing child process {child.pid}", "WARN")
                            try:
                                child.terminate()
                            except Exception:
                                pass
                        gone, alive = psutil.wait_procs(children, timeout=3)
                        for p in alive:
                            log(f"⚠️ Forcibly killing child process {p.pid}", "WARN")
                            try:
                                p.kill()
                            except Exception:
                                pass
                    except Exception as e:
                        log(f"⚠️ Error terminando procesos hijos: {e}", "ERROR")
            except Exception as e:
                log(f"⚠️ Failed to terminate navegador: {e}", "ERROR")
                try:
                    self.browser_process.kill()
                except Exception:
                    pass
        
    def limpiar_perfil_navegador(self):
        if self.navigator_profile_dir and os.path.exists(self.navigator_profile_dir):
            try:
                import shutil
                shutil.rmtree(self.navigator_profile_dir)
                log(f"🗑️ Perfil Navegador eliminado: {self.navigator_profile_dir}", "SUCCESS")
            except Exception as e:
                log(f"⚠️ Error eliminando perfil Navegador: {e}", "ERROR")

    def cleanup(self):
        """Limpia los recursos utilizados por el administrador del navegador."""
        self.cerrar_navegador()
        self.limpiar_perfil_navegador()
