"""Vocabulário PT-BR para Whisper (RealtimeSTT, faster-whisper e Groq)."""
from __future__ import annotations

import json
import os

# Groq Whisper aceita prompt de estilo até ~224 tokens.
LIMITE_GROQ_CHARS = 800

HOTWORDS_FERRAMENTAS = (
    "Registro", "REGISTRO", "WhatsApp", "clipboard", "volume",
    "configuracoes", "configurações", "lembrete", "microfone",
    "MAGI", "CUDA", "Whisper", "Gemini", "Groq", "Ollama",
    "pywebview", "pausar", "aumenta", "diminui", "mudo",
)

_PROMPT_BASE = (
    "Transcricao em portugues do Brasil (PT-BR). "
    "Usuario fala portugues brasileiro informal: girias, abreviacoes, internet, tecnologia. "
    "Exemplos: cara, mano, beleza, valeu, ta, ne, po, oxe, vei, role, "
    "abre, fecha, muda, aumenta, diminui, Registro, computador."
)


def normalizar_modelo_whisper(modelo: str | None) -> str:
    """Default small multilingual. Nunca base nem *.en nesta GPU."""
    nome = str(modelo or "small").strip() or "small"
    if nome.endswith(".en"):
        nome = nome[:-3] or "small"
    if nome == "base":
        nome = "small"
    return nome


def nomes_do_perfil(usuario_path: str | None) -> list[str]:
    if not usuario_path or not os.path.isfile(usuario_path):
        return []
    try:
        with open(usuario_path, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(dados, dict):
        return []
    nomes = []
    for chave in ("nome", "Name", "usuario", "user", "apelido", "cidade"):
        valor = dados.get(chave)
        if valor and str(valor).strip():
            nomes.append(str(valor).strip())
    return nomes


def montar_prompt_stt(contexto: str = "", usuario_path: str | None = None, limite: int | None = None) -> str:
    palavras = list(HOTWORDS_FERRAMENTAS)
    for nome in nomes_do_perfil(usuario_path):
        if nome not in palavras:
            palavras.append(nome)
    partes = [_PROMPT_BASE, "Palavras: " + ", ".join(palavras) + "."]
    ctx = (contexto or "").strip()
    if ctx:
        partes.append("Contexto recente: " + ctx[:220])
    texto = " ".join(partes)
    if limite is not None:
        return texto[: max(0, int(limite))]
    return texto
