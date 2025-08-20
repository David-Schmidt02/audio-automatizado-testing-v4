"""
Gestión del servidor X virtual (Xvfb) para el proyecto de automatización.
"""
import os
import subprocess
import time
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from my_logger import log
from config import XVFB_SCREEN, XVFB_RESOLUTION


def start_xvfb(display_number):
    """
    Inicia el servidor X virtual (Xvfb).
    
    Returns:
        subprocess.Popen: Proceso de Xvfb iniciado
    """
    log(f"Iniciando Xvfb con DISPLAY: {display_number}")
    xvfb_proc = subprocess.Popen([
        "Xvfb", display_number, 
        "-screen", XVFB_SCREEN, XVFB_RESOLUTION,
        "-nolisten", "tcp",  # No escuchar conexiones TCP
        "-noreset",          # No reiniciar cuando se desconecta el último cliente
        "+extension", "RANDR"  # Extensión para cambio de resolución
    ])
    os.environ["DISPLAY"] = display_number
    
    # Verificación activa en lugar de sleep fijo
    log("Esperando que Xvfb esté listo...")
    for attempt in range(10):  # Máximo 2 segundos (10 * 0.2s)
        try:
            # Verificar si Xvfb está respondiendo
            result = subprocess.run(
                ["xdpyinfo", "-display", display_number], 
                capture_output=True, 
                timeout=0.5
            )
            if result.returncode == 0:
                log(f"Xvfb listo en {(attempt + 1) * 0.2:.1f}s", "SUCCESS")
                return xvfb_proc
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            log("❌ Xvfb no está listo", "ERROR")
            return None
        time.sleep(0.2)
    
    # Fallback: si no se puede verificar, asumir que está listo
    log("Xvfb iniciado (verificación timeout)", "SUCCESS")
    return xvfb_proc


def stop_xvfb(xvfb_proc):
    """
    Detiene el servidor X virtual (Xvfb).
    
    Args:
        xvfb_proc (subprocess.Popen): Proceso de Xvfb a detener
    """
    log("Closing Xvfb...")
    xvfb_proc.terminate()
    xvfb_proc.wait()
    log("✅ Cleanup: Xvfb complete.", "SUCCESS")