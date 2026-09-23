import time
import threading

try:
    import win32gui
    import win32con
    _WIN32 = True
except ImportError:
    _WIN32 = False
    print("[JANELA] pywin32 não encontrado. Funções de janela desativadas.")

_TITULO = "REG / UI"
_hwnd_cache = None
_obter_webview = None


def registrar_webview(fn):
    global _obter_webview
    _obter_webview = fn


def _webview():
    if _obter_webview is None:
        return None
    try:
        return _obter_webview()
    except Exception:
        return None


def _encontrar_hwnd(tentativas=30, intervalo=0.3):
    global _hwnd_cache
    if not _WIN32:
        return None
    if _hwnd_cache and win32gui.IsWindow(_hwnd_cache):
        return _hwnd_cache
    for _ in range(tentativas):
        hwnd = win32gui.FindWindow(None, _TITULO)
        if hwnd:
            _hwnd_cache = hwnd
            return hwnd
        hwnd = _buscar_parcial(_TITULO)
        if hwnd:
            _hwnd_cache = hwnd
            return hwnd
        time.sleep(intervalo)
    print("[JANELA] Janela não encontrada após tentativas.")
    return None


def resetar_cache():
    global _hwnd_cache
    _hwnd_cache = None
    return _hwnd_rapido()


def _hwnd_rapido():
    return _encontrar_hwnd(tentativas=3, intervalo=0.05)


def _buscar_parcial(parte):
    resultado = [0]
    def _cb(hwnd, _):
        if parte.lower() in win32gui.GetWindowText(hwnd).lower():
            resultado[0] = hwnd
    win32gui.EnumWindows(_cb, None)
    return resultado[0]


def definir_sempre_visivel():
    if not _WIN32:
        return
    def _aplicar():
        hwnd = _encontrar_hwnd()
        if hwnd:
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            print(f"[JANELA] Sempre visível ativado. HWND={hwnd}")
        else:
            print("[JANELA] Falha ao ativar sempre visível.")
    threading.Thread(target=_aplicar, daemon=True).start()


def trazer_para_frente():
    hwnd = _hwnd_rapido()
    if hwnd:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            win32gui.SetForegroundWindow(hwnd)
            return
        except Exception:
            pass
    janela = _webview()
    if not janela:
        return
    try:
        janela.restore()
        janela.show()
    except Exception:
        pass


def esconder():
    hwnd = _hwnd_rapido()
    if hwnd:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            return True
        except Exception:
            pass
    janela = _webview()
    if not janela:
        return False
    try:
        janela.hide()
        return True
    except Exception:
        return False


def mostrar():
    hwnd = _hwnd_rapido()
    if hwnd:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            return True
        except Exception:
            pass
    janela = _webview()
    if not janela:
        return False
    try:
        janela.show()
        return True
    except Exception:
        return False
