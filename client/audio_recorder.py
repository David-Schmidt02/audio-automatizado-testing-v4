#!/usr/bin/env python3
"""
Simple Audio Recorder - Patrón Go
Captura audio de YouTube y lo guarda en archivos WAV de 15 segundos.
Sigue el patrón del script Go: simple, directo, eficiente.
"""

import os
import sys
import time
import signal
import random
import subprocess
import tempfile
import threading
from pathlib import Path

# Configuración de audio
SAMPLE_RATE = 48000
CHANNELS = 1
BIT_DEPTH = 16
RECORD_INTERVAL = 15  # segundos
DEFAULT_RECORDS_DIR = "records"  # Directorio por defecto

# Variables globales para cleanup
sink_name = None
module_id = None
firefox_process = None
recording_process = None
firefox_profile_dir = None
stop_recording = threading.Event()

def log(message, level="INFO"):
    """Log simple con timestamp."""
    timestamp = time.strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}
    icon = icons.get(level, "📝")
    print(f"[{timestamp}] {icon} {message}")

def cleanup():
    """Limpieza completa del sistema."""
    global firefox_process, recording_process, module_id, firefox_profile_dir
    
    log("Iniciando limpieza del sistema...")
    
    # Detener grabación
    stop_recording.set()
    
    # Terminar Firefox
    if firefox_process:
        try:
            firefox_process.terminate()
            firefox_process.wait(timeout=5)
            log("Firefox terminado")
        except:
            try:
                firefox_process.kill()
                log("Firefox forzado a cerrar")
            except:
                pass
    
    # Terminar grabación
    if recording_process:
        try:
            recording_process.terminate()
            recording_process.wait(timeout=3)
            log("Proceso de grabación terminado")
        except:
            try:
                recording_process.kill()
                log("Proceso de grabación forzado a cerrar")
            except:
                pass
    
    # Limpiar perfil temporal de Firefox
    if firefox_profile_dir and os.path.exists(firefox_profile_dir):
        try:
            import shutil
            shutil.rmtree(firefox_profile_dir)
            log(f"Perfil Firefox eliminado: {firefox_profile_dir}")
        except:
            log("Error eliminando perfil Firefox", "WARN")
    
    # Descargar módulo PulseAudio
    if module_id:
        try:
            subprocess.run(["pactl", "unload-module", module_id], check=True)
            log(f"Módulo PulseAudio {module_id} descargado")
        except:
            log("Error descargando módulo PulseAudio", "WARN")
    
    log("Limpieza completa", "SUCCESS")

def signal_handler(sig, frame):
    """Manejador de señales para cleanup graceful."""
    cleanup()
    sys.exit(0)

def create_audio_sink():
    """Crea un sink de PulseAudio único."""
    global sink_name, module_id
    
    # Generar nombre único
    sink_name = f"audio-recorder-{random.randint(10000, 99999)}"
    
    log(f"Creando sink PulseAudio: {sink_name}")
    
    try:
        # Crear sink
        result = subprocess.run([
            "pactl", "load-module", "module-null-sink", 
            f"sink_name={sink_name}"
        ], capture_output=True, text=True, check=True)
        
        module_id = result.stdout.strip()
        log(f"Sink creado exitosamente (módulo: {module_id})", "SUCCESS")
        
        # Esperar inicialización
        log("Esperando inicialización del sink...")
        time.sleep(2)
        
        return sink_name
        
    except subprocess.CalledProcessError as e:
        log(f"Error creando sink: {e}", "ERROR")
        return None

