import os
import io
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
from pedalboard import (
    Pedalboard, 
    Compressor, 
    HighpassFilter, 
    Gain, 
    Limiter, 
    PeakFilter, 
    PitchShift, 
    Delay, 
    Reverb, 
    Chorus
)


CHUNK_SIZE = 1024
VAD_CHUNK = 512
RATE_HZ = 16000 
VOICE = "pt-BR-ThalitaNeural" 

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
            PitchShift(semitones=2.5),

            Chorus(rate_hz=1.5, depth=0.15, centre_delay_ms=5.0, feedback=0.0, mix=0.25),

            Delay(delay_seconds=0.018, feedback=0.1, mix=0.35),

            PeakFilter(cutoff_frequency_hz=3800, gain_db=12, q=1.5),

            Reverb(room_size=0.25, damping=0.3, wet_level=0.10, dry_level=0.45),

            HighpassFilter(cutoff_frequency_hz=450),

            Compressor(threshold_db=-20, ratio=8, attack_ms=0.1, release_ms=50),
            
            Gain(gain_db=4),
            
            Limiter(threshold_db=-0.5)
        ])

    def _adicionar_respiracoes_texto(self, texto):
        '''simula o ritmo de pensamento antes de enviar pro TTS'''
        texto = texto.replace('... ', ', hmm... ') 
        return texto

    def _aplicar_drift_analogico(self, audio_samples, sample_rate):
        num_samples = len(audio_samples)
        tempo = np.arange(num_samples) / sample_rate
        freq_resp = 0.1 
        envelope = 0.98 + 0.02 * np.sin(2 * np.pi * freq_resp * tempo)
        return audio_samples * envelope

    def falar(self, texto, emocao='neutro'):
        if not texto: return False
        
        texto_limpo = html.unescape(self._adicionar_respiracoes_texto(texto)).replace("<", "").replace(">", "").strip()
        print(f"[MIRA] Modulando: {texto_limpo}...")


        rate = "+10%"
        pitch = "-15Hz"
        volume = "+0%"
        
        if emocao == "sarcasmo_tedio":
            rate = "+0%"; pitch = "-15Hz"
        elif emocao == "irritado":
            rate = "+25%"; pitch = "-5Hz"; volume = "+10%"
        elif emocao == "arrogante":
            rate = "+5%"; pitch = "-12Hz"
        elif emocao == "feliz": 
            rate = "+15%"; pitch = "-5Hz"

        async def gerar_e_tocar():

            comunicar = edge_tts.Communicate(
                texto_limpo, VOICE, rate=rate, pitch=pitch, volume=volume
            )
            
            memoria_audio = io.BytesIO()
            
            async for chunk in comunicar.stream():
                if chunk["type"] == "audio":
                    memoria_audio.write(chunk["data"])
            
            memoria_audio.seek(0)
            
            audio, sample_rate = sf.read(memoria_audio)
            
            if len(audio.shape) > 1: audio = audio[:, 0]

            audio = self._aplicar_drift_analogico(audio, sample_rate)
            audio_processado = self.board(audio, sample_rate)
            
            audio_int16 = (audio_processado * 32767).astype(np.int16)
            fala_bytes = audio_int16.tobytes()
            
            self.esta_falando = True
            self.interrompido = False
            
            stream_out = self.pa.open(
                format=pyaudio.paInt16, channels=1, 
                rate=sample_rate, output=True
            )
            
            total_bytes = len(fala_bytes)
            cursor = 0
            chunk_size = CHUNK_SIZE * 4
            
            consecutivos_voz = 0
            LIMITE_CONFIRMACAO = 3
            
            while cursor < total_bytes:
                if self.interrompido: break
                
                chunk = fala_bytes[cursor : cursor + chunk_size]
                stream_out.write(chunk)
                cursor += chunk_size
                
                if cursor < total_bytes - (chunk_size * 2):
                    try:
                        dados = self.stream.read(VAD_CHUNK, exception_on_overflow=False)
                        if self.vad_model:
                            audio_float = np.frombuffer(dados, np.int16).astype(np.float32) / 32768.0
                            conf = self.vad_model(torch.from_numpy(audio_float), 16000).item()
                            
                            if conf > 0.8:
                                consecutivos_voz += 1
                            else:
                                consecutivos_voz = 0
                            
                            if consecutivos_voz >= LIMITE_CONFIRMACAO:
                                print(f"[INTERRUPÇÃO] Detectada.")
                                self.interrompido = True
                    except: pass

            stream_out.stop_stream()
            stream_out.close()
            
            if self.interrompido:
                await asyncio.sleep(0.1)
                
            self.esta_falando = False
            return self.interrompido

        try:
            return asyncio.run(gerar_e_tocar())
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
        print("OUVINDO COMANDO. . . ")
        try:
            with sr.Microphone() as s:
                self.recognizer.adjust_for_ambient_noise(s, duration=0.5)
                audio = self.recognizer.listen(s, timeout=4)
                return self.recognizer.recognize_google(audio, language="pt-BR")
        except: return None
        finally: self.stream.start_stream()