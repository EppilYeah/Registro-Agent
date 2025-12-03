import struct
import pyaudio
import pvporcupine
import os
import config

# --- CONFIGURAÇÃO MANUAL (Para teste) ---
# Se a barra de volume não mexer, mude este número para 0, 1, 2, etc.
INDEX_MICROFONE = None 

def main():

    pasta_atual = os.path.join(os.getcwd(), "app", "core")
    

    keyword_path = os.path.join(pasta_atual, "REGISTRO_pt_windows_v3_0_0.ppn")
    model_path = os.path.join(pasta_atual, "porcupine_params_pt.pv")

    print(f"--- DIAGNÓSTICO DE ÁUDIO ---")
    print(f"Procurando arquivos em: {pasta_atual}")
    
    if not os.path.exists(keyword_path):
        print(f"❌ ERRO: Arquivo .ppn não encontrado!")
        return
    if not os.path.exists(model_path):
        print(f"❌ ERRO: Arquivo .pv não encontrado!")
        return

    try:
        # Cria o Porcupine com sensibilidade alta para teste
        porcupine = pvporcupine.create(
            access_key=config.PICOVOICE_KEY,
            keyword_paths=[keyword_path],
            model_path=model_path,
            sensitivities=[1.0] 
        )
        print("✅ Porcupine carregado com sucesso.")
    except Exception as e:
        print(f"❌ ERRO FATAL AO CRIAR PORCUPINE: {e}")
        print("Verifique sua AccessKey no config.py ou se a conta Picovoice está ativa.")
        return

    pa = pyaudio.PyAudio()

    try:
        # Abre o microfone
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
            input_device_index=INDEX_MICROFONE
        )
        print(f"✅ Microfone aberto (Index: {INDEX_MICROFONE if INDEX_MICROFONE is not None else 'Padrão'}).")
    except Exception as e:
        print(f"❌ ERRO AO ABRIR MICROFONE: {e}")
        return

    print("\n🔊 TESTE INICIADO (Ctrl+C para parar)")
    print("1. Fale algo para ver a barra de volume mexer.")
    print("2. Diga 'REGISTRO' para ver se detecta.\n")

    try:
        while True:
            # Lê o áudio do microfone
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

            # 1. MONITOR DE VOLUME (Visual)
            # Calcula o volume atual para desenhar a barra
            volume_atual = max(pcm)
            barra = "|" * int(volume_atual / 500) 
            # O \r faz ele atualizar a mesma linha sem pular
            print(f"\rVol: {volume_atual:05d} {barra}", end="")

            # 2. DETECÇÃO DA WAKE WORD
            result = porcupine.process(pcm)
            if result >= 0:
                # Se detectar, limpa a linha e mostra o aviso
                print("\n\n🔥🔥🔥 REGISTRO DETECTADO! 🔥🔥🔥\n")

    except KeyboardInterrupt:
        print("\n\n🛑 Teste encerrado pelo usuário.")
    finally:
        if audio_stream: audio_stream.close()
        if pa: pa.terminate()
        porcupine.delete()

if __name__ == "__main__":
    main()