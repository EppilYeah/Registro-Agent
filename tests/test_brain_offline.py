import json
import os
import tempfile
from unittest.mock import MagicMock

from app.core.brain import Brain
from app.core.resposta import parsear_resposta_json


def _brain_isolado():
    palace = MagicMock()
    palace.recuperar.return_value = ["[usuario/identidade Luis] Mora em Recife"]
    b = Brain(conectar=False, palace=palace)
    tmp = tempfile.mkdtemp()
    b.caminho_usuario = os.path.join(tmp, "usuario.json")
    b.caminho_perfil = os.path.join(tmp, "perfil.json")
    b.caminho_memoria_recente = os.path.join(tmp, "memoria_recente.json")
    b._memoria_cache = []
    b._sessao_atual = []
    return b


def test_montar_prompt_inclui_memoria_e_nao_diz_vazio():
    b = _brain_isolado()
    texto = b._montar_prompt_turno("cadê minha cidade?")
    assert "[MEMORIA]" in texto
    assert "Recife" in texto
    assert "Sem memorias" not in texto
    b.palace.recuperar.return_value = []
    texto2 = b._montar_prompt_turno("oi")
    assert "[MEMORIA]" not in texto2


def test_carregar_memoria_usa_turnos_reais():
    b = _brain_isolado()
    b._memoria_cache = [
        {"autor": "Luis", "texto": "Meu nome é Luis Felipe"},
        {"autor": "REGISTRO", "texto": "Anotado."},
    ]
    hist = b.carregar_memoria()
    assert hist[0].role == "user"
    assert "Luis Felipe" in hist[0].parts[0].text
    assert hist[1].role == "model"
    assert "Anotado." in hist[1].parts[0].text


def test_instrucao_sistema_carrega_prompt():
    b = _brain_isolado()
    inst = b._instrucao_sistema()
    assert "REGISTRO" in inst
    assert "texto_resposta" in inst


def test_atualizar_dicionario_ignora_json_de_fala(monkeypatch):
    b = _brain_isolado()
    b._requisicoes_sessao = 5
    b.client = MagicMock()
    b.modelo_nome = "gemini-2.5-flash"
    b._sessao_atual = [{"autor": "Luis", "texto": "Meu nome é Luis Felipe"}]
    fake = MagicMock()
    fake.text = json.dumps({"emocao": "neutro", "texto_resposta": "Anotado."})
    b.client.models.generate_content.return_value = fake
    b.atualizar_dicionario_usuario()
    assert not os.path.exists(b.caminho_usuario)


def test_atualizar_dicionario_salva_fatos(monkeypatch):
    b = _brain_isolado()
    b._requisicoes_sessao = 5
    b.client = MagicMock()
    b.modelo_nome = "gemini-2.5-flash"
    b._sessao_atual = [{"autor": "Luis", "texto": "Moro em Recife"}]
    fake = MagicMock()
    fake.text = json.dumps({"nome": "Luis Felipe", "cidade": "Recife"})
    b.client.models.generate_content.return_value = fake
    b.atualizar_dicionario_usuario()
    with open(b.caminho_usuario, encoding="utf-8") as f:
        dados = json.load(f)
    assert dados["nome"] == "Luis Felipe"
    assert dados["cidade"] == "Recife"
    assert "texto_resposta" not in dados


def test_processar_entrada_sem_cliente_nao_trava():
    b = _brain_isolado()
    b.chat = None
    b.client = None
    b._encontrar_combinacao_funcional = MagicMock(return_value=None)
    dados = b.processar_entrada("oi")
    assert dados["emocao"] == "confuso"
    assert "Gemini" in dados["texto_resposta"]


class _Resposta:
    def __init__(self, text=None, explode=False):
        self.candidates = []
        self._text = text
        self._explode = explode

    @property
    def text(self):
        if self._explode:
            raise ValueError("no text")
        return self._text


def test_processar_entrada_recupera_json_apos_afc_vazio():
    b = _brain_isolado()
    b.client = MagicMock()
    chat = MagicMock()
    chat.send_message.side_effect = [
        _Resposta(explode=True),
        _Resposta(text='{"emocao": "neutro", "texto_resposta": "80%."}'),
    ]
    b.chat = chat
    dados = b.processar_entrada("aumenta o volume")
    assert dados["texto_resposta"] == "80%."
    assert chat.send_message.call_count == 2
    assert parsear_resposta_json('{"emocao": "neutro", "texto_resposta": "80%."}')["emocao"] == "neutro"
