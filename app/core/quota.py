"""429 / retry-after. Cota Gemini é por projeto, não por chave."""
from __future__ import annotations

import logging
import re
import time

logger = logging.getLogger(__name__)

TETO_ESPERA_SEG = 15.0
ESPERA_MIN_SEG = 0.2
ESPERA_PADRAO_SEG = 2.0


class QuotaError(Exception):
    def __init__(self, mensagem: str, retry_after: float = ESPERA_PADRAO_SEG, provedor: str = ""):
        super().__init__(mensagem)
        self.retry_after = float(retry_after)
        self.provedor = provedor or ""


def _numero(valor) -> float | None:
    if valor is None:
        return None
    try:
        n = float(str(valor).strip())
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return n


_RE_RETRY_AFTER = re.compile(r"retry[-_ ]after['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)", re.I)
_RE_RETRY_DELAY = re.compile(r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s?", re.I)
_RE_RETRY_IN = re.compile(r"retry in\s+(\d+(?:\.\d+)?)\s*s", re.I)


def extrair_retry_after(erro=None, headers=None, default: float = ESPERA_PADRAO_SEG, teto: float = TETO_ESPERA_SEG) -> float:
    if isinstance(erro, QuotaError) and erro.retry_after:
        return max(ESPERA_MIN_SEG, min(float(erro.retry_after), teto))
    headers = headers or {}
    if hasattr(headers, "get"):
        bruto = headers.get("retry-after") or headers.get("Retry-After")
        n = _numero(bruto)
        if n is not None:
            return max(ESPERA_MIN_SEG, min(n, teto))
    n = _numero(getattr(erro, "retry_after", None))
    if n is not None:
        return max(ESPERA_MIN_SEG, min(n, teto))
    texto = str(erro or "")
    for regex in (_RE_RETRY_AFTER, _RE_RETRY_DELAY, _RE_RETRY_IN):
        match = regex.search(texto)
        if match:
            n = _numero(match.group(1))
            if n is not None:
                return max(ESPERA_MIN_SEG, min(n, teto))
    return max(ESPERA_MIN_SEG, min(float(default), teto))


def eh_erro_quota(erro) -> bool:
    texto = str(erro or "").lower()
    return any(x in texto for x in ("429", "quota", "resource_exhausted", "rate limit", "rate_limit", "too many requests"))


def esperar_retry_after(erro=None, headers=None, provedor: str = "") -> float:
    """Espera o retry-after (teto 15s) e segue. Sem loop de 60s."""
    if isinstance(erro, QuotaError):
        provedor = provedor or erro.provedor
    seg = extrair_retry_after(erro, headers=headers)
    logger.info("quota %s: retry-after %.1fs (sem sleep fixo de 60s)", provedor or "?", seg)
    print(f"[QUOTA] {provedor or '?'} retry-after {seg:.1f}s; em seguida o próximo provedor.")
    time.sleep(seg)
    return seg