def create_optimized_firefox_profile():
    """Crea un perfil de Firefox optimizado para captura de audio."""
    global firefox_profile_dir
    
    # Crear directorio con nombre identificable
    session_id = random.randint(1000, 9999)
    profile_name = f"audio-recorder-profile-{session_id}"
    firefox_profile_dir = os.path.join(tempfile.gettempdir(), profile_name)
    
    log(f"Creando perfil Firefox: {profile_name}")
    
    try:
        # Crear directorio del perfil
        os.makedirs(firefox_profile_dir, exist_ok=True)
        
        # Crear archivo de preferencias optimizado
        prefs_js = os.path.join(firefox_profile_dir, "prefs.js")
        
        preferences = [
            '// Configuración optimizada para captura de audio',
            'user_pref("media.autoplay.default", 0);',  # Permitir autoplay
            'user_pref("media.autoplay.blocking_policy", 0);',  # No bloquear autoplay
            'user_pref("media.volume_scale", "1.0");',  # Volumen máximo
            'user_pref("dom.webnotifications.enabled", false);',  # Sin notificaciones
            'user_pref("app.update.enabled", false);',  # Sin actualizaciones
            'user_pref("browser.startup.homepage_override.mstone", "ignore");',  # Sin página de bienvenida
            'user_pref("toolkit.startup.max_resumed_crashes", -1);',  # No mostrar recuperación
            'user_pref("browser.tabs.crashReporting.sendReport", false);',  # Sin reportes
            'user_pref("datareporting.healthreport.uploadEnabled", false);',  # Sin telemetría
            'user_pref("media.gmp-gmpopenh264.enabled", true);',  # Habilitar H264
            'user_pref("media.navigator.permission.disabled", true);',  # Sin permisos de medios
        ]
        
        with open(prefs_js, 'w', encoding='utf-8') as f:
            f.write('\n'.join(preferences))
        
        log(f"Perfil creado exitosamente: {firefox_profile_dir}", "SUCCESS")
        return firefox_profile_dir
        
    except Exception as e:
        log(f"Error creando perfil Firefox: {e}", "ERROR")
        return None

def start_firefox(url, sink_name):
    """Inicia Firefox con perfil optimizado y audio dirigido al sink."""
    global firefox_process
    
    log(f"Iniciando Firefox con URL: {url}")
    
    # Crear perfil optimizado
    profile_dir = create_optimized_firefox_profile()
    if not profile_dir:
        log("Error creando perfil Firefox", "ERROR")
        return None
    
    try:
        # Configurar entorno con sink de audio
        env = os.environ.copy()
        env["PULSE_SINK"] = sink_name
        
        log(f"Configurando PULSE_SINK={sink_name}")
        
        # Lanzar Firefox con perfil optimizado
        firefox_process = subprocess.Popen([
            "firefox",
            "--new-instance",
            "--profile", profile_dir,
            "--new-window",
            url
        ], env=env)
        
        log("Firefox iniciado exitosamente con perfil optimizado", "SUCCESS")
        return firefox_process
        
    except Exception as e:
        log(f"Error iniciando Firefox: {e}", "ERROR")
        return None

def record_audio_chunks(pulse_device, output_dir=DEFAULT_RECORDS_DIR):
    """Graba audio en chunks de 15 segundos."""
    global recording_process
    
    # Crear directorio de salida
    Path(output_dir).mkdir(exist_ok=True)
    
    log(f"Iniciando grabación desde: {pulse_device}")
    log(f"Guardando en: {output_dir}")
    
    chunk_counter = 1
    
    while not stop_recording.is_set():
        try:
            # Crear nombre de archivo
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"audio_chunk_{timestamp}_{chunk_counter:03d}.wav"
            filepath = os.path.join(output_dir, filename)
            
            log(f"Grabando chunk {chunk_counter}: {filename}")
            
            # Comando ffmpeg
            cmd = [
                "ffmpeg",
                "-y",  # Sobrescribir
                "-f", "pulse",
                "-i", pulse_device,
                "-t", str(RECORD_INTERVAL),  # Duración
                "-acodec", "pcm_s16le",
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "-loglevel", "error",  # Solo errores
                filepath
            ]
            
            # Ejecutar grabación
            recording_process = subprocess.run(cmd, capture_output=True, text=True)
            
            if recording_process.returncode == 0:
                # Verificar archivo
                if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                    log(f"Chunk completado: {filename}", "SUCCESS")
                else:
                    log(f"Archivo muy pequeño: {filename}", "WARN")
            else:
                log(f"Error en grabación: {recording_process.stderr}", "ERROR")
            
            chunk_counter += 1
            
        except Exception as e:
            log(f"Error grabando chunk: {e}", "ERROR")
            time.sleep(1)  # Pausa antes de reintentar

