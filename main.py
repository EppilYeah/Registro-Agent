import logging
import webview
import threading
import time
import os
import settings
from app.core.brain import Brain
from app.core.audio import AudioHandler
from app.core.vision import VisionHandler
from app.services.system import Systemhandler

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("registro")

print("INICIANDO REGISTRO")

settings.carregar()

_DIR = os.path.dirname(os.path.abspath(__file__))
_JANELA = None
_ui_pronta = threading.Event()
_em_conversa = False
_ultimo_acordar = time.time()

LLM_TTS_TIMEOUT_SEC = 120

_STT_RELOAD_KEYS = frozenset({
    "whisper_modelo",
    "whisper_device",
    "stt_post_speech_silence_sec",
    "stt_realtime_silero_sensitivity",
})

def _js(codigo):
    try:
        if _JANELA:
            _JANELA.evaluate_js(codigo)
    except Exception as e:
        print(f"[JS] Erro ao executar '{codigo}': {e}")

def _atualizar_rosto(emocao, falando):
    _js(f"window.jsAtualizarRosto('{emocao}', {'true' if falando else 'false'})")

def _contexto_historico():
    try:
        ultimas = [d["texto"] for d in brain._memoria_cache[-4:] if d.get("autor") != "REGISTRO"]
        return " ".join(ultimas[-3:])
    except (KeyError, TypeError, IndexError) as e:
        logger.debug("contexto historico: %s", e)
        return ""

audio = AudioHandler(funcao_contexto_historico=_contexto_historico)
brain = Brain()
visao = VisionHandler(funcao_js=_js)


def _encerramento_graceful():
    logger.warning("Encerramento solicitado (finalizar_sofrimento).")
    try:
        visao.parar()
    except Exception:
        logger.exception("Parar visao no encerramento")

    def _exit_depois():
        time.sleep(0.5)
        os._exit(0)

    threading.Timer(2.5, _exit_depois).start()
    try:
        global _JANELA
        if _JANELA:
            _JANELA.destroy()
    except Exception:
        logger.exception("Fechar webview no encerramento")


sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio,
    funcao_js=_js,
    funcao_brain_client=brain.client,
    funcao_modelo_gemini=lambda: brain.modelo_nome,
    funcao_encerramento_graceful=_encerramento_graceful,
)
brain.sistema = sistema


class API:
    def ui_pronta(self):
        _ui_pronta.set()

    def atualizar_setting(self, chave, valor):
        settings.set(chave, valor)
        if chave in _STT_RELOAD_KEYS:
            threading.Thread(target=audio.recarregar_stt, daemon=True).start()

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
        except Exception as e:
            logger.debug("loop_idle: %s", e)


def ciclo_principal():
    global _em_conversa, _ultimo_acordar

    _ui_pronta.wait()

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
                    _JANELA.restore()
                    _JANELA.resize(500, 500)
                    _JANELA.move(100, 100)
                except Exception as e:
                    logger.debug("Restaurar janela: %s", e)

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
                        if not tts_iniciado.wait(timeout=LLM_TTS_TIMEOUT_SEC):
                            logger.error(
                                "Timeout (%ss) aguardando resposta/TTS do modelo.",
                                LLM_TTS_TIMEOUT_SEC,
                            )
                            audio.falar("Demorei demais para processar isso.", "neutro")
                        thread_llm.join(timeout=10.0)
                        if thread_llm.is_alive():
                            logger.warning("Thread do LLM ainda em execucao apos join.")

                        foi_interrompido = tts_result[0]
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