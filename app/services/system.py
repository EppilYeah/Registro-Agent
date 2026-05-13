import logging
import os
import sys
import threading
import subprocess
import datetime
import pyautogui
import math
import time
import io
import pyperclip
import settings
import config
from PIL import ImageGrab
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IMMDeviceEnumerator, EDataFlow, ERole
from ctypes import cast, POINTER
from comtypes import CoCreateInstance, GUID

logger = logging.getLogger(__name__)


class Systemhandler:
    def __init__(
        self,
        funcao_falar=None,
        funcao_gerar_texto=None,
        funcao_js=None,
        funcao_brain_client=None,
        funcao_modelo_gemini=None,
        funcao_encerramento_graceful=None,
    ):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0

        self.funcao_falar = funcao_falar
        self.funcao_gerar_texto = funcao_gerar_texto
        self.funcao_js = funcao_js
        self.funcao_brain_client = funcao_brain_client
        self.funcao_modelo_gemini = funcao_modelo_gemini
        self.funcao_encerramento_graceful = funcao_encerramento_graceful
        self.volume_control = None

        self._inicializar_audio()

        self.skills = {
            "volume_pc": self.volume_pc,
            "pausar_midia": self.pausar_midia,
            "abrir_whatsapp_web": self.abrir_whatsapp_web,
            "agendar_lembrete": self.agendar_lembrete,
            "abrir_configuracoes": self.abrir_configuracoes,
            "alterar_configuracao": self.alterar_configuracao,
            "finalizar_sofrimento": self.finalizar_sofrimento,
            "pesquisar_web": self.pesquisar_web,
            "ler_clipboard": self.ler_clipboard,
            "escrever_clipboard": self.escrever_clipboard,
            "executar_comando": self.executar_comando,
            "ver_tela": self.ver_tela,
            "consultar_perfil_usuario": self.consultar_perfil_usuario,
        }

    def _inicializar_audio(self):
        try:
            CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
            IID_IMMDeviceEnumerator = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
            deviceEnumerator = CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL)
            device = deviceEnumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            IID_IAudioEndpointVolume = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
            interface = device.Activate(IID_IAudioEndpointVolume, CLSCTX_ALL, None)
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            volume_atual = self.volume_control.GetMasterVolumeLevelScalar()
            print(f"[AUDIO] Driver carregado. Volume atual: {int(volume_atual * 100)}%")
        except Exception as e:
            print(f"[AUDIO] Falha ao inicializar: {e}")
            import traceback
            traceback.print_exc()
            self.volume_control = None

    def volume_pc(self, modo, valor=0):
        if not self.volume_control:
            return "Erro: Driver de áudio não disponível. Execute como administrador."
        try:
            valor_float = float(valor) if valor is not None else 0.0
            valor_os = valor_float / 100.0
            volume_atual = self.volume_control.GetMasterVolumeLevelScalar()
            novo_volume = volume_atual
            if modo == "definir":
                novo_volume = valor_os
            elif modo == "aumentar":
                novo_volume = volume_atual + valor_os
            elif modo == "diminuir":
                novo_volume = volume_atual - valor_os
            elif modo == "mudo":
                mute_atual = self.volume_control.GetMute()
                self.volume_control.SetMute(not mute_atual, None)
                status = "ativado" if not mute_atual else "desativado"
                return f"Mudo {status}."
            novo_volume = max(0.0, min(1.0, novo_volume))
            self.volume_control.SetMasterVolumeLevelScalar(novo_volume, None)
            return f"Volume ajustado para {int(novo_volume * 100)}%."
        except Exception as e:
            return f"Erro ao ajustar volume: {e}"

    def pausar_midia(self):
        try:
            pyautogui.press("playpause")
            return "Mídia pausada/retomada."
        except Exception as e:
            return f"Erro: {e}"

    def abrir_whatsapp_web(self):
        try:
            if os.name == "nt":
                os.startfile("https://web.whatsapp.com/")
                return "WhatsApp Web aberto."
            return "Sistema operacional não suportado."
        except Exception as e:
            return f"Erro: {e}"

    def agendar_lembrete(self, tempo_segundos, mensagem):
        try:
            tempo = int(tempo_segundos)
            t = threading.Timer(tempo, self._disparar_alerta, args=[mensagem])
            t.start()
            return f"Lembrete agendado para daqui a {tempo} segundos."
        except ValueError:
            return "Erro: O tempo precisa ser um número em segundos."
        except Exception as e:
            return f"Erro: {e}"

    def _disparar_alerta(self, mensagem_bruta):
        print(f"\n[ALERTA] {mensagem_bruta}")
        texto_final = f"Lembrete: {mensagem_bruta}"
        if self.funcao_gerar_texto:
            try:
                texto_final = self.funcao_gerar_texto(mensagem_bruta)
            except Exception as e:
                logger.debug("alerta gerar_texto: %s", e)
        if self.funcao_falar:
            self.funcao_falar(texto_final, "arrogante")

    def abrir_configuracoes(self):
        try:
            if self.funcao_js:
                self.funcao_js("window.jsAbrirConfig()")
            return "Painel de configurações aberto."
        except Exception as e:
            return f"Erro: {e}"

    def alterar_configuracao(self, chave, valor):
        _CHAVES_PERMITIDAS = {"vad_ativo", "camera_ativa", "modo_debug", "comportamento_espontaneo"}
        if chave not in _CHAVES_PERMITIDAS:
            return f"Configuração '{chave}' não reconhecida."
        try:
            settings.set(chave, bool(valor))
            estado = "ativado" if valor else "desativado"
            nomes = {
                "vad_ativo": "Detecção de interrupção",
                "camera_ativa": "Rastreamento facial",
                "modo_debug": "Modo debug",
                "comportamento_espontaneo": "Comportamento espontâneo",
            }
            if self.funcao_js:
                js_val = "true" if valor else "false"
                self.funcao_js(f"window.sincronizarToggle('{chave}', {js_val})")
            return f"{nomes.get(chave, chave)} {estado}."
        except Exception as e:
            return f"Erro: {e}"

    def pesquisar_web(self, query):
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                resultados = list(ddgs.text(query, region="br-pt", max_results=3))
            if not resultados:
                return f"Sem resultados para '{query}'."
            partes = []
            for r in resultados:
                corpo = r.get("body", "").strip()
                if corpo:
                    primeira_frase = corpo.split(".")[0].strip()
                    partes.append(primeira_frase[:120])
            return "\n".join(partes) if partes else f"Sem resultados para '{query}'."
        except Exception as e:
            return f"Erro na pesquisa: {e}"

    def ler_clipboard(self):
        try:
            texto = pyperclip.paste()
            if not texto:
                return "Clipboard vazio."
            return f"Clipboard: {texto[:500]}"
        except Exception as e:
            return f"Erro ao ler clipboard: {e}"

    def escrever_clipboard(self, texto):
        try:
            pyperclip.copy(texto)
            return "Texto copiado para o clipboard."
        except Exception as e:
            return f"Erro ao escrever clipboard: {e}"

    def executar_comando(self, cmd, confirmado=False):
        if not confirmado:
            return f"Confirmação necessária para executar: '{cmd}'"
        try:
            resultado = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=15
            )
            saida = resultado.stdout.strip() or resultado.stderr.strip() or "Comando executado sem saída."
            return saida[:600]
        except subprocess.TimeoutExpired:
            return "Timeout: comando demorou mais de 15 segundos."
        except Exception as e:
            return f"Erro ao executar: {e}"

    def ver_tela(self):
        if not self.funcao_brain_client:
            return "Cliente de IA não disponível para análise visual."

        try:
            img = ImageGrab.grab()
            img = img.resize((1280, 720))

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            jpeg_bytes = buf.getvalue()

            from google.genai import types as gtypes
            instrucao = "Descreva de forma concisa o que está visível nesta tela. Foque no conteúdo principal."

            candidatos = []
            if self.funcao_modelo_gemini:
                try:
                    m = self.funcao_modelo_gemini()
                    if m:
                        candidatos.append(m)
                except Exception as e:
                    logger.warning("modelo Gemini (callback): %s", e)
            for m in config.LISTA_MODELOS:
                if m not in candidatos:
                    candidatos.append(m)
            if "gemini-2.0-flash" not in candidatos:
                candidatos.append("gemini-2.0-flash")

            ultimo_erro = None
            for modelo in candidatos:
                try:
                    response = self.funcao_brain_client.models.generate_content(
                        model=modelo,
                        contents=[
                            gtypes.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                            instrucao,
                        ],
                    )
                    return response.text.strip()
                except Exception as e:
                    ultimo_erro = e
                    logger.warning("ver_tela modelo %s: %s", modelo, e)
            return f"Erro ao analisar tela: {ultimo_erro}"
        except Exception as e:
            logger.exception("ver_tela captura")
            return f"Erro ao capturar tela: {e}"

    def consultar_perfil_usuario(self, campo=None):
        try:
            import os, json
            raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            caminho = os.path.join(raiz, "data", "usuario.json")
            with open(caminho, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            if not campo:
                resultado = {k: v for k, v in dados.items() if k != "ultima_atualizacao"}
                return json.dumps(resultado, ensure_ascii=False)
            valor = dados.get(campo)
            if valor is None:
                return f"Campo '{campo}' não encontrado no perfil."
            return str(valor)
        except FileNotFoundError:
            return "Perfil do usuário ainda não existe."
        except Exception as e:
            return f"Erro ao consultar perfil: {e}"

    def finalizar_sofrimento(self):
        if self.funcao_encerramento_graceful:
            try:
                self.funcao_encerramento_graceful()
                return "Encerrando."
            except Exception as e:
                logger.exception("encerramento graceful")
                return f"Erro ao encerrar: {e}"
        time.sleep(3)
        os._exit(0)