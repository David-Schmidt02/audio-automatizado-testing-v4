"""
Manager para manejar todas las operaciones de PulseAudio.
Incluye creación de sinks, gestión de streams, verificaciones y cleanup.
"""

import os
import sys
import subprocess
import time
import random
import re

# Agregar el directorio padre al path para importar logger_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_client import log


class PulseAudioManager:
    """Gestor completo de operaciones PulseAudio."""
    
    def __init__(self):
        """Inicializa el manager de PulseAudio."""
        self.module_id = None
        self.sink_name = None
        self.sink_index = None
        self.pulse_device = None  # Monitor del sink (para grabación)
        self.identificador = None
        
        log("PulseAudioManager inicializado", "SUCCESS")
    
    def create_null_sink(self, identificador=None):
        """
        Crea un sink virtual (null sink) en PulseAudio.
        
        Args:
            identificador: ID único para el sink (opcional, se genera automáticamente)
            
        Returns:
            tuple: (sink_name, module_id) si éxito, (None, None) si error
        """
        if identificador is None:
            identificador = random.randint(0, 100000)
        
        self.identificador = identificador
        sink_name = f"sink-{identificador}"
        
        log(f"Creando PulseAudio sink: {sink_name}", "INFO")
        
        try:
            # Crear el sink con pactl load-module
            output = subprocess.check_output([
                "pactl", "load-module", "module-null-sink", f"sink_name={sink_name}"
            ])
            
            # Obtener el ID del módulo creado
            module_id = output.decode().strip()
            
            # Guardar estado
            self.module_id = module_id
            self.sink_name = sink_name
            self.pulse_device = f"{sink_name}.monitor"
            
            log(f"Módulo creado con ID: {module_id}", "SUCCESS")
            
            # Esperar un poco para que se inicialice
            time.sleep(2)
            
            # Verificar que se creó correctamente
            if self.verify_sink_creation(sink_name):
                log(f"✅ Sink '{sink_name}' creado exitosamente", "SUCCESS")
                return sink_name, module_id
            else:
                log(f"❌ Error verificando sink '{sink_name}'", "ERROR")
                return None, None
                
        except subprocess.CalledProcessError as e:
            log(f"Error ejecutando pactl load-module: {e}", "ERROR")
            log(f"Código de salida: {e.returncode}", "ERROR")
            if hasattr(e, 'stderr') and e.stderr:
                log(f"Salida stderr: {e.stderr}", "ERROR")
            return None, None
        except Exception as e:
            log(f"Error inesperado creando sink: {e}", "ERROR")
            return None, None
    
    def verify_sink_creation(self, sink_name):
        """
        Verifica que el sink fue creado correctamente.
        
        Args:
            sink_name: Nombre del sink a verificar
            
        Returns:
            bool: True si el sink existe y funciona
        """
        log(f"Verificando creación de sink: {sink_name}", "INFO")
        
        try:
            # Listar sinks disponibles
            sinks_output = subprocess.check_output(["pactl", "list", "short", "sinks"])
            sinks_list = sinks_output.decode().strip()
            
            log(f"Sinks disponibles:\n{sinks_list}", "DEBUG")
            
            if sink_name in sinks_list:
                log(f"✅ Sink '{sink_name}' encontrado en lista", "SUCCESS")
                
                # También verificar el monitor
                if self.verify_monitor_creation(f"{sink_name}.monitor"):
                    return True
                else:
                    log(f"⚠️ Sink existe pero monitor no verificado", "WARN")
                    return False
            else:
                log(f"❌ Sink '{sink_name}' no aparece en la lista", "ERROR")
                return False
                
        except Exception as e:
            log(f"Error verificando sink: {e}", "ERROR")
            return False
    
    def verify_monitor_creation(self, monitor_name):
        """
        Verifica que el monitor del sink fue creado correctamente.
        
        Args:
            monitor_name: Nombre del monitor a verificar (ej: "sink-12345.monitor")
            
        Returns:
            bool: True si el monitor existe
        """
        log(f"Verificando creación de monitor: {monitor_name}", "INFO")
        
        try:
            # Listar sources (monitores son sources)
            sources_output = subprocess.check_output(["pactl", "list", "short", "sources"])
            sources_list = sources_output.decode().strip()
            
            log(f"Monitores disponibles:\n{sources_list}", "DEBUG")
            
            if monitor_name in sources_list:
                log(f"✅ Monitor '{monitor_name}' creado y disponible", "SUCCESS")
                return True
            else:
                log(f"⚠️ Monitor '{monitor_name}' no aparece en la lista", "WARN")
                return False
                
        except Exception as e:
            log(f"Error verificando monitor: {e}", "ERROR")
            return False
    
    def find_streams_by_pid(self, pid):
        """
        Encuentra streams de audio asociados a un PID específico.
        
        Args:
            pid: PID del proceso a buscar
            
        Returns:
            list: Lista de IDs de streams encontrados
        """
        firefox_streams = []
        
        try:
            log(f"Buscando streams para PID {pid}...", "DEBUG")
            
            # Obtener información detallada de sink-inputs
            result = subprocess.run(["pactl", "list", "sink-inputs"], 
                                  capture_output=True, text=True, check=True)
            
            output = result.stdout
            
            # Dividir por bloques de Sink Input
            stream_blocks = re.split(r'Sink Input #(\d+)', output)
            
            for i in range(1, len(stream_blocks), 2):
                stream_id = stream_blocks[i]
                stream_info = stream_blocks[i + 1]
                
                # Buscar el PID en múltiples formatos posibles
                pid_patterns = [
                    f'application.process.id = "{pid}"',
                    f'application.process.id = {pid}',
                    f'application.process.id="{pid}"',
                    f'application.process.id={pid}'
                ]
                
                for pattern in pid_patterns:
                    if pattern in stream_info:
                        log(f"Stream {stream_id} encontrado para PID {pid} (método PID)", "DEBUG")
                        firefox_streams.append(stream_id)
                        break
            
            # Método alternativo: buscar por nombre de aplicación
            firefox_patterns = [
                'application.name = "Firefox"',
                'application.name = Firefox',
                'media.name = "Firefox"'
            ]
            
            for i in range(1, len(stream_blocks), 2):
                stream_id = stream_blocks[i]
                stream_info = stream_blocks[i + 1]
                
                if stream_id not in firefox_streams:  # No duplicar
                    for pattern in firefox_patterns:
                        if pattern in stream_info:
                            log(f"Stream {stream_id} encontrado por nombre Firefox", "DEBUG")
                            firefox_streams.append(stream_id)
                            break
            
            # Eliminar duplicados y retornar
            unique_streams = list(set(firefox_streams))
            log(f"Streams encontrados para PID {pid}: {unique_streams}", "INFO")
            return unique_streams
            
        except Exception as e:
            log(f"Error buscando streams para PID {pid}: {e}", "ERROR")
            return []
    
    def wait_for_streams(self, pid, max_wait_time=30, check_interval=2):
        """
        Espera hasta que aparezcan streams de audio para un PID específico.
        
        Args:
            pid: PID del proceso a monitorear
            max_wait_time: Tiempo máximo de espera en segundos
            check_interval: Intervalo entre verificaciones en segundos
            
        Returns:
            list: Lista de streams encontrados (vacía si timeout)
        """
        log(f"Esperando streams de audio para PID {pid}...", "INFO")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            streams = self.find_streams_by_pid(pid)
            
            if streams:
                log(f"✅ Streams encontrados: {streams}", "SUCCESS")
                return streams
            
            elapsed = int(time.time() - start_time)
            log(f"⏳ Esperando streams... ({elapsed}s/{max_wait_time}s)", "DEBUG")
            time.sleep(check_interval)
        
        log(f"⚠️ Timeout: No se encontraron streams después de {max_wait_time}s", "WARN")
        return []
    
    def move_streams_to_sink(self, stream_ids, sink_name):
        """
        Mueve una lista de streams a un sink específico.
        
        Args:
            stream_ids: Lista de IDs de streams a mover
            sink_name: Nombre del sink destino
            
        Returns:
            int: Número de streams movidos exitosamente
        """
        if not stream_ids:
            log("No hay streams para mover", "WARN")
            return 0
        
        log(f"Moviendo {len(stream_ids)} streams al sink '{sink_name}'", "INFO")
        moved_count = 0
        
        for stream_id in stream_ids:
            try:
                log(f"Moviendo stream {stream_id}...", "DEBUG")
                subprocess.run(["pactl", "move-sink-input", stream_id, sink_name], check=True)
                log(f"✅ Stream {stream_id} movido exitosamente", "SUCCESS")
                moved_count += 1
            except subprocess.CalledProcessError as e:
                log(f"❌ Error moviendo stream {stream_id}: {e}", "ERROR")
                continue
        
        log(f"🎉 Resultado: {moved_count}/{len(stream_ids)} streams movidos", "SUCCESS")
        return moved_count
    
    def verify_audio_capture(self, sink_name=None):
        """
        Verifica que el sink monitor está capturando audio correctamente.
        
        Args:
            sink_name: Nombre del sink a verificar (usa self.sink_name si no se especifica)
            
        Returns:
            bool: True si está capturando audio
        """
        if sink_name is None:
            sink_name = self.sink_name
        
        if not sink_name:
            log("No hay sink configurado para verificar", "ERROR")
            return False
        
        monitor_device = f"{sink_name}.monitor"
        log(f"Verificando captura de audio en {monitor_device}...", "INFO")
        
        try:
            # Verificar que el monitor existe en la lista de sources
            cmd = ["pactl", "list", "sources", "short"]
            sources_output = subprocess.check_output(cmd)
            sources_text = sources_output.decode()
            
            if monitor_device in sources_text:
                log(f"✅ Monitor {monitor_device} disponible", "SUCCESS")
                
                # Verificar información detallada
                detailed_cmd = ["pactl", "list", "sources"]
                detailed_output = subprocess.check_output(detailed_cmd)
                detailed_text = detailed_output.decode()
                
                if monitor_device in detailed_text:
                    log(f"✅ Monitor {monitor_device} operativo", "SUCCESS")
                    return True
                else:
                    log(f"⚠️ Monitor no encontrado en listado detallado", "WARN")
                    return False
            else:
                log(f"❌ Monitor {monitor_device} no disponible", "ERROR")
                return False
                
        except Exception as e:
            log(f"Error verificando captura de audio: {e}", "ERROR")
            return False
    
    def verify_sink_has_audio(self, sink_name=None, timeout=10):
        """
        Verifica que hay streams activos conectados al sink.
        
        Args:
            sink_name: Nombre del sink a verificar
            timeout: Tiempo límite para la verificación
            
        Returns:
            bool: True si el sink tiene streams activos
        """
        if sink_name is None:
            sink_name = self.sink_name
        
        if not sink_name:
            log("No hay sink configurado para verificar", "ERROR")
            return False
        
        log(f"Verificando streams activos en sink '{sink_name}'...", "INFO")
        
        try:
            # Listar sink-inputs conectados
            result = subprocess.run(["pactl", "list", "short", "sink-inputs"], 
                                  capture_output=True, text=True, check=True)
            
            sink_inputs = result.stdout.strip().split('\n')
            streams_in_sink = 0
            
            for line in sink_inputs:
                if line.strip() and sink_name in line:
                    streams_in_sink += 1
                    log(f"✅ Stream encontrado: {line.strip()}", "DEBUG")
            
            if streams_in_sink > 0:
                log(f"✅ Sink '{sink_name}' tiene {streams_in_sink} streams activos", "SUCCESS")
                return True
            else:
                log(f"⚠️ Sink '{sink_name}' no tiene streams activos", "WARN")
                return False
                
        except Exception as e:
            log(f"Error verificando streams en sink: {e}", "ERROR")
            return False
    
    def debug_audio_streams(self):
        """Función de debug para mostrar todos los streams de audio activos."""
        try:
            log("=== DEBUG: Streams de audio activos ===", "DEBUG")
            
            # Información detallada
            result = subprocess.run(["pactl", "list", "sink-inputs"], 
                                  capture_output=True, text=True, check=True)
            log("Información detallada:", "DEBUG")
            log(result.stdout, "DEBUG")
            
            # Información resumida
            short_result = subprocess.run(["pactl", "list", "short", "sink-inputs"], 
                                        capture_output=True, text=True, check=True)
            log("=== Streams resumidos ===", "DEBUG")
            log(short_result.stdout, "DEBUG")
            
            log("=== Fin DEBUG ===", "DEBUG")
            
        except Exception as e:
            log(f"Error en debug de streams: {e}", "ERROR")
    
    def get_sink_info(self):
        """
        Obtiene información del sink actual.
        
        Returns:
            dict: Información del sink o None si no hay sink configurado
        """
        if not self.sink_name:
            return None
        
        return {
            'sink_name': self.sink_name,
            'module_id': self.module_id,
            'pulse_device': self.pulse_device,
            'identificador': self.identificador,
            'sink_index': self.sink_index
        }
    
    def cleanup(self):
        """Limpia todos los recursos de PulseAudio creados por este manager."""
        log("🛑 Limpiando recursos de PulseAudio...", "INFO")
        
        try:
            if self.module_id:
                subprocess.run(["pactl", "unload-module", self.module_id], check=True)
                log(f"✅ Módulo PulseAudio {self.module_id} descargado", "SUCCESS")
            else:
                log("No hay módulo para descargar", "INFO")
                
        except subprocess.CalledProcessError as e:
            log(f"Error descargando módulo PulseAudio: {e}", "ERROR")
        except Exception as e:
            log(f"Error inesperado en cleanup: {e}", "ERROR")
        finally:
            # Limpiar estado
            self.module_id = None
            self.sink_name = None
            self.sink_index = None
            self.pulse_device = None
            self.identificador = None
            
            log("✅ PulseAudioManager limpiado", "SUCCESS")
