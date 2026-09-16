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
import pyaudio
import vosk
import torch
import settings
import speech_recognition as sr
import soundfile as sf
import numpy as np
import config
from pedalboard import Pedalboard, Compressor, HighpassFilter, Gain, Limiter, PeakFilter, PitchShift, Delay, Reverb, Chorus
from app.core.stt_vocab import LIMITE_GROQ_CHARS, montar_prompt_stt, normalizar_modelo_whisper
from app.core.roteador import groq_ok, usar_groq_stt

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
    _WHISPER_OK = True
except ImportError:
    _WHISPER_OK = False

CONF = {
    "rate": 16000, "chunk": 1024, "vad_chunk": 512,
    "voice": "pt-BR-ThalitaNeural",
    "paths": {"vosk": "modelo_vosk", "vad": "silero_vad.jit"},
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

logger = logging.getLogger(__name__)

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
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()
        self.board = Pedalboard([
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

    async def _falar_streaming_edge(self, txt, params):
        padrao = r'(?<=[.!?]) +'
        sentencas = [s.strip() for s in re.split(padrao, txt) if s.strip()]
        if not sentencas:
            sentencas = [txt]
        fila_play = queue.Queue(maxsize=5)
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
        txt = html.unescape(texto.replace("... ", ", hmmm... ")).replace("<", "").replace(">", "").strip()
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
        if self.stream_vad and self.stream_vad.is_stopped():
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
            except Exception as e:
                logger.debug("wake_word loop: %s", e)

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

    def ouvir_comando(self):
        if not self.recorder and self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()
        print("[REGISTRO] Ouvindo comando...")
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
        if not self.vad_model:
            return None
        if self._stream_gravacao is None:
            try:
                self._stream_gravacao = self.pa.open(
                    format=pyaudio.paInt16, channels=1,
                    rate=CONF["rate"], input=True,
                    frames_per_buffer=CONF["vad_chunk"]
                )
            except Exception as e:
                logger.warning("gravacao stream open: %s", e)
                return None
        try:
            if self._stream_gravacao.is_stopped():
                self._stream_gravacao.start_stream()
        except Exception as e:
            logger.debug("gravacao start: %s", e)
            self._stream_gravacao = None
            return None
        frames_gravados = []
        frames_silencio = 0
        frames_voz = 0
        falando_detectado = False
        inicio = time.time()
        buf = np.empty(CONF["vad_chunk"], dtype=np.float32)
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
                break
            np.copyto(buf, np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0)
            energia = np.sqrt(np.mean(buf ** 2))
            with torch.no_grad():
                tensor = torch.from_numpy(buf)
                conf = self.vad_model(tensor, 16000).item()
                del tensor
            eh_voz = conf > limiar and energia > energia_min
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
                if frames_silencio >= frames_fim:
                    print("[VAD] Fim de fala.")
                    break
        if frames_voz < min_voz:
            return None
        audio_bytes = b"".join(frames_gravados)
        return np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0