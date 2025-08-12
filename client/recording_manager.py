"""
Manager para manejar todas las operaciones de grabación de audio.
Incluye grabación de WAV por intervalos y streaming RTP.
"""

import os
import sys
import time
import threading
import subprocess
import socket
import struct
import random

# Agregar el directorio padre al path para importar logger_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_client import log


class RecordingManager:
    """Gestor de grabaciones de audio WAV y streaming RTP."""
    
    def __init__(self, pulse_device=None):
        """
        Inicializa el manager de grabación.
        
        Args:
            pulse_device: Dispositivo PulseAudio para grabar (ej: "sink-12345.monitor")
        """
        self.pulse_device = pulse_device
        self.stop_event = threading.Event()
        self.recording_thread = None
        self.streaming_thread = None
        self.parec_process = None
        
        # Configuración de audio
        self.sample_rate = 48000
        self.channels = 1
        self.bit_depth = 16
        
        # Configuración RTP
        self.payload_type_l16 = 96
        self.rtp_clock_rate = 48000
        
        log("RecordingManager inicializado", "SUCCESS")
    
    def set_pulse_device(self, pulse_device):
        """Establece el dispositivo PulseAudio a usar."""
        self.pulse_device = pulse_device
        log(f"Dispositivo PulseAudio configurado: {pulse_device}", "INFO")
    
    def start_wav_recording(self, interval=15, output_dir="records"):
        """
        Inicia la grabación de archivos WAV cada cierto intervalo.
        
        Args:
            interval: Intervalo en segundos entre grabaciones
            output_dir: Directorio donde guardar los archivos
            
        Returns:
            bool: True si se inició correctamente
        """
        if not self.pulse_device:
            log("Error: No hay dispositivo PulseAudio configurado", "ERROR")
            return False
        
        if self.recording_thread and self.recording_thread.is_alive():
            log("La grabación WAV ya está activa", "WARN")
            return True
        
        # Crear directorio si no existe
        os.makedirs(output_dir, exist_ok=True)
        
        def record_continuously():
            """Función interna para grabar continuamente."""
            contador = 1
            log(f"🎵 Iniciando grabación WAV cada {interval} segundos", "INFO")
            
            while not self.stop_event.is_set():
                try:
                    # Crear nombre de archivo con timestamp
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    output_file = f"audio_chunk_{timestamp}_{contador:03d}.wav"
                    full_path = os.path.join(output_dir, output_file)
                    
                    log(f"🎵 Grabando: {output_file}", "INFO")
                    
                    # Comando ffmpeg para grabar exactamente el intervalo especificado
                    cmd = [
                        "ffmpeg",
                        "-y",  # Sobrescribir archivo si existe
                        "-f", "pulse",
                        "-i", self.pulse_device,
                        "-t", str(interval),  # Duración
                        "-acodec", "pcm_s16le",
                        "-ar", str(self.sample_rate),
                        "-ac", str(self.channels),
                        "-loglevel", "error",  # Solo mostrar errores, no info verbosa
                        full_path
                    ]
                    
                    # Ejecutar ffmpeg y esperar a que termine
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if proc.returncode == 0:
                        # Verificar que el archivo se creó y tiene contenido
                        if os.path.exists(full_path) and os.path.getsize(full_path) > 1000:  # Al menos 1KB
                            log(f"✅ Grabación completada: {output_file}", "SUCCESS")
                        else:
                            log(f"⚠️ Archivo creado pero muy pequeño: {output_file}", "WARN")
                    elif proc.returncode == 255:
                        # Código 255 = Interrupción por señal (Ctrl+C) - NORMAL
                        if os.path.exists(full_path) and os.path.getsize(full_path) > 1000:
                            duration_recorded = os.path.getsize(full_path) / (self.sample_rate * self.channels * 2)  # Aproximado
                            log(f"🔄 Grabación interrumpida pero guardada: {output_file} (~{duration_recorded:.1f}s)", "INFO")
                        else:
                            log(f"🗑️ Grabación interrumpida sin contenido útil: {output_file}", "WARN")
                            # Eliminar archivo vacío o muy pequeño
                            if os.path.exists(full_path):
                                os.remove(full_path)
                    else:
                        # Error real de ffmpeg
                        error_lines = proc.stderr.strip().split('\n')
                        # Solo mostrar las últimas líneas importantes, no todo el output
                        relevant_error = error_lines[-1] if error_lines else "Error desconocido"
                        log(f"❌ Error en grabación: {relevant_error}", "ERROR")
                        log(f"📝 Comando: ffmpeg ... {output_file}", "DEBUG")
                    
                    contador += 1
                    
                except Exception as e:
                    log(f"Error grabando WAV: {e}", "ERROR")
                    if not self.stop_event.is_set():
                        time.sleep(5)  # Esperar antes de reintentar
        
        # Iniciar hilo de grabación
        self.stop_event.clear()
        self.recording_thread = threading.Thread(target=record_continuously, daemon=True)
        self.recording_thread.start()
        
        log(f"🎙️ Sistema de grabación WAV iniciado (cada {interval}s)", "SUCCESS")
        return True
    
    def start_rtp_streaming(self, destination):
        """
        Inicia el streaming RTP del audio.
        
        Args:
            destination: Dirección destino en formato "host:puerto"
            
        Returns:
            bool: True si se inició correctamente
        """
        if not self.pulse_device:
            log("Error: No hay dispositivo PulseAudio configurado", "ERROR")
            return False
        
        if self.streaming_thread and self.streaming_thread.is_alive():
            log("El streaming RTP ya está activo", "WARN")
            return True
        
        try:
            # Configurar socket UDP
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            host, port = destination.split(":")
            port = int(port)
            udp_addr = (host, port)
            
            # Configurar parec
            parec_cmd = [
                "parec",
                "--format=s16be",
                f"--rate={self.sample_rate}",
                f"--channels={self.channels}",
                f"--device={self.pulse_device}"
            ]
            
            self.parec_process = subprocess.Popen(
                parec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            # Configuración RTP
            buffer_size = (self.sample_rate // 50) * self.channels * (self.bit_depth // 8)
            ssrc = random.randint(0, (1 << 32) - 1)
            seq_num = random.randint(0, 65535)
            timestamp = 0
            
            def rtp_header(payload_type, seq, ts, ssrc):
                """Crea el header RTP."""
                v_p_x_cc = 0x80
                m_pt = payload_type & 0x7F
                return struct.pack("!BBHII", v_p_x_cc, m_pt, seq, ts, ssrc)
            
            def stream_audio():
                """Función interna para streaming continuo."""
                nonlocal seq_num, timestamp
                log(f"🌐 Iniciando streaming RTP a {destination}", "INFO")
                
                while not self.stop_event.is_set():
                    try:
                        data = self.parec_process.stdout.read(buffer_size)
                        if not data:
                            break
                        
                        timestamp += self.rtp_clock_rate // 50
                        header = rtp_header(self.payload_type_l16, seq_num, timestamp, ssrc)
                        seq_num = (seq_num + 1) % 65536
                        packet = header + data
                        udp_sock.sendto(packet, udp_addr)
                        
                    except Exception as e:
                        log(f"Error en streaming RTP: {e}", "ERROR")
                        break
                
                log("Streaming RTP terminado", "INFO")
            
            # Iniciar hilo de streaming
            self.stop_event.clear()
            self.streaming_thread = threading.Thread(target=stream_audio, daemon=True)
            self.streaming_thread.start()
            
            log(f"🌐 Streaming RTP iniciado a {destination}", "SUCCESS")
            return True
            
        except Exception as e:
            log(f"Error iniciando streaming RTP: {e}", "ERROR")
            return False
    
    def stop_all_recordings(self):
        """Detiene todas las grabaciones y streaming activos."""
        log("🛑 Deteniendo todas las grabaciones...", "INFO")
        
        # Señalar parada a todos los hilos
        self.stop_event.set()
        
        # Esperar a que terminen los hilos con timeout más generoso para grabación
        if self.recording_thread and self.recording_thread.is_alive():
            log("⏳ Esperando que termine la grabación actual...", "DEBUG")
            self.recording_thread.join(timeout=20)  # 20s para permitir que ffmpeg termine limpiamente
            if self.recording_thread.is_alive():
                log("⚠️ Timeout esperando grabación, forzando parada", "WARN")
            else:
                log("✅ Hilo de grabación WAV detenido limpiamente", "SUCCESS")
        
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=5)
            log("✅ Hilo de streaming RTP detenido", "SUCCESS")
        
        # Terminar proceso parec si está activo
        if self.parec_process and self.parec_process.poll() is None:
            self.parec_process.kill()
            log("✅ Proceso parec terminado", "SUCCESS")
        
        log("✅ Todas las grabaciones detenidas", "SUCCESS")
    
    def is_recording_active(self):
        """Verifica si hay grabaciones activas."""
        wav_active = self.recording_thread and self.recording_thread.is_alive()
        rtp_active = self.streaming_thread and self.streaming_thread.is_alive()
        return wav_active or rtp_active
    
    def get_status(self):
        """Obtiene el estado actual del manager."""
        return {
            'pulse_device': self.pulse_device,
            'wav_recording': self.recording_thread and self.recording_thread.is_alive(),
            'rtp_streaming': self.streaming_thread and self.streaming_thread.is_alive(),
            'parec_active': self.parec_process and self.parec_process.poll() is None,
            'sample_rate': self.sample_rate,
            'channels': self.channels
        }
    
    def cleanup(self):
        """Limpieza completa del manager."""
        self.stop_all_recordings()
        log("RecordingManager limpiado completamente", "SUCCESS")
