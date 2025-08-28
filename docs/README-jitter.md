# Guía de Verificación - Jitter Buffer y Timestamps RTP

## Resumen de Cambios

Este documento describe las mejoras implementadas en el sistema de timestamps RTP y jitter buffer para resolver inconsistencias y mejorar la calidad del audio.

### Problemas Solucionados

1. **Cliente**: El timestamp RTP ahora se mantiene separado del sequence_number, evitando inconsistencias por batching
2. **Servidor**: Captura timestamps de llegada usando `time.monotonic()` y calcula jitter según RFC3550
3. **Jitter Buffer**: Ordenamiento modular de secuencias y lógica mejorada para corrección de `next_seq`

## Verificación Local

### 1. Captura de Paquetes con tcpdump

```bash
# Capturar tráfico RTP en el puerto 6001
sudo tcpdump -i any -w rtp_capture.pcap port 6001

# O capturar solo durante una prueba específica (30 segundos)
timeout 30s sudo tcpdump -i any -w rtp_test.pcap port 6001
```

### 2. Análisis con tshark/Wireshark

```bash
# Mostrar información básica de paquetes RTP
tshark -r rtp_capture.pcap -Y "rtp" -T fields -e frame.time_relative -e rtp.seq -e rtp.timestamp -e rtp.ssrc

# Verificar consistencia de timestamps
tshark -r rtp_capture.pcap -Y "rtp" -T fields -e rtp.seq -e rtp.timestamp | awk '
{
    if (NR > 1) {
        seq_diff = $1 - prev_seq
        ts_diff = $2 - prev_ts
        if (seq_diff == 1) {
            print "Seq:", $1, "TS diff:", ts_diff, "(esperado: 960)"
        }
    }
    prev_seq = $1; prev_ts = $2
}'

# Análisis de jitter con tshark
tshark -r rtp_capture.pcap -Y "rtp" -z rtp,streams
```

### 3. Validación de Deltas de Timestamp

```bash
# Script para verificar que los deltas de timestamp sean consistentes (960 samples por frame)
cat > verify_timestamps.py << 'EOF'
#!/usr/bin/env python3
import sys

def verify_rtp_timestamps(pcap_file):
    import subprocess
    
    # Extraer timestamps y secuencias con tshark
    cmd = ["tshark", "-r", pcap_file, "-Y", "rtp", "-T", "fields", 
           "-e", "rtp.seq", "-e", "rtp.timestamp", "-e", "rtp.ssrc"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error ejecutando tshark: {result.stderr}")
        return
    
    streams = {}
    
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
            
        parts = line.split('\t')
        if len(parts) >= 3:
            seq, ts, ssrc = int(parts[0]), int(parts[1]), parts[2]
            
            if ssrc not in streams:
                streams[ssrc] = []
            streams[ssrc].append((seq, ts))
    
    # Verificar cada stream
    for ssrc, packets in streams.items():
        packets.sort()  # Ordenar por secuencia
        print(f"\n=== Stream SSRC {ssrc} ===")
        
        inconsistencies = 0
        for i in range(1, len(packets)):
            seq_prev, ts_prev = packets[i-1]
            seq_curr, ts_curr = packets[i]
            
            if seq_curr == (seq_prev + 1) % 65536:
                ts_diff = (ts_curr - ts_prev) % (2**32)
                expected_diff = 960  # FRAME_SIZE
                
                if ts_diff != expected_diff:
                    print(f"  INCONSISTENCIA: seq {seq_prev}->{seq_curr}, ts_diff={ts_diff} (esperado: {expected_diff})")
                    inconsistencies += 1
        
        print(f"  Total de inconsistencias: {inconsistencies} de {len(packets)-1} transiciones")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 verify_timestamps.py <archivo.pcap>")
        sys.exit(1)
    
    verify_rtp_timestamps(sys.argv[1])
EOF

chmod +x verify_timestamps.py
python3 verify_timestamps.py rtp_capture.pcap
```

### 4. Verificación de Logs del Servidor

```bash
# Los logs del servidor ahora incluyen información detallada de jitter
# Buscar logs de instrumentación:
grep "\[UDP\]\[Recv\]" server_logs.txt | head -10
grep "\[Jitter\]" server_logs.txt | head -10
grep "\[Buffer\]\[Process\]" server_logs.txt | head -10
```

### 5. Prueba de Stress

```bash
# Ejecutar múltiples clientes para verificar el comportamiento bajo carga
cd client/
for i in {1..3}; do
    python3 main.py "https://stream-url.com/live" "ffmpeg" &
done

# Dejar correr por 60 segundos y luego analizar
sleep 60
pkill -f "python3 main.py"

# Verificar archivos WAV generados
ls -la server/records/*/
```

## Métricas de Verificación

### Timestamps RTP Esperados
- **Delta fijo**: 960 samples entre paquetes consecutivos
- **Frecuencia**: 48000 Hz
- **Duración por frame**: 20ms (960/48000)

### Jitter Aceptable
- **Jitter típico**: < 5ms en red local
- **Jitter alto**: > 20ms indica problemas de red
- **Threshold de timeout**: 80ms (MAX_WAIT)

### Logs Clave a Verificar

1. **Cliente**: `📤 Enviado paquete seq=X, rtp_ts=Y`
2. **Servidor**: `[UDP][Recv] SSRC=X, seq=Y, rtp_ts=Z, arrival=T`
3. **Jitter**: `[Jitter] Cliente X: jitter=Y.Zms`
4. **Buffer**: `[Buffer][Process] Procesando seq=X, rtp_ts=Y`

## Reversión si es Necesario

```bash
# Si hay problemas, revertir a la versión anterior
git checkout main
git pull origin main

# O revertir cambios específicos
git revert <commit-hash>
```

## Problemas Conocidos y Soluciones

### Timestamp Wraparound
- Los timestamps RTP usan 32 bits y pueden hacer wraparound
- El código maneja esto usando aritmética modular: `% (2**32)`

### Reordenamiento de Paquetes
- El jitter buffer usa ordenamiento modular para manejar secuencias desordenadas
- Threshold configurable para evitar saltos innecesarios

### Memoria y Performance
- Los buffers ahora almacenan más información por paquete
- Garbage collection explícito en segmentación de archivos WAV