"""
Utilidades JavaScript para interactuar con YouTube a través de Selenium.
Contiene funciones para verificar estado, reactivar video, detectar errores, etc.
"""

import time
import sys
import os
import subprocess
import importlib.util

# Agregar el directorio padre al path para importar logger_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_client import log
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class YouTubeJSUtils:
    """Clase que contiene todas las utilidades JavaScript para YouTube."""
    
    @staticmethod
    def get_player_state(driver):
        """Obtiene el estado completo del reproductor de YouTube."""
        return driver.execute_script("""
            // Verificar varios indicadores de estado de YouTube
            var video = document.querySelector('video');
            var playButton = document.querySelector('.ytp-play-button');
            var pauseOverlay = document.querySelector('.ytp-pause-overlay');
            var endScreen = document.querySelector('.ytp-endscreen-content');
            var adPlaying = document.querySelector('.ad-showing');
            
            return {
                hasVideo: !!video,
                videoCurrentTime: video ? video.currentTime : null,
                videoDuration: video ? video.duration : null,
                videoPaused: video ? video.paused : null,
                videoEnded: video ? video.ended : null,
                videoMuted: video ? video.muted : null,
                videoVolume: video ? video.volume : null,
                videoReadyState: video ? video.readyState : null,
                videoNetworkState: video ? video.networkState : null,
                videoError: video && video.error ? video.error.message : null,
                hasPlayButton: !!playButton,
                playButtonTitle: playButton ? playButton.title : null,
                hasPauseOverlay: !!pauseOverlay,
                hasEndScreen: !!endScreen,
                isAdPlaying: !!adPlaying,
                pageTitle: document.title,
                currentUrl: window.location.href
            };
        """)
    
    @staticmethod
    def get_stream_info(driver):
        """Obtiene información específica del stream en vivo."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            var titleElement = document.querySelector('h1.ytd-watch-metadata yt-formatted-string');
            var channelElement = document.querySelector('a.yt-simple-endpoint.style-scope.yt-formatted-string');
            
            return {
                hasVideo: !!video,
                videoPaused: video ? video.paused : null,
                videoEnded: video ? video.ended : null,
                videoDuration: video ? video.duration : null,
                videoCurrentTime: video ? video.currentTime : null,
                isLive: video ? (video.duration === Infinity || isNaN(video.duration)) : false,
                currentTitle: titleElement ? titleElement.textContent.trim() : null,
                channelName: channelElement ? channelElement.textContent.trim() : null,
                currentUrl: window.location.href,
                pageTitle: document.title,
                hasError: !!document.querySelector('.ytp-error'),
                isOffline: !!document.querySelector('.ytp-offline-slate') || 
                          document.title.toLowerCase().includes('offline') ||
                          document.title.toLowerCase().includes('no disponible')
            };
        """)
    
    @staticmethod
    def is_video_playing(driver):
        """Verifica rápidamente si el video está reproduciendo."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            return video ? !video.paused : false;
        """)
    
    @staticmethod
    def play_video(driver):
        """Intenta reproducir el video usando JavaScript."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            if (video && video.paused) {
                video.play().catch(function(error) {
                    console.log('Error al reproducir:', error);
                });
            }
        """)
    
    @staticmethod
    def configure_audio(driver, muted=False, volume=1.0):
        """Configura el audio del video (volumen y mute)."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            if (video) {
                video.muted = arguments[0];
                video.volume = arguments[1];
            }
        """, muted, volume)
    
    @staticmethod
    def pause_and_play(driver, pause_delay=500):
        """Pausa y luego reproduce el video con un delay."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            if (video) {
                video.pause();
                setTimeout(function() {
                    video.play().catch(function(error) {
                        console.log('Error al reproducir:', error);
                    });
                }, arguments[0]);
            }
        """, pause_delay)
    
    @staticmethod
    def simulate_user_activity(driver):
        """Simula actividad del usuario para mantener YouTube activo."""
        return driver.execute_script("""
            // Un solo evento de mouse aleatorio
            var event = new MouseEvent('mousemove', {
                view: window,
                bubbles: true,
                cancelable: true,
                clientX: Math.random() * window.innerWidth,
                clientY: Math.random() * window.innerHeight
            });
            document.dispatchEvent(event);
            
            // Hover ligero en el video
            var video = document.querySelector('video');
            if (video) {
                var hoverEvent = new MouseEvent('mouseenter', {
                    view: window,
                    bubbles: true,
                    cancelable: true
                });
                video.dispatchEvent(hoverEvent);
            }
            
            // Mantener focus
            window.focus();
        """)
    
    @staticmethod
    def get_detailed_video_state(driver):
        """Obtiene estado detallado del video para diagnóstico."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            if (video) {
                return {
                    paused: video.paused,
                    ended: video.ended,
                    currentTime: video.currentTime,
                    duration: video.duration,
                    muted: video.muted,
                    volume: video.volume,
                    readyState: video.readyState,
                    networkState: video.networkState,
                    error: video.error ? video.error.message : null
                };
            }
            return null;
        """)
    
    @staticmethod
    def get_final_state_summary(driver):
        """Obtiene un resumen final del estado para diagnóstico."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            return {
                videoPaused: video ? video.paused : null,
                videoCurrentTime: video ? video.currentTime : null,
                videoMuted: video ? video.muted : null,
                hasPlayButton: !!document.querySelector('.ytp-play-button'),
                url: window.location.href
            };
        """)
    
    @staticmethod
    def configure_stream_for_recording(driver):
        """Configura el stream para grabación optimizada."""
        return driver.execute_script("""
            var video = document.querySelector('video');
            if (video) {
                video.muted = false;
                video.volume = 1.0;
                video.play().catch(function(error) {
                    console.log('Error al reproducir después de cambio:', error);
                });
            }
        """)

    @staticmethod
    def skip_ads(driver, timeout=60):
        """Salta anuncios de YouTube si aparecen."""
        log("Intentando saltar anuncios (si aparecen)...", "INFO")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Intentar varios selectores para botones de saltar anuncio
                skip_selectors = [
                    ".ytp-ad-skip-button",
                    ".ytp-skip-ad-button", 
                    "[aria-label*='Skip']",
                    "[aria-label*='Omitir']",
                    ".skip-button",
                    "#skip-button"
                ]
                
                for selector in skip_selectors:
                    try:
                        skip_button = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        log("Botón 'Saltar anuncio' encontrado. Haciendo clic...", "SUCCESS")
                        skip_button.click()
                        time.sleep(2)
                        break
                    except:
                        continue
                else:
                    # Si no encontró ningún botón, salir del bucle principal
                    break
                    
            except:
                break
        log("Proceso de saltar anuncios finalizado", "SUCCESS")

    @staticmethod
    def ensure_video_is_playing(driver, max_attempts=5):
        """Asegura que el video esté reproduciendo y genere audio."""
        log("Verificando que el video esté reproduciendo...", "INFO")
        
        for attempt in range(max_attempts):
            try:
                video_state = driver.execute_script("""
                    var video = document.querySelector('video');
                    if (!video) return {error: 'No video found'};
                    
                    return {
                        exists: true,
                        paused: video.paused,
                        ended: video.ended,
                        muted: video.muted,
                        volume: video.volume,
                        currentTime: video.currentTime,
                        duration: video.duration,
                        readyState: video.readyState,
                        networkState: video.networkState
                    };
                """)
                
                if 'error' in video_state:
                    log(f"❌ Intento {attempt + 1}: No se encontró elemento video", "WARN")
                    time.sleep(3)
                    continue
                
                # Verificar si el video está pausado
                if video_state.get('paused', True):
                    log(f"⏸️ Intento {attempt + 1}: Video pausado, intentando reproducir...", "WARN")
                    driver.execute_script("""
                        var video = document.querySelector('video');
                        if (video) {
                            video.muted = false;
                            video.volume = 1.0;
                            video.play().catch(e => console.log('Error playing:', e));
                        }
                    """)
                    time.sleep(3)
                    continue
                
                # Verificar si el video está silenciado
                if video_state.get('muted', True):
                    log(f"🔇 Intento {attempt + 1}: Video silenciado, activando audio...", "WARN")
                    driver.execute_script("""
                        var video = document.querySelector('video');
                        if (video) {
                            video.muted = false;
                            video.volume = 1.0;
                        }
                    """)
                    time.sleep(2)
                    continue
                
                # Si llegamos aquí, el video debería estar reproduciendo con audio
                log(f"✅ Video reproduciéndose: volume={video_state.get('volume')}, currentTime={video_state.get('currentTime')}", "SUCCESS")
                return True
                
            except Exception as e:
                log(f"Error verificando estado del video: {e}", "ERROR")
                time.sleep(2)
        
        log("❌ No se pudo asegurar que el video esté reproduciendo correctamente", "ERROR")
        return False

    @staticmethod
    def load_and_execute_live_stream_js(driver):
        """Carga y ejecuta el script de live stream."""
        try:
            js_path = os.path.join(os.path.dirname(__file__), 'live_stream_video.js')
            with open(js_path, 'r', encoding='utf-8') as js_file:
                script_js = js_file.read()
            
            log(f"JavaScript cargado: {len(script_js)} caracteres", "DEBUG")
            
            # Ejecutar el script y verificar si se ejecutó correctamente
            result = driver.execute_script(script_js)
            log("Script JavaScript ejecutado exitosamente", "SUCCESS")
            
            # Verificar que el video existe y está configurado
            video_check = driver.execute_script("""
                var video = document.querySelector('video');
                if (video) {
                    return {
                        found: true,
                        muted: video.muted,
                        volume: video.volume,
                        paused: video.paused,
                        duration: video.duration,
                        currentTime: video.currentTime
                    };
                }
                return {found: false};
            """)
            
            if video_check and video_check.get('found'):
                log(f"Video encontrado y configurado: muted={video_check.get('muted')}, volume={video_check.get('volume')}, paused={video_check.get('paused')}", "SUCCESS")
                return True
            else:
                log("Advertencia: No se encontró elemento video en la página", "WARN")
                return False
                
        except Exception as e:
            log(f"Error ejecutando JavaScript: {e}", "ERROR")
            return False

    @staticmethod  
    def debug_audio_streams():
        """Función de debug para mostrar todos los streams de audio activos."""
        try:
            result = subprocess.run(["pactl", "list", "sink-inputs"], 
                                  capture_output=True, text=True, check=True)
            
            log("=== DEBUG: Streams de audio activos ===", "DEBUG")
            log(result.stdout, "DEBUG")
            log("=== Fin DEBUG ===", "DEBUG")
            
            # También mostrar la versión corta
            short_result = subprocess.run(["pactl", "list", "short", "sink-inputs"], 
                                        capture_output=True, text=True, check=True)
            log("=== Streams cortos ===", "DEBUG")
            log(short_result.stdout, "DEBUG")
            
        except Exception as e:
            log(f"Error en debug de streams: {e}", "ERROR")

    @staticmethod
    def complete_youtube_setup(driver, video_url):
        """Método completo para configurar YouTube con todas las verificaciones."""
        log(f"Iniciando configuración completa de YouTube para: {video_url}", "INFO")
        
        # 1. Navegar a la URL
        log(f"Navegando a: {video_url}", "INFO")
        driver.get(video_url)
        
        # 2. Saltar anuncios
        YouTubeJSUtils.skip_ads(driver, timeout=60)
        
        # 3. Esperar carga inicial
        log("Esperando carga inicial de la página...", "INFO")
        time.sleep(5)
        
        # 4. Ejecutar JavaScript de configuración
        if not YouTubeJSUtils.load_and_execute_live_stream_js(driver):
            log("Fallo en la carga de JavaScript, continuando...", "WARN")
        
        # 5. Asegurar que el video esté reproduciendo
        log("Verificando reproducción de video con audio...", "INFO")
        if YouTubeJSUtils.ensure_video_is_playing(driver):
            log("✅ Video configurado y reproduciendo con audio", "SUCCESS")
            
            # 6. Esperar generación de streams de audio
            log("Esperando generación de streams de audio...", "INFO")
            time.sleep(8)
            
            # 7. Debug de streams
            YouTubeJSUtils.debug_audio_streams()
            return True
        else:
            log("⚠️ Advertencia: No se pudo confirmar reproducción con audio", "WARN")
            YouTubeJSUtils.debug_audio_streams()
            return False


