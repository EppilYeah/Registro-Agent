import os
import json
import pyaudio
import vosk
import asyncio
import edge_tts
import numpy as np
import torch
import speech_recognition as sr
import random
import html
import soundfile as sf
from pedalboard import Pedalboard, Compressor, HighpassFilter, Bitcrush, Gain, Limiter
from pedalboard.io import AudioFile


CHUNK_SIZE = 1024
VAD_CHUNK = 512
RATE_HZ = 16000 
VOICE = "pt-BR-FranciscaNeural" 

class AudioHandler:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        pasta_atual = os.path.dirname(os.path.abspath(__file__))
        
        #CARREGAMENTO VOSK/VAD
        caminho_vosk = os.path.join(pasta_atual, "modelo_vosk")
        caminho_vad = os.path.join(pasta_atual, "silero_vad.jit")
        
        # VAD
        try:
            self.vad_model = torch.jit.load(caminho_vad)
            self.vad_model.eval()
            print("[AUDIO] VAD Silero: OK")
        except: self.vad_model = None

        # Vosk
        try:
            self.modelo_vosk = vosk.Model(caminho_vosk)
            self.rec = vosk.KaldiRecognizer(self.modelo_vosk, RATE_HZ)
        except: pass

        self.recognizer = sr.Recognizer()
        
        # Stream Microfone
        try:
            self.stream = self.pa.open(
                format=pyaudio.paInt16, channels=1, rate=RATE_HZ,
                input=True, frames_per_buffer=8000
            )
            self.stream.start_stream()
        except: pass
        
        self.esta_falando = False
        self.interrompido = False


        self.board = Pedalboard([

            HighpassFilter(cutoff_frequency_hz=500),
            
            Bitcrush(bit_depth=12),
            
            Compressor(threshold_db=-15, ratio=4, attack_ms=1, release_ms=100),
            
            Gain(gain_db=3),
            
            Limiter(threshold_db=-1)
        ])

    def _adicionar_respiracoes_texto(self, texto):
        '''Simula o ritmo de pensamento antes de enviar pro TTS'''
        texto = texto.replace('... ', ', hmm... ') 
        return texto

    def _aplicar_drift_analogico(self, audio_samples, sample_rate):
        '''
        Cria uma oscilação suave de volume (Drift) como um rádio valvulado ou respiração.
        '''
        num_samples = len(audio_samples)
        tempo = np.arange(num_samples) / sample_rate
        
        freq_resp = 0.2 
        
        envelope = 0.95 + 0.05 * np.sin(2 * np.pi * freq_resp * tempo)
        
        jitter = np.random.normal(1.0, 0.005, num_samples) 
        
        envelope_final = envelope * jitter
        
        return audio_samples * envelope_final

    def falar(self, texto, emocao='neutro'):
        if not texto: return False
        
        texto_processado = self._adicionar_respiracoes_texto(texto)
        texto_limpo = html.unescape(texto_processado).replace("<", "").replace(">", "").strip()
        
        print(f"[MIRA] Modulando: {texto_limpo[:30]}...")
        
        nome_arquivo = "temp_voz.mp3"
        if os.path.exists(nome_arquivo): os.remove(nome_arquivo)

        caos = random.randint(-5, 5)
        rate = "+0%"
        pitch = "+0Hz"
        volume = "+0%"
        
        if emocao == "sarcasmo_tedio":
            rate = f"{int(-12 + caos)}%" 
            pitch = "-5Hz"
            volume = "-5%"
        
        elif emocao == "irritado":
            rate = f"{int(+15 + caos)}%"
            pitch = "+4Hz"
            volume = "+15%"
            
        elif emocao == "arrogante":
            rate = "-8%"
            pitch = "+2Hz"
            
        elif emocao == "confuso":
            rate = "-15%"
            pitch = "-2Hz"
            
        elif emocao == "feliz": 
            rate = "+8%"
            pitch = f"{int(+8 + caos)}Hz"

        async def gerar():
            comunicar = edge_tts.Communicate(texto_limpo, VOICE, rate=rate, pitch=pitch)
            await comunicar.save(nome_arquivo)
            
        try:
            asyncio.run(gerar())
            
            audio, sample_rate = sf.read(nome_arquivo)
            
            if len(audio.shape) > 1: audio = audio[:, 0] # Mono

            audio = self._aplicar_drift_analogico(audio, sample_rate)
            
            audio_processado = self.board(audio, sample_rate)
            
            audio_int16 = (audio_processado * 32767).astype(np.int16)
            fala_bytes = audio_int16.tobytes()
            
            self.esta_falando = True
            self.interrompido = False
            

            stream_out = self.pa.open(
                format=pyaudio.paInt16, 
                channels=1, 
                rate=sample_rate, 
                output=True
            )
            
            total_bytes = len(fala_bytes)
            cursor = 0
            chunk_size = 1024 * 2 
            
            while cursor < total_bytes:
                if self.interrompido: break
                
                chunk = fala_bytes[cursor : cursor + chunk_size]
                stream_out.write(chunk)
                cursor += chunk_size
                
                if cursor < total_bytes - (chunk_size * 5):
                    try:
                        dados = self.stream.read(VAD_CHUNK, exception_on_overflow=False)
                        if self.vad_model:
                            audio_float = np.frombuffer(dados, np.int16).astype(np.float32) / 32768.0
                            tensor = torch.from_numpy(audio_float)
                            conf = self.vad_model(tensor, 16000).item()
                            if conf > 0.6:
                                print(f"[CORTADO] Conf: {conf:.2f}")
                                self.interrompido = True
                    except: pass

            stream_out.stop_stream()
            stream_out.close()
            self.esta_falando = False
            return self.interrompido

        except Exception as e:
            print(f"[ERRO AUDIO] {e}")
            self.esta_falando = False
            return False

    def ouvir_wake_word(self):
        if self.stream.is_stopped(): self.stream.start_stream()
        while True:
            try:
                data = self.stream.read(4000, exception_on_overflow=False)
                if self.rec.AcceptWaveform(data):
                    if "registro" in json.loads(self.rec.Result())["text"]: return True
                else:
                    if "registro" in json.loads(self.rec.PartialResult()).get("partial", ""):
                        self.rec.Reset(); return True
            except: pass

    def ouvir_comando(self):
        self.stream.stop_stream()
        print("🎤")
        try:
            with sr.Microphone() as s:
                self.recognizer.adjust_for_ambient_noise(s, duration=0.5)
                audio = self.recognizer.listen(s, timeout=4)
                return self.recognizer.recognize_google(audio, language="pt-BR")
        except: return None
        finally: self.stream.start_stream()