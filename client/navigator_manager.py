import subprocess
import os
import random
import sys
import tempfile
import psutil

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

from my_logger import log_and_save
from flags_nav_ffmpeg.flags_comunes import CHROME_CHROMIUM_COMMON_FLAGS, GRAPHICS_MIN_FLAGS, PRODUCTION_FLAGS

class Navigator():
    def __init__(self, name, sink_name, headless, ssrc):
        self.navigator_name = name
        self.profile_path = None
        self.sink_name = sink_name
        self.headless = headless
        self.ssrc = ssrc

        self.browser_process = None
        self.navigator_profile_dir = None

        self.random_id = random.randint(10000, 99999)


    def create_navigator_profile(self):
        """Crea un directorio de perfil para el navegador."""
        if self.navigator_name == "Chrome" or self.navigator_name == "Chromium":
            return self.create_chrome_chromium_profile()
        log_and_save("❌ Navegador no soportado", "ERROR", self.ssrc)
        return None

    def create_chrome_chromium_profile(self):
        """Crea un directorio de perfil para Chrome y Chromium."""
        log_and_save(f"🛠️ Creating profile for {self.navigator_name}", "INFO", self.ssrc)
        base_dir = os.path.expanduser("~/.config/")
        os.makedirs(base_dir, exist_ok=True)
        # Nombre único para el perfil
        if self.navigator_name == "Chrome":
            profile_name = f"chrome-autoplay-{self.random_id}"
        else:
            profile_name = f"chrome-chromium-autoplay-{self.random_id}"
        self.navigator_profile_dir = os.path.join(base_dir, profile_name)
        os.makedirs(self.navigator_profile_dir, exist_ok=True)
        return self.navigator_profile_dir


    def launch_navigator(self, url, display_num):
        """Lanza el navegador especificado con el sink preconfigurado y perfil ya creado."""
        log_and_save(f"🚀 Launching {self.navigator_name} with URL: {url}", "INFO", self.ssrc)

        # Variables de entorno
        env = os.environ.copy()
        env["PULSE_SINK"] = self.sink_name
        if display_num:
            env["DISPLAY"] = display_num
        try:
            if self.navigator_name == "Chrome" or self.navigator_name == "Chromium":
                self.browser_process = self.launch_chrome_chromium(url, env)
            log_and_save(f"✅ {self.navigator_name} launched with preconfigured audio sink and autoplay", "INFO", self.ssrc)
            return self.browser_process
        except Exception as e:
            log_and_save(f"❌ Error lanzando {self.navigator_name}: {e}", "ERROR", self.ssrc)
            return None

    def launch_chrome_chromium(self, url, env):
        """Lanza Google Chrome o Chromium en modo headless usando el perfil creado y el display indicado, con afinidad/prioridad si es Linux."""
        from flags_nav_ffmpeg.flags_comunes import CPU_FLAGS
        import platform
        profile_args = [f"--user-data-dir={self.navigator_profile_dir}"]
        navigator_name = self.navigator_name.lower()
        if navigator_name == "chrome":
            base_cmd = ["google-chrome"]
        else:
            base_cmd = ["chromium"]
        cmd = (
            base_cmd
            + CHROME_CHROMIUM_COMMON_FLAGS
            + GRAPHICS_MIN_FLAGS
            + PRODUCTION_FLAGS
            + profile_args
            + [url]
            )

        """if self.headless:
            cmd.insert(1, "--headless")"""
        
        return subprocess.Popen(cmd, env=env)


    def terminate_child_processes(self, browser_process):
        if browser_process.poll() is None:  # el padre sigue vivo
            try:
                parent = psutil.Process(browser_process.pid)
                children = parent.children(recursive=True)
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                return

            if not children:
                log_and_save("No child processes found to terminate.", "WARN", self.ssrc)
                return

            for child in children:
                log_and_save(f"⚠️ Killing child process {child.pid}", "WARN", self.ssrc)
                try:
                    child.terminate()
                except Exception:
                    pass

            gone, alive = psutil.wait_procs(children, timeout=3)
            for p in alive:
                log_and_save(f"⚠️ Forcibly killing child process {p.pid}", "WARN", self.ssrc)
                try:
                    p.kill()
                except Exception:
                    pass
        else:
            log_and_save("No child processes to terminate.", "INFO", self.ssrc)

    def cerrar_navegador(self):
        """Cierra el proceso de navegador (Chrome/Chromium/Firefox) y sus hijos si están en ejecución."""
        if hasattr(self, 'browser_process') and self.browser_process:
            log_and_save("🔥 Terminating navegador...", "WARN", self.ssrc)
            log_and_save(f"Proceso de navegador: {self.browser_process.pid}", "INFO", self.ssrc)

            try:
                # 1. primero los hijos
                self.terminate_child_processes(self.browser_process)

                # 2. ahora el padre
                self.browser_process.terminate()
                try:
                    self.browser_process.communicate(timeout=5)
                except Exception:
                    pass

            except Exception as e:
                log_and_save(f"⚠️ Failed to terminate navegador: {e}", "ERROR", self.ssrc)
                try:
                    self.browser_process.kill()
                except Exception:
                    pass
    
    def limpiar_perfil_navegador(self):
        log_and_save("🔥 Cleaning up navegador profile...", "WARN", self.ssrc)
        if self.navigator_profile_dir and os.path.exists(self.navigator_profile_dir):
            try:
                import shutil
                shutil.rmtree(self.navigator_profile_dir)
                log_and_save(f"🗑️ Perfil Navegador eliminado: {self.navigator_profile_dir}", "SUCCESS", self.ssrc)
            except Exception as e:
                log_and_save(f"⚠️ Error eliminando perfil Navegador: {e}", "ERROR", self.ssrc)

    def cleanup(self):
        """Limpia los recursos utilizados por el administrador del navegador."""
        self.cerrar_navegador()
        self.limpiar_perfil_navegador()
