import json
from datetime import datetime
from google.ai.generativelanguage_v1beta.types import content
import google.generativeai as genai
import config



class Brain:
    def __init__(self):
        genai.configure(api_key=config.API_KEY)
        self.caminho_memoria = "data/brain.jsonl"
        self.chat = self.carregar_modelo_seguro()

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
        config_json = {
            "response_mime_type": "application/json"
        }
        for nome_modelo in config.LISTA_MODELOS:
            try:
                print(f"INICIANDO REGISTRO - {nome_modelo}")
                modelo_teste = genai.GenerativeModel(
                    nome_modelo,
                    generation_config=config_json)
                historico_completo = self.carregar_memoria()
                chat_pronto = modelo_teste.start_chat(history=historico_completo)
                modelo_teste.generate_content("Teste de conexão")
                print("\n\n REGISTRO INICIADO; ")
                return chat_pronto
            except Exception as e:
                print(f"ERRO AO INICIAR - {e}")
                continue
        raise Exception("IMPOSSIVEL INICIAR REGISTRO - ABORTANDO OPERAÇÃO")
    
    def carregar_memoria(self):
        historico = []
        historico.append({
            "role": "user", 
            "parts": [config.PROMPT_PERSONALIDADE] # Ou PROMPT_PERSONALIDADE, confira o nome no config
        })
        historico.append({
            "role": "model", 
            "parts": ['{"emocao": "neutro", "texto_resposta": "Sistemas online."}']
        })
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
                for linha in linhas:
                    dados = json.loads(linha)
                    if dados["autor"] == "REGISTRO":
                        role = "model"
                    else:
                        role = "user"
                    
                    pacote_IA = {
                        "role" : role,
                        "parts" : [dados["texto"]]
                    }
                    historico.append(pacote_IA)
        except FileNotFoundError:
            pass
        return historico