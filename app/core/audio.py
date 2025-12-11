import os
import json
import pyaudio
import vosk
import asyncio
import edge_tts
import numpy
import time
import torch

CHUNK_SIZE = 1024
RATE_HZ = 16000
THRESHOLD = 1500
VOICE = "pt-BR-FranciscaNeural"

class AudioHandler:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        
        pasta_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_modelo = os.path.join(pasta_atual, "modelo_vosk")
        os.environ["PATH"] += os.pathsep + pasta_atual

        try:
            self.modelo = vosk.Model(caminho_modelo)
            self.rec = vosk.KaldiRecognizer(self.modelo, RATE_HZ)
        except Exception as e:
            print(f"[AUDIO] ERRO AO INICIALIZAR MODULO DE VOZ: {e}")
            self.modelo = None
            self.rec = None
        
        self.esta_falando = False
        self.interrompido = False
        