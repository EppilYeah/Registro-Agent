import os
import json
import pyaudio
import vosk
import asyncio
import edge_tts
import numpy as np
from pydub import AudioSegment
import speech_recognition as sr
import time
import torch

CHUNK_SIZE = 1024
VAD_CHUNK = 512
RATE_HZ = 16000
THRESHOLD = 1500
VOICE = "pt-BR-FranciscaNeural"

class AudioHandler:
    def __init__(self):
        self.pa = pyaudio.PyAudio() #Pyaudio inicializado
        
        #PASTAS - 1
        pasta_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_modelo_vosk = os.path.join(pasta_atual, "modelo_vosk") # vosk
        caminho_modelo_silero_vad = os.path.join(pasta_atual, "silero_vad.jit") # silero VAD
        os.environ["PATH"] += os.pathsep + pasta_atual
        
        caminho_ffmpeg = os.path.join(pasta_atual, "ffmpeg.exe")
        caminho_ffprobe = os.path.join(pasta_atual, "ffprobe.exe")

        #TORCH
        device = torch.device('cpu')
        self.vad_model = torch.jit.load(caminho_modelo_silero_vad) # inicialização modelo VAD
        self.vad_model.eval() # modelo em modo de avaliação
        
        #PASTAS - 2
        AudioSegment.converter = caminho_ffmpeg
        AudioSegment.ffprobe = caminho_ffprobe
        os.environ["PATH"] += os.pathsep + pasta_atual
        
        
        #GOOGLE
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 2.0
        self.recognizer.dynamic_energy_threshold = True

        #VOSK
        try:
            self.modelo = vosk.Model(caminho_modelo_vosk)
            self.rec = vosk.KaldiRecognizer(self.modelo, RATE_HZ)
        except Exception as e:
            print(f"[AUDIO] ERRO AO INICIALIZAR MODULO DE VOZ: {e}")
            self.modelo = None
            self.rec = None
            
        #PYAUDIO
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=8000
        )
        self.stream.start_stream()
        
        self.esta_falando = False
        self.interrompido = False



    def ouvir_wake_word(self):
        '''Ouve a wake word "registro"'''
        print("----- AGUARDANDO ------")
        
        if self.stream.is_stopped():
            self.stream.start_stream()
        while True:
            data = self.stream.read(4000, exception_on_overflow=False)
            
            if self.rec.AcceptWaveform(data):
                resultado = json.loads(self.rec.Result())
                texto = resultado["text"]
                if "registro" in texto or "registros" in texto:
                    print("WAKE WORD DETECTADA")
                    return True
            else:
                parcial = json.loads(self.rec.PartialResult())
                texto_parcial = parcial["partial"]
                if "registro" in texto_parcial:
                    self.rec.Reset() 
                    print("WAKE WORD DETECTADA (Rápida)!")
                    return True




    def falar(self, texto, emocao='neutro'):
        '''metodo de fala com edge-tts'''
        
        self.esta_falando = True   
        self.interrompido = False 
        print(F"MODULANDO : {texto}")
        nome_arquivo = "resposta_temp.mp3"
        
        rate_str = "+20%"
        pitch_str = "+10Hz"
        
        if emocao == "sarcasmo_tedio":
            rate_str = "+20%"
            pitch_str = "+10Hz"
        elif emocao == "irritado":
            rate_str = "+10%"
            pitch_str = "+5Hz"
        elif emocao == "feliz" or emocao == "arrogante":
            rate_str = "+20%"
            pitch_str = "+10Hz"
        elif emocao == "confuso":
            rate_str = "-10%"; pitch_str = "-5Hz"
            
        if os.path.exists(nome_arquivo):
            os.remove(nome_arquivo)
        
        async def gerar():
            comunicar = edge_tts.Communicate(texto, VOICE, pitch=pitch_str, rate=rate_str)
            await comunicar.save(nome_arquivo)
            
        asyncio.run(gerar())
        # TODO: CRIAR EFEITOS PRA APLICAR <--
        fala_fragmentada = AudioSegment.from_mp3(nome_arquivo)
        fala_convertida = fala_fragmentada.set_frame_rate(RATE_HZ)
        fala_bytes = fala_convertida.raw_data

        stream_out = self.pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE_HZ,
        output=True 
        )
        try:
            for i in range(0, len(fala_bytes), CHUNK_SIZE):
                chunk_out = fala_bytes[i:i + CHUNK_SIZE]
                stream_out.write(chunk_out)
                
                dados_mic = self.stream.read(VAD_CHUNK, exception_on_overflow=False)
                
                if self.vad_model:
                    audio_int16 = np.frombuffer(dados_mic, dtype=np.int16) # converte a porra dos bytes pra array int16 numpy
                    audio_float32 = audio_int16.astype(np.float32) / 32768.0 # normaliza essa merda pra float32
                    tensor_audio = torch.from_numpy(audio_float32)
                    probabilidade = self.vad_model(tensor_audio, 16000).item()
                    
                    if probabilidade > 0.5: #50% de certeza
                        print(f"INTERROMPIDO - VOZ DETECTADA - CONFIANÇA: {probabilidade:.2f}")
                        self.interrompido = True
                        break
        finally:
            self.esta_falando = False
        stream_out.stop_stream()
        stream_out.close()
        return self.interrompido
        
    def ouvir_comando(self):
        
        self.stream.stop_stream()
        print("OUVINDO")
        try:
            with sr.Microphone() as source: # microfone inicializado
                self.recognizer.adjust_for_ambient_noise(source)
                try:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=None)
                    print("PROCESSANDO")
                    comando = self.recognizer.recognize_google(audio, language="pt-BR")
                    print(f"VOCÊ DISSE: {comando}")
                    return comando
                except sr.WaitTimeoutError:
                    print(". . .")
                    return None
                except sr.UnknownValueError:
                    print("NÃO ENTENDIDO")
                    return None
                except Exception as e:
                    print(f"ERRO: {e}")
                    return None
        finally:
            #RELIGA o Vosk
            self.stream.start_stream()
            