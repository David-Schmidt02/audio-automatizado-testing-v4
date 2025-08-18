BUFFER_SIZE = 4096
FRAME_SIZE = 960
SAMPLE_RATE = 48000
CHANNELS = 1
RTP_VERSION = 2
PAYLOAD_TYPE = 96
SAMPLE_FORMAT = "int16"

# IPs
# Dirección IP y puerto del servidor RTP
DEST_IP = "172.21.100.130"  
DEST_PORT = 6001
# Dirección IP y puerto del cliente RTP
LISTEN_IP = "172.21.100.130" # Debe ser la de la misma máquina Host 192.168.0.....
LISTEN_PORT = 6001 # Puerto de escucha del cliente RTP, debe ser el mismo que DEST_PORT 