def get_youtube_player_state(driver):
    """Función wrapper para obtener estado del reproductor."""
    try:
        state = YouTubeJSUtils.get_player_state(driver)
        log(f"Estado de YouTube: {state}", "DEBUG")
        return state
    except Exception as e:
        log(f"Error obteniendo estado del reproductor: {e}", "ERROR")
        return None


def activate_youtube_video(driver):
    """Activa/reproduce el video de YouTube usando múltiples métodos."""
    try:
        log("Activando video de YouTube...", "DEBUG")
        
        # Método 1: Click en video (usando Selenium)
        try:
            video_element = driver.find_element(By.TAG_NAME, "video")
            driver.execute_script("arguments[0].click();", video_element)
        except:
            pass
        
        # Método 2: Comando play() JavaScript
        YouTubeJSUtils.play_video(driver)
        
        # Método 3: Botón play si existe
        try:
            play_button = driver.find_element(By.CSS_SELECTOR, ".ytp-play-button")
            play_button.click()
        except:
            pass
        
        # Método 4: Configurar audio
        YouTubeJSUtils.configure_audio(driver, muted=False, volume=1.0)
        
        return True
        
    except Exception as e:
        log(f"Error activando video: {e}", "ERROR")
        return False


def keep_youtube_active_optimized(driver):
    """Mantiene YouTube activo con estrategias optimizadas."""
    try:
        log("Manteniendo YouTube activo...", "DEBUG")
        
        # Verificar estado una vez
        is_playing = YouTubeJSUtils.is_video_playing(driver)
        
        if not is_playing:
            log("Video pausado, reactivando...", "WARN")
            activate_youtube_video(driver)
        
        # Simular actividad de usuario moderada
        YouTubeJSUtils.simulate_user_activity(driver)
        
        return True
        
    except Exception as e:
        log(f"Error en actividad: {e}", "DEBUG")
        return False


