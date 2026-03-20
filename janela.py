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

def _encontrar_hwnd(tentativas=30, intervalo=0.3):
    if not _WIN32:
        return None
    for _ in range(tentativas):
        hwnd = win32gui.FindWindow(None, _TITULO)
        if hwnd:
            return hwnd
        hwnd = _buscar_parcial(_TITULO)
        if hwnd:
            return hwnd
        time.sleep(intervalo)
    print("[JANELA] Janela não encontrada após tentativas.")
    return None

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
    if not _WIN32:
        return
    hwnd = win32gui.FindWindow(None, _TITULO)
    if not hwnd:
        hwnd = _buscar_parcial(_TITULO)
    if not hwnd:
        return
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except:
        pass