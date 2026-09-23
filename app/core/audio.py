import re
import logging
import os
import io
import json
import asyncio
import html
import threading
import queue
import time
import re
import pyaudio
import vosk
import torch
import settings
import speech_recognition as sr
import soundfile as sf
import numpy as np
<<<<<<< HEAD
from pedalboard import Pedalboard, Compressor, HighpassFilter, Gain, Limiter, PeakFilter

try:
    from kokoro import KPipeline
    _KOKORO_OK = True
except ImportError:
    _KOKORO_OK = False
=======
import config
from pedalboard import Pedalboard, Compressor, HighpassFilter, Gain, Limiter, PeakFilter, PitchShift, Delay, Reverb, Chorus
from app.core.stt_vocab import LIMITE_GROQ_CHARS, montar_prompt_stt, normalizar_modelo_whisper
from app.core.roteador import groq_ok, usar_groq_stt
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

try:
    import edge_tts
    _EDGETTS_OK = True
except ImportError:
    _EDGETTS_OK = False

try:
    from RealtimeSTT import AudioToTextRecorder
    _REALTIMESTT_OK = True
except ImportError:
    _REALTIMESTT_OK = False

try:
    from faster_whisper import WhisperModel
<<<<<<< HEAD
except ImportError:
    WhisperModel = None
=======
    _WHISPER_OK = True
except ImportError:
    _WHISPER_OK = False
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

CONF = {
    "rate": 16000, "chunk": 1024, "vad_chunk": 512,
    "voice": "pt-BR-ThalitaNeural",
    "paths": {"vosk": "modelo_vosk", "vad": "silero_vad.jit"},
<<<<<<< HEAD
    "kokoro_rate": 24000,
    "kokoro_voz": "pf_dora,af_nicole",
    "kokoro_voz_en": "af_nicole",
=======
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
}

EMOCOES_EDGE = {
    "neutro":          {"rate": "+4%",  "pitch": "-22Hz", "volume": "+0%"},
    "sarcasmo_tedio": {"rate": "+2%",  "pitch": "-20Hz", "volume": "+0%"},
    "irritado":        {"rate": "+22%", "pitch": "-8Hz",  "volume": "+8%"},
    "arrogante":       {"rate": "+6%",  "pitch": "-18Hz", "volume": "+0%"},
    "feliz":           {"rate": "+10%", "pitch": "-12Hz", "volume": "+0%"},
    "confuso":         {"rate": "+6%",  "pitch": "-16Hz", "volume": "+0%"},
    "desconfiado":     {"rate": "-2%",  "pitch": "-24Hz", "volume": "-4%"},
    "ouvindo":         {"rate": "+5%",  "pitch": "-22Hz", "volume": "+0%"},
}

<<<<<<< HEAD
EMOCOES_KOKORO = {
    "neutro":         {"speed": 1.0,  "gain_db": 0},
    "sarcasmo_tedio": {"speed": 0.95, "gain_db": 0},
    "irritado":       {"speed": 1.08, "gain_db": 2},
    "arrogante":      {"speed": 1.0,  "gain_db": 0},
    "feliz":          {"speed": 1.05, "gain_db": 1},
    "confuso":        {"speed": 0.97, "gain_db": 0},
    "desconfiado":    {"speed": 0.94, "gain_db": -1},
    "ouvindo":        {"speed": 1.0,  "gain_db": 0},
}

BUFFER_TTS_BYTES = 32768

_PRONUNCIA = {
    "luis": "Luís",
    "cpu": "cê pê u",
    "gpu": "gê pê u",
    "ram": "râm",
    "api": "a p i",
    "tts": "tê tê esse",
    "stt": "esse tê tê",
    "vad": "vade",
    "usb": "u esse bê",
}

_EN_SET = frozenset(
    "ok okay windows chrome discord python gemini whisper kokoro github cursor "
    "flash debug wifi bluetooth steam youtube google microsoft openai llama "
    "nvidia intel amd whatsapp token cuda json html css http https "
    "clipboard screenshot download upload software hardware driver server "
    "kernel compile debug login logout update upgrade reboot shutdown "
    "yes no hello world error warning exception timeout cache thread "
    "stream buffer socket folder file path script prompt model "
    "okey yeah sorry please thanks thank".split()
)

_PT_CURTO = frozenset("a o e de da do em um uma no na os as umas uns ao à".split())

_WHISPER_PROMPT_BASE = (
    "Assistente de voz em portugues brasileiro informal. "
    "O usuario fala de forma casual, com girias, abreviacoes e linguagem coloquial. "
    "Exemplos: cara, mano, abre, fecha, muda, aumenta, diminui, ta, ne, po, oxe, vei."
)

=======
logger = logging.getLogger(__name__)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

class AudioHandler:
    def __init__(self, funcao_contexto_historico=None):
        self.pa = pyaudio.PyAudio()
        self.root = os.path.dirname(os.path.abspath(__file__))
        self.funcao_contexto_historico = funcao_contexto_historico
        self.falando = False
        self.interrompido = False
        self._stt_groq = False
        _raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.caminho_usuario = os.path.join(_raiz, "data", "usuario.json")
        self._stream_gravacao = None
