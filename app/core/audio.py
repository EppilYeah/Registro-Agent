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
from pedalboard import Pedalboard, Compressor, HighpassFilter, Gain, Limiter, PeakFilter, PitchShift, Delay, Reverb, Chorus

try:
    from kokoro import KPipeline
    _KOKORO_OK = True
except ImportError:
    _KOKORO_OK = False

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
    from faster_whisper import WhisperModel

CONF = {
    "rate": 16000, "chunk": 1024, "vad_chunk": 512,
    "voice": "pt-BR-ThalitaNeural",
    "paths": {"vosk": "modelo_vosk", "vad": "silero_vad.jit"},
    "kokoro_rate": 24000,
    "kokoro_voz": "pf_dora",
}

EMOCOES_EDGE = {
    "neutro":         {"rate": "+10%", "pitch": "-15Hz", "volume": "+0%"},
    "sarcasmo_tedio": {"rate": "+0%",  "pitch": "-15Hz", "volume": "+0%"},
    "irritado":       {"rate": "+25%", "pitch": "-5Hz",  "volume": "+10%"},
    "arrogante":      {"rate": "+5%",  "pitch": "-12Hz", "volume": "+0%"},
    "feliz":          {"rate": "+15%", "pitch": "-5Hz",  "volume": "+0%"},
    "confuso":        {"rate": "+5%",  "pitch": "-10Hz", "volume": "+0%"},
    "desconfiado":    {"rate": "+0%",  "pitch": "-18Hz", "volume": "-5%"},
    "ouvindo":        {"rate": "+10%", "pitch": "-15Hz", "volume": "+0%"},
}

EMOCOES_KOKORO = {
    "neutro":         {"speed": 0.9,  "gain_db": 0},
    "sarcasmo_tedio": {"speed": 0.85, "gain_db": 0},
    "irritado":       {"speed": 1.05, "gain_db": 2},
    "arrogante":      {"speed": 0.92, "gain_db": 0},
    "feliz":          {"speed": 0.95, "gain_db": 1},
    "confuso":        {"speed": 0.88, "gain_db": 0},
    "desconfiado":    {"speed": 0.82, "gain_db": -1},
    "ouvindo":        {"speed": 0.9,  "gain_db": 0},
}

BUFFER_TTS_BYTES = 32768

_WHISPER_PROMPT_BASE = (
    "Assistente de voz em portugues brasileiro informal. "
    "O usuario fala de forma casual, com girias, abreviacoes e linguagem coloquial. "
    "Exemplos: cara, mano, abre, fecha, muda, aumenta, diminui, ta, ne, po, oxe, vei."
)


