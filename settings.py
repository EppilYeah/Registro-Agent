import json
import logging
import os

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
_CAMINHO = os.path.join(_DIR, "data", "settings.json")

_PADROES = {
    "vad_ativo": True,
    "camera_ativa": True,
    "vad_threshold": 0.5,
    "vad_energia": 0.02,
    "vad_consecutivo": 8,
    "energia_microfone": 300,
<<<<<<< HEAD
    "modelo": "gemini-flash-latest",
=======
    "modelo": "gemini-2.5-flash",
    "llm_provedor": "auto",
    "groq_modelo": "openai/gpt-oss-20b",
    "ollama_modelo": "qwen3:8b",
    "ollama_host": "http://127.0.0.1:11434",
    "stt_groq_se_cuda_ocupada": True,
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
    "modo_debug": False,
    "comportamento_espontaneo": True,
    "espontaneo_cooldown_min": 20,
    "espontaneo_limite_diario": 3,
    "modo_ambient_timeout_min": 5,
    "dormindo_timeout_min": 15,
<<<<<<< HEAD
    "whisper_modelo": "base",
    "whisper_device": "cpu",
    "palace_path": "",
    "palace_max_distancia": 0.0,
=======
    "whisper_modelo": "small",
    "whisper_device": "cuda",
    "whisper_beam_size": 3,
    "stt_vad_threshold": 0.58,
    "stt_vad_energia": 0.06,
    "stt_frames_silencio_fim": 34,
    "stt_min_frames_voz": 4,
    "stt_max_espera_seg": 10.0,
    "stt_recorder_timeout_sec": 60.0,
    "stt_post_speech_silence_sec": 0.65,
    "stt_realtime_silero_sensitivity": 0.45,
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
}

_cfg = {}

def carregar():
    global _cfg
    _cfg = _PADROES.copy()
    try:
        with open(_CAMINHO, 'r', encoding='utf-8') as f:
            _cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("settings carregar: %s", e)
    return _cfg

def salvar():
    try:
        os.makedirs(os.path.dirname(_CAMINHO), exist_ok=True)
        with open(_CAMINHO, 'w', encoding='utf-8') as f:
            json.dump(_cfg, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.warning("settings salvar: %s", e)

def get(chave):
    return _cfg.get(chave, _PADROES.get(chave))

def set(chave, valor):
    _cfg[chave] = valor
    salvar()

def todos():
    return _cfg.copy()