from app.core.quota import (
    TETO_ESPERA_SEG,
    QuotaError,
    eh_erro_quota,
    esperar_retry_after,
    extrair_retry_after,
)


def test_retry_after_do_header():
    assert extrair_retry_after(headers={"retry-after": "3"}) == 3.0
    assert extrair_retry_after(headers={"Retry-After": "8.5"}) == 8.5


def test_retry_after_teto_nao_e_60s():
    assert TETO_ESPERA_SEG == 15.0
    assert extrair_retry_after(headers={"Retry-After": "60"}) == 15.0
    assert extrair_retry_after("Please retry in 60s") == 15.0


def test_retry_after_no_texto_gemini():
    erro = "429 RESOURCE_EXHAUSTED retryDelay: '5s'"
    assert extrair_retry_after(erro) == 5.0
    assert extrair_retry_after("rate limit retry-after: 4") == 4.0


def test_quota_error_preserva_retry_after():
    err = QuotaError("429 too many requests", retry_after=3.0, provedor="groq")
    assert extrair_retry_after(err) == 3.0
    assert eh_erro_quota(err)
    assert eh_erro_quota("RESOURCE_EXHAUSTED")


def test_esperar_retry_after_nao_dorme_60s(monkeypatch):
    slept = []
    monkeypatch.setattr("app.core.quota.time.sleep", lambda s: slept.append(s))
    esperar_retry_after(QuotaError("429", retry_after=60, provedor="gemini"), provedor="gemini")
    assert slept == [15.0]
    slept.clear()
    esperar_retry_after(QuotaError("429", retry_after=2.5, provedor="groq"))
    assert slept == [2.5]