class AudioHandler:
    def __init__(self, funcao_contexto_historico=None):
        self.pa = pyaudio.PyAudio()
        self.root = os.path.dirname(os.path.abspath(__file__))
        self.funcao_contexto_historico = funcao_contexto_historico

        self.falando = False
        self.interrompido = False
        self._stream_gravacao = None

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

        self._carregar_modelos()
        self.stream_vad = self._iniciar_mic()
        self._calibrar_microfone()

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

        self._carregar_kokoro()
        self._carregar_stt()

        self.rec_sr = sr.Recognizer()
        self.rec_sr.pause_threshold = 0.8
        self.rec_sr.non_speaking_duration = 0.3
        self.rec_sr.energy_threshold = settings.get("energia_microfone")
        self.rec_sr.dynamic_energy_threshold = False

    def _carregar_kokoro(self):
        if not _KOKORO_OK:
            self.kokoro = None
            print("[AUDIO] Kokoro indisponivel, usando edge-tts.")
            return
        try:
            self.kokoro = KPipeline(lang_code='p')
            print(f"[AUDIO] Kokoro carregado (voz: {CONF['kokoro_voz']}).")
        except Exception as e:
            self.kokoro = None
            print(f"[AUDIO] Kokoro falhou: {e}")

    def _carregar_stt(self):
        if _REALTIMESTT_OK:
            try:
                self.recorder = AudioToTextRecorder(
                    model=settings.get("whisper_modelo") or "base",
                    language="pt",
                    silero_sensitivity=0.4,
                    webrtc_sensitivity=2,
                    post_speech_silence_duration=0.6,
                    min_length_of_recording=0.3,
                    min_gap_between_recordings=0.0,
                    spinner=False,
                    enable_realtime_transcription=False,
                )
                self.whisper = None
                print("[AUDIO] RealtimeSTT carregado.")
            except Exception as e:
                self.recorder = None
                print(f"[AUDIO] RealtimeSTT falhou: {e}")
                self._carregar_whisper_fallback()
        else:
            self.recorder = None
            self._carregar_whisper_fallback()

    def _carregar_whisper_fallback(self):
        modelo = settings.get("whisper_modelo") or "base"
        device = settings.get("whisper_device") or "cpu"
        compute = "float16" if device == "cuda" else "int8"
        try:
            self.whisper = WhisperModel(modelo, device=device, compute_type=compute)
            print(f"[AUDIO] Whisper {modelo} ({device}) carregado.")
        except Exception as e:
            self.whisper = None
            print(f"[AUDIO] Whisper indisponivel: {e}")

    def recarregar_whisper(self):
        modelo = settings.get("whisper_modelo") or "base"
        device = settings.get("whisper_device") or "cpu"
        if self.recorder:
            print("[AUDIO] RealtimeSTT ativo, ignorando troca de modelo.")
            return
        try:
            if self.whisper:
                del self.whisper
        except:
            pass
        self._carregar_whisper_fallback()

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

    def _falar_kokoro(self, txt, emocao):
        import re
        params = EMOCOES_KOKORO.get(emocao, EMOCOES_KOKORO["neutro"])
        gain = 10 ** (params["gain_db"] / 20) if params["gain_db"] != 0 else 1.0

        sentencas = [s.strip() for s in re.split(r'(?<=[.!?])\s+', txt) if s.strip()]
        if not sentencas:
            sentencas = [txt]

        try:
            self.falando, self.interrompido = True, False
            stream_vad = self._abrir_stream_vad_dedicado()
            thread_vad = threading.Thread(
                target=self._monitorar_vad_thread,
                args=(stream_vad,),
                daemon=True
            )
            thread_vad.start()

            out_stream = self.pa.open(
                format=pyaudio.paInt16, channels=1,
                rate=CONF["kokoro_rate"], output=True
            )

            for sentenca in sentencas:
                if self.interrompido:
                    break
                chunks = []
                for _, _, audio in self.kokoro(sentenca, voice=CONF["kokoro_voz"], speed=params["speed"]):
                    chunks.append(audio)
                if not chunks:
                    continue
                audio_np = np.concatenate(chunks).astype(np.float32) * gain
                audio_bytes = self._efeitos_analogicos(audio_np.copy(), CONF["kokoro_rate"])

                chunk_size = 4096
                for i in range(0, len(audio_bytes), chunk_size):
                    if self.interrompido:
                        break
                    out_stream.write(audio_bytes[i:i + chunk_size])

                if not self.interrompido and len(sentencas) > 1:
                    silencio = np.zeros(int(CONF["kokoro_rate"] * 0.18), dtype=np.int16)
                    out_stream.write(silencio.tobytes())

            out_stream.stop_stream()
            out_stream.close()
            self.falando = False
            return self.interrompido

        except Exception as e:
            print(f"[KOKORO] Erro: {e}, usando edge-tts.")
            self.falando = False
            return None

    async def _falar_streaming_edge(self, txt, params):
        comunicar = edge_tts.Communicate(txt, CONF["voice"], **params)
        fila_play = queue.Queue(maxsize=6)

        self.falando, self.interrompido = True, False

        stream_vad = self._abrir_stream_vad_dedicado()
        thread_vad = threading.Thread(
            target=self._monitorar_vad_thread,
            args=(stream_vad,),
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

        if acumulador.tell() > 0 and not self.interrompido:
            try:
                fila_play.put(self._processar_chunk(acumulador.getvalue()))
            except:
                pass
        acumulador.close()

        fila_play.put(None)
        thread_play.join()
        self.falando = False
        return self.interrompido

    def falar(self, texto, emocao="neutro"):
        if not texto:
            return False

        txt = html.unescape(texto.replace("... ", ", hmmm... ")).replace(
            "<", "").replace(">", "").strip()
        print(f"[REGISTRO] Falando: {txt}...")

        if self.kokoro:
            resultado = self._falar_kokoro(txt, emocao)
            if resultado is not None:
                return resultado

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
        if self.kokoro:
            threading.Thread(target=self._prequecer_kokoro, daemon=True).start()
        elif _EDGETTS_OK:
            asyncio.run_coroutine_threadsafe(self._prequecer_edge(), self._loop)

    def _prequecer_kokoro(self):
        try:
            list(self.kokoro(".", voice=CONF["kokoro_voz"], speed=1.0))
        except:
            pass

    async def _prequecer_edge(self):
        try:
            comunicar = edge_tts.Communicate(" ", CONF["voice"])
            async for _ in comunicar.stream():
                break
        except:
            pass

    def preparar_ouvir(self):
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
            except:
                pass

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

    def ouvir_comando(self):
        if self.stream_vad and not self.stream_vad.is_stopped():
            self.stream_vad.stop_stream()
        print("[REGISTRO] Ouvindo comando...")

        if self.recorder:
            try:
                texto = self.recorder.text()
                if texto:
                    print(f"[REALTIME] {texto}")
                    if self.stream_vad and self.stream_vad.is_stopped():
                        self.stream_vad.start_stream()
                    return texto.strip()
            except Exception as e:
                print(f"[REALTIME] Erro: {e}")

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
            except:
                if self.stream_vad and self.stream_vad.is_stopped():
                    self.stream_vad.start_stream()
                return None

        if audio_np is None or len(audio_np) == 0:
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return None

        if self.whisper:
            try:
                segments, _ = self.whisper.transcribe(
                    audio_np,
                    language="pt",
                    beam_size=5,
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
            audio_int16 = (audio_np * 32768).astype(np.int16)
            audio_sr_data = sr.AudioData(audio_int16.tobytes(), 16000, 2)
            texto = self.rec_sr.recognize_google(audio_sr_data, language="pt-BR")
            if self.stream_vad and self.stream_vad.is_stopped():
                self.stream_vad.start_stream()
            return texto
        except:
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
            except:
                return None
        try:
            if self._stream_gravacao.is_stopped():
                self._stream_gravacao.start_stream()
        except:
            self._stream_gravacao = None
            return None

        frames_gravados = []
        frames_silencio = 0
        frames_voz = 0
        falando_detectado = False
        inicio = time.time()
        buf = np.empty(CONF["vad_chunk"], dtype=np.float32)

        print("[VAD] Aguardando voz...")

        while True:
            if time.time() - inicio > 8:
                break
            try:
                raw = self._stream_gravacao.read(CONF["vad_chunk"], exception_on_overflow=False)
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
                if frames_silencio >= 30:
                    print("[VAD] Fim de fala.")
                    break

        if frames_voz < 5:
            return None

        audio_bytes = b"".join(frames_gravados)
        return np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0