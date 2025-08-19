# Audio Automatizado Testing v4 - Instalación Modular y Sistema RTP

Sistema automatizado para grabar audio desde streams de video y transmitirlo en tiempo real usando **RTP**. Incluye automatización de navegador, captura de audio, segmentación y almacenamiento, pensado para Ubuntu Server 24.04+ y compatible con Windows en el lado servidor.

---

## 🏗️ Arquitectura del Sistema

```
Cliente (Linux)          Servidor (Linux/Windows)
┌─────────────────┐     ┌─────────────────────┐
│   Firefox/Chrome│     │                     │
│   ↓             │     │   UDP Socket        │
│   PulseAudio    │     │   ↓                 │
│   ↓             │────▶│   RTP Parser        │
│   FFmpeg        │     │   ↓                 │
│   ↓             │     │   WAV Generator     │
│   RTP Client    │     │   (por SSRC)        │
└─────────────────┘     └─────────────────────┘
```

---

## 📋 Requisitos del Sistema

### Cliente (Linux)
- **Ubuntu Server 24.04+**
- **Python 3.12+** y **python3.12-venv**
- **Firefox** o **Google Chrome**
- **PulseAudio**
- **FFmpeg**
- **Git**

### Servidor (Linux/Windows)
- **Python 3.12+**
- **Librerías Python**: `rtp`, `wave`
- **Puerto UDP 6001** disponible (configurable)

---

## 🚀 Instalación Paso a Paso (Cliente Ubuntu 24.04+)

### 1. Instalar Python y venv

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv git
```

### 2. Crear y activar entorno virtual

```bash
python3.12 -m venv audio-test-env
source audio-test-env/bin/activate
```

### 3. Clonar el repositorio dentro del entorno

```bash
# (Asegúrate de tener el entorno virtual activado)
git clone https://github.com/David-Schmidt02/audio-automatizado-testing-v4.git
cd audio-automatizado-testing-v4
```

### 4. Instalar dependencias del sistema

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 5. Instalar dependencias Python

```bash
# (El setup.sh ya se encarga e instalarlo)
pip install -r requirements.txt
```

---

## 📁 Estructura del Proyecto

```
audio-automatizado-testing-v4/
├── README.md                    # Documentación principal
├── my_logger.py                 # Sistema de logging con colores
├── client/                      # 🖥️ Cliente (captura y envío)
│   ├── main.py                  # Script principal del cliente
│   ├── audio_recorder.py        # Grabación con FFmpeg y segmentación
│   └── rtp_client.py            # Creación y envío de paquetes RTP
├── server/                      # 🌐 Servidor (recepción y almacenamiento)
│   └── main.py                  # Receptor RTP y generador de WAV
├── scripts/
│   └── setup.sh                 # Instalador automatizado (opcional)
├── requirements.txt             # Dependencias Python
└── config.py, my_logger.py, ...
```

---

## ⚙️ Características Técnicas

- **Audio**: 48kHz, 16-bit, Mono
- **RTP**: PayloadType DYNAMIC_96, frames de 160 samples
- **Streaming**: UDP en tiempo real, identificación por SSRC
- **Archivos**: WAV automáticos cada 240 paquetes (~5 segundos)
- **Multi-cliente**: Soporte simultáneo por SSRC

---

## 🕹️ Uso Básico

### Servidor
```bash
cd server/
python main.py
# Salida: 🎧 Listening for RTP audio on <IP>:6001
```

### Cliente
```bash
cd client/
python main.py --url "https://stream-url.com/live"
```

---

## 🔧 Configuración Rápida

### Cliente (`client/rtp_client.py`)
```python
DEST_IP = "<IP del servidor>"
DEST_PORT = 6001
FRAME_SIZE = 160
SAMPLE_RATE = 48000
```

### Servidor (`server/main.py`)
```python
LISTEN_IP = "<IP de escucha>"
LISTEN_PORT = 6001
CHANNELS = 1
```

---

## 🛠️ Solución de Problemas

### PulseAudio no responde
```bash
pulseaudio -k && pulseaudio --start
```

### Verificar dispositivos de audio
```bash
pactl list sinks short
```

### Problemas de red
```bash
netstat -tuln | grep 6001
telnet <IP servidor> 6001
```

### Variables de entorno para VM
```bash
export DISPLAY=:0
export MOZ_DISABLE_CONTENT_SANDBOX=1
```

---

## 📊 Logging y Debug

- **INFO** (Cyan): Información general
- **DEBUG** (Magenta): Detalles técnicos
- **ERROR** (Rojo): Errores del sistema
- **SUCCESS** (Verde): Operaciones exitosas

---

## 🔄 Flujo de Datos

1. **Cliente**: Firefox/Chrome reproduce stream → PulseAudio captura → FFmpeg segmenta → RTP envía
2. **Red**: Paquetes RTP via UDP
3. **Servidor**: Recibe RTP → Extrae payload → Agrupa por SSRC → Genera WAV

---

## 📈 Rendimiento

- **Latencia**: ~160ms (frame size + red)
- **Throughput**: ~384 kbps por cliente (48kHz * 16bit * 1ch)
- **Clientes simultáneos**: Limitado por ancho de banda y CPU

---

## 📝 Notas

- Siempre activa el entorno virtual antes de instalar o ejecutar scripts Python.
- El script `setup.sh` puede automatizar la instalación en sistemas compatibles.
- Para personalizaciones, revisa los archivos de configuración y los scripts en `client/` y `server/`.

---

## 🧩 Créditos y Licencia

Desarrollado por David Schmidt. Uso libre para fines educativos y de testing.
