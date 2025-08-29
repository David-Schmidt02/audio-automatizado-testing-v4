echo "=== Instalando Chromium clásico (ppa:xtradeb/apps) ==="
sudo add-apt-repository ppa:xtradeb/apps -y
sudo apt update
sudo apt install chromium -y

echo "=== Instalando Google Chrome estable ==="
if ! command -v google-chrome &> /dev/null; then
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/google-chrome-stable_current_amd64.deb
    sudo apt install /tmp/google-chrome-stable_current_amd64.deb -y
    rm /tmp/google-chrome-stable_current_amd64.deb
else
    echo "Google Chrome ya está instalado."
fi

echo "=== SETUP AUDIO AUTOMATIZADO TESTING V4 - SISTEMA RTP ==="
echo "Sistema de streaming de audio en tiempo real con RTP usando Python 3.12+"
echo ""

# Limpiar repositorios problemáticos antes de actualizar
echo "=== Limpiando repositorios problemáticos ==="
sudo rm -f /etc/apt/sources.list.d/*chromium-dev*
sudo rm -f /etc/apt/sources.list.d/*saiarcot895*
sudo apt-key del $(sudo apt-key list | grep -B1 -A1 "saiarcot895\|chromium-dev" | grep "pub" | cut -d'/' -f2 | cut -d' ' -f1) 2>/dev/null || true

# Actualizar sistema
echo "=== Actualizando sistema ==="
sudo apt update || {
    echo "Error en apt update. Intentando limpiar y reparar..."
    sudo apt clean
    sudo apt autoremove -y
    sudo dpkg --configure -a
    sudo apt --fix-broken install -y
    sudo apt updatez
}

# Verificar Python 3.12 (viene por defecto en Ubuntu 24.04+)
echo "=== Verificando Python 3.12 ==="
if ! command -v python3.12 &> /dev/null; then
    echo "Error: Python 3.12 no está disponible."
    echo "Este script requiere Ubuntu 24.04 o superior con Python 3.12"
    exit 1
else
    echo "Python 3.12 disponible:"
    python3.12 --version
fi

# Instalar dependencias del sistema para RTP streaming
echo "=== Instalando dependencias del sistema ==="
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    pulseaudio \
    pulseaudio-utils \
    ffmpeg \
    wget \
    unzip \
    curl \
    netcat-openbsd \
    net-tools \
    xdotool

echo "✅ Dependencias del sistema instaladas"

# Verificar que estamos en un entorno virtual
if [[ "$VIRTUAL_ENV" == "" ]]; then
  echo "Error: No se detectó un entorno virtual activado."
  echo "Por favor, crea y activa un entorno virtual antes de ejecutar este script:"
  echo "  python3.12 -m venv audio-test-env"
  echo "  source audio-test-env/bin/activate"
  exit 1
fi

echo "Entorno virtual detectado: $VIRTUAL_ENV"

# Verificar que pip esté disponible en el entorno virtual
echo "=== Configurando pip para Python 3.12 en el entorno virtual ==="
if ! python3.12 -m pip --version &> /dev/null; then
    echo "pip no disponible para Python 3.12 en el entorno virtual. Instalando..."
    
    # Descargar e instalar pip directamente
    wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
    python3.12 /tmp/get-pip.py
    rm /tmp/get-pip.py
    
    # Verificar instalación
    if python3.12 -m pip --version; then
        echo "pip instalado correctamente en el entorno virtual"
    else
        echo "Error: No se pudo instalar pip en el entorno virtual."
        exit 1
    fi
else
    echo "pip ya está disponible para Python 3.12 en el entorno virtual"
fi

# Actualizar pip e instalar dependencias Python para RTP
echo "=== Instalando dependencias Python para RTP ==="
python3.12 -m pip install --upgrade pip

# Verificar que requirements.txt existe
if [ -f "requirements.txt" ]; then
    echo "📦 Instalando desde requirements.txt..."
    python3.12 -m pip install -r requirements.txt
    echo "✅ Dependencias Python instaladas desde requirements.txt"
else
    echo "⚠️  requirements.txt no encontrado. Instalando dependencias manualmente..."
    python3.12 -m pip install selenium>=4.0.0 webdriver-manager>=3.8.0 rtp>=0.0.3
    echo "✅ Dependencias básicas instaladas"
fi

# Verificar instalación de librerías RTP críticas
echo "🔍 Verificando instalación de librería RTP..."
if python3.12 -c "import rtp; print(f'✅ RTP library: {rtp.__version__ if hasattr(rtp, \"__version__\") else \"installed\"}')" 2>/dev/null; then
    echo "✅ Librería RTP disponible"
else
    echo "❌ Error: Librería RTP no está disponible"
    echo "Intentando instalación manual..."
    python3.12 -m pip install rtp --force-reinstall
fi

# Configurar PulseAudio para pruebas automatizadas
echo "=== Configurando PulseAudio ==="

# Crear configuración de PulseAudio para pruebas
mkdir -p "$HOME/.config/pulse"

# Asegurar que PulseAudio esté funcionando
if ! pulseaudio --check; then
    echo "Iniciando PulseAudio..."
    pulseaudio --start
else
    echo "PulseAudio ya está ejecutándose"
fi

# Verificar que tenemos dispositivos de audio disponibles
echo "Dispositivos de audio disponibles:"
pactl list short sources
pactl list short sinks

# Configurar variables de entorno para RTP y audio streaming
echo "=== Configurando variables de entorno ==="
cat >> "$HOME/.bashrc" << 'EOF'

# Variables para RTP Audio Streaming v4
export PULSE_RUNTIME_PATH="/run/user/$(id -u)/pulse"
export DISPLAY=${DISPLAY:-:0}
export MOZ_DISABLE_CONTENT_SANDBOX=1
export RTP_AUDIO_PORT=6001
export RTP_AUDIO_IP=172.21.100.130
EOF

echo "✅ Variables de entorno para RTP agregadas a ~/.bashrc"

# Verificar instalación
echo "=== Verificando instalación ==="
echo "🐍 Python:"
python3.12 --version

echo "📦 Dependencias Python:"
python3.12 -c "import selenium; print(f'  Selenium: {selenium.__version__}')"
python3.12 -c "import rtp; print(f'  RTP: {rtp.__version__ if hasattr(rtp, \"__version__\") else \"installed\"}')" 2>/dev/null || echo "  RTP: ❌ No disponible"


echo "🎵 Audio:"
pulseaudio --version
ffmpeg -version | head -1

echo "🔧 Herramientas de red:"
if command -v netcat &> /dev/null; then
    echo "  Netcat: ✅ Disponible"
else
    echo "  Netcat: ❌ No disponible"
fi


echo ""
echo "=== INSTALACIÓN COMPLETADA - AUDIO AUTOMATIZADO TESTING V4 ==="
echo "🚀 Sistema RTP listo para streaming de audio"
echo "🐍 Python 3.12 configurado correctamente"  
echo "🎵 PulseAudio configurado para captura de audio"
echo "📦 FFmpeg listo para procesamiento de audio"
echo ""
echo "📋 Próximos pasos:"
echo "1. Servidor: cd server && python3.12 main.py"
echo "2. Cliente: cd client && python3.12 main.py --url <stream-url>"
echo ""
echo "💡 NOTA: Si tienes problemas de audio, reinicia PulseAudio con:"
echo "   pulseaudio -k && pulseaudio --start"