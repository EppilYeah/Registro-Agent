import os
import io
import json
import asyncio
import html
import threading
import queue
import time
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
    "feliz":          {"rate": "+15%", "pitch": "-5Hz",  "volume": "+0%"},
    "confuso":        {"rate": "+5%",  "pitch": "-10Hz", "volume": "+0%"},
    "desconfiado":    {"rate": "+0%",  "pitch": "-18Hz", "volume": "-5%"},
    "ouvindo":        {"rate": "+10%", "pitch": "-15Hz", "volume": "+0%"}
}

BUFFER_TTS_BYTES = 32768


class AudioHandler:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.root = os.path.dirname(os.path.abspath(__file__))

        # inicialização de Modelos (VAD, Vosk, SR)
        self._carregar_modelos()

        # Inicialização de Stream e Estado
        self.stream_vad = self._iniciar_mic()
        self.falando = False
        self.interrompido = False

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()

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

        self._calibrar_microfone()

    def _calibrar_microfone(self):
        if self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()
        with sr.Microphone() as source:
            self.rec_sr.adjust_for_ambient_noise(source, duration=1.5)
        if self.stream_vad and self.stream_vad.is_stopped():
            self.stream_vad.start_stream()
        print("[AUDIO] Microfone calibrado.")

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
        self.rec_sr.pause_threshold = 0.8
        self.rec_sr.non_speaking_duration = 0.4
        self.rec_sr.energy_threshold = 300
        self.rec_sr.dynamic_energy_threshold = False

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
        np.multiply(audio, 0.98 + 0.02 * np.sin(
            2 * np.pi * 0.1 * np.arange(len(audio), dtype=np.float32) / sr), out=audio)

        # Pedalboard
        processado = self.board(audio, sr)
        return (processado * 32767).astype(np.int16).tobytes()

    def _monitorar_vad_thread(self):
        voz_consecutiva = 0
        buf_vad = np.empty(CONF["vad_chunk"], dtype=np.float32)
        while self.falando and not self.interrompido:
            if self.vad_model and self.stream_vad:
                if self.stream_vad.is_stopped():
                    time.sleep(0.02)
                    continue
                try:
                    raw = self.stream_vad.read(
                        CONF["vad_chunk"], exception_on_overflow=False)
                    np.copyto(buf_vad,
                              np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0)

                    energia = np.sqrt(np.mean(buf_vad ** 2))

                    with torch.no_grad():
                        tensor = torch.from_numpy(buf_vad)
                        conf = self.vad_model(tensor, 16000).item()
                        del tensor

                    if conf > 0.88 and energia > 0.08:
                        voz_consecutiva += 1
                    else:
                        voz_consecutiva = max(0, voz_consecutiva - 1)

                    if voz_consecutiva >= 8:
                        print("[MIRA] Interrupção detectada.")
                        self.interrompido = True
                except:
                    time.sleep(0.02)

    def _processar_chunk(self, raw_bytes):
        buf = io.BytesIO(raw_bytes)
        data, sr_chunk = sf.read(buf)
        buf.close()
        mono = (data if len(data.shape) == 1 else data[:, 0]).astype(np.float32)
        return self._efeitos_analogicos(mono, sr_chunk), sr_chunk

    async def _falar_streaming(self, txt, params):
        comunicar = edge_tts.Communicate(txt, CONF["voice"], **params)
        fila_play = queue.Queue(maxsize=6)

        self.falando, self.interrompido = True, False

        thread_vad = threading.Thread(target=self._monitorar_vad_thread, daemon=True)
        thread_vad.start()

        out_stream_ref = [None]

        def _tocar():
            while True:
                item = fila_play.get()
                if item is None or self.interrompido:
                    break
                audio_bytes, sr_chunk = item
                if out_stream_ref[0] is None:
                    out_stream_ref[0] = self.pa.open(
                        format=pyaudio.paInt16, channels=1,
                        rate=sr_chunk, output=True)
                if not self.interrompido:
                    out_stream_ref[0].write(audio_bytes)
                del audio_bytes
            if out_stream_ref[0]:
                out_stream_ref[0].stop_stream()
                out_stream_ref[0].close()

        thread_play = threading.Thread(target=_tocar, daemon=True)
        thread_play.start()

        acumulador = io.BytesIO()
        async for chunk in comunicar.stream():
            if self.interrompido:
                break
            if chunk["type"] == "audio":
                acumulador.write(chunk["data"])
                if acumulador.tell() >= BUFFER_TTS_BYTES:
                    try:
                        fila_play.put(self._processar_chunk(acumulador.getvalue()))
                    except Exception as e:
                        print(f"[TTS CHUNK] {e}")
                    acumulador = io.BytesIO()

        tamanho_restante = acumulador.tell()
        if tamanho_restante > 0 and not self.interrompido:
            try:
                fila_play.put(self._processar_chunk(acumulador.getvalue()))
            except Exception as e:
                print(f"[TTS CHUNK FINAL] {e}")
        acumulador.close()

        fila_play.put(None)
        thread_play.join()
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
                if self.interrompido:
                    # breve pausa se foi interrompido antes
                    await asyncio.sleep(0.1)
                return await self._falar_streaming(txt, params)
            except Exception as e:
                print(f"[ERRO TTS] {e}")
                return False

        future = asyncio.run_coroutine_threadsafe(_executar(), self._loop)
        return future.result()

    def preparar_ouvir(self):
        if self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()

    def ouvir_wake_word(self):
        if self.stream_vad.is_stopped():
            self.stream_vad.start_stream()
        print("[REGISTRO] Aguardando Wake Word...")
        while True:
            try:
                data = self.stream_vad.read(4000, exception_on_overflow=False)
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
        if self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()
        print("[REGISTRO] Ouvindo comando...")
        try:
            with sr.Microphone() as source:
                audio = self.rec_sr.listen(
                    source, timeout=5, phrase_time_limit=15)
                return self.rec_sr.recognize_google(audio, language="pt-BR")
        except sr.WaitTimeoutError:
            return None
        except:
            return None
        finally:
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()