<<<<<<< HEAD
        self.supervisor = None
        self._falhas_mic = 0
        self._comando_pendente = None
        self._stt_cuda_morto = False

=======
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()
        self.board = Pedalboard([
<<<<<<< HEAD
            PeakFilter(cutoff_frequency_hz=2800, gain_db=2.0, q=0.8),
            HighpassFilter(cutoff_frequency_hz=90),
            Compressor(threshold_db=-18, ratio=3, attack_ms=8, release_ms=90),
            Gain(gain_db=2),
            Limiter(threshold_db=-1.0)
=======
            PitchShift(semitones=3.0),
            Chorus(rate_hz=0.85, depth=0.2, centre_delay_ms=6.0, feedback=0.03, mix=0.22),
            Delay(delay_seconds=0.011, feedback=0.11, mix=0.24),
            PeakFilter(cutoff_frequency_hz=3100, gain_db=9.0, q=1.35),
            PeakFilter(cutoff_frequency_hz=7200, gain_db=3.5, q=1.85),
            Reverb(room_size=0.13, damping=0.62, wet_level=0.06, dry_level=0.58),
            HighpassFilter(cutoff_frequency_hz=380),
            Compressor(threshold_db=-22, ratio=5.5, attack_ms=0.12, release_ms=42),
            Gain(gain_db=3.5),
            Limiter(threshold_db=-0.8),
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        ])
        self._carregar_modelos()
        self.stream_vad = self._iniciar_mic()
        self._calibrar_microfone()

    def _carregar_modelos(self):
        try:
            path_vad = os.path.join(self.root, CONF["paths"]["vad"])
            self.vad_model = torch.jit.load(path_vad).eval()
        except Exception as e:
            logger.warning("VAD Silero: %s", e)
            self.vad_model = None
        try:
            path_vosk = os.path.join(self.root, CONF["paths"]["vosk"])
            self.rec_vosk = vosk.KaldiRecognizer(vosk.Model(path_vosk), CONF["rate"])
        except Exception as e:
            logger.warning("Vosk: %s", e)
            self.rec_vosk = None
        self._carregar_stt()
        self.rec_sr = sr.Recognizer()
        self.rec_sr.pause_threshold = 0.8
        self.rec_sr.non_speaking_duration = 0.3
        self.rec_sr.energy_threshold = settings.get("energia_microfone")
        self.rec_sr.dynamic_energy_threshold = False

<<<<<<< HEAD
    def _carregar_kokoro(self):
        self.kokoro = None
        self.kokoro_en = None
        if not _KOKORO_OK:
            print("[AUDIO] Kokoro indisponivel, usando edge-tts.")
            return
        try:
            self.kokoro = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M")
            try:
                self.kokoro_en = KPipeline(
                    lang_code="a",
                    repo_id="hexgrad/Kokoro-82M",
                    model=self.kokoro.model,
                )
            except Exception as e:
                print(f"[AUDIO] Pipeline EN Kokoro falhou: {e}")
            print(f"[AUDIO] Kokoro carregado (voz: {CONF['kokoro_voz']}).")
        except Exception as e:
            self.kokoro = None
            print(f"[AUDIO] Kokoro falhou: {e}")
=======
    def _modelo_whisper(self):
        return normalizar_modelo_whisper(settings.get("whisper_modelo"))

    def _prompt_stt(self, groq=False):
        ctx = ""
        if self.funcao_contexto_historico:
            try:
                ctx = self.funcao_contexto_historico() or ""
            except Exception as e:
                logger.debug("prompt contextual STT: %s", e)
        return montar_prompt_stt(
            contexto=ctx,
            usuario_path=self.caminho_usuario,
            limite=LIMITE_GROQ_CHARS if groq else None,
        )

    def _deve_usar_groq_stt(self):
        return usar_groq_stt()
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

    def _carregar_stt(self):
        self._stt_groq = False
        device = str(settings.get("whisper_device") or "cuda").lower()
        modelo = self._modelo_whisper()
        if self._deve_usar_groq_stt():
            self._stt_groq = True
            self.recorder = None
            print("[AUDIO] CUDA ocupada ou STT Groq pedido — Whisper large-v3-turbo na nuvem.")
            self._carregar_whisper_fallback(device_forcado="cpu")
            return
        if _REALTIMESTT_OK:
            try:
                post_sil = float(settings.get("stt_post_speech_silence_sec") or 0.65)
                post_sil = max(0.35, min(1.2, post_sil))
                silero = float(settings.get("stt_realtime_silero_sensitivity") or 0.45)
                silero = max(0.2, min(0.8, silero))
                beam = int(settings.get("whisper_beam_size") or 3)
                beam = max(1, min(5, beam))
                kwargs = {
                    "model": modelo,
                    "language": "pt",
                    "silero_sensitivity": silero,
                    "webrtc_sensitivity": 2,
                    "post_speech_silence_duration": post_sil,
                    "min_length_of_recording": 0.25,
                    "min_gap_between_recordings": 0.0,
                    "spinner": False,
                    "enable_realtime_transcription": False,
                    "initial_prompt": self._prompt_stt(),
                    "beam_size": beam,
                    "device": "cuda" if device == "cuda" else "cpu",
                }
                try:
                    self.recorder = AudioToTextRecorder(**kwargs)
                except TypeError:
                    kwargs.pop("beam_size", None)
                    kwargs.pop("device", None)
                    try:
                        self.recorder = AudioToTextRecorder(**kwargs)
                    except TypeError:
                        kwargs.pop("initial_prompt", None)
                        self.recorder = AudioToTextRecorder(**kwargs)
                self.whisper = None
                vocab = "vocabulario injetado" if "initial_prompt" in kwargs else "sem initial_prompt nesta versao"
                print(f"[AUDIO] RealtimeSTT {modelo} ({kwargs.get('device', 'auto')}, PT-BR, {vocab}).")
                return
            except Exception as e:
                self.recorder = None
                print(f"[AUDIO] RealtimeSTT falhou: {e}")
                if groq_ok():
                    self._stt_groq = True
                    print("[AUDIO] Fallback Groq Whisper.")
        else:
            self.recorder = None
        self._carregar_whisper_fallback()

