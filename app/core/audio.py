import os
import json
import pyaudio
import vosk
import asyncio
import edge_tts
import numpy
from pydub import AudioSegment
import speech_recognition as sr
import time
import torch

CHUNK_SIZE = 1024
RATE_HZ = 16000
THRESHOLD = 1500
VOICE = "pt-BR-FranciscaNeural"

class AudioHandler:
    def __init__(self):
        self.pa = pyaudio.PyAudio() #Pyaudio inicializado
        
        pasta_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_modelo_vosk = os.path.join(pasta_atual, "modelo_vosk") # vosk
        caminho_modelo_silero_vad = os.path.join(pasta_atual, "modelo_silero_vad") # silero VAD
        os.environ["PATH"] += os.pathsep + pasta_atual
        
        caminho_ffmpeg = os.path.join(pasta_atual, "ffmpeg.exe")
        caminho_ffprobe = os.path.join(pasta_atual, "ffprobe.exe")
        
        AudioSegment.converter = caminho_ffmpeg
        AudioSegment.ffprobe = caminho_ffprobe

        os.environ["PATH"] += os.pathsep + pasta_atual
        
        device = torch.device('cpu')
        model, decoder, utils = torch.jit.load(caminho_modelo_silero_vad) # inicialização modelo VAD
        model.eval() # modelo em modo de avaliação
        
        
        self.r = sr.Recognizer() #Speech recognizer
        with sr.Microphone(sample_rate = RATE_HZ) as mic: # microfone inicializado
            self.r.adjust_for_ambient_noise(mic)
            print("DIGA ALGO. . .")
            audio = self.r.listen(mic)
            

        try:
            self.modelo = vosk.Model(caminho_modelo_vosk)
            self.rec = vosk.KaldiRecognizer(self.modelo, RATE_HZ)
        except Exception as e:
            print(f"[AUDIO] ERRO AO INICIALIZAR MODULO DE VOZ: {e}")
            self.modelo = None
            self.rec = None
        
        self.esta_falando = False
        self.interrompido = False
        
        
    def falar(self, texto, emocao='neutro'):
        '''metodo de fala com edge-tts'''
        
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
        chunks = fala_bytes / CHUNK_SIZE