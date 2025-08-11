import os
import sys
import signal
import time
import random
import shutil
import socket
import struct
import tempfile
import subprocess
from pathlib import Path
from start_firefox import clean_and_create_selenium_profile, configuracion_firefox, open_firefox_and_play_video
# Importaciones para Selenium
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

from logger_client import log

# Parámetros
SAMPLE_RATE = 48000 # Frecuencia de muestreo, determina la calidad del audio
CHANNELS = 1 # Número de canales de audio
BIT_DEPTH = 16 # Profundidad de bits por muestra
PAYLOAD_TYPE_L16 = 96 # Tipo de carga útil para audio lineal de 16 bits
RTP_CLOCK_RATE = 48000 # Frecuencia de reloj RTP
MTU = 1500 # Unidad máxima de transmisión

firefox_proc = None
parec_proc = None
module_index = None
profile_dir = None
identificador = None
driver = None
service = Service(GeckoDriverManager().install())

def create_null_sink():
    global identificador
    identificador = random.randint(0, 100000)
    sink_name = f"rtp-stream-{identificador}"
    print(f"🎧 Creando PulseAudio sink: {sink_name}")
    output = subprocess.check_output([
        "pactl", "load-module", "module-null-sink", f"sink_name={sink_name}"
    ])
    log(f"Salida de pactl load-module:\n{output.decode().strip()}", "DEBUG")
    return sink_name, output.decode().strip()

def launch_firefox(url, sink_name):
    global identificador
    global profile_dir
    global driver
    global service
    profile_dir = clean_and_create_selenium_profile(identificador)
    # Configuración de Firefox
    firefox_options = Options()
    firefox_options = configuracion_firefox(firefox_options)
    profile = FirefoxProfile(profile_directory=profile_dir)
    firefox_options.profile = profile
    # Iniciar el navegador
    driver = open_firefox_and_play_video(firefox_options, url, sink_name, service)
    print(f"🦊 Perfil temporal: {profile_dir}")

def start_parec_and_stream(destination, pulse_device):
    global parec_proc
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    host, port = destination.split(":")
    port = int(port)
    udp_addr = (host, port)

    parec_cmd = [
        "parec",
        "--format=s16be",
        f"--rate={SAMPLE_RATE}",
        f"--channels={CHANNELS}",
        f"--device={pulse_device}"
    ]

    parec_proc = subprocess.Popen(
        parec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Tamaño de frame de 20ms
    buffer_size = (SAMPLE_RATE // 50) * CHANNELS * (BIT_DEPTH // 8)

    ssrc = random.randint(0, (1 << 32) - 1)
    seq_num = random.randint(0, 65535)
    timestamp = 0

    def rtp_header(payload_type, seq, ts, ssrc):
        v_p_x_cc = 0x80
        m_pt = payload_type & 0x7F
        return struct.pack("!BBHII", v_p_x_cc, m_pt, seq, ts, ssrc)

    def stream_audio():
        nonlocal seq_num, timestamp
        while True:
            data = parec_proc.stdout.read(buffer_size)
            if not data:
                break
            timestamp += RTP_CLOCK_RATE // 50
            header = rtp_header(PAYLOAD_TYPE_L16, seq_num, timestamp, ssrc)
            seq_num = (seq_num + 1) % 65536
            packet = header + data
            udp_sock.sendto(packet, udp_addr)

    # Hilo para logs de stderr
    import threading
    def log_stderr():
        for line in iter(parec_proc.stderr.readline, b""):
            print(f"parec: {line.decode().strip()}")

    threading.Thread(target=log_stderr, daemon=True).start()
    threading.Thread(target=stream_audio, daemon=True).start()

    return parec_proc

def cleanup():
    global driver, parec_proc, module_index, profile_dir
    print("\n🛑 Limpiando...")
    if driver:
        driver.quit()
    if parec_proc and parec_proc.poll() is None:
        parec_proc.kill()
    if module_index:
        subprocess.run(["pactl", "unload-module", module_index])
    if profile_dir and os.path.exists(profile_dir):
        shutil.rmtree(profile_dir)
    print("✅ Limpieza completa.")

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

def main():
    global parec_proc, module_index

    if len(sys.argv) != 3:
        print(f"Uso: {sys.argv[0]} <URL> <host:puerto>")
        sys.exit(1)

    url = sys.argv[1]
    destination = sys.argv[2]

    sink_name, module_index = create_null_sink()
    time.sleep(2)  # esperar inicialización sink

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    launch_firefox(url, sink_name)
    pulse_device = f"{sink_name}.monitor"
    parec_proc = start_parec_and_stream(destination, pulse_device)

    # Esperar señales
    signal.pause()

if __name__ == "__main__":
    main()
