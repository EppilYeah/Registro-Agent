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
import settings
import speech_recognition as sr
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel
from pedalboard import Pedalboard, Compressor, HighpassFilter, Gain, Limiter, PeakFilter, PitchShift, Delay, Reverb, Chorus

try:
    import noisereduce as nr
    _NOISEREDUCE_OK = True
except ImportError:
    _NOISEREDUCE_OK = False

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

_WHISPER_PROMPT_BASE = (
    "Assistente de voz em portugues brasileiro informal. "
    "O usuario fala de forma casual, com girias, abreviacoes e linguagem coloquial. "
    "Exemplos: cara, mano, abre, fecha, muda, aumenta, diminui, ta, ne, po, oxe, vei."
)

_VAD_SILENCE_FRAMES = 20
_VAD_MIN_SPEECH_FRAMES = 5
_VAD_TIMEOUT_SEC = 8


class AudioHandler:
    def __init__(self, funcao_contexto_historico=None):
        self.pa = pyaudio.PyAudio()
        self.root = os.path.dirname(os.path.abspath(__file__))
        self.funcao_contexto_historico = funcao_contexto_historico

        self._carregar_modelos()

        self.stream_vad = self._iniciar_mic()
        self._stream_gravacao = None
        self.falando = False
        self.interrompido = False

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()

        self.board = Pedalboard([
            PitchShift(semitones=2.5),
            Chorus(rate_hz=1.5, depth=0.15, centre_delay_ms=5.0, feedback=0.0, mix=0.25),
            Delay(delay_seconds=0.018, feedback=0.1, mix=0.35),
            PeakFilter(cutoff_frequency_hz=3800, gain_db=12, q=1.5),
            Reverb(room_size=0.25, damping=0.3, wet_level=0.1, dry_level=0.45),
            HighpassFilter(cutoff_frequency_hz=450),
            Compressor(threshold_db=-20, ratio=8, attack_ms=0.1, release_ms=50),
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
        try:
            path_vad = os.path.join(self.root, CONF["paths"]["vad"])
            self.vad_model = torch.jit.load(path_vad).eval()
        except:
            self.vad_model = None

        try:
            path_vosk = os.path.join(self.root, CONF["paths"]["vosk"])
            self.rec_vosk = vosk.KaldiRecognizer(vosk.Model(path_vosk), CONF["rate"])
        except:
            self.rec_vosk = None

        self._carregar_whisper()

        self.rec_sr = sr.Recognizer()
        self.rec_sr.pause_threshold = 0.5
        self.rec_sr.non_speaking_duration = 0.3
        self.rec_sr.energy_threshold = settings.get("energia_microfone")
        self.rec_sr.dynamic_energy_threshold = False

    def _carregar_whisper(self):
        modelo = settings.get("whisper_modelo") or "base"
        device = settings.get("whisper_device") or "cpu"
        compute = "float16" if device == "cuda" else "int8"
        try:
            self.whisper = WhisperModel(modelo, device=device, compute_type=compute)
            print(f"[AUDIO] Whisper {modelo} ({device}) carregado.")
        except Exception as e:
            self.whisper = None
            print(f"[AUDIO] Whisper indisponivel ({modelo}/{device}): {e}")

    def recarregar_whisper(self):
        try:
            if self.whisper:
                del self.whisper
        except:
            pass
        self._carregar_whisper()

    def _iniciar_mic(self):
        try:
            stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=CONF["rate"],
                                  input=True, frames_per_buffer=8000)
            stream.start_stream()
            return stream
        except:
            return None

    def _abrir_stream_vad_dedicado(self):
        try:
            stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=CONF["rate"],
                                  input=True, frames_per_buffer=CONF["vad_chunk"])
            stream.start_stream()
            return stream
        except:
            return None

    def _obter_stream_gravacao(self):
        if self._stream_gravacao is None:
            try:
                self._stream_gravacao = self.pa.open(
                    format=pyaudio.paInt16, channels=1,
                    rate=CONF["rate"], input=True,
                    frames_per_buffer=CONF["vad_chunk"]
                )
            except:
                return None
        try:
            if self._stream_gravacao.is_stopped():
                self._stream_gravacao.start_stream()
        except:
            self._stream_gravacao = None
            return self._obter_stream_gravacao()
        return self._stream_gravacao

    def _efeitos_analogicos(self, audio, sr_rate):
        np.multiply(audio, 0.98 + 0.02 * np.sin(
            2 * np.pi * 0.1 * np.arange(len(audio), dtype=np.float32) / sr_rate), out=audio)
        processado = self.board(audio, sr_rate)
        return (processado * 32767).astype(np.int16).tobytes()

    def _monitorar_vad_thread(self, stream_dedicado):
        voz_consecutiva = 0
        buf_vad = np.empty(CONF["vad_chunk"], dtype=np.float32)

        while self.falando and not self.interrompido:
            if not self.vad_model or not stream_dedicado:
                time.sleep(0.02)
                continue
            if not settings.get("vad_ativo"):
                time.sleep(0.05)
                continue
            try:
                if stream_dedicado.is_stopped():
                    time.sleep(0.02)
                    continue
                raw = stream_dedicado.read(CONF["vad_chunk"], exception_on_overflow=False)
                np.copyto(buf_vad, np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0)

                energia = np.sqrt(np.mean(buf_vad ** 2))

                with torch.no_grad():
                    tensor = torch.from_numpy(buf_vad)
                    conf = self.vad_model(tensor, 16000).item()
                    del tensor

                threshold = settings.get("vad_threshold")
                energia_min = settings.get("vad_energia")
                consecutivo_max = settings.get("vad_consecutivo")

                if conf > threshold and energia > energia_min:
                    voz_consecutiva += 1
                else:
                    voz_consecutiva = max(0, voz_consecutiva - 1)

                if voz_consecutiva >= consecutivo_max:
                    print("[MIRA] Interrupcao detectada.")
                    self.interrompido = True
            except:
                time.sleep(0.02)

        try:
            stream_dedicado.stop_stream()
            stream_dedicado.close()
        except:
            pass

    def _processar_chunk(self, raw_bytes):
        buf = io.BytesIO(raw_bytes)
        data, sr_chunk = sf.read(buf)
        buf.close()
        mono = (data if len(data.shape) == 1 else data[:, 0]).astype(np.float32)
        return self._efeitos_analogicos(mono, sr_chunk), sr_chunk

    def _gravar_com_vad(self):
        if not self.vad_model:
            return None

        mic_stream = self._obter_stream_gravacao()
        if not mic_stream:
            return None

        frames_gravados = []
        frames_silencio = 0
        frames_voz = 0
        falando_detectado = False
        inicio = time.time()
        buf = np.empty(CONF["vad_chunk"], dtype=np.float32)

        print("[VAD] Aguardando voz...")

        while True:
            if time.time() - inicio > _VAD_TIMEOUT_SEC:
                break

            try:
                raw = mic_stream.read(CONF["vad_chunk"], exception_on_overflow=False)
            except:
                break

            np.copyto(buf, np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0)

            energia = np.sqrt(np.mean(buf ** 2))

            with torch.no_grad():
                tensor = torch.from_numpy(buf)
                conf = self.vad_model(tensor, 16000).item()
                del tensor

            eh_voz = conf > settings.get("vad_threshold") and energia > settings.get("vad_energia")

            if eh_voz:
                if not falando_detectado:
                    falando_detectado = True
                    print("[VAD] Voz detectada.")
                frames_voz += 1
                frames_silencio = 0
                frames_gravados.append(raw)
            elif falando_detectado:
                frames_gravados.append(raw)
                frames_silencio += 1
                if frames_silencio >= _VAD_SILENCE_FRAMES:
                    print("[VAD] Fim de fala detectado.")
                    break

        if frames_voz < _VAD_MIN_SPEECH_FRAMES:
            return None

        audio_bytes = b"".join(frames_gravados)
        audio_np = np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0
        return audio_np

    def _reduzir_ruido(self, audio_np):
        if not _NOISEREDUCE_OK:
            return audio_np
        try:
            return nr.reduce_noise(y=audio_np, sr=CONF["rate"], stationary=True, prop_decrease=0.4)
        except:
            return audio_np

    def _construir_prompt_contextual(self):
        prompt = _WHISPER_PROMPT_BASE
        if self.funcao_contexto_historico:
            try:
                contexto = self.funcao_contexto_historico()
                if contexto:
                    prompt = prompt + " Contexto recente: " + contexto
            except:
                pass
        return prompt

    async def _falar_streaming(self, txt, params):
        comunicar = edge_tts.Communicate(txt, CONF["voice"], **params)
        fila_play = queue.Queue(maxsize=6)

        self.falando, self.interrompido = True, False

        stream_vad_dedicado = self._abrir_stream_vad_dedicado()
        thread_vad = threading.Thread(
            target=self._monitorar_vad_thread,
            args=(stream_vad_dedicado,),
            daemon=True
        )
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

    async def _prequecer_tts(self):
        try:
            comunicar = edge_tts.Communicate(" ", CONF["voice"])
            async for _ in comunicar.stream():
                break
        except:
            pass

    def falar(self, texto, emocao='neutro'):
        if not texto:
            return False

        txt = html.unescape(texto.replace('... ', ', hmmm... ')).replace(
            "<", "").replace(">", "").strip()
        print(f"[REGISTRO] Falando: {txt}...")

        params = EMOCOES.get(emocao, EMOCOES['neutro'])

        async def _executar():
            try:
                if self.interrompido:
                    await asyncio.sleep(0.1)
                return await self._falar_streaming(txt, params)
            except Exception as e:
                print(f"[ERRO TTS] {e}")
                return False

        future = asyncio.run_coroutine_threadsafe(_executar(), self._loop)
        return future.result()

    def prequecer(self):
        asyncio.run_coroutine_threadsafe(self._prequecer_tts(), self._loop)

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

        audio_np = None

        if self.vad_model:
            audio_np = self._gravar_com_vad()

        if audio_np is None:
            try:
                self.rec_sr.energy_threshold = settings.get("energia_microfone")
                with sr.Microphone() as source:
                    audio_data = self.rec_sr.listen(source, timeout=5, phrase_time_limit=15)
                raw = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
                audio_np = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
            except sr.WaitTimeoutError:
                if self.stream_vad and self.stream_vad.is_stopped():
                    self.stream_vad.start_stream()
                return None
            except:
                if self.stream_vad and self.stream_vad.is_stopped():
                    self.stream_vad.start_stream()
                return None

        if audio_np is None or len(audio_np) == 0:
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return None

        audio_np = self._reduzir_ruido(audio_np)

        if self.whisper:
            try:
                segments, _ = self.whisper.transcribe(
                    audio_np,
                    language="pt",
                    beam_size=5,
                    initial_prompt=self._construir_prompt_contextual(),
                    vad_filter=False,
                    temperature=0.0,
                    condition_on_previous_text=False,
                )
                texto = " ".join(s.text for s in segments).strip()
                if texto:
                    print(f"[WHISPER] {texto}")
                    if self.stream_vad and self.stream_vad.is_stopped():
                        self.stream_vad.start_stream()
                    return texto
            except Exception as e:
                print(f"[WHISPER] Falha, usando Google: {e}")

        try:
            audio_int16 = (audio_np * 32768).astype(np.int16)
            audio_sr = sr.AudioData(audio_int16.tobytes(), 16000, 2)
            texto = self.rec_sr.recognize_google(audio_sr, language="pt-BR")
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return texto
        except:
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return None