from app.core.chat_compat import (
    completar_com_tools,
    ollama_chat,
    ollama_options_cpu,
    schema_para_json,
    tools_para_openai,
)


def test_ollama_options_forca_cpu():
    opts = ollama_options_cpu(0.4)
    assert opts["num_gpu"] == 0
    assert opts["temperature"] == 0.4


def test_schema_e_tools_openai():
    assert schema_para_json({"type": "object", "properties": {"modo": {"type": "string"}}})["type"] == "object"

    class Decl:
        name = "volume_pc"
        description = "Volume do PC"
        parameters = {"type": "object", "properties": {"modo": {"type": "string"}}}

    class Tool:
        function_declarations = [Decl()]

    tools = tools_para_openai([Tool()])
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "volume_pc"
    assert "modo" in tools[0]["function"]["parameters"]["properties"]


def test_ollama_chat_envia_num_gpu_zero(monkeypatch):
    captured = {}

    def fake_post(url, payload, headers, timeout=90.0):
        captured["url"] = url
        captured["payload"] = payload
        return {"message": {"content": '{"emocao":"neutro","texto_resposta":"ok"}'}}

    monkeypatch.setattr("app.core.chat_compat._post_json", fake_post)
    texto, calls = ollama_chat(
        [{"role": "user", "content": "oi"}],
        host="http://127.0.0.1:11434",
        modelo="qwen3:8b",
    )
    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["options"]["num_gpu"] == 0
    assert calls == []
    assert "ok" in texto


def test_completar_com_tools_executa_skill_e_json(monkeypatch):
    disparos = []

    def fake_groq(messages, **kwargs):
        if any(m.get("role") == "tool" for m in messages):
            return '{"emocao":"neutro","texto_resposta":"80%."}', []
        return "", [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "volume_pc", "arguments": '{"modo":"aumentar","valor":20}'},
        }]

    monkeypatch.setattr("app.core.chat_compat.groq_chat", fake_groq)
    skills = {"volume_pc": lambda **a: disparos.append(a) or "volume 80"}
    dados = completar_com_tools(
        provedor="groq",
        system="REGISTRO",
        user="aumenta o volume",
        skills=skills,
        tools_openai=[{"type": "function", "function": {"name": "volume_pc"}}],
        modelo="openai/gpt-oss-20b",
        api_key="gsk_test",
    )
    assert disparos and disparos[0]["modo"] == "aumentar"
    assert dados["texto_resposta"] == "80%."
