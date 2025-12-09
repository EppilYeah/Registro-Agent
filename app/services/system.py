import os
import threading
import subprocess
import datetime
import pyautogui
import math
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize


class Systemhandler:
    def __init__(self, funcao_falar=None, funcao_gerar_texto=None):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0
        
        self.funcao_falar = funcao_falar
        self.funcao_gerar_texto = funcao_gerar_texto
        self.volume_control = None
        
        self._inicializar_audio()
        
        self.skills = {
            "volume_pc" : self.volume_pc,
            "pausar_midia" : self.pausar_midia,
            "abrir_whatsapp_web" : self.abrir_whatsapp_web,
            "agendar_lembrete" : self.agendar_lembrete
        }
    
    def _inicializar_audio(self):
        try:
            CoInitialize()
            
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            
            volume_atual = self.volume_control.GetMasterVolumeLevelScalar()
            print(f"[AUDIO] Driver carregado. Volume atual: {int(volume_atual * 100)}%")
            
        except AttributeError as e:
            print(f"[AUDIO] Erro de interface COM: {e}")
            print("[AUDIO] Tente: pip uninstall pycaw && pip install pycaw")
            self.volume_control = None
        except Exception as e:
            print(f"[AUDIO] Falha ao inicializar driver: {e}")
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