"""Helpers puros: parse da resposta do Gemini e classificação de memória."""
from __future__ import annotations

import json

EMO_RESPOSTA_VALIDAS = frozenset({
    "neutro", "sarcasmo_tedio", "irritado", "confuso", "arrogante", "desconfiado", "feliz",
})

WINGS_VALIDAS = frozenset({
    "conversa", "usuario", "projeto", "sistema", "preferencia", "tarefa",
})

ROOMS_VALIDAS = frozenset({
    "geral", "identidade", "preferencias", "trabalho", "tecnico", "agenda", "humor",
})

_TRIVIAIS = frozenset({
    "ok", "sim", "nao", "não", "tchau", "obrigado", "obrigada", "valeu",
    "ta", "tá", "beleza", "isso", "uhum", "hm", "hmm",
})


def normalizar_resposta(dados) -> dict:
    if not isinstance(dados, dict):
        return {"emocao": "neutro", "texto_resposta": str(dados)}
    em = dados.get("emocao", "neutro")
    tx = dados.get("texto_resposta", "")
    if em not in EMO_RESPOSTA_VALIDAS:
        em = "neutro"
    if tx is None:
        tx = ""
    return {"emocao": em, "texto_resposta": str(tx).strip()}


def parsear_objeto_json(texto: str) -> dict:
    """Extrai um objeto JSON genérico; não exige o schema emocao/texto_resposta."""
    if not texto or not str(texto).strip():
        return {}
    txt = str(texto).replace("```json", "").replace("```", "").strip()
    decoder = json.JSONDecoder()
    for i, ch in enumerate(txt):
        if ch != "{":
            continue
        try:
            dados, _ = decoder.raw_decode(txt[i:])
            if isinstance(dados, dict):
                return dados
        except json.JSONDecodeError:
            continue
    return {}


def parsear_resposta_json(texto: str) -> dict:
    if not texto or not str(texto).strip():
        return normalizar_resposta({"emocao": "confuso", "texto_resposta": "Sem resposta."})
    dados = parsear_objeto_json(texto)
    if dados.get("texto_resposta") or dados.get("emocao") in EMO_RESPOSTA_VALIDAS:
        return normalizar_resposta(dados)
    txt = str(texto).replace("```json", "").replace("```", "").strip()
    if _parece_fala(txt):
        return normalizar_resposta({"emocao": "neutro", "texto_resposta": txt})
    return normalizar_resposta({"emocao": "neutro", "texto_resposta": txt})


def _parece_fala(txt: str) -> bool:
    if not txt or txt.startswith("{") or txt.startswith("["):
        return False
    return len(txt) < 400 and "\n#" not in txt


def sanitizar_wing_room(wing: str, room: str) -> tuple[str, str]:
    w = (wing or "conversa").lower().replace(" ", "_")
    r = (room or "geral").lower().replace(" ", "_")
    if w not in WINGS_VALIDAS:
        w = "conversa"
    if r not in ROOMS_VALIDAS:
        r = "geral"
    return w, r


def classificar_memoria_heuristica(texto: str, autor: str = "") -> tuple[str, str]:
    t = (texto or "").lower()
    if any(x in t for x in ("meu nome", "eu sou", "me chamo", "pode me chamar", "me chama")):
        return sanitizar_wing_room("usuario", "identidade")
    if any(x in t for x in ("moro", "mora em", "minha cidade", "eu vivo em")):
        return sanitizar_wing_room("usuario", "identidade")
    if any(x in t for x in ("gosto de", "prefiro", "nao gosto", "não gosto", "minha prefer")):
        return sanitizar_wing_room("preferencia", "preferencias")
    if any(x in t for x in ("projeto", "repositorio", "repositório", "codigo", "código", "refator", "commit")):
        return sanitizar_wing_room("projeto", "tecnico")
    if any(x in t for x in ("lembra", "lembrete", "amanha", "amanhã", "reunião", "reuniao", "me avisa")):
        return sanitizar_wing_room("tarefa", "agenda")
    if any(x in t for x in ("volume", "configura", "camera", "câmera", "microfone", "whisper")):
        return sanitizar_wing_room("sistema", "tecnico")
    if autor == "REGISTRO":
        return sanitizar_wing_room("conversa", "geral")
    return sanitizar_wing_room("conversa", "geral")


def deve_persistir_memoria(texto: str, autor: str) -> bool:
    t = (texto or "").strip()
    if len(t) < 12:
        return False
    if t.lower() in _TRIVIAIS:
        return False
    if autor == "REGISTRO" and len(t) < 28:
        return False
    return True


def formatar_hit_memoria(texto: str, meta: dict | None = None, distancia: float | None = None) -> str:
    texto = (texto or "").strip()
    if not texto:
        return ""
    meta = meta or {}
    wing = meta.get("wing") or "conversa"
    room = meta.get("room") or "geral"
    autor = meta.get("autor") or "?"
    data = str(meta.get("data") or "")[:16]
    dist = ""
    if distancia is not None:
        try:
            dist = f" d={float(distancia):.2f}"
        except (TypeError, ValueError):
            dist = ""
    return f"[{wing}/{room} {autor} {data}{dist}] {texto}"


def eh_perfil_resposta_llm(dados: dict) -> bool:
    """True se o JSON parece a fala do REGISTRO, não um perfil de usuário."""
    if not isinstance(dados, dict):
        return True
    chaves = set(dados.keys()) - {"ultima_atualizacao"}
    return chaves <= {"emocao", "texto_resposta"} and "texto_resposta" in dados


CAMPOS_PERFIL_BLOQUEADOS = frozenset({"emocao", "texto_resposta", "ultima_atualizacao"})
_VALORES_PERFIL_VAZIOS = frozenset({"", "null", "none", "desconhecido", "n/a", "unknown"})


def mesclar_perfil_usuario(atual: dict, novo: dict) -> dict:
    """Atualiza o perfil sem trocar fatos reais por JSON de fala ou campos vazios."""
    if not isinstance(atual, dict):
        atual = {}
    if not isinstance(novo, dict) or eh_perfil_resposta_llm(novo):
        return dict(atual)
    if "emocao" in novo and "texto_resposta" in novo:
        return dict(atual)
    saida = dict(atual)
    for chave, valor in novo.items():
        if chave in CAMPOS_PERFIL_BLOQUEADOS or valor is None:
            continue
        if isinstance(valor, str):
            texto = valor.strip()
            if not texto or texto.lower() in _VALORES_PERFIL_VAZIOS:
                continue
            saida[chave] = texto
        else:
            saida[chave] = valor
    return saida
