import json
from datetime import datetime
import google.generativeai as genai
import config

class Brain:
    '''Responsavel por toda parte logica de processamento e pensamento'''
    def __init__(self):
        genai.configure(api_key=config.API_KEY)
        self.caminho_memoria = "data/brain.jsonl"
        

        self.chat, self.modelo = self.carregar_modelo_seguro()

    def _registrar_memoria(self, texto, quem_falou):
        mensagem = {
            "data": str(datetime.now()),
            "autor" : quem_falou,
            "texto" : texto,
            }

        try:
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps(mensagem, ensure_ascii=False) + "\n")
        except FileNotFoundError:
            pass

    def processar_entrada(self, prompt_usuario):
        '''Processa o prompt do usuario e traduz pra IA'''
        self._registrar_memoria(prompt_usuario, "Luis")
        
        try:
            response = self.chat.send_message(prompt_usuario) 
            texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
            dados_ia = json.loads(texto_limpo)
            
            texto_dados_ia = dados_ia.get("texto_resposta", "Erro ao ler resposta")
            self._registrar_memoria(texto_dados_ia, "REGISTRO")
            return dados_ia
        except Exception as e:
            print(f"Erro ao processar entrada: {e}")
            return {"texto_resposta": "Tive um erro interno ao processar sua mensagem.", "emocao": "confuso"}

    def carregar_modelo_seguro(self):
        '''Inicializa a IA com as configurações e testa os modelos disponiveis'''
        config_json = {
            "response_mime_type": "application/json", #converte automaticamente tudo pra json
            "temperature": 1.0,
            "top_p": 0.95,        #variedade vocabulario
            "top_k": 40           #criatividade escolhas
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
                return chat_pronto, modelo_teste
            except Exception as e:
                print(f"ERRO AO INICIAR - {e}")
                continue
        raise Exception("IMPOSSIVEL INICIAR REGISTRO - ABORTANDO OPERAÇÃO")

    def carregar_memoria(self):
        '''Carrega a memoria da IA'''
        historico = []
        historico.append({
            "role": "user", 
            "parts": [config.PROMPT_PERSONALIDADE]
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

    def gerar_texto_aleatorio(self, lembrete_bruto):
        '''Gera um texto aleatorio baseado no prompt'''
        prompt_especifico = f"""
        CONTEXTO: O usuário pediu um lembrete sobre: "{lembrete_bruto}".
        TAREFA: Escreva uma única frase curta avisando o usuário sobre isso.
        PERSONALIDADE: {config.PROMPT_PERSONALIDADE} (Use o tom definido aqui).
        REGRAS: Não use JSON aqui. Retorne apenas o texto puro para ser falado.
        """
        try:
            response = self.modelo.generate_content(
                prompt_especifico,
                generation_config={"response_mime_type": "text/plain"} 
            )
            return response.text
        except Exception as e:
            print(f"Erro ao gerar lembrete: {e}")
            return f"Atenção: {lembrete_bruto}" # Fallback