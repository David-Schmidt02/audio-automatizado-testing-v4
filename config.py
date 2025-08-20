BUFFER_SIZE = 4096
FRAME_SIZE = 960
SAMPLE_RATE = 48000
CHANNELS = 1
RTP_VERSION = 2
PAYLOAD_TYPE = 96
SAMPLE_FORMAT = "int16"

# IPs
# Configuracion para el Cliente: Dirección IP y puerto del servidor RTP
DEST_IP = "172.21.100.130"  
DEST_PORT = 6001
METADATA_PORT = 6002
# Configuracion para el Servidor: Dirección IP y puerto del cliente RTP
LISTEN_IP = "172.21.100.130" # Debe ser la de la misma máquina Host 192.168.0.....
LISTEN_PORT = 6001 # Puerto de escucha del cliente RTP, debe ser el mismo que DEST_PORT 
NUM_DISPLAY_PORT = 6003

# Configuracion para XVFB
XVFB_DISPLAY = None
XVFB_SCREEN = "0"
#XVFB_RESOLUTION = "1920x1080x24"
XVFB_RESOLUTION = "1024x768x24"
# Configuracion para el WAV y el JITTER BUFFER
INACTIVITY_TIMEOUT = 5  # segundos de inactividad para cerrar WAV
JITTER_BUFFER_SIZE = 20
MAX_WAIT = 0.08  # Máximo tiempo de espera para procesar paquetes en el jitter buffer
WAV_SEGMENT_SECONDS = 180  # Segundos de cada segmento WAV

HEADLESS = None