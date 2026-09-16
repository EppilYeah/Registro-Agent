import json
import os
import tempfile

from app.core.stt_vocab import HOTWORDS_FERRAMENTAS, LIMITE_GROQ_CHARS, montar_prompt_stt, nomes_do_perfil, normalizar_modelo_whisper


def test_nomes_do_perfil_usuario_json():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "usuario.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"nome": "Luis Felipe", "apelido": "Luis", "cidade": "Recife"}, f)
        nomes = nomes_do_perfil(caminho)
    assert "Luis Felipe" in nomes
    assert "Luis" in nomes
    assert "Recife" in nomes


def test_nomes_do_perfil_arquivo_ausente():
    assert nomes_do_perfil("/tmp/nao-existe-registro-usuario.json") == []


def test_montar_prompt_inclui_registro_tools_e_nomes():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "usuario.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"nome": "Luis Felipe"}, f)
        prompt = montar_prompt_stt(contexto="aumenta o volume", usuario_path=caminho)
    assert "portugues" in prompt.lower() or "PT-BR" in prompt
    assert "Registro" in prompt
    assert "WhatsApp" in prompt
    assert "Luis Felipe" in prompt
    for palavra in ("volume", "clipboard", "CUDA"):
        assert palavra in HOTWORDS_FERRAMENTAS
        assert palavra in prompt
    assert "aumenta o volume" in prompt


def test_whisper_default_small_nao_base_nem_en():
    assert normalizar_modelo_whisper("small") == "small"
    assert normalizar_modelo_whisper("base") == "small"
    assert normalizar_modelo_whisper("small.en") == "small"
    assert normalizar_modelo_whisper("base.en") == "small"
    assert normalizar_modelo_whisper("") == "small"
    assert normalizar_modelo_whisper(None) == "small"


def test_montar_prompt_respeita_limite_groq():
    longo = montar_prompt_stt(contexto="x" * 2000)
    curto = montar_prompt_stt(contexto="x" * 2000, limite=LIMITE_GROQ_CHARS)
    assert len(curto) <= LIMITE_GROQ_CHARS
    assert len(longo) >= len(curto)
