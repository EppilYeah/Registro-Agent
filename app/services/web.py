import os
import threading


class WebService:
    def abrir_whatsapp_web(self):
        try:
            if os.name == "nt":
                os.startfile("https://web.whatsapp.com/")
                return "WhatsApp Web aberto."
            return "Sistema operacional não suportado."
        except Exception as e:
            return f"Erro: {e}"

    def pesquisar_web(self, query):
        box = [f"Pesquisa excedeu o tempo para '{query}'."]

        def _rodar():
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    resultados = list(ddgs.text(query, region="br-pt", max_results=3))
                if not resultados:
                    box[0] = f"Sem resultados para '{query}'."
                    return
                partes = []
                for r in resultados:
                    titulo = (r.get("title") or "").strip()
                    corpo = (r.get("body") or "").strip()
                    if titulo and corpo:
                        partes.append(f"{titulo}: {corpo[:180]}")
                    elif corpo:
                        partes.append(corpo[:200])
                    elif titulo:
                        partes.append(titulo)
                box[0] = "\n".join(partes) if partes else f"Sem resultados para '{query}'."
            except Exception as e:
                box[0] = f"Erro na pesquisa: {e}"

        t = threading.Thread(target=_rodar, daemon=True)
        t.start()
        t.join(8)
        return box[0]
