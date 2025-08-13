# Audio Automatizado Testing v4 - Sistema RTP de Streaming de Audio

Sistema de captura y streaming de audio en tiempo real usando **RTP** (Real-time Transport Protocol) con **Firefox** y **FFmpeg**. Soporta múltiples clientes simultáneos diferenciados por SSRC.

## 🏗️ Arquitectura del Sistema

```
Cliente (Linux)          Servidor (Linux/Windows)
┌─────────────────┐     ┌─────────────────────┐
│   Firefox       │     │                     │
│   ↓             │     │   UDP Socket        │
│   PulseAudio    │     │   ↓                 │
│   ↓             │────▶│   RTP Parser        │
│   FFmpeg        │     │   ↓                 │
│   ↓             │     │   WAV Generator     │
│   RTP Client    │     │   (por SSRC)        │
└─────────────────┘     └─────────────────────┘
```

## 📁 Estructura del Proyecto

```
audio-automatizado-testing-v4/
├── README.md                    # Documentación principal
├── my_logger.py                 # Sistema de logging con colores
├── client/                      # 🖥️ Cliente (captura y envío)
│   ├── main.py                  # Script principal del cliente
│   ├── audio_recorder.py        # Grabación con FFmpeg y segmentación
│   └── rtp_client.py           # Creación y envío de paquetes RTP
└── server/                      # 🌐 Servidor (recepción y almacenamiento)
    └── main.py                  # Receptor RTP y generador de WAV
```

## 🚀 Componentes Principales

### 📱 Cliente (`client/`)
- **`main.py`**: Orquestador principal que coordina Firefox, PulseAudio y grabación
- **`audio_recorder.py`**: Maneja FFmpeg para captura continua con segmentación automática
- **`rtp_client.py`**: Encapsula audio en paquetes RTP y los envía via UDP

### 🖥️ Servidor (`server/`)
- **`main.py`**: Recibe paquetes RTP, los parsea y genera archivos WAV por cliente (SSRC)

### 🔧 Utilidades
- **`my_logger.py`**: Sistema de logging centralizado con colores y timestamps

## ⚙️ Características Técnicas

- **🎵 Audio**: 48kHz, 16-bit, Mono
- **📦 RTP**: PayloadType DYNAMIC_96, segmentación en frames de 160 samples
- **🔄 Streaming**: UDP en tiempo real con identificación por SSRC
- **📝 Archivos**: WAV automáticos cada 240 paquetes (~5 segundos)
- **🖥️ Multi-cliente**: Soporte simultáneo diferenciado por SSRC

## 🚀 Inicio Rápido

### Servidor (Receptor)
```bash
# 1. Instalar dependencias
pip install rtp wave

# 2. Ejecutar servidor
cd server/
python main.py
```

### Cliente (Transmisor)  
```bash
# 1. Instalar dependencias del sistema (Ubuntu)
sudo apt update
sudo apt install -y firefox pulseaudio-utils ffmpeg python3-pip

# 2. Instalar dependencias Python
pip install selenium rtp wave

# 3. Ejecutar cliente
cd client/
python main.py --url "https://example.com/live"
```

## 📋 Requisitos del Sistema

### Cliente (Linux)
- **Ubuntu 20.04+** o distribución compatible
- **Firefox** (para automatización web)
- **PulseAudio** (manejo de audio del sistema)
- **FFmpeg** (captura y procesamiento de audio)
- **Python 3.12+** con librerías: `selenium`, `rtp`, `wave`

### Servidor (Linux/Windows)
- **Python 3.12+** con librerías: `rtp`, `wave`
- **Puerto UDP 6001** disponible (configurable)

## 🔧 Configuración

### Variables de Configuración

#### Cliente (`client/rtp_client.py`)
```python
DEST_IP = "172.21.100.130"    # IP del servidor
DEST_PORT = 6001              # Puerto del servidor
FRAME_SIZE = 160              # Samples por paquete RTP
SAMPLE_RATE = 48000           # Frecuencia de muestreo
```

#### Servidor (`server/main.py`)
```python
LISTEN_IP = "172.21.100.130"  # IP de escucha
LISTEN_PORT = 6001            # Puerto de escucha
CHANNELS = 1                  # Mono
```

## 🎮 Uso Detallado

### 1. Iniciar Servidor
```bash
cd server/
python main.py
# Salida: 🎧 Listening for RTP audio on 172.21.100.130:6001
```

### 2. Ejecutar Cliente
```bash
cd client/
python main.py --url "https://stream-url.com/live"
```

### 3. Archivos Generados
```
server/
├── record-20250813-143022-1234567890.wav  # Cliente SSRC: 1234567890
├── record-20250813-143025-9876543210.wav  # Cliente SSRC: 9876543210
└── ...
```

## 🛠️ Solución de Problemas

### Problemas de Audio (Cliente Linux)
```bash
# Reiniciar PulseAudio
pulseaudio -k && pulseaudio --start

# Verificar dispositivos de audio
pactl list sinks short

# Verificar procesos Firefox
ps aux | grep firefox
```

### Problemas de Red
```bash
# Verificar puerto servidor
netstat -tuln | grep 6001

# Test de conectividad
telnet 172.21.100.130 6001
```

### Variables de Entorno para VM
```bash
export DISPLAY=:0
export MOZ_DISABLE_CONTENT_SANDBOX=1
```

## 📊 Logging y Debug

El sistema incluye logging detallado con colores:
- **INFO** (Cyan): Información general
- **DEBUG** (Magenta): Detalles técnicos  
- **ERROR** (Rojo): Errores del sistema
- **SUCCESS** (Verde): Operaciones exitosas

## 🔄 Flujo de Datos

1. **Cliente**: Firefox reproduce stream → PulseAudio captura → FFmpeg segmenta → RTP envía
2. **Red**: Paquetes RTP via UDP 
3. **Servidor**: Recibe RTP → Extrae payload → Agrupa por SSRC → Genera WAV

## 📈 Rendimiento

- **Latencia**: ~160ms (frame size + network)
- **Throughput**: ~384 kbps por cliente (48kHz * 16bit * 1ch)
- **Clientes simultáneos**: Limitado por ancho de banda y CPU

