import os
import sys
import threading
import subprocess
import datetime
import pyautogui
import math
import time
import subprocess
import settings
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IMMDeviceEnumerator, EDataFlow, ERole
from ctypes import cast, POINTER
from comtypes import CoCreateInstance, GUID



class Systemhandler:
    def __init__(self, funcao_falar=None, funcao_gerar_texto=None, funcao_js=None):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0

        self.funcao_falar = funcao_falar
        self.funcao_gerar_texto = funcao_gerar_texto
        self.funcao_js = funcao_js
        self.volume_control = None

        self._inicializar_audio()

        self.skills = {
            "volume_pc" : self.volume_pc,
            "pausar_midia" : self.pausar_midia,
            "abrir_whatsapp_web" : self.abrir_whatsapp_web,
            "agendar_lembrete" : self.agendar_lembrete,
            "abrir_configuracoes" : self.abrir_configuracoes,
            "alterar_configuracao" : self.alterar_configuracao
        }

    def _inicializar_audio(self):
        try:
            CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
            IID_IMMDeviceEnumerator = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')

            deviceEnumerator = CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                CLSCTX_ALL
            )

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
            valor_float = float(valor)
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
            except:
                pass

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
        _CHAVES_PERMITIDAS = {"vad_ativo", "camera_ativa", "modo_debug"}
        if chave not in _CHAVES_PERMITIDAS:
            return f"Configuração '{chave}' não reconhecida."
        try:
            settings.set(chave, bool(valor))
            estado = "ativado" if valor else "desativado"
            nomes = {
                "vad_ativo": "Detecção de interrupção",
                "camera_ativa": "Rastreamento facial",
                "modo_debug": "Modo debug"
            }
            if self.funcao_js:
                js_val = "true" if valor else "false"
                self.funcao_js(f"window.sincronizarToggle('{chave}', {js_val})")
            return f"{nomes.get(chave, chave)} {estado}."
        except Exception as e:
            return f"Erro: {e}"

    def finalizar_sofrimento(self):
        time.sleep(5)
        os._exit(0)