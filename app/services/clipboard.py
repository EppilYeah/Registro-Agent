import pyperclip


class ClipboardService:
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
            pyperclip.copy(str(texto) if texto is not None else "")
            return "Texto copiado para o clipboard."
        except Exception as e:
            return f"Erro ao escrever clipboard: {e}"
