"""Chat OpenAI-compatible (Groq) e Ollama CPU-only, com function calling."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.core.quota import QuotaError, eh_erro_quota, extrair_retry_after
from app.core.resposta import parsear_resposta_json
from app.core.stt_vocab import LIMITE_GROQ_CHARS

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 8
_JSON_FINAL = (
    "As ferramentas ja rodaram (ou nao eram necessarias). "
    'Responda AGORA somente o JSON {"emocao": "...", "texto_resposta": "..."}. '
    "texto_resposta e o que sera falado: 1 a 2 frases, PT-BR, sem markdown, sem emojis."
)


def schema_para_json(schema) -> dict:
    if schema is None:
        return {"type": "object", "properties": {}}
    if isinstance(schema, dict):
        return schema
    tipo_bruto = str(getattr(schema, "type", "OBJECT")).split(".")[-1].lower()
    mapa = {
        "object": "object", "string": "string", "number": "number",
        "integer": "integer", "boolean": "boolean", "array": "array",
        "type_unspecified": "object",
    }
    out = {"type": mapa.get(tipo_bruto, "object")}
    desc = getattr(schema, "description", None)
    if desc:
        out["description"] = desc
    props = getattr(schema, "properties", None) or {}
    if props:
        out["properties"] = {k: schema_para_json(v) for k, v in props.items()}
    req = getattr(schema, "required", None)
    if req:
        out["required"] = list(req)
    return out


def tools_para_openai(lista_ferramentas) -> list[dict]:
    saida = []
    for tool in lista_ferramentas or []:
        for decl in getattr(tool, "function_declarations", None) or []:
            nome = getattr(decl, "name", None)
            if not nome:
                continue
            saida.append({
                "type": "function",
                "function": {
                    "name": nome,
                    "description": getattr(decl, "description", None) or "",
                    "parameters": schema_para_json(getattr(decl, "parameters", None)),
                },
            })
    return saida


def ollama_options_cpu(temperature: float = 0.7) -> dict:
    """Força 8B na CPU — a 1660 Super de 6 GB fica com o Whisper."""
    return {"num_gpu": 0, "temperature": temperature}


def _headers_http(resp) -> dict:
    try:
        return {k.lower(): v for k, v in (resp.headers.items() if hasattr(resp, "headers") else [])}
    except Exception:
        return {}


def _post_json(url: str, payload: dict, headers: dict, timeout: float = 90.0) -> dict:
    corpo = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=corpo, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read().decode("utf-8")
            return json.loads(bruto) if bruto else {}
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        hdrs = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
        if e.code == 429 or eh_erro_quota(detalhe):
            raise QuotaError(
                detalhe or str(e),
                retry_after=extrair_retry_after(detalhe, headers=hdrs),
                provedor="http",
            ) from e
        raise RuntimeError(f"HTTP {e.code}: {detalhe[:400]}") from e


def _executar_skill(skills: dict, nome: str, args: dict) -> str:
    fn = (skills or {}).get(nome)
    if not fn:
        return f"Ferramenta '{nome}' nao encontrada."
    try:
        resultado = fn(**(args or {}))
        return str(resultado) if resultado is not None else "ok"
    except TypeError:
        try:
            return str(fn())
        except Exception as e:
            return f"Erro na ferramenta {nome}: {e}"
    except Exception as e:
        return f"Erro na ferramenta {nome}: {e}"


def _args_tool(bruto) -> dict:
    if isinstance(bruto, dict):
        return bruto
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except json.JSONDecodeError:
        return {}


def _mensagem_openai_para_ollama(msg: dict) -> dict:
    role = msg.get("role")
    if role == "tool":
        return {"role": "tool", "content": msg.get("content") or ""}
    if role == "assistant" and msg.get("tool_calls"):
        chamadas = []
        for c in msg["tool_calls"]:
            fn = c.get("function") or {}
            chamadas.append({
                "function": {
                    "name": fn.get("name"),
                    "arguments": _args_tool(fn.get("arguments")),
                }
            })
        out = {"role": "assistant", "content": msg.get("content") or ""}
        if chamadas:
            out["tool_calls"] = chamadas
        return out
    return {"role": role, "content": msg.get("content") or ""}


def _normalizar_tool_calls_openai(calls) -> list[dict]:
    saida = []
    for i, c in enumerate(calls or []):
        if isinstance(c, dict):
            fn = c.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, dict):
                args = json.dumps(args, ensure_ascii=False)
            saida.append({
                "id": c.get("id") or f"call_{i}",
                "type": "function",
                "function": {"name": fn.get("name"), "arguments": args or "{}"},
            })
            continue
        fn = getattr(c, "function", None)
        if fn is None:
            continue
        args = getattr(fn, "arguments", "{}")
        saida.append({
            "id": getattr(c, "id", None) or f"call_{i}",
            "type": "function",
            "function": {"name": getattr(fn, "name", None), "arguments": args or "{}"},
        })
    return saida


def groq_chat(messages: list, *, modelo: str, api_key: str, tools=None, temperature: float = 0.7) -> tuple[str, list]:
    payload = {
        "model": modelo,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 800,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    dados = _post_json(
        "https://api.groq.com/openai/v1/chat/completions",
        payload,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    choice = (dados.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    texto = msg.get("content") or ""
    calls = _normalizar_tool_calls_openai(msg.get("tool_calls"))
    return texto, calls


def ollama_chat(messages: list, *, host: str, modelo: str, tools=None, temperature: float = 0.7) -> tuple[str, list]:
    host = (host or "http://127.0.0.1:11434").rstrip("/")
    payload = {
        "model": modelo,
        "messages": [_mensagem_openai_para_ollama(m) for m in messages],
        "stream": False,
        "options": ollama_options_cpu(temperature),
    }
    if tools:
        payload["tools"] = tools
    dados = _post_json(
        f"{host}/api/chat",
        payload,
        {"Content-Type": "application/json"},
        timeout=180.0,
    )
    msg = dados.get("message") or {}
    texto = msg.get("content") or ""
    calls = _normalizar_tool_calls_openai(msg.get("tool_calls"))
    return texto, calls


def completar_com_tools(
    *,
    provedor: str,
    system: str,
    user: str,
    skills: dict,
    tools_openai: list,
    modelo: str,
    api_key: str = "",
    host: str = "",
    temperature: float = 0.7,
) -> dict:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    usar_tools = bool(tools_openai and skills)

    def _uma_vez(msgs, com_tools: bool):
        if provedor == "groq":
            return groq_chat(
                msgs, modelo=modelo, api_key=api_key,
                tools=tools_openai if com_tools else None,
                temperature=temperature,
            )
        if provedor == "ollama":
            return ollama_chat(
                msgs, host=host, modelo=modelo,
                tools=tools_openai if com_tools else None,
                temperature=temperature,
            )
        raise RuntimeError(f"provedor desconhecido: {provedor}")

    for _ in range(_MAX_TOOL_ROUNDS):
        texto, calls = _uma_vez(messages, usar_tools)
        if calls:
            messages.append({
                "role": "assistant",
                "content": texto or "",
                "tool_calls": calls,
            })
            for c in calls:
                fn = c.get("function") or {}
                nome = fn.get("name") or ""
                args = _args_tool(fn.get("arguments"))
                resultado = _executar_skill(skills, nome, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": c.get("id") or nome,
                    "content": resultado,
                })
            continue
        if not (texto or "").strip():
            messages.append({"role": "user", "content": _JSON_FINAL})
            texto, _ = _uma_vez(messages, False)
        return parsear_resposta_json(texto)

    messages.append({"role": "user", "content": _JSON_FINAL})
    texto, _ = _uma_vez(messages, False)
    return parsear_resposta_json(texto)


def transcrever_groq_wav(wav_bytes: bytes, *, api_key: str, prompt: str = "", modelo: str = "whisper-large-v3-turbo") -> str:
    try:
        from groq import Groq
    except ImportError as e:
        raise RuntimeError("pacote groq ausente; pip install groq") from e
    client = Groq(api_key=api_key)
    try:
        res = client.audio.transcriptions.create(
            file=("fala.wav", wav_bytes, "audio/wav"),
            model=modelo,
            language="pt",
            prompt=(prompt or "")[:LIMITE_GROQ_CHARS],
            temperature=0.0,
        )
    except Exception as e:
        if eh_erro_quota(e):
            hdrs = {}
            resp = getattr(e, "response", None)
            if resp is not None:
                hdrs = getattr(resp, "headers", {}) or {}
            raise QuotaError(str(e), retry_after=extrair_retry_after(e, headers=hdrs), provedor="groq-stt") from e
        raise
    return (getattr(res, "text", None) or str(res) or "").strip()
