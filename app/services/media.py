import threading
import pyautogui
from comtypes import CLSCTX_ALL
from pycaw.pycaw import IAudioEndpointVolume, IMMDeviceEnumerator, EDataFlow, ERole
from ctypes import cast, POINTER
from comtypes import CoCreateInstance, GUID


class MediaService:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        self.volume_control = None
        self._volume_tid = None
        self._inicializar_audio()

    def _com_init(self):
        try:
            from comtypes import CoInitialize
            CoInitialize()
        except Exception:
            pass

    def _inicializar_audio(self):
        self._com_init()
        try:
            CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            deviceEnumerator = CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL)
            device = deviceEnumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            IID_IAudioEndpointVolume = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
            interface = device.Activate(IID_IAudioEndpointVolume, CLSCTX_ALL, None)
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            self._volume_tid = threading.get_ident()
            volume_atual = self.volume_control.GetMasterVolumeLevelScalar()
            print(f"[AUDIO] Driver carregado. Volume atual: {int(volume_atual * 100)}%")
            return True
        except Exception as e:
            print(f"[AUDIO] Falha ao inicializar: {e}")
            self.volume_control = None
            self._volume_tid = None
            return False

    def _garantir_volume(self):
        tid = threading.get_ident()
        if self.volume_control is not None and self._volume_tid == tid:
            return True
        return self._inicializar_audio()

    def volume_pc(self, modo, valor=0):
        if not self._garantir_volume():
            return "Erro: Driver de áudio não disponível."
        try:
            valor_float = float(valor or 0)
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
            else:
                return f"Modo de volume desconhecido: '{modo}'."
            novo_volume = max(0.0, min(1.0, novo_volume))
            self.volume_control.SetMasterVolumeLevelScalar(novo_volume, None)
            return f"Volume ajustado para {int(novo_volume * 100)}%."
        except Exception as e:
            self.volume_control = None
            self._volume_tid = None
            return f"Erro ao ajustar volume: {e}"

    def pausar_midia(self):
        try:
            pyautogui.press("playpause")
            return "Mídia pausada/retomada."
        except Exception as e:
            return f"Erro: {e}"