def force_youtube_audio_refresh(driver):
    """Método agresivo para forzar que YouTube reproduzca audio."""
    log("Aplicando método agresivo para reactivar audio...", "WARN")
    
    try:
        # Obtener estado completo
        youtube_state = get_youtube_player_state(driver)
        
        if not youtube_state:
            return False
        
        # Estrategia según el estado
        if youtube_state.get('hasEndScreen'):
            log("Video terminó, recargar página...", "WARN")
            driver.refresh()
            time.sleep(1.5)
            skip_ads(driver, timeout=30)
        
        # Pausar y reproducir
        YouTubeJSUtils.pause_and_play(driver, pause_delay=500)
        time.sleep(0.5)

        # Configurar audio
        YouTubeJSUtils.configure_audio(driver, muted=False, volume=1.0)
        
        # Intentar hacer clic en botón play si existe
        try:
            play_button = driver.find_element(By.CSS_SELECTOR, ".ytp-play-button")
            if "ytp-play-button" in play_button.get_attribute("class"):
                log("Haciendo clic en botón play...")
                play_button.click()
                time.sleep(0.5)
        except:
            log("No se encontró botón de play", "DEBUG")
        
        # Intentar hacer clic en el área del video
        try:
            video_element = driver.find_element(By.TAG_NAME, "video")
            driver.execute_script("arguments[0].click();", video_element)
        except:
            log("No se pudo hacer clic en el video", "DEBUG")
        
        return True
        
    except Exception as e:
        log(f"Error en método agresivo: {e}", "ERROR")
        return False


def diagnose_video_state(driver):
    """Diagnóstica el estado detallado del video para debugging."""
    try:
        log("Diagnosticando estado del video en Firefox...", "DEBUG")
            
        video_state = YouTubeJSUtils.get_detailed_video_state(driver)
        
        if video_state:
            log(f"Estado del video: paused={video_state.get('paused', 'unknown')}, ended={video_state.get('ended', 'unknown')}", "DEBUG")
            
            current_time = video_state.get('currentTime')
            duration = video_state.get('duration')
            
            if current_time is not None and duration is not None:
                log(f"Tiempo: {current_time:.1f}/{duration:.1f}s", "DEBUG")
            else:
                log(f"Tiempo: {current_time}/{duration}s", "DEBUG")
                
            log(f"Audio: muted={video_state.get('muted', 'unknown')}, volume={video_state.get('volume', 'unknown')}", "DEBUG")
            log(f"Ready: {video_state.get('readyState', 'unknown')}, Network: {video_state.get('networkState', 'unknown')}", "DEBUG")
            
            if video_state.get('error'):
                log(f"Error en video: {video_state['error']}", "ERROR")
                
            return video_state
        else:
            log("No se encontró elemento video", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error diagnosticando estado del video: {e}", "ERROR")
        return None


def get_final_diagnostic_state(driver):
    """Obtiene estado final para diagnóstico."""
    try:
        final_state = YouTubeJSUtils.get_final_state_summary(driver)
        log(f"Estado final después de intentos: {final_state}", "DEBUG")
        return final_state
    except Exception as e:
        log(f"Error obteniendo estado final: {e}", "ERROR")
        return None


def check_stream_continuity_refactored(driver):
    """Verifica si el stream sigue activo y detecta cambios de programación."""
    try:
        log("Verificando continuidad del stream...", "DEBUG")
        
        stream_info = YouTubeJSUtils.get_stream_info(driver)
        log(f"Estado del stream: {stream_info}", "DEBUG")
        
        # Verificar si hay problemas
        if stream_info.get('hasError'):
            log("Error detectado en el reproductor de YouTube", "ERROR")
            return False, "player_error"
            
        if stream_info.get('isOffline'):
            log("Canal detectado como offline", "WARN")
            return False, "channel_offline"
            
        if not stream_info.get('hasVideo'):
            log("No se encontró elemento de video", "ERROR")
            return False, "no_video"
            
        if not stream_info.get('isLive'):
            log("El contenido no es un stream en vivo", "WARN")
            return False, "not_live"
            
        if stream_info.get('videoEnded'):
            log("El video ha terminado", "WARN")
            return False, "video_ended"
            
        # Todo parece estar bien
        current_title = stream_info.get('currentTitle', 'Desconocido')
        channel_name = stream_info.get('channelName', 'Desconocido')
        log(f"Stream activo: '{current_title}' en '{channel_name}'", "SUCCESS")
        
        return True, {
            'title': current_title,
            'channel': channel_name,
            'url': stream_info.get('currentUrl'),
            'is_live': stream_info.get('isLive')
        }
        
    except Exception as e:
        log(f"Error verificando continuidad del stream: {e}", "ERROR")
        return False, "check_error"
