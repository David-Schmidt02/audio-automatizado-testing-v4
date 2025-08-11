var video = document.querySelector('video');
if (video) {
    video.muted = false;
    video.volume = 1.0;
    // NO configurar loop para live streams

    // ESTRATEGIA PARA LIVE STREAMS: Interceptar eventos de pausa
    var originalPause = video.pause;
    video.pause = function() {
        console.log('Live stream pause intercepted and blocked!');
        // No ejecutar pause en live streams
    };

    // Prevenir que se pause automáticamente con múltiples listeners
    ['pause', 'suspend', 'stalled', 'waiting'].forEach(function(eventType) {
        video.addEventListener(eventType, function(e) {
            console.log('Live stream event intercepted:', eventType);
            setTimeout(function() {
                if (video.paused && !video.ended) {
                    video.play().catch(function(error) {
                        console.log('Error al reproducir live stream:', error);
                    });
                }
            }, 100);  // Pausa más larga para live streams
        });
    });

    // Interceptar eventos de conexión de red para live streams
    video.addEventListener('loadstart', function() {
        console.log('Live stream loading started');
    });

    video.addEventListener('canplay', function() {
        console.log('Live stream can play');
        if (video.paused) {
            video.play().catch(function(error) {
                console.log('Error en canplay:', error);
            });
        }
    });

    // Interceptar eventos de visibilidad de página
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            console.log('Live stream page hidden detected, maintaining stream...');
        } else {
            console.log('Live stream page visible again, ensuring stream plays...');
            if (video.paused && !video.ended) {
                video.play().catch(function(error) {
                    console.log('Error al reproducir en visibilitychange:', error);
                });
            }
        }
    });

    // Asegurar que el live stream esté reproduciendo
    video.play().catch(function(error) {
        console.log('Error al reproducir live stream inicial:', error);
    });

    // Detectar si es realmente un live stream
    setTimeout(function() {
        var isLive = video.duration === Infinity || isNaN(video.duration);
        console.log('Is live stream:', isLive, 'Duration:', video.duration);
        if (isLive) {
            console.log('Live stream confirmed - continuous playback mode');
        }
    }, 2000);
}
