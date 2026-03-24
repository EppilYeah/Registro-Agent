import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_CAMINHO = os.path.join(_DIR, "data", "settings.json")

_PADROES = {
    "vad_ativo": True,
    "camera_ativa": True,
    "vad_threshold": 0.88,
    "vad_energia": 0.08,
    "vad_consecutivo": 8,
    "energia_microfone": 300,
    "modelo": "gemini-2.5-flash",
    "modo_debug": False,
    "comportamento_espontaneo": True,
    "espontaneo_cooldown_min": 20,
    "espontaneo_limite_diario": 3,
    "modo_ambient_timeout_min": 5,
    "dormindo_timeout_min": 15,
    "whisper_modelo": "base",
    "whisper_device": "cpu",
}

_cfg = {}

def carregar():
    global _cfg
    _cfg = _PADROES.copy()
    try:
        with open(_CAMINHO, 'r', encoding='utf-8') as f:
            _cfg.update(json.load(f))
    except:
        pass
    return _cfg

def salvar():
    try:
        os.makedirs(os.path.dirname(_CAMINHO), exist_ok=True)
        with open(_CAMINHO, 'w', encoding='utf-8') as f:
            json.dump(_cfg, f, indent=2, ensure_ascii=False)
    except:
        pass

def get(chave):
    return _cfg.get(chave, _PADROES.get(chave))

def set(chave, valor):
    _cfg[chave] = valor
    salvar()

def todos():
    return _cfg.copy()