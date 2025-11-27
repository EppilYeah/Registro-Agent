import json, random
from datetime import datetime, date, time, timedelta

def limpar_texto(texto):
    textolimpo = texto.strip().lower()
    return textolimpo

class Brain:
    def __init__(self):
        self.caminho_memoria = "data/brain.jsonl"
        
    def _registrar_memoria(self, texto, quem_falou):
        mensagem = {
            "data": str(datetime.now()),
            "autor" : quem_falou,
            "texto" : texto,
            }
        with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
            f.write(json.dumps(mensagem, ensure_ascii=False) + "\n")
    
    def processar_entrada(self, prompt_usuario):
        self._registrar_memoria(prompt_usuario, "Luis")
        texto_limpo = limpar_texto(prompt_usuario)
        if "oi" in texto_limpo:
            resposta = "Olá! tudo bem?"
        elif "nome" in texto_limpo:
            resposta = "REGISTRO;"
        else:
            respostas = ["Ainda não produzi essa resposta", "Ainda não sou inteligewnte nesse ponto", "Baixando inteligencia - falha"]
            resposta = random.choice(respostas)
        self._registrar_memoria(resposta, "REGISTRO")
        return resposta
    