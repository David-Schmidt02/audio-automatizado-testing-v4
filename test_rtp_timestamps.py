#!/usr/bin/env python3
"""
Test básico para validar la funcionalidad de timestamps RTP
"""
import sys
import os

# Add parent directory to path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

def test_client_rtp_timestamps():
    """Test que el cliente mantenga timestamps RTP separados"""
    from client.rtp_client import send_rtp_stream_to_server, create_rtp_packet, _rtp_timestamp_trackers
    
    # Simular datos de audio (960 samples * 2 bytes = 1920 bytes por frame)
    test_data = b'\x00' * (960 * 2 * 3)  # 3 frames de datos
    ssrc = 12345
    seq_start = 100
    
    # Limpiar trackers para test
    _rtp_timestamp_trackers.clear()
    
    # Simular envío (sin red real)
    import socket
    original_sendto = socket.socket.sendto
    sent_packets = []
    
    def mock_sendto(self, data, address):
        sent_packets.append(data)
        return len(data)
    
    socket.socket.sendto = mock_sendto
    
    try:
        final_seq = send_rtp_stream_to_server(test_data, ssrc, seq_start)
        
        # Verificar que se enviaron 3 paquetes
        print(f"✅ Enviados {len(sent_packets)} paquetes (esperado: 3)")
        assert len(sent_packets) == 3, f"Esperados 3 paquetes, enviados {len(sent_packets)}"
        
        # Verificar que el sequence number avanzó correctamente
        expected_final = (seq_start + 3) % 65536
        print(f"✅ Sequence final: {final_seq} (esperado: {expected_final})")
        assert final_seq == expected_final, f"Sequence final incorrecto: {final_seq} vs {expected_final}"
        
        # Verificar que el RTP timestamp tracker se actualizó
        expected_rtp_ts = 960 * 3  # 3 frames * 960 samples
        actual_rtp_ts = _rtp_timestamp_trackers[ssrc]
        print(f"✅ RTP timestamp final: {actual_rtp_ts} (esperado: {expected_rtp_ts})")
        assert actual_rtp_ts == expected_rtp_ts, f"RTP timestamp incorrecto: {actual_rtp_ts} vs {expected_rtp_ts}"
        
        print("✅ Test del cliente RTP pasó exitosamente")
        return True
        
    finally:
        socket.socket.sendto = original_sendto

def test_create_rtp_packet():
    """Test la creación de paquetes RTP con timestamp separado"""
    from client.rtp_client import create_rtp_packet
    
    payload = bytearray(b'\x01' * 1920)  # 960 samples * 2 bytes
    seq_num = 42
    ssrc = 12345
    rtp_timestamp = 960 * 10  # Timestamp independiente
    
    packet = create_rtp_packet(payload, seq_num, ssrc, rtp_timestamp)
    
    print(f"✅ Paquete RTP creado: seq={packet.sequenceNumber}, ts={packet.timestamp}, ssrc={packet.ssrc}")
    
    assert packet.sequenceNumber == seq_num
    assert packet.timestamp == rtp_timestamp
    assert packet.ssrc == ssrc
    assert len(packet.payload) == len(payload)
    
    print("✅ Test de create_rtp_packet pasó exitosamente")
    return True

def test_server_buffer_structure():
    """Test que el servidor maneje la nueva estructura de buffer"""
    # Cambiar al directorio server y añadir al path
    original_cwd = os.getcwd()
    server_dir = os.path.join(os.getcwd(), 'server')
    os.chdir(server_dir)
    sys.path.insert(0, server_dir)
    
    try:
        from client_manager import find_next_sequence_modular
        
        # Test de find_next_sequence_modular
        buffer_keys = [100, 102, 104, 106]  # Secuencias con huecos
        current_next = 101
        
        next_seq = find_next_sequence_modular(buffer_keys, current_next)
        print(f"✅ Próxima secuencia modular: {next_seq} (de {buffer_keys}, actual: {current_next})")
        assert next_seq == 100, f"Esperado 100, obtenido {next_seq}"
        
        # Test con wrap-around
        buffer_keys = [65535, 0, 1, 2]
        current_next = 65534
        
        next_seq = find_next_sequence_modular(buffer_keys, current_next)
        print(f"✅ Próxima secuencia modular (wrap-around): {next_seq}")
        assert next_seq == 65535, f"Esperado 65535, obtenido {next_seq}"
        
        print("✅ Test de estructura de buffer del servidor pasó exitosamente")
        return True
        
    finally:
        os.chdir(original_cwd)

def main():
    """Ejecutar todos los tests"""
    print("🧪 Ejecutando tests de timestamps RTP...")
    
    try:
        test_create_rtp_packet()
        test_client_rtp_timestamps()
        test_server_buffer_structure()
        
        print("\n🎉 Todos los tests pasaron exitosamente!")
        print("✅ Los cambios de timestamps RTP están funcionando correctamente")
        
    except Exception as e:
        print(f"\n❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)