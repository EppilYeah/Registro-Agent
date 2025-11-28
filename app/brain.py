import json
import google.generativeai as genai
import config
from datetime import datetime, date, time, timedelta



class Brain:
    def __init__(self):
        genai.configure(api_key=config.API_KEY)
        self.caminho_memoria = "data/brain.jsonl"
        self.model = genai.GenerativeModel('gemini-pro')
        personalidade = [
            {"role" : "user", "parts" : [config.PROMPT_PERSONALIDADE]},
            {"role" : "model", "parts": ['{"emocao": "neutro", "texto_resposta": "REGISTRO INICIADO"}']}
        ]
        self.chat = self.model.start_chat(history = personalidade)
        
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
        response = self.chat.send_message(prompt_usuario)
        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
        dados_ia = json.loads(texto_limpo)
        texto_dados_ia = dados_ia["texto_resposta"]
        self._registrar_memoria(texto_dados_ia, "REGISTRO")
        return dados_ia
        
    def carregar_modelo_seguro(self):
        for nome_modelo in config.LISTA_MODELOS:
            try:
                print(f"INICIANDO REGISTRO - {nome_modelo}")
                modelo_teste = genai.GenerativeModel(nome_modelo)
                modelo_teste.generate_content("Teste de conexão")
                print("\n\n REGISTRO INICIADO; ")
                return modelo_teste
            except Exception as e:
                print(f"ERRO AO INICIAR - {e}")
                continue
        raise Exception("IMPOSSIVEL INICIAR REGISTRO - ABORTANDO OPERAÇÃO")