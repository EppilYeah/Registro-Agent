import os
import threading
import subprocess
import datetime
import pyautogui
import math
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from comtypes import CoInitialize
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


class Systemhandler:
    def __init__(self, funcao_falar=None, funcao_gerar_texto=None):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0
        
        self.funcao_falar = funcao_falar
        self.funcao_gerar_texto = funcao_gerar_texto
        
        try:
            from comtypes import CoInitialize
            CoInitialize()
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate( # pylint: disable=E1101
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            print(">> Driver de Áudio Carregado.")
            
        except Exception as e:
            print(f"Erro crítico no driver de áudio: {e}")
            # Tenta o método legado se o novo falhar
            self.volume_control = None
        
        self.skills = {
            "volume_pc" : self.volume_pc,
            "pausar_midia" : self.pausar_midia,
            "abrir_whatsapp_web" : self.abrir_whatsapp_web,
            "agendar_lembrete" : self.agendar_lembrete
        }
    
    def volume_pc(self, modo, valor=0):
        if not self.volume_control:
            return "Erro: Driver de áudio não detectado."

        try:
            valor_os = float(valor) / 100.0
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
                return "Mudo alternado."

            novo_volume = max(0.0, min(1.0, novo_volume))
            
            self.volume_control.SetMasterVolumeLevelScalar(novo_volume, None)
            
            # Retorna porcentagem bonita para a IA ler
            return f"Volume ajustado para {int(novo_volume * 100)}%."
            
        except Exception as e:
            return f"ERRO ao ajustar volume: {e}"
        
    def pausar_midia(self):
        try:
            pyautogui.press("playpause")
            return "Mídia pausada/retomada."
        except Exception as e:
            return f"ERRO: {e}"
    
    def abrir_whatsapp_web(self):
        try:
            if os.name == "nt": #windows
                os.startfile("https://web.whatsapp.com/")
        except Exception as e:
            return f"ERRO: {e}"
    
    def agendar_lembrete(self, tempo_segundos, mensagem):
        try:
            tempo = int(tempo_segundos)
            t = threading.Timer(tempo, self._disparar_alerta, args=[mensagem])
            t.start()
            return f"Feito. Daqui a {tempo} segundos eu te cobro."
        except ValueError:
            return "Erro: O tempo precisa ser um número em segundos."
        
    def _disparar_alerta(self, mensagem_bruta):
        print(f"\nALARME: {mensagem_bruta}")
        
        texto_final = f"Lembrete: {mensagem_bruta}"
        
        if self.funcao_gerar_texto:
            texto_final = self.funcao_gerar_texto(mensagem_bruta)
            
        if self.funcao_falar:

            self.funcao_falar(texto_final, "arrogante")

