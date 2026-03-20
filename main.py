import webview
import threading
import time
import os
import settings
from app.core.brain import Brain
from app.core.audio import AudioHandler
from app.core.vision import VisionHandler
from app.services.system import Systemhandler

print("INICIANDO REGISTRO")

settings.carregar()

_DIR = os.path.dirname(os.path.abspath(__file__))
_JANELA = None
_ui_pronta = threading.Event()

def _js(codigo):
    try:
        if _JANELA:
            _JANELA.evaluate_js(codigo)
    except Exception as e:
        print(f"[JS] Erro ao executar '{codigo}': {e}")

def _atualizar_rosto(emocao, falando):
    _js(f"window.jsAtualizarRosto('{emocao}', {'true' if falando else 'false'})")

audio = AudioHandler()
brain = Brain()
visao = VisionHandler(funcao_js=_js)
sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio,
    funcao_js=_js
)
brain.sistema = sistema

class API:
    def ui_pronta(self):
        _ui_pronta.set()

    def atualizar_setting(self, chave, valor):
        settings.set(chave, valor)

    def obter_settings(self):
        return settings.todos()

    def fechar_configuracoes(self):
        pass

    def fechar_janela(self):
        if _JANELA:
            _JANELA.destroy()

    def maximizar_janela(self):
        if _JANELA:
            _JANELA.maximize()

    def restaurar_janela(self):
        if _JANELA:
            _JANELA.restore()
            _JANELA.resize(500, 500)
            _JANELA.move(100, 100)

def ciclo_principal():
    global _JANELA
    _ui_pronta.wait()

    print("REGISTRO INICIADO")
    audio.falar("REGISTRO INICIADO", "neutro")

    visao.iniciar()

    _atualizar_rosto("neutro", False)

    while True:
        try:
            if audio.ouvir_wake_word():
                try:
                    _JANELA.show()
                except:
                    pass

                modo_conversa = True
                tentativas_silencio = 0
                comando_atual = None

                while modo_conversa:
                    _atualizar_rosto("ouvindo", False)

                    if not comando_atual:
                        comando_atual = audio.ouvir_comando()

                    if comando_atual:
                        print(f"VOCÊ: {comando_atual}")
                        tentativas_silencio = 0

                        if any(x in comando_atual.lower() for x in ["tchau", "desligar", "dormir"]):
                            audio.falar("Até logo.", "neutro")
                            modo_conversa = False
                            _atualizar_rosto("neutro", False)
                            break

                        _atualizar_rosto("confuso", False)
                        audio.preparar_ouvir()

                        tts_iniciado = threading.Event()
                        tts_result = [False]

                        def _on_resposta(dados):
                            emocao = dados["emocao"]
                            texto = dados["texto_resposta"]
                            _atualizar_rosto(emocao, True)
                            tts_result[0] = audio.falar(texto, emocao)
                            _atualizar_rosto(emocao, False)
                            tts_iniciado.set()

                        thread_llm = threading.Thread(
                            target=brain.processar_entrada,
                            args=(comando_atual,),
                            kwargs={"on_resposta": _on_resposta},
                            daemon=True
                        )
                        thread_llm.start()
                        tts_iniciado.wait()
                        thread_llm.join()

                        foi_interrompido = tts_result[0]
                        comando_atual = None

                        if foi_interrompido:
                            _atualizar_rosto("irritado", False)
                            comando_atual = audio.ouvir_comando()
                            if comando_atual:
                                continue

                    else:
                        tentativas_silencio += 1
                        print(f"SILÊNCIO {tentativas_silencio}/2")
                        if tentativas_silencio >= 2:
                            _atualizar_rosto("neutro", False)
                            modo_conversa = False

            time.sleep(0.1)

        except Exception as e:
            print(f"[ERRO CRÍTICO] {e}")
            modo_conversa = False
            time.sleep(1)

if __name__ == "__main__":
    _JANELA = webview.create_window(
        'REG / UI',
        os.path.join(_DIR, 'ui', 'web', 'index.html'),
        width=500,
        height=500,
        x=100,
        y=100,
        frameless=True,
        on_top=True,
        transparent=True,
        js_api=API()
    )

    thread_alma = threading.Thread(target=ciclo_principal)
    thread_alma.daemon = True
    thread_alma.start()

    webview.start(gui='edgechromium')