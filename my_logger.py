import logging
import datetime
import os

# Configuración del logger
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

# Colores para el logging
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'  # Reset color

def log(message, level="INFO"):
    """Sistema de logging con colores usando hora local y guardado en archivo."""
    now = datetime.datetime.now()
    timestamp = now.strftime("%H:%M:%S")

    color_map = {
        "INFO": Colors.CYAN,
        "WARN": Colors.YELLOW,
        "ERROR": Colors.RED,
        "SUCCESS": Colors.GREEN,
        "DEBUG": Colors.MAGENTA,
        "HEADER": Colors.BLUE + Colors.BOLD
    }
    color = color_map.get(level, Colors.WHITE)
    print(f"{color}[{timestamp}] [{level}] {message}{Colors.END}")

    # Guardar en archivo logs/server.log (sobrescribe al iniciar)
    log_dir = "logs"
    log_file = os.path.join(log_dir, "server.log")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    # Si es la primera vez, abre en modo 'w', luego en modo 'a'
    if not hasattr(log, "_file_initialized"):
        mode = "w"
        log._file_initialized = True
    else:
        mode = "a"
    with open(log_file, mode, encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")