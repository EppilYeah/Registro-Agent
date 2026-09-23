import json
import os


class ProfileService:
    def __init__(self):
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.caminho = os.path.join(raiz, "data", "usuario.json")

    def consultar_perfil_usuario(self, campo=None):
        try:
            with open(self.caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            campo_limpo = (campo or "").strip() or None
            if not campo_limpo:
                resultado = {k: v for k, v in dados.items() if k != "ultima_atualizacao"}
                return json.dumps(resultado, ensure_ascii=False)
            valor = dados.get(campo_limpo)
            if valor is None:
                return f"Campo '{campo_limpo}' não encontrado no perfil."
            return str(valor)
        except FileNotFoundError:
            return "Perfil do usuário ainda não existe."
        except Exception as e:
            return f"Erro ao consultar perfil: {e}"
