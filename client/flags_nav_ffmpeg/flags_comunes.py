# Flags para afinidad y prioridad de CPU (ejemplo: usar con taskset, chrt, nice)
CPU_FLAGS = {
    # Afinidad de CPU: lista de núcleos a usar (ejemplo: "0,1" para los dos primeros cores)
    #"taskset": "0",
    # Prioridad en tiempo real (chrt) o nice
    #"chrt": 20,  # Prioridad FIFO (más alto = más prioridad)
    #"nice": -10, # Prioridad de nice (más bajo = más prioridad)
}
CHROME_CHROMIUM_COMMON_FLAGS = [
    "--window-size=1920,1080",  # Tamaño de ventana
    "--incognito",  # Modo incógnito -> Ignora el perfil creado
    "--autoplay-policy=no-user-gesture-required",  # Permitir autoplay sin interacción del usuario
    "--disable-notifications",  # Desactivar notificaciones
    "--disable-popup-blocking",  # Desactivar bloqueo de ventanas emergentes
    "--disable-extensions",  # Desactivar extensiones
    "--no-first-run",  # Ignorar la página de primer uso
    "--no-default-browser-check",  # Ignorar verificación de navegador predeterminado
    "--disable-features=ChromeWhatsNewUI,Translate,BackgroundNetworking,Sync",  # Desactivar características no deseadas
    "--disable-component-update",  # Desactivar actualizaciones de componentes
    "--disable-default-apps",  # Desactivar aplicaciones predeterminadas
    "--disable-translate",  # Desactivar traducción
    "--disable-infobars",  # Desactivar barras de información
    "--disable-signin-promo",  # Desactivar promoción de inicio de sesión
    #"--disable-dev-shm-usage",  # Desactivar uso de /dev/shm -> Involucra la memoria compartida, poca seguridad excepto que estés en docker
    "--start-minimized",
]

GRAPHICS_MIN_FLAGS = [
    "--disable-gpu", # Desactivar GPU -> Util si no se posee GPU
    #"--disable-accelerated-2d-canvas",  # Desactivar aceleración de canvas 2D
    "--disable-accelerated-video-decode",  # Desactivar aceleración de decodificación de video
    "--disable-accelerated-video",  # Desactivar aceleración de video
    #"--disable-3d-apis",  # Desactivar APIs 3D
    "--disable-webgl",  # Desactivar WebGL
    "--disable-webgl2",  # Desactivar WebGL2
    #"--disable-features=CanvasOopRasterization,WebGLDraftExtensions,WebGL2ComputeContext",
    #"--single-process",
    # "--no-zygote",  # Solo si tienes problemas de procesos zombie
]

PRODUCTION_FLAGS = [
    "--no-default-browser-check", # Ignorar verificación de navegador predeterminado
    "--no-first-run",  # Ignorar la página de primer uso
    "--disable-sync",  # Desactivar sincronización
    "--disable-component-update",  # Desactivar actualizaciones de componentes
    "--disable-background-networking",  # Desactivar redes en segundo plano
    "--disable-default-apps",  # Desactivar aplicaciones predeterminadas
    # "--no-sandbox",  # Solo si es seguro en tu entorno
]