import webview
import threading
import time
import os
import settings
from app.core.brain import Brain
from app.core.audio import AudioHandler
from app.core.vision import VisionHandler
from app.services.system import Systemhandler
from app.core.errors import Supervisor
import janela

print("INICIANDO REGISTRO")

settings.carregar()

_DIR = os.path.dirname(os.path.abspath(__file__))
_JANELA = None
_ui_pronta = threading.Event()
_em_conversa = False
_ultimo_acordar = time.time()

def _js(codigo):
    try:
        if not _JANELA:
            return
        try:
            _JANELA.evaluate_js(codigo, lambda *_: None)
        except TypeError:
            _JANELA.evaluate_js(codigo)
    except Exception as e:
        print(f"[JS] Erro ao executar '{codigo}': {e}")

def _atualizar_rosto(emocao, falando):
    _js(f"window.jsAtualizarRosto('{emocao}', {'true' if falando else 'false'})")

def _contexto_historico():
    try:
        ultimas = [d["texto"] for d in brain._memoria_cache[-4:] if d.get("autor") != "REGISTRO"]
        return " ".join(ultimas[-3:])
    except:
        return ""

audio = AudioHandler(funcao_contexto_historico=_contexto_historico)
brain = Brain()
visao = VisionHandler(funcao_js=_js)
sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio,
    funcao_js=_js,
    obter_client=lambda: brain.client,
    obter_modelo=lambda: brain.modelo_nome,
)
brain.sistema = sistema
supervisor = Supervisor(audio=audio, visao=visao, brain=brain, sistema=sistema)


class API:
    def ui_pronta(self):
        _ui_pronta.set()

    def atualizar_setting(self, chave, valor):
        settings.set(chave, valor)
        if chave in ("whisper_modelo", "whisper_device"):
            threading.Thread(target=audio.recarregar_whisper, daemon=True).start()

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


def _loop_idle():
    while True:
        time.sleep(30)
        if _em_conversa:
            continue
        try:
            inativo = time.time() - _ultimo_acordar
            dormindo_timeout = settings.get("dormindo_timeout_min") * 60
            ambient_timeout = settings.get("modo_ambient_timeout_min") * 60

            if inativo >= dormindo_timeout:
                _js("window.jsAtualizarRosto('dormindo', false)")
                if _JANELA:
                    _JANELA.resize(80, 80)
            elif inativo >= ambient_timeout:
                _js("window.jsAtualizarRosto('neutro', false)")
                if _JANELA:
                    _JANELA.resize(80, 80)
        except:
            pass


def ciclo_principal():
    global _em_conversa, _ultimo_acordar

    _ui_pronta.wait()
    janela.registrar_webview(lambda: _JANELA)
    janela.definir_sempre_visivel()

    print("REGISTRO INICIADO")
    audio.falar("REGISTRO INICIADO", "neutro")

    visao.iniciar()
    _atualizar_rosto("neutro", False)

    brain.iniciar_comportamento_espontaneo(
        lambda texto, emocao: (
            _atualizar_rosto(emocao, True),
            audio.falar(texto, emocao),
            _atualizar_rosto(emocao, False)
        )
    )

    thread_idle = threading.Thread(target=_loop_idle, daemon=True)
    thread_idle.start()

    while True:
        try:
            if audio.ouvir_wake_word():
                _ultimo_acordar = time.time()
                _em_conversa = True

                try:
                    janela.trazer_para_frente()
                    _JANELA.restore()
                    _JANELA.resize(500, 500)
                    _JANELA.move(100, 100)
                except:
                    pass

                _atualizar_rosto("neutro", False)
                brain.iniciar_sessao()

                modo_conversa = True
                tentativas_silencio = 0
                comando_atual = None

                while modo_conversa:
                    _atualizar_rosto("ouvindo", False)

                    if not comando_atual:
                        comando_atual = audio.ouvir_comando()

                    if comando_atual:
                        print(f"VOCE: {comando_atual}")
                        tentativas_silencio = 0

                        if any(x in comando_atual.lower() for x in ["tchau", "desligar", "dormir"]):
                            despedida = brain.gerar_despedida()
                            audio.falar(despedida, "neutro")
                            modo_conversa = False
                            _atualizar_rosto("neutro", False)
                            break

                        _atualizar_rosto("confuso", False)
                        audio.preparar_ouvir()
                        audio.prequecer()

                        pronta = threading.Event()
                        dados_box = [None]
                        t_llm = time.time()

                        def _on_resposta(dados):
                            if dados_box[0] is None:
                                dados_box[0] = dados
                                pronta.set()

                        def _rodar_llm():
                            try:
                                brain.processar_entrada(comando_atual, on_resposta=_on_resposta)
                            finally:
                                pronta.set()

                        thread_llm = threading.Thread(target=_rodar_llm, daemon=True)
                        thread_llm.start()
                        if not pronta.wait(32):
                            print("[LAT] llm timeout 32s")
                            if dados_box[0] is None:
                                dados_box[0] = {
                                    "emocao": "neutro",
                                    "texto_resposta": "A API nao respondeu a tempo.",
                                }
                        print(f"[LAT] llm={time.time() - t_llm:.2f}s")

                        dados = dados_box[0] or {}
                        texto = (dados.get("texto_resposta") or "").strip()
                        emocao = dados.get("emocao") or "neutro"
                        foi_interrompido = False
                        if texto:
                            _atualizar_rosto(emocao, True)
                            t_tts = time.time()
                            foi_interrompido = audio.falar(texto, emocao)
                            print(f"[LAT] tts={time.time() - t_tts:.2f}s")
                            _atualizar_rosto(emocao, False)
                        else:
                            print("[LAT] turno sem texto")

                        thread_llm.join(timeout=8)
                        comando_atual = None

                        if foi_interrompido:
                            _atualizar_rosto("irritado", False)
                            comando_atual = audio.ouvir_comando()
                            if comando_atual:
                                continue

                    else:
                        tentativas_silencio += 1
                        print(f"SILENCIO {tentativas_silencio}/2")
                        if tentativas_silencio >= 2:
                            _atualizar_rosto("neutro", False)
                            modo_conversa = False

                _em_conversa = False
                _ultimo_acordar = time.time()
                brain.flush_perfil()
                threading.Thread(target=brain.gerar_resumo_sessao, daemon=True).start()
                threading.Thread(target=brain.atualizar_dicionario_usuario, daemon=True).start()

            time.sleep(0.1)

        except Exception as e:
            print(f"[ERRO CRITICO] {e}")
            _em_conversa = False
            dados = supervisor.tratar(e, turno_ativo=True)
            if dados:
                try:
                    emocao = dados.get("emocao", "confuso")
                    _atualizar_rosto(emocao, True)
                    audio.falar(dados.get("texto_resposta", ""), emocao)
                    _atualizar_rosto("neutro", False)
                except Exception:
                    pass
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