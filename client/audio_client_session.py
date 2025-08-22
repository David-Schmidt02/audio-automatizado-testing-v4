
import os
import random
import subprocess
import sys
import tempfile
import threading
import time

from rtp_client import send_rtp_stream_to_server 
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

from my_logger import log
from config import BUFFER_SIZE


class AudioClientSession:
    def __init__(self, id_instance):
        self.sink_name = None
        self.module_id = None
        self.recording_thread = None


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


    def record_audio(self, pulse_device):
        """Graba y envía un stream continuo de audio usando ffmpeg sin segmentación."""
        log("🎵 Starting continuous audio streaming (sin segmentación)", "INFO")

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "pulse",
                "-i", pulse_device,
                "-acodec", "pcm_s16le",
                "-ar", "48000",
                "-ac", "1",
                "-f", "s16le",     # ⚠️ NO "wav"
                "-loglevel", "error",
                "pipe:1"
            ]

            log(f"🚀 Starting ffmpeg streaming...", "INFO")

            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
                try:
                    while not self.stop_event.is_set():
                        data = process.stdout.read(BUFFER_SIZE)
                        if not data:
                            break
                        try:
                            send_rtp_stream_to_server(data, self.id_instance)
                        except Exception as e:
                            log(f"⚠️ Error enviando audio: {e}", "ERROR")
                            break

                    if process.poll() is None:
                        log("Stopping FFmpeg...", "INFO")
                        process.terminate()
                        try:
                            process.communicate(timeout=5)
                            log("✅ FFmpeg stopped successfully.", "SUCCESS")
                        except Exception:
                            pass
                except Exception as e:
                    log(f"❌ Error in continuous streaming: {e}", "ERROR")
        except Exception as e:
            log(f"❌ Error in continuous streaming: {e}", "ERROR")
        

    def start_audio_recording(self, pulse_device):
        """Inicia el hilo de grabación de audio."""

        pulse_device_monitor = f"{pulse_device}.monitor"
        log(f"🎤 Starting audio capture from PulseAudio source: {pulse_device_monitor}", "INFO")
        self.recording_thread = threading.Thread(
            target=self.record_audio, 
            args=(pulse_device_monitor,), 
            daemon=True
        )
        self.recording_thread.start()
        return self.recording_thread


    def cleanup(self):
        """Limpieza de recursos al finalizar."""
        log("Cleaning up Audio Client Session", "WARN")

        # Señalar a todos los hilos que paren
        self.stop_event.set()

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

        log("✅ Cleanup: Audio Client Session complete.", "SUCCESS")

