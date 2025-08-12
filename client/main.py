#!/usr/bin/env python3
"""
Sistema de audio automatizado simplificado - Análogo al script de Go
Captura audio de YouTube live streams y guarda chunks de 15 segundos.
Sigue exactamente el patrón del script Go para máxima simplicidad.
"""

import os
import sys
import signal
import time
import threading
import subprocess
import random

# Variable global para parar hilos
stop_event = threading.Event()

# Variables globales para cleanup
sink_name = None
module_id = None
firefox_process = None
recording_thread = None


def cleanup():
    """Limpieza de recursos al finalizar - siguiendo patrón Go."""
    global sink_name, module_id, firefox_process, recording_thread
    
    print("\n🛑 Received shutdown signal. Cleaning up...")
    
    # Señalar a todos los hilos que paren
    stop_event.set()
    
    # Terminar Firefox
    if firefox_process:
        print("🔥 Terminating Firefox...")
        try:
            firefox_process.terminate()
            firefox_process.wait(timeout=5)
        except Exception as e:
            print(f"⚠️ Failed to terminate Firefox: {e}")
            try:
                firefox_process.kill()
            except:
                pass
    
    # Esperar a que termine el hilo de grabación
    if recording_thread and recording_thread.is_alive():
        print("🔥 Waiting for recording thread to finish...")
        recording_thread.join(timeout=10)
    
    # Descargar módulo PulseAudio
    if module_id:
        print(f"🎧 Unloading PulseAudio module: {module_id}")
        try:
            subprocess.run(["pactl", "unload-module", module_id], check=True)
        except Exception as e:
            print(f"⚠️ Failed to unload PulseAudio module: {e}")
    
    print("✅ Cleanup complete. Exiting.")


def signal_handler(sig, frame):
    """Handler para señales de sistema."""
    cleanup()
    sys.exit(0)


def create_pulse_sink():
    """Crea un sink PulseAudio único - siguiendo patrón Go."""
    global sink_name, module_id
    
    # Generar nombre único
    sink_name = f"simple-audio-{random.randint(10000, 99999)}"
    print(f"🎧 Creating PulseAudio sink: {sink_name}")
    
    try:
        # Crear sink
        result = subprocess.run([
            "pactl", "load-module", "module-null-sink", 
            f"sink_name={sink_name}"
        ], capture_output=True, text=True, check=True)
        
        module_id = result.stdout.strip()
        print(f"✅ PulseAudio sink created with module ID: {module_id}")
        
        # Esperar inicialización como en Go
        print("⏳ Waiting for PulseAudio sink to initialize...")
        time.sleep(2)
        
        return sink_name
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create PulseAudio sink: {e}")
        print("Make sure PulseAudio is running.")
        return None


def launch_firefox(url, sink_name):
    """Lanza Firefox con el sink preconfigurado - siguiendo patrón Go."""
    global firefox_process
    
    print(f"🚀 Launching Firefox with URL: {url}")
    
    # Configurar variables de entorno como en Go
    env = os.environ.copy()
    env["PULSE_SINK"] = sink_name
    
    try:
        # Lanzar Firefox con sink preconfigurado
        firefox_process = subprocess.Popen([
            "firefox",
            "--new-instance", 
            "--new-window",
            url
        ], env=env)
        
        print("✅ Firefox launched with preconfigured audio sink")
        return True
        
    except Exception as e:
        print(f"❌ Failed to start Firefox: {e}")
        return False


def record_audio_chunks(pulse_device, interval=15, output_dir="records"):
    """Graba chunks de audio de duración específica usando ffmpeg."""
    print(f"🎵 Starting audio recording: {interval}s chunks in '{output_dir}' directory")
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    chunk_number = 1
    
    while not stop_event.is_set():
        try:
            # Crear nombre de archivo con timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"audio_chunk_{timestamp}_{chunk_number:03d}.wav"
            full_path = os.path.join(output_dir, output_file)
            
            print(f"🎵 Recording: {output_file}")
            
            # Comando ffmpeg para grabar exactamente el intervalo especificado
            cmd = [
                "ffmpeg",
                "-y",  # Sobrescribir archivo si existe
                "-f", "pulse",
                "-i", pulse_device,
                "-t", str(interval),  # Duración
                "-acodec", "pcm_s16le",
                "-ar", "48000",
                "-ac", "1",
                "-loglevel", "error",  # Solo mostrar errores
                full_path
            ]
            
            # Ejecutar ffmpeg y esperar a que termine
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Verificar que el archivo se creó y tiene contenido
                if os.path.exists(full_path) and os.path.getsize(full_path) > 1000:
                    print(f"✅ Recording completed: {output_file}")
                else:
                    print(f"⚠️ File created but very small: {output_file}")
            else:
                print(f"❌ FFmpeg error: {result.stderr.strip()}")
            
            chunk_number += 1
            
        except Exception as e:
            print(f"❌ Error recording audio: {e}")
            if not stop_event.is_set():
                time.sleep(5)  # Esperar antes de reintentar


def start_audio_recording(pulse_device):
    """Inicia el hilo de grabación de audio."""
    global recording_thread
    
    pulse_device_monitor = f"{pulse_device}.monitor"
    print(f"🎤 Starting audio capture from PulseAudio source: {pulse_device_monitor}")
    
    recording_thread = threading.Thread(
        target=record_audio_chunks, 
        args=(pulse_device_monitor,), 
        daemon=True
    )
    recording_thread.start()
    return recording_thread


def main():
    """Función principal siguiendo exactamente el patrón del script Go."""
    
    # 1. Validar argumentos de línea de comandos
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <URL>")
        print(f"\nExample: {sys.argv[0]} 'https://www.youtube.com/@todonoticias/live'")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Configurar señales para cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 2. Crear sink PulseAudio único
    sink_name = create_pulse_sink()
    if not sink_name:
        sys.exit(1)
    
    # 3. Lanzar Firefox con sink preconfigurado
    if not launch_firefox(url, sink_name):
        cleanup()
        sys.exit(1)
    
    # 4. Iniciar captura y grabación de audio
    start_audio_recording(sink_name)
    
    print("🎯 System initialized successfully!")
    print("🎵 Recording 15-second audio chunks to 'records/' directory")
    print("Press Ctrl+C to stop...")
    
    # 5. Esperar señal de shutdown
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    cleanup()


if __name__ == "__main__":
    main()
