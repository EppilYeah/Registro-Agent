import os
import io
import json
import asyncio
import html
import pyaudio
import vosk
import edge_tts
import torch
import eel
import speech_recognition as sr
import soundfile as sf
import numpy as np
from pedalboard import Pedalboard, Compressor, HighpassFilter, Gain, Limiter, PeakFilter, PitchShift, Delay, Reverb, Chorus

# CONFIGURAÇÕES E CONSTANTES
CONF = {
    "rate": 16000, "chunk": 1024, "vad_chunk": 512,
    "voice": "pt-BR-ThalitaNeural",
    "paths": {"vosk": "modelo_vosk", "vad": "silero_vad.jit"}
}

EMOCOES = {
    "neutro":         {"rate": "+10%", "pitch": "-15Hz", "volume": "+0%"},
    "sarcasmo_tedio": {"rate": "+0%",  "pitch": "-15Hz", "volume": "+0%"},
    "irritado":       {"rate": "+25%", "pitch": "-5Hz",  "volume": "+10%"},
    "arrogante":      {"rate": "+5%",  "pitch": "-12Hz", "volume": "+0%"},
    "feliz":          {"rate": "+15%", "pitch": "-5Hz",  "volume": "+0%"}
}


class AudioHandler:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.root = os.path.dirname(os.path.abspath(__file__))

        # inicialização de Modelos (VAD, Vosk, SR)
        self._carregar_modelos()

        # Inicialização de Stream e Estado
        self.stream = self._iniciar_mic()
        self.falando = False
        self.interrompido = False

        # efeitos
        self.board = Pedalboard([
            PitchShift(semitones=2.5),
            Chorus(rate_hz=1.5, depth=0.15,
                   centre_delay_ms=5.0, feedback=0.0, mix=0.25),
            Delay(delay_seconds=0.018, feedback=0.1, mix=0.35),
            PeakFilter(cutoff_frequency_hz=3800, gain_db=12, q=1.5),
            Reverb(room_size=0.25, damping=0.3, wet_level=0.1, dry_level=0.45),
            HighpassFilter(cutoff_frequency_hz=450),
            Compressor(threshold_db=-20, ratio=8,
                       attack_ms=0.1, release_ms=50),
            Gain(gain_db=4), Limiter(threshold_db=-0.5)
        ])

    def _carregar_modelos(self):
        """Carrega recursos pesados"""
        try:
            path_vad = os.path.join(self.root, CONF["paths"]["vad"])
            self.vad_model = torch.jit.load(path_vad).eval()
        except:
            self.vad_model = None

        try:
            path_vosk = os.path.join(self.root, CONF["paths"]["vosk"])
            self.rec_vosk = vosk.KaldiRecognizer(
                vosk.Model(path_vosk), CONF["rate"])
        except:
            self.rec_vosk = None

        self.rec_sr = sr.Recognizer()
        self.rec_sr.pause_threshold = 2.0
        self.rec_sr.energy_threshold = 300
        self.rec_sr.dynamic_energy_threshold = True

    def _iniciar_mic(self):
        try:
            stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=CONF["rate"],
                                  input=True, frames_per_buffer=8000)
            stream.start_stream()
            return stream
        except:
            return None

    # PROCESSAMENTO DE ÁUDIO
    def _efeitos_analogicos(self, audio, sr):
        """Drift Matemático + Pedalboard"""
        # Drift
        t = np.arange(len(audio)) / sr
        envelope = 0.98 + 0.02 * np.sin(2 * np.pi * 0.1 * t)
        audio_drift = audio * envelope

        # Pedalboard
        processado = self.board(audio_drift, sr)
        return (processado * 32767).astype(np.int16).tobytes()

    async def _sintetizar_tts(self, texto, params):
        """áudio cru do EdgeTTS"""
        comunicar = edge_tts.Communicate(texto, CONF["voice"], **params)
        memoria = io.BytesIO()
        async for chunk in comunicar.stream():
            if chunk["type"] == "audio":
                memoria.write(chunk["data"])
        memoria.seek(0)
        return sf.read(memoria)  # retorna data, samplerate

    # LOOP DE REPRODUÇÃO COM VAD
    def _tocar_monitorando(self, audio_bytes, sample_rate):
        self.falando, self.interrompido = True, False
        out_stream = self.pa.open(
            format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)

        cursor = 0
        total = len(audio_bytes)
        step = CONF["chunk"] * 4
        voz_consecutiva = 0

        while cursor < total and not self.interrompido:
            # toca trecho
            chunk = audio_bytes[cursor: cursor + step]
            out_stream.write(chunk)
            cursor += step

            # Verifica Interrupção (VAD)
            if self.vad_model and self.stream and (cursor < total - step):
                try:
                    raw = self.stream.read(
                        CONF["vad_chunk"], exception_on_overflow=False)
                    float_audio = np.frombuffer(
                        raw, np.int16).astype(np.float32) / 32768.0
                    
                    energia = np.sqrt(np.mean(float_audio ** 2))
                    
                    conf = self.vad_model(
                        torch.from_numpy(float_audio), 16000).item()

                    if conf > 0.92 and energia > 0.05:
                        voz_consecutiva += 1
                    else:
                        voz_consecutiva = max(0, voz_consecutiva - 1) 

                    if voz_consecutiva >= 8:
                        print("[MIRA] Interrupção detectada.")
                        self.interrompido = True
                except:
                    pass

        out_stream.stop_stream()
        out_stream.close()
        self.falando = False
        return self.interrompido

    # API PÚBLICA
    def falar(self, texto, emocao='neutro'):
        if not texto:
            return False

        # Prepara texto
        txt = html.unescape(texto.replace('... ', ', hmmm... ')).replace(
            "<", "").replace(">", "").strip()
        print(f"[REGISTRO] Falando: {txt}...")

        # Seleciona parametros
        params = EMOCOES.get(emocao, EMOCOES['neutro'])
        
        async def _executar():
            try:
                data, sr_tts = await self._sintetizar_tts(txt, params)
                audio_mono = data if len(data.shape) == 1 else data[:, 0]
                audio_final = self._efeitos_analogicos(audio_mono, sr_tts)

                if self.interrompido:
                    # breve pausa se foi interrompido antes
                    await asyncio.sleep(0.1)
                return self._tocar_monitorando(audio_final, sr_tts)
            except Exception as e:
                print(f"[ERRO TTS] {e}")
                return False

        return asyncio.run(_executar())

    def ouvir_wake_word(self):
        if self.stream.is_stopped():
            self.stream.start_stream()
        print("[REGISTRO] Aguardando Wake Word...")
        while True:
            try:
                data = self.stream.read(4000, exception_on_overflow=False)
                if self.rec_vosk.AcceptWaveform(data):
                    res = json.loads(self.rec_vosk.Result())
                else:
                    res = json.loads(self.rec_vosk.PartialResult())

                if "registro" in res.get("text", "") or "registro" in res.get("partial", ""):
                    self.rec_vosk.Reset()
                    return True
            except:
                pass

    def ouvir_comando(self):
        self.stream.stop_stream()
        print("[REGISTRO] Ouvindo comando...")
        try:
            with sr.Microphone() as source:
                self.rec_sr.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.rec_sr.listen(
                    source, timeout=5, phrase_time_limit=15)
                return self.rec_sr.recognize_google(audio, language="pt-BR")
        except sr.WaitTimeoutError:
            return None
        except:
            return None
        finally:
            self.stream.start_stream()
