import os
import threading
import subprocess
import datetime
import pyautogui

class Systemhandler:
    def __init__(self, funcao_falar=None, funcao_gerar_texto=None):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0
        
        self.funcao_falar = funcao_falar
        self.funcao_gerar_texto = funcao_gerar_texto
        
        self.skills = {
            "volume" : self.volume_pc,
            "pausa" : self.pausar_midia,
            "abrir whatsapp" : self.abrir_whatsapp_web,
            "agendar_lembrete" : self.agendar_lembrete
        }
    
    def volume_pc(self, acao):
        try:
            pyautogui.press("volumemute" if acao == "mudo" else "volumeup" if acao == "aumentar" else "volumedown")
            return "Volume ajustado."
        except Exception as e:
            return f"ERRO: {e}"
        
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

