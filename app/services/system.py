from app.services.util import filtrar_kwargs
from app.services.media import MediaService
from app.services.clipboard import ClipboardService
from app.services.web import WebService
from app.services.screen import ScreenService
from app.services.shell import ShellService
from app.services.reminders import RemindersService
from app.services.app_control import AppControlService
from app.services.profile import ProfileService
from app.services.memory import MemoryService


class Systemhandler:
    def __init__(self, funcao_falar=None, funcao_gerar_texto=None, funcao_js=None, obter_client=None, obter_modelo=None):
        self.media = MediaService()
        self.clipboard = ClipboardService()
        self.web = WebService()
        self.screen = ScreenService(obter_client=obter_client, obter_modelo=obter_modelo)
        self.shell = ShellService()
        self.reminders = RemindersService(funcao_falar=funcao_falar, funcao_gerar_texto=funcao_gerar_texto)
        self.app_control = AppControlService(funcao_js=funcao_js)
        self.profile = ProfileService()
        self.memory = MemoryService()
        self.supervisor = None

        self.skills = {
            "volume_pc": self.media.volume_pc,
            "pausar_midia": self.media.pausar_midia,
            "abrir_whatsapp_web": self.web.abrir_whatsapp_web,
            "agendar_lembrete": self.reminders.agendar_lembrete,
            "abrir_configuracoes": self.app_control.abrir_configuracoes,
            "alterar_configuracao": self.app_control.alterar_configuracao,
            "finalizar_sofrimento": self.app_control.finalizar_sofrimento,
            "pesquisar_web": self.web.pesquisar_web,
            "ler_clipboard": self.clipboard.ler_clipboard,
            "escrever_clipboard": self.clipboard.escrever_clipboard,
            "executar_comando": self.shell.executar_comando,
            "ver_tela": self.screen.ver_tela,
            "consultar_perfil_usuario": self.profile.consultar_perfil_usuario,
            "buscar_memoria": self.memory.buscar_memoria,
        }

    def executar(self, nome, **kwargs):
        fn = self.skills.get(nome)
        if fn is None:
            return f"'{nome}' não existe"
        try:
            return fn(**filtrar_kwargs(fn, kwargs))
        except Exception as e:
            from app.core.errors import classificar
            erro = classificar(e)
            if self.supervisor and erro.recuperavel:
                codigo = "volume_com" if nome == "volume_pc" or erro.codigo == "volume_com" else erro.codigo
                if codigo in ("volume_com", "janela", "tool"):
                    if self.supervisor.reparar(codigo) and codigo == "volume_com":
                        try:
                            return fn(**filtrar_kwargs(fn, kwargs))
                        except Exception as e2:
                            return f"Erro: {e2}"
            return f"Erro: {e}"

    def __getattr__(self, nome):
        if nome in self.skills:
            return self.skills[nome]
        raise AttributeError(nome)
