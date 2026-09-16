import sys
from unittest.mock import MagicMock

import config
import settings
from app.core.roteador import (
    chave_gemini_unica,
    cuda_livre_para_stt,
    groq_ok,
    ordem_provedores,
)


def test_ordem_auto_groq_gemini_ollama(monkeypatch):
    assert ordem_provedores("auto", tem_groq=True, tem_gemini=True) == ["groq", "gemini", "ollama"]
    assert ordem_provedores("auto", tem_groq=False, tem_gemini=True) == ["gemini", "ollama"]
    assert ordem_provedores("auto", tem_groq=True, tem_gemini=False) == ["groq", "ollama"]
    assert ordem_provedores("groq") == ["groq"]
    assert ordem_provedores("ollama") == ["ollama"]


def test_chave_gemini_unica_ignora_rotacao(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "API_KEYS", ["proj-a-key-1", "proj-a-key-2"])
    monkeypatch.setattr(config, "API_KEY", "proj-a-key-1")
    assert chave_gemini_unica() == "proj-a-key-1"


def test_groq_ok_le_config(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "gsk_test")
    assert groq_ok() is True
    monkeypatch.setattr(config, "GROQ_API_KEY", "  ")
    assert groq_ok() is False


def test_settings_default_whisper_small_cuda():
    assert settings._PADROES["whisper_modelo"] == "small"
    assert settings._PADROES["whisper_device"] == "cuda"
    assert settings._PADROES["llm_provedor"] == "auto"
    assert settings._PADROES["stt_groq_se_cuda_ocupada"] is True


def test_cuda_livre_para_stt(monkeypatch):
    monkeypatch.setattr(settings, "get", lambda chave: "cuda" if chave == "whisper_device" else None)
    fake = MagicMock()
    fake.cuda.is_available.return_value = True
    fake.cuda.mem_get_info.return_value = (200 * 1024 * 1024, 6 * 1024 * 1024 * 1024)
    monkeypatch.setitem(sys.modules, "torch", fake)
    assert cuda_livre_para_stt(800) is False
    fake.cuda.mem_get_info.return_value = (900 * 1024 * 1024, 6 * 1024 * 1024 * 1024)
    assert cuda_livre_para_stt(800) is True
    monkeypatch.setattr(settings, "get", lambda chave: "cpu")
    assert cuda_livre_para_stt(800) is False
