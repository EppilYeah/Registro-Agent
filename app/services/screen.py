import io
import time
from PIL import ImageGrab
import janela


class ScreenService:
    def __init__(self, obter_client=None, obter_modelo=None):
        self.obter_client = obter_client
        self.obter_modelo = obter_modelo

    def _resolver(self, alvo):
        if alvo is None:
            return None
        return alvo() if callable(alvo) else alvo

    def ver_tela(self):
        try:
            client = self._resolver(self.obter_client)
            if not client:
                return "Cliente de IA não disponível para análise visual."

            modelo = self._resolver(self.obter_modelo) or "gemini-flash-latest"

            escondeu = janela.esconder()
            if escondeu:
                time.sleep(0.25)
            try:
                img = ImageGrab.grab()
            finally:
                if escondeu:
                    janela.mostrar()

            img = img.resize((1280, 720))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            raw = buf.getvalue()

            from google.genai import types as gtypes
            response = client.models.generate_content(
                model=modelo,
                contents=[
                    gtypes.Part.from_bytes(data=raw, mime_type="image/jpeg"),
                    "Descreva de forma concisa o que está visível nesta tela. Foque no conteúdo principal. Ignore a interface do REGISTRO se ainda aparecer.",
                ],
            )
            texto = (response.text or "").strip()
            return texto or "Tela capturada, mas o modelo não descreveu nada."
        except Exception as e:
            try:
                janela.mostrar()
            except Exception:
                pass
            return f"Erro ao capturar tela: {e}"
