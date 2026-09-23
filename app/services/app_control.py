import os
import threading
import settings
from app.services.util import as_bool


class AppControlService:
    def __init__(self, funcao_js=None):
        self.funcao_js = funcao_js

    def abrir_configuracoes(self):
        try:
            if self.funcao_js:
                self.funcao_js("window.jsAbrirConfig()")
            return "Painel de configurações aberto."
        except Exception as e:
            return f"Erro: {e}"

    def alterar_configuracao(self, chave, valor):
        permitidas = {"vad_ativo", "camera_ativa", "modo_debug", "comportamento_espontaneo"}
        if chave not in permitidas:
            return f"Configuração '{chave}' não reconhecida."
        try:
            ligado = as_bool(valor)
            settings.set(chave, ligado)
            estado = "ativado" if ligado else "desativado"
            nomes = {
                "vad_ativo": "Detecção de interrupção",
                "camera_ativa": "Rastreamento facial",
                "modo_debug": "Modo debug",
                "comportamento_espontaneo": "Comportamento espontâneo",
            }
            if self.funcao_js:
                js_val = "true" if ligado else "false"
                self.funcao_js(f"window.sincronizarToggle('{chave}', {js_val})")
            return f"{nomes.get(chave, chave)} {estado}."
        except Exception as e:
            return f"Erro: {e}"

    def finalizar_sofrimento(self):
        t = threading.Timer(10.0, lambda: os._exit(0))
        t.daemon = True
        t.start()
        return "Encerrando o REGISTRO em alguns segundos."
