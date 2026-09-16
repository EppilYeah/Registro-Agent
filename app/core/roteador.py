"""Ordem Groq → Gemini → Ollama CPU. Sem 8B na 1660 Super."""
from __future__ import annotations

import os

import config
import settings


def chave_gemini_unica() -> str | None:
    """Cota Gemini é por projeto. Só uma chave — rotação no mesmo projeto não aumenta quota."""
    direta = (os.getenv("GEMINI_API_KEY") or "").strip()
    if direta:
        return direta
    if config.API_KEYS:
        return config.API_KEYS[0]
    if config.API_KEY:
        return str(config.API_KEY).strip() or None
    return None


def groq_ok() -> bool:
    return bool((config.GROQ_API_KEY or "").strip())


def ollama_host() -> str:
    return (settings.get("ollama_host") or config.OLLAMA_HOST or "http://127.0.0.1:11434").rstrip("/")


def groq_modelo() -> str:
    return settings.get("groq_modelo") or config.GROQ_MODELO


def ollama_modelo() -> str:
    return settings.get("ollama_modelo") or config.OLLAMA_MODELO


def ordem_provedores(modo: str | None = None, *, tem_groq: bool | None = None, tem_gemini: bool | None = None) -> list[str]:
    modo = (modo if modo is not None else settings.get("llm_provedor") or "auto").lower().strip()
    if modo in ("groq", "gemini", "ollama"):
        return [modo]
    if tem_groq is None:
        tem_groq = groq_ok()
    if tem_gemini is None:
        tem_gemini = bool(chave_gemini_unica())
    ordem = []
    if tem_groq:
        ordem.append("groq")
    if tem_gemini:
        ordem.append("gemini")
    ordem.append("ollama")
    return ordem


def cuda_livre_para_stt(minimo_mb: float = 800.0) -> bool:
    """True se a 1660 Super (ou outra CUDA) tem VRAM para Whisper small."""
    device = str(settings.get("whisper_device") or "cuda").lower()
    if device in ("cpu", "groq"):
        return False
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        livre, _total = torch.cuda.mem_get_info()
        return (livre / (1024 * 1024)) >= float(minimo_mb)
    except Exception:
        return False


def usar_groq_stt(*, tem_groq: bool | None = None, device: str | None = None, se_cuda_ocupada=None) -> bool:
    """Groq Whisper só se a chave existir e (device=groq ou CUDA sem VRAM)."""
    if tem_groq is None:
        tem_groq = groq_ok()
    if not tem_groq:
        return False
    device = str(device if device is not None else (settings.get("whisper_device") or "cuda")).lower()
    if device == "groq":
        return True
    if se_cuda_ocupada is None:
        se_cuda_ocupada = settings.get("stt_groq_se_cuda_ocupada")
    if se_cuda_ocupada is False:
        return False
    return not cuda_livre_para_stt()

