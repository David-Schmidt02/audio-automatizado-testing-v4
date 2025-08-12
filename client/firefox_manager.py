"""
Manager para manejar todas las operaciones de Firefox y Selenium.
Incluye gestión de perfiles, configuración, lanzamiento y integración con audio.
"""

import os
import sys
import time
import random
import shutil
import subprocess

# Agregar el directorio padre al path para importar logger_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_client import log
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.common.by import By
from webdriver_manager.firefox import GeckoDriverManager
from youtube_js_utils import YouTubeJSUtils


class FirefoxManager:
    """Gestor completo de operaciones Firefox y Selenium."""
    
    def __init__(self, pulse_audio_manager=None):
        """
        Inicializa el manager de Firefox.
        
        Args:
            pulse_audio_manager: Instancia de PulseAudioManager para colaboración
        """
        self.pulse_audio_manager = pulse_audio_manager
        self.identificador = None
        self.profile_dir = None
        self.driver = None
        self.firefox_pid = None
        self.service = None
        
        # Configurar servicio de GeckoDriver
        try:
            self.service = Service(GeckoDriverManager().install())
            log("GeckoDriver configurado correctamente", "SUCCESS")
        except Exception as e:
            log(f"Error configurando GeckoDriver: {e}", "ERROR")
            self.service = None
        
        log("FirefoxManager inicializado", "SUCCESS")
    
    def set_pulse_audio_manager(self, pulse_audio_manager):
        """Establece el manager de PulseAudio para colaboración."""
        self.pulse_audio_manager = pulse_audio_manager
        log("PulseAudioManager configurado en FirefoxManager", "INFO")
    
    def create_selenium_profile(self, identificador=None):
        """
        Crea un perfil de Firefox limpio con configuraciones optimizadas.
        
        Args:
            identificador: ID único para el perfil (opcional)
            
        Returns:
            str: Ruta del directorio del perfil creado
        """
        if identificador is None:
            identificador = random.randint(0, 100000)
        
        self.identificador = identificador
        profile_dir = os.path.expanduser(f"~/.mozilla/firefox/selenium-vm-profile-{identificador}")
        
        log(f"Creando perfil de Firefox: {identificador}", "INFO")
        
        # Borrar perfil viejo si existe
        if os.path.exists(profile_dir):
            try:
                shutil.rmtree(profile_dir)
                log(f"Perfil antiguo eliminado: {profile_dir}", "INFO")
            except Exception as e:
                log(f"Error eliminando perfil antiguo: {e}", "ERROR")
        
        # Crear directorio del perfil
        os.makedirs(profile_dir, exist_ok=True)
        
        # Crear archivo de preferencias optimizado
        prefs_file = os.path.join(profile_dir, "prefs.js")
        prefs_content = '''// Configuraciones optimizadas para Selenium y audio
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

// Configuraciones de audio optimizadas
user_pref("media.cubeb.backend", "pulse");
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.allow-muted", true);
user_pref("media.block-autoplay-until-in-foreground", false);

// Configuraciones anti-detección
user_pref("dom.webdriver.enabled", false);
user_pref("useAutomationExtension", false);
user_pref("browser.tabs.remote.autostart", false);
user_pref("browser.tabs.remote.autostart.2", false);

// Optimizaciones de rendimiento
user_pref("layers.acceleration.disabled", true);
user_pref("dom.webnotifications.enabled", false);
user_pref("dom.push.enabled", false);

// User agent realista
user_pref("general.useragent.override", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0");
'''
        
        with open(prefs_file, 'w') as f:
            f.write(prefs_content)
        
        self.profile_dir = profile_dir
        log("✅ Perfil de Firefox creado exitosamente", "SUCCESS")
        log(f"🦊 Perfil ubicado en: {profile_dir}", "INFO")
        
        return profile_dir
    
    def configure_firefox_options(self, options=None):
        """
        Configura las opciones dinámicas de Firefox.
        
        Args:
            options: Opciones existentes (opcional, se crean nuevas si no se proporciona)
            
        Returns:
            Options: Opciones configuradas de Firefox
        """
        if options is None:
            options = Options()
        
        log("Configurando opciones dinámicas de Firefox...", "INFO")
        
        # Configuraciones de audio avanzadas
        options.set_preference("media.autoplay.default", 0)
        options.set_preference("media.autoplay.allow-muted", True)
        options.set_preference("media.block-autoplay-until-in-foreground", False)
        
        # Desactivar notificaciones y popups
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("dom.push.enabled", False)
        
        # Configuraciones adicionales para estabilidad
        options.set_preference("browser.cache.disk.enable", False)
        options.set_preference("browser.cache.memory.enable", False)
        options.set_preference("network.http.use-cache", False)
        
        log("✅ Opciones de Firefox configuradas", "SUCCESS")
        return options
    
    def start_firefox(self, options=None):
        """
        Inicia Firefox con las configuraciones establecidas.
        
        Args:
            options: Opciones de Firefox (opcional)
            
        Returns:
            tuple: (driver, pid) si éxito, (None, None) si error
        """
        if not self.service:
            log("Error: GeckoDriver no configurado", "ERROR")
            return None, None
        
        # Configurar opciones si no se proporcionaron
        if options is None:
            options = self.configure_firefox_options()
        
        # Configurar perfil si existe
        if self.profile_dir:
            profile = FirefoxProfile(profile_directory=self.profile_dir)
            options.profile = profile
            log(f"Perfil configurado: {self.profile_dir}", "INFO")
        
        log("🚀 Iniciando Firefox con Selenium...", "INFO")
        log("VERSIÓN DE FirefoxManager: v1.0 - Gestión completa", "DEBUG")
        
        try:
            # Iniciar Firefox
            driver = webdriver.Firefox(service=self.service, options=options)
            
            # Obtener PID del proceso Firefox
            try:
                pid = driver.service.process.pid
                log(f"✅ Firefox iniciado con PID: {pid}", "SUCCESS")
            except Exception as e:
                log(f"Warning: No se pudo obtener PID de Firefox: {e}", "WARN")
                pid = None
            
            # Guardar estado
            self.driver = driver
            self.firefox_pid = pid
            
            return driver, pid
            
        except Exception as e:
            log(f"❌ Error iniciando Firefox: {e}", "ERROR")
            return None, None
    
    def wait_for_audio_streams(self, max_wait_time=45, check_interval=3):
        """
        Espera hasta que Firefox genere streams de audio usando PulseAudioManager.
        
        Args:
            max_wait_time: Tiempo máximo de espera en segundos
            check_interval: Intervalo entre verificaciones
            
        Returns:
            list: Lista de streams encontrados
        """
        if not self.pulse_audio_manager:
            log("Error: No hay PulseAudioManager configurado", "ERROR")
            return []
        
        if not self.firefox_pid:
            log("Error: No hay PID de Firefox disponible", "ERROR")
            return []
        
        log(f"Esperando streams de audio para Firefox PID {self.firefox_pid}...", "INFO")
        
        # Usar el método del PulseAudioManager
        streams = self.pulse_audio_manager.wait_for_streams(
            self.firefox_pid, 
            max_wait_time=max_wait_time, 
            check_interval=check_interval
        )
        
        if streams:
            log(f"✅ Firefox generó {len(streams)} streams de audio", "SUCCESS")
        else:
            log("⚠️ Firefox no generó streams de audio en el tiempo esperado", "WARN")
        
        return streams
    
    def move_audio_to_sink(self, sink_name):
        """
        Mueve todo el audio de Firefox al sink especificado.
        
        Args:
            sink_name: Nombre del sink destino
            
        Returns:
            bool: True si se movió audio exitosamente
        """
        if not self.pulse_audio_manager:
            log("Error: No hay PulseAudioManager configurado", "ERROR")
            return False
        
        log(f"🎵 Iniciando redirección de audio de Firefox al sink '{sink_name}'", "INFO")
        
        # Esperar hasta que Firefox genere streams
        firefox_streams = self.wait_for_audio_streams(max_wait_time=45, check_interval=3)
        
        if not firefox_streams:
            log("❌ No se generaron streams de audio para Firefox", "ERROR")
            log("Posibles causas:", "INFO")
            log("  • El video no se está reproduciendo", "INFO")
            log("  • El audio está bloqueado en el navegador", "INFO")
            log("  • Hay problemas con la configuración de PulseAudio", "INFO")
            return False
        
        # Mover streams usando PulseAudioManager
        moved_count = self.pulse_audio_manager.move_streams_to_sink(firefox_streams, sink_name)
        
        if moved_count > 0:
            log(f"🎉 Audio de Firefox redirigido exitosamente ({moved_count} streams)", "SUCCESS")
            
            # Verificar que el sink está recibiendo audio
            time.sleep(2)  # Esperar estabilización
            if self.pulse_audio_manager.verify_sink_has_audio(sink_name):
                log(f"🔊 Confirmado: Sink '{sink_name}' recibiendo audio", "SUCCESS")
                return True
            else:
                log(f"⚠️ Warning: No se confirma audio en sink '{sink_name}'", "WARN")
                return True  # Aún considerarlo exitoso
        else:
            log("❌ No se pudo mover ningún stream de audio", "ERROR")
            return False
    
    def launch_and_configure(self, url, sink_name):
        """
        Función principal que orquesta todo el proceso de Firefox + YouTube + Audio.
        
        Args:
            url: URL del video de YouTube
            sink_name: Nombre del sink para redirigir audio
            
        Returns:
            bool: True si todo se configuró exitosamente
        """
        log("🚀 Iniciando proceso completo Firefox + YouTube + Audio", "INFO")
        
        try:
            # 1. Crear perfil de Firefox
            if not self.profile_dir:
                self.create_selenium_profile()
            
            # 2. Configurar y lanzar Firefox
            firefox_options = self.configure_firefox_options()
            driver, pid = self.start_firefox(firefox_options)
            
            if not driver:
                log("❌ Error: No se pudo iniciar Firefox", "ERROR")
                return False
            
            # 3. Configurar YouTube usando YouTubeJSUtils
            log("📺 Configurando YouTube...", "INFO")
            if YouTubeJSUtils.complete_youtube_setup(driver, url):
                log("✅ YouTube configurado exitosamente", "SUCCESS")
            else:
                log("⚠️ YouTube configurado con advertencias", "WARN")
            
            # 4. Mover audio al sink específico
            log("🎵 Configurando redirección de audio...", "INFO")
            if self.move_audio_to_sink(sink_name):
                log("✅ Audio redirigido correctamente", "SUCCESS")
            else:
                log("❌ Error redirigiendo audio", "ERROR")
                return False
            
            log("🎬 Firefox y YouTube listos para streaming", "SUCCESS")
            return True
            
        except Exception as e:
            log(f"❌ Error en configuración completa: {e}", "ERROR")
            return False
    
    def get_driver(self):
        """Obtiene el driver de Selenium actual."""
        return self.driver
    
    def get_firefox_pid(self):
        """Obtiene el PID de Firefox actual."""
        return self.firefox_pid
    
    def is_firefox_running(self):
        """Verifica si Firefox está ejecutándose."""
        return self.driver is not None and self.firefox_pid is not None
    
    def get_status(self):
        """Obtiene el estado actual del manager."""
        return {
            'identificador': self.identificador,
            'profile_dir': self.profile_dir,
            'firefox_pid': self.firefox_pid,
            'driver_active': self.driver is not None,
            'service_configured': self.service is not None,
            'pulse_manager_set': self.pulse_audio_manager is not None
        }
    
    def cleanup(self):
        """Limpia todos los recursos de Firefox creados por este manager."""
        log("🛑 Limpiando recursos de Firefox...", "INFO")
        
        # Cerrar driver de Firefox
        try:
            if self.driver:
                self.driver.quit()
                log("✅ Driver de Firefox cerrado", "SUCCESS")
        except Exception as e:
            log(f"Error cerrando driver: {e}", "ERROR")
        
        # Eliminar perfil temporal
        try:
            if self.profile_dir and os.path.exists(self.profile_dir):
                shutil.rmtree(self.profile_dir)
                log(f"✅ Perfil temporal eliminado: {self.profile_dir}", "SUCCESS")
        except Exception as e:
            log(f"Error eliminando perfil: {e}", "ERROR")
        
        # Limpiar estado
        self.driver = None
        self.firefox_pid = None
        self.profile_dir = None
        self.identificador = None
        
        log("✅ FirefoxManager limpiado completamente", "SUCCESS")
