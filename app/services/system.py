import os
import subprocess
import datetime
import pyautogui

class Systemhandler:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0
        
        self.skills = {
            "volume" : self.volume_pc,
            "pausa" : self.pausar_midia,
            "abrir whatsapp" : self.abrir_whatsapp,
            "agendar_lembrete" : self.agendar_lembrete
        }
    
    def volume_pc(self):
        pass
    
    def pausar_midia(self):
        pass
    
    def abrir_whatsapp(self):
        pass
    
    def agendar_lembrete(self):
        pass
    