<<<<<<< HEAD
    def _cuda_indisponivel(self, erro):
        t = str(erro).lower()
        return any(x in t for x in (
            "cublas", "cudnn", "nvrtc", "cuda",
            "not found or cannot be loaded",
        ))

    def _cublas_ok(self):
        if os.name != "nt":
            return True
        try:
            import ctypes
            ctypes.WinDLL("cublas64_12.dll")
            return True
        except OSError:
            return False

    def _carregar_whisper_fallback(self, forcar_device=None):
        if WhisperModel is None:
            self.whisper = None
            print("[AUDIO] faster-whisper indisponivel.")
            return False
        modelo = settings.get("whisper_modelo") or "base"
        device = forcar_device or settings.get("whisper_device") or "cpu"
        if self._stt_cuda_morto and device == "cuda":
            device = "cpu"
        if device == "cuda" and not self._cublas_ok():
            print("[AUDIO] cublas64_12.dll ausente. Whisper em CPU.")
            self._stt_cuda_morto = True
            settings.set("whisper_device", "cpu")
            device = "cpu"
        compute = "float16" if device == "cuda" else "int8"
        try:
            self.whisper = WhisperModel(modelo, device=device, compute_type=compute)
            print(f"[AUDIO] Whisper {modelo} ({device}) carregado.")
            return True
        except Exception as e:
            print(f"[AUDIO] Whisper {device} indisponivel: {e}")
            self.whisper = None
            if device == "cuda":
                self._stt_cuda_morto = True
                settings.set("whisper_device", "cpu")
                return self._carregar_whisper_fallback(forcar_device="cpu")
            return False

    def recarregar_whisper(self):
        self.recarregar_stt()

    def recarregar_stt(self):
        if self._stt_cuda_morto:
            settings.set("whisper_device", "cpu")
        try:
            self.recorder = None
        except Exception:
            pass
        try:
            if self.whisper:
                del self.whisper
        except Exception:
            pass
        self.whisper = None
        self._carregar_stt()
        return self.recorder is not None or self.whisper is not None

    def reiniciar_mic(self):
        try:
            if self.stream_vad:
                try:
                    self.stream_vad.stop_stream()
                    self.stream_vad.close()
                except Exception:
                    pass
            self.stream_vad = self._iniciar_mic()
            if self._stream_gravacao:
                try:
                    self._stream_gravacao.stop_stream()
                    self._stream_gravacao.close()
                except Exception:
                    pass
                self._stream_gravacao = None
            self._falhas_mic = 0
            print("[AUDIO] Mic reaberto.")
            return self.stream_vad is not None
        except Exception as e:
            print(f"[AUDIO] Falha ao reabrir mic: {e}")
            self.stream_vad = None
            return False
=======
    def _carregar_whisper_fallback(self, device_forcado=None):
        if not _WHISPER_OK:
            self.whisper = None
            print("[AUDIO] Whisper indisponivel: modulo faster_whisper ausente.")
            return
        modelo = self._modelo_whisper()
        device = device_forcado or (settings.get("whisper_device") or "cuda")
        if device == "groq":
            device = "cpu"
        ordem = [device]
        if device == "cuda":
            ordem.append("cpu")
        ultimo = None
        for dev in ordem:
            compute = "float16" if dev == "cuda" else "int8"
            try:
                self.whisper = WhisperModel(modelo, device=dev, compute_type=compute)
                print(f"[AUDIO] Whisper {modelo} ({dev}/{compute}) carregado.")
                return
            except Exception as e:
                ultimo = e
                self.whisper = None
        print(f"[AUDIO] Whisper indisponivel: {ultimo}")

    def recarregar_stt(self):
        if self.recorder:
            try:
                if hasattr(self.recorder, "shutdown"):
                    self.recorder.shutdown()
            except Exception as e:
                logger.warning("Recorder shutdown: %s", e)
            self.recorder = None
        if self.whisper:
            try:
                del self.whisper
            except Exception as e:
                logger.debug("recarregar_stt del whisper: %s", e)
            self.whisper = None
        self._carregar_stt()
        print("[AUDIO] STT recarregado.")

    def recarregar_whisper(self):
        self.recarregar_stt()
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

    def _calibrar_microfone(self):
        if self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()
        with sr.Microphone() as source:
            self.rec_sr.adjust_for_ambient_noise(source, duration=1.5)
        if self.stream_vad and self.stream_vad.is_stopped():
            self.stream_vad.start_stream()
        print("[AUDIO] Microfone calibrado.")

    def _iniciar_mic(self):
        try:
            stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=CONF["rate"],
                                  input=True, frames_per_buffer=8000)
            stream.start_stream()
            return stream
        except Exception as e:
            logger.warning("Mic principal: %s", e)
            return None

    def _abrir_stream_vad_dedicado(self):
        try:
            stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=CONF["rate"],
                                  input=True, frames_per_buffer=CONF["vad_chunk"])
            stream.start_stream()
            return stream
        except Exception as e:
            logger.warning("Stream VAD dedicado: %s", e)
            return None

    def _efeitos_analogicos(self, audio, sr_rate):
        processado = self.board(audio, sr_rate)
        return (np.clip(processado, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

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
                if conf > settings.get("vad_threshold") and energia > settings.get("vad_energia"):
                    voz_consecutiva += 1
                else:
                    voz_consecutiva = max(0, voz_consecutiva - 1)
                if voz_consecutiva >= settings.get("vad_consecutivo"):
                    print("[MIRA] Interrupcao detectada.")
                    self.interrompido = True
            except Exception as e:
                logger.debug("monitorar_vad: %s", e)
                time.sleep(0.02)
        try:
            stream_dedicado.stop_stream()
            stream_dedicado.close()
        except Exception as e:
            logger.debug("fechar stream VAD: %s", e)

    def _processar_chunk(self, raw_bytes):
        buf = io.BytesIO(raw_bytes)
        data, sr_chunk = sf.read(buf)
        buf.close()
        mono = (data if len(data.shape) == 1 else data[:, 0]).astype(np.float32)
        return self._efeitos_analogicos(mono, sr_chunk), sr_chunk

<<<<<<< HEAD
    def _tocar_audio(self, audio_bytes, sr_rate):
        self.falando, self.interrompido = True, False

        stream_vad = self._abrir_stream_vad_dedicado()
        thread_vad = threading.Thread(
            target=self._monitorar_vad_thread,
            args=(stream_vad,),
            daemon=True
        )
        thread_vad.start()

        out = self.pa.open(format=pyaudio.paInt16, channels=1, rate=sr_rate, output=True)
        try:
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                if self.interrompido:
                    break
                out.write(audio_bytes[i:i + chunk_size])
        finally:
            out.stop_stream()
            out.close()

        self.falando = False
        return self.interrompido

    def _trim_silencio(self, audio, sr, limiar=0.018, pad_s=0.04):
        if audio is None or audio.size == 0:
            return audio
        amp = np.abs(audio)
        idx = np.where(amp > limiar)[0]
        if idx.size == 0:
            return audio[:0]
        pad = int(sr * pad_s)
        ini = max(0, int(idx[0]) - pad)
        fim = min(audio.size, int(idx[-1]) + pad)
        return audio[ini:fim]

    def _para_np(self, audio):
        if audio is None:
            return np.zeros(0, dtype=np.float32)
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        audio_np = np.asarray(audio, dtype=np.float32)
        if audio_np.ndim > 1:
            audio_np = np.mean(audio_np, axis=-1)
        return np.ascontiguousarray(audio_np)

    def _normalizar_tts(self, texto):
        def subst(m):
            w = m.group(0)
            chave = w.lower()
            if chave in _PRONUNCIA:
                return _PRONUNCIA[chave]
            return w
        return re.sub(r"[A-Za-zÀ-ÿ0-9_]+", subst, texto)

    def _token_ingles(self, tok):
        if re.search(r"[À-ÿ]", tok):
            return False
        low = tok.lower().strip(".")
        if low in _PT_CURTO or len(low) <= 2:
            return False
        if low in _EN_SET:
            return True
        if re.match(r"[A-Z][a-z]+[A-Z]", tok):
            return True
        if re.search(r"(?:th|wh|ck|tion|ness|ware|ing)$", low):
            return True
        if "w" in low or "y" in low:
            return True
        return False

    def _segmentos_tts(self, texto):
        if not self.kokoro_en:
            return [("pt", texto)]
        tokens = re.findall(r"[A-Za-zÀ-ÿ0-9_]+|[^\w]+", texto, flags=re.UNICODE)
        segs = []
        buf = ""
        lang = "pt"
        for tok in tokens:
            if not re.search(r"[A-Za-zÀ-ÿ0-9]", tok):
                buf += tok
                continue
            novo = "en" if self._token_ingles(tok) else "pt"
            if buf and novo != lang:
                trecho = buf.strip()
                if trecho:
                    segs.append((lang, trecho))
                buf = tok
                lang = novo
            else:
                buf += tok
                lang = novo
        if buf.strip():
            segs.append((lang, buf.strip()))
        return segs or [("pt", texto)]

    def _iter_audio_kokoro(self, txt, speed, gain):
        gap = np.zeros(int(CONF["kokoro_rate"] * 0.05), dtype=np.float32)
        primeiro = True
        for lang, trecho in self._segmentos_tts(txt):
            if self.interrompido:
                break
            if lang == "en" and self.kokoro_en:
                pipe = self.kokoro_en
                voz = CONF["kokoro_voz_en"]
            else:
                pipe = self.kokoro
                voz = CONF["kokoro_voz"]
            for _, _, audio in pipe(trecho, voice=voz, speed=speed, split_pattern=None):
                if self.interrompido:
                    break
                audio_np = self._para_np(audio) * gain
                audio_np = self._trim_silencio(audio_np, CONF["kokoro_rate"])
                if audio_np.size == 0:
                    continue
                if primeiro:
                    primeiro = False
                    yield audio_np
                else:
                    yield np.concatenate([gap, audio_np])

    def _falar_kokoro(self, txt, emocao):
        params = EMOCOES_KOKORO.get(emocao, EMOCOES_KOKORO["neutro"])
        gain = 10 ** (params["gain_db"] / 20) if params["gain_db"] != 0 else 1.0
        fila = queue.Queue()

        def produzir():
            try:
                for audio_np in self._iter_audio_kokoro(txt, params["speed"], gain):
                    if self.interrompido:
                        break
                    fila.put(audio_np)
            except Exception as e:
                fila.put(e)
            finally:
                fila.put(None)

        try:
            self.falando, self.interrompido = True, False
            stream_vad = self._abrir_stream_vad_dedicado()
            thread_vad = threading.Thread(
                target=self._monitorar_vad_thread,
                args=(stream_vad,),
                daemon=True
            )
            thread_vad.start()
            threading.Thread(target=produzir, daemon=True).start()

            out_stream = self.pa.open(
                format=pyaudio.paInt16, channels=1,
                rate=CONF["kokoro_rate"], output=True
            )
            tocou = False
            try:
                while True:
                    item = fila.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        if tocou:
                            break
                        raise item
                    if self.interrompido:
                        break
                    audio_bytes = self._efeitos_analogicos(
                        item.copy(), CONF["kokoro_rate"]
                    )
                    chunk_size = 4096
                    for i in range(0, len(audio_bytes), chunk_size):
                        if self.interrompido:
                            break
                        out_stream.write(audio_bytes[i:i + chunk_size])
                    tocou = True
            finally:
                out_stream.stop_stream()
                out_stream.close()
            self.falando = False
            return self.interrompido

        except Exception as e:
            print(f"[KOKORO] Erro: {e}, usando edge-tts.")
            self.falando = False
            if self.supervisor:
                self.supervisor.reparar("tts")
            return None

    async def _falar_streaming_edge(self, txt, params):
        comunicar = edge_tts.Communicate(txt, CONF["voice"], **params)
        fila_play = queue.Queue(maxsize=6)

=======
    async def _falar_streaming_edge(self, txt, params):
        padrao = r'(?<=[.!?]) +'
        sentencas = [s.strip() for s in re.split(padrao, txt) if s.strip()]
        if not sentencas:
            sentencas = [txt]
        fila_play = queue.Queue(maxsize=5)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        self.falando, self.interrompido = True, False
        stream_vad = self._abrir_stream_vad_dedicado()
        thread_vad = threading.Thread(target=self._monitorar_vad_thread, args=(stream_vad,), daemon=True)
        thread_vad.start()
        out_stream_ref = [None]
        def _tocar():
            while True:
                item = fila_play.get()
                if item is None or self.interrompido:
                    break
                audio_bytes, sr_chunk = item
                if out_stream_ref[0] is None:
                    out_stream_ref[0] = self.pa.open(format=pyaudio.paInt16, channels=1, rate=sr_chunk, output=True)
                chunk_size = 4096
                for i in range(0, len(audio_bytes), chunk_size):
                    if self.interrompido:
                        break
                    out_stream_ref[0].write(audio_bytes[i:i + chunk_size])
            if out_stream_ref[0]:
                out_stream_ref[0].stop_stream()
                out_stream_ref[0].close()
        thread_play = threading.Thread(target=_tocar, daemon=True)
        thread_play.start()
        for sentenca in sentencas:
            if self.interrompido:
                break
            comunicar = edge_tts.Communicate(sentenca, CONF["voice"], **params)
            acumulador = io.BytesIO()
            async for chunk in comunicar.stream():
                if self.interrompido:
                    break
                if chunk["type"] == "audio":
                    acumulador.write(chunk["data"])
            if acumulador.tell() > 0 and not self.interrompido:
                try:
                    audio_proc = self._processar_chunk(acumulador.getvalue())
                    fila_play.put(audio_proc)
                except Exception as e:
                    logger.error("Erro MP3 ignorado: %s", e)
            acumulador.close()
        fila_play.put(None)
        thread_play.join()
        self.falando = False
        return self.interrompido

    def falar(self, texto, emocao="neutro"):
        if not texto:
            return False
<<<<<<< HEAD

        txt = html.unescape(texto).replace("<", "").replace(">", "").strip()
        txt = re.sub(r"\.{3,}", ".", txt)
        txt = self._normalizar_tts(txt)
=======
        txt = html.unescape(texto.replace("... ", ", hmmm... ")).replace("<", "").replace(">", "").strip()
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        print(f"[REGISTRO] Falando: {txt}...")
        if not _EDGETTS_OK:
            print("[TTS] Sem engine disponivel.")
            return False
        params = EMOCOES_EDGE.get(emocao, EMOCOES_EDGE["neutro"])
        async def _executar():
            try:
                if self.interrompido:
                    await asyncio.sleep(0.1)
                return await self._falar_streaming_edge(txt, params)
            except Exception as e:
                print(f"[ERRO TTS] {e}")
                return False
        future = asyncio.run_coroutine_threadsafe(_executar(), self._loop)
        return future.result()

    def prequecer(self):
        if _EDGETTS_OK:
            asyncio.run_coroutine_threadsafe(self._prequecer_edge(), self._loop)

<<<<<<< HEAD
    def _prequecer_kokoro(self):
        try:
            list(self.kokoro("ok", voice=CONF["kokoro_voz"], speed=1.0, split_pattern=None))
            if self.kokoro_en:
                list(self.kokoro_en("ok", voice=CONF["kokoro_voz_en"], speed=1.0, split_pattern=None))
        except:
            pass

=======
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
    async def _prequecer_edge(self):
        try:
            comunicar = edge_tts.Communicate(" ", CONF["voice"])
            async for _ in comunicar.stream():
                break
        except Exception as e:
            logger.debug("prequecer edge: %s", e)

    def preparar_ouvir(self):
        if self.recorder:
            return
        if self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()

    def ouvir_wake_word(self):
        if not self.stream_vad:
            if self.supervisor:
                self.supervisor.reparar("mic")
        if self.stream_vad and self.stream_vad.is_stopped():
            try:
                self.stream_vad.start_stream()
            except Exception:
                if self.supervisor:
                    self.supervisor.reparar("mic")
        print("[REGISTRO] Aguardando Wake Word...")
        while True:
            try:
                if not self.stream_vad:
                    if self.supervisor:
                        self.supervisor.reparar("mic")
                    time.sleep(0.5)
                    continue
                if not self.rec_vosk:
                    time.sleep(0.5)
                    continue
                data = self.stream_vad.read(4000, exception_on_overflow=False)
                self._falhas_mic = 0
                if self.rec_vosk.AcceptWaveform(data):
                    res = json.loads(self.rec_vosk.Result())
                    bruto = res.get("text", "") or ""
                else:
                    res = json.loads(self.rec_vosk.PartialResult())
<<<<<<< HEAD
                    bruto = res.get("partial", "") or ""

                if "registro" in bruto.lower():
                    self._comando_pendente = self._resto_apos_wake(bruto)
                    self.rec_vosk.Reset()
                    return True
            except Exception:
                self._falhas_mic += 1
                if self._falhas_mic >= 3 and self.supervisor:
                    self.supervisor.reparar("mic")
                    self._falhas_mic = 0
                time.sleep(0.2)
=======
                if "registro" in res.get("text", "") or "registro" in res.get("partial", ""):
                    self.rec_vosk.Reset()
                    return True
            except Exception as e:
                logger.debug("wake_word loop: %s", e)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

    def _construir_prompt_contextual(self):
        return self._prompt_stt(groq=False)

    def _np_para_wav(self, audio_np, sr_rate=16000):
        import wave
        clip = np.clip(audio_np.astype(np.float32), -1.0, 1.0)
        int16 = (clip * 32767.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr_rate)
            w.writeframes(int16.tobytes())
        return buf.getvalue()

    def _transcrever_groq(self, audio_np):
        from app.core.chat_compat import transcrever_groq_wav
        wav = self._np_para_wav(audio_np, CONF["rate"])
        texto = transcrever_groq_wav(
            wav,
            api_key=config.GROQ_API_KEY,
            prompt=self._prompt_stt(groq=True),
            modelo=config.GROQ_WHISPER_MODELO,
        )
        return (texto or "").strip()

    def _resto_apos_wake(self, texto):
        if not texto:
            return None
        m = re.search(r"registro[\s,.:;!-]*", texto, flags=re.IGNORECASE)
        if not m:
            return None
        resto = texto[m.end():].strip(" ,.-")
        return resto or None

    def _limpar_wake(self, texto):
        if not texto:
            return ""
        return re.sub(r"^(registro)[\s,.:;!-]*", "", texto.strip(), flags=re.IGNORECASE).strip()

    def _juntar_comando(self, pendente, transcrito):
        p = self._limpar_wake(pendente or "")
        t = self._limpar_wake(transcrito or "")
        if p and t:
            if p.lower() in t.lower():
                return t
            if t.lower() in p.lower():
                return p
            return (p + " " + t).strip()
        return t or p or None

    def _transcrever_audio(self, audio_np):
        if audio_np is None or len(audio_np) == 0:
            return None
        t0 = time.time()
        if self.whisper:
            try:
                texto = self._whisper_texto(audio_np)
                print(f"[LAT] stt={time.time() - t0:.2f}s")
                return texto
            except Exception as e:
                print(f"[WHISPER] Falha: {e}")
                if self._cuda_indisponivel(e):
                    self._stt_cuda_morto = True
                    settings.set("whisper_device", "cpu")
                    if self._carregar_whisper_fallback(forcar_device="cpu"):
                        try:
                            texto = self._whisper_texto(audio_np)
                            print(f"[LAT] stt={time.time() - t0:.2f}s")
                            return texto
                        except Exception as e2:
                            print(f"[WHISPER] CPU tambem falhou: {e2}")
                if self.supervisor:
                    self.supervisor.reparar("stt")
        try:
            audio_int16 = (audio_np * 32768).astype(np.int16)
            audio_sr_data = sr.AudioData(audio_int16.tobytes(), 16000, 2)
            texto = self.rec_sr.recognize_google(audio_sr_data, language="pt-BR")
            print(f"[LAT] stt={time.time() - t0:.2f}s")
            return texto
        except Exception:
            print(f"[LAT] stt={time.time() - t0:.2f}s")
            return None

    def _whisper_texto(self, audio_np):
        kwargs = dict(
            language="pt",
            beam_size=1,
            temperature=0.0,
            initial_prompt=self._construir_prompt_contextual(),
            vad_filter=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )
        try:
            segments, _ = self.whisper.transcribe(audio_np, without_timestamps=True, **kwargs)
        except TypeError:
            segments, _ = self.whisper.transcribe(audio_np, **kwargs)
        texto = " ".join(s.text for s in segments).strip()
        if texto:
            print(f"[WHISPER] {texto}")
        return texto or None

    def ouvir_comando(self):
        if not self.recorder and self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()
        print("[REGISTRO] Ouvindo comando...")
<<<<<<< HEAD
        pendente = self._comando_pendente
        self._comando_pendente = None

        if self.recorder:
            try:
                texto = self.recorder.text()
                if texto:
                    print(f"[REALTIME] {texto}")
                    if self.stream_vad and self.stream_vad.is_stopped():
                        self.stream_vad.start_stream()
                    junto = self._juntar_comando(pendente, texto)
                    return junto
            except Exception as e:
                print(f"[REALTIME] Erro: {e}")
                if self.supervisor:
                    self.supervisor.reparar("stt")

        audio_np = self._gravar_com_vad_manual(timeout_onset=2.5, timeout_total=20)
        if audio_np is None and not pendente:
=======
        if self._deve_usar_groq_stt():
            audio_np = self._gravar_com_vad_manual()
            if audio_np is not None and len(audio_np) > 0:
                try:
                    t = self._transcrever_groq(audio_np)
                    if t:
                        print(f"[GROQ-STT] {t}")
                        if self.stream_vad and self.stream_vad.is_stopped():
                            self.stream_vad.start_stream()
                        return t
                except Exception as e:
                    logger.warning("Groq STT falhou, caindo no Whisper local: %s", e)
        if self.recorder and not self._deve_usar_groq_stt():
            timeout = float(settings.get("stt_recorder_timeout_sec") or 60.0)
            timeout = max(15.0, min(180.0, timeout))
            caixa = {"texto": None, "erro": None}
            def _rec_text():
                try:
                    caixa["texto"] = self.recorder.text()
                except Exception as e:
                    caixa["erro"] = e
            th = threading.Thread(target=_rec_text, daemon=True)
            th.start()
            th.join(timeout=timeout)
            if th.is_alive():
                logger.warning("RealtimeSTT excedeu %.0fs; usando gravacao VAD/Whisper.", timeout)
            elif caixa["erro"]:
                print(f"[REALTIME] Erro: {caixa['erro']}")
            elif caixa["texto"]:
                t = (caixa["texto"] or "").strip()
                if t:
                    print(f"[REALTIME] {t}")
                    if self.stream_vad and self.stream_vad.is_stopped():
                        self.stream_vad.start_stream()
                    return t
        audio_np = self._gravar_com_vad_manual()
        if audio_np is None:
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
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
<<<<<<< HEAD
            except Exception:
                if self.stream_vad and self.stream_vad.is_stopped():
                    self.stream_vad.start_stream()
                return None

        transcrito = self._transcrever_audio(audio_np) if audio_np is not None else None
        junto = self._juntar_comando(pendente, transcrito)
        if self.stream_vad and self.stream_vad.is_stopped():
            self.stream_vad.start_stream()
        return junto

    def _gravar_com_vad_manual(self, timeout_onset=8, timeout_total=20):
=======
            except Exception as e:
                logger.debug("listen fallback: %s", e)
                if self.stream_vad and self.stream_vad.is_stopped():
                    self.stream_vad.start_stream()
                return None
        if audio_np is None or len(audio_np) == 0:
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return None
        if self.whisper:
            try:
                beam = int(settings.get("whisper_beam_size") or 3)
                beam = max(1, min(5, beam))
                audio_in = np.clip(audio_np.astype(np.float32), -1.0, 1.0)
                segments, _ = self.whisper.transcribe(
                    audio_in,
                    language="pt",
                    beam_size=beam,
                    initial_prompt=self._construir_prompt_contextual(),
                    vad_filter=False,
                    temperature=[0.0, 0.2, 0.4],
                    condition_on_previous_text=False,
                    no_speech_threshold=0.3,
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
            clip = np.clip(audio_np.astype(np.float32), -1.0, 1.0)
            audio_int16 = (clip * 32767.0).astype(np.int16)
            audio_sr_data = sr.AudioData(audio_int16.tobytes(), 16000, 2)
            texto = self.rec_sr.recognize_google(audio_sr_data, language="pt-BR")
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return texto
        except sr.UnknownValueError:
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return None
        except Exception as e:
            logger.debug("recognize_google: %s", e)
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return None

    def _gravar_com_vad_manual(self):
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        if not self.vad_model:
            return None
        if self._stream_gravacao is None:
            try:
                self._stream_gravacao = self.pa.open(
                    format=pyaudio.paInt16, channels=1,
                    rate=CONF["rate"], input=True,
                    frames_per_buffer=CONF["vad_chunk"]
                )
<<<<<<< HEAD
            except Exception:
                if self.supervisor:
                    self.supervisor.reparar("mic")
=======
            except Exception as e:
                logger.warning("gravacao stream open: %s", e)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
                return None
        try:
            if self._stream_gravacao.is_stopped():
                self._stream_gravacao.start_stream()
<<<<<<< HEAD
        except Exception:
=======
        except Exception as e:
            logger.debug("gravacao start: %s", e)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
            self._stream_gravacao = None
            if self.supervisor:
                self.supervisor.reparar("mic")
            return None
        frames_gravados = []
        preroll = []
        frames_silencio = 0
        frames_voz = 0
        falando_detectado = False
        inicio = time.time()
        inicio_fala = None
        buf = np.empty(CONF["vad_chunk"], dtype=np.float32)
<<<<<<< HEAD
        limiar = float(settings.get("vad_threshold") or 0.5)
        energia_min = float(settings.get("vad_energia") or 0.02)
        limiar_onset = min(limiar, 0.6)
        limiar_hold = min(0.35, limiar * 0.55)
        energia_hold = max(0.008, energia_min * 0.25)

        print("[VAD] Aguardando voz...")
        t_vad = time.time()

        while True:
            agora = time.time()
            if falando_detectado and inicio_fala and agora - inicio_fala > timeout_total:
                break
            if not falando_detectado and agora - inicio > timeout_onset:
                break
            try:
                raw = self._stream_gravacao.read(CONF["vad_chunk"], exception_on_overflow=False)
            except Exception:
=======
        limiar = float(settings.get("stt_vad_threshold") or 0.58)
        limiar = max(0.35, min(0.92, limiar))
        energia_min = float(settings.get("stt_vad_energia") or 0.06)
        energia_min = max(0.01, min(0.35, energia_min))
        frames_fim = int(settings.get("stt_frames_silencio_fim") or 34)
        frames_fim = max(18, min(55, frames_fim))
        min_voz = int(settings.get("stt_min_frames_voz") or 4)
        min_voz = max(2, min(15, min_voz))
        max_espera = float(settings.get("stt_max_espera_seg") or 10.0)
        max_espera = max(5.0, min(25.0, max_espera))
        print("[VAD] Aguardando voz...")
        while True:
            if time.time() - inicio > max_espera:
                break
            try:
                raw = self._stream_gravacao.read(CONF["vad_chunk"], exception_on_overflow=False)
            except Exception as e:
                logger.debug("gravacao read: %s", e)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
                break
            np.copyto(buf, np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0)
            energia = np.sqrt(np.mean(buf ** 2))
            with torch.no_grad():
                tensor = torch.from_numpy(buf)
                conf = self.vad_model(tensor, 16000).item()
                del tensor
<<<<<<< HEAD

            if falando_detectado:
                eh_voz = conf > limiar_hold or energia > energia_hold
            else:
                eh_voz = conf > limiar_onset and energia > energia_min

=======
            eh_voz = conf > limiar and energia > energia_min
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
            if eh_voz:
                if not falando_detectado:
                    falando_detectado = True
                    inicio_fala = agora
                    print("[VAD] Voz detectada.")
                    frames_gravados.extend(preroll)
                    preroll = []
                frames_voz += 1
                frames_silencio = 0
                frames_gravados.append(raw)
            elif falando_detectado:
                frames_silencio += 1
<<<<<<< HEAD
                if frames_silencio <= 12:
                    frames_gravados.append(raw)
                if frames_silencio >= 28 and energia < energia_hold:
                    print("[VAD] Fim de fala.")
                    break
                if frames_silencio >= 42:
                    print("[VAD] Fim de fala.")
                    break
            else:
                preroll.append(raw)
                if len(preroll) > 15:
                    preroll.pop(0)

        print(f"[LAT] vad={time.time() - t_vad:.2f}s")

        if frames_voz < 5:
=======
                if frames_silencio >= frames_fim:
                    print("[VAD] Fim de fala.")
                    break
        if frames_voz < min_voz:
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
            return None
        audio_bytes = b"".join(frames_gravados)
        return np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0
