from app.core.roteador import usar_groq_stt


def test_groq_stt_quando_cuda_ocupada(monkeypatch):
    monkeypatch.setattr("app.core.roteador.cuda_livre_para_stt", lambda: False)
    assert usar_groq_stt(tem_groq=True, device="cuda", se_cuda_ocupada=True) is True


def test_groq_stt_nao_quando_cuda_livre(monkeypatch):
    monkeypatch.setattr("app.core.roteador.cuda_livre_para_stt", lambda: True)
    assert usar_groq_stt(tem_groq=True, device="cuda", se_cuda_ocupada=True) is False


def test_groq_stt_forcado_por_device():
    assert usar_groq_stt(tem_groq=True, device="groq", se_cuda_ocupada=False) is True


def test_groq_stt_sem_chave(monkeypatch):
    monkeypatch.setattr("app.core.roteador.cuda_livre_para_stt", lambda: False)
    assert usar_groq_stt(tem_groq=False, device="cuda", se_cuda_ocupada=True) is False


def test_groq_stt_desligado_por_setting(monkeypatch):
    monkeypatch.setattr("app.core.roteador.cuda_livre_para_stt", lambda: False)
    assert usar_groq_stt(tem_groq=True, device="cuda", se_cuda_ocupada=False) is False
