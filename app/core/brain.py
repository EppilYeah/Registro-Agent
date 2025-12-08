import json
from datetime import datetime
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
import config
import traceback
import time

class Brain:
    '''Responsável por toda parte lógica de processamento e pensamento'''
    
    def __init__(self):
        genai.configure(api_key=config.API_KEY)
        self.caminho_memoria = "data/brain.jsonl"
        self.modelo_atual_nome = "" 
        
        # Carrega o modelo com sistema de segurança
        self.chat, self.modelo = self._carregar_modelo_seguro()
        
        # O sistema será injetado pelo main.py
        self.sistema = None

    def _registrar_memoria(self, texto, quem_falou):
        """Salva a conversa no arquivo JSONL para persistência"""
        mensagem = {
            "data": str(datetime.now()),
            "autor": quem_falou,
            "texto": texto,
        }

        try:
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps(mensagem, ensure_ascii=False) + "\n")
        except FileNotFoundError:
            pass # Se a pasta data não existir, ignora por enquanto

    def processar_entrada(self, prompt_usuario):
        '''Processa o prompt do usuário, lida com ferramentas e traduz pra IA'''
        self._registrar_memoria(prompt_usuario, "Luis")
        
        try:
            # Envio inicial
            response = self.chat.send_message(prompt_usuario)
            
            turnos_funcao = 0
            
            #  Loop de Resolução de Ferramentas
            while response.parts and response.parts[0].function_call and turnos_funcao < 5:
                turnos_funcao += 1
                partes_resposta_ferramenta = []
                
                resultado_acao = "ERRO: Ferramenta desconhecida." 
                
                for part in response.parts:
                    print(f" [SISTEMA] Retorno da ferramenta: {resultado_acao}")
                    if part.function_call:
                        fname = part.function_call.name
                        fargs = dict(part.function_call.args)
                        print(f"[SISTEMA] Acionando braço mecânico: {fname} | Params: {fargs}")
                        
                        
                        # Execução Dinâmica Segura
                        if hasattr(self, 'sistema') and self.sistema:
                            if hasattr(self.sistema, fname):
                                try:
                                    metodo = getattr(self.sistema, fname)
                                    # Desempacota os argumentos
                                    resultado_acao = metodo(**fargs)
                                except TypeError as e:
                                    resultado_acao = f"Erro de Assinatura (Config vs System): {e}"
                                except Exception as e:
                                    resultado_acao = f"Erro interno na ferramenta: {e}"
                            else:
                                resultado_acao = f"Erro: O método '{fname}' não existe no system.py."
                        
                        partes_resposta_ferramenta.append(
                            content.Part(
                                function_response=content.FunctionResponse(
                                    name=fname,
                                    response={'result': str(resultado_acao)}  
                                )
                            )
                        )
                
                response = self.chat.send_message(partes_resposta_ferramenta)

            # Tratamento da Resposta Final (Texto/JSON)
            try:
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                dados_ia = json.loads(texto_limpo)
            except (ValueError, json.JSONDecodeError):
                # Fallback
                print(" A IA esqueceu o JSON. Forçando formatação...")
                response = self.chat.send_message("Protocolo de Saída incorreto. Retorne APENAS o JSON final.")
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                try:
                    dados_ia = json.loads(texto_limpo)
                except:
                    # Último recurso se tudo falhar
                    dados_ia = {
                        "emocao": "confuso", 
                        "texto_resposta": response.text # Fala o que vier
                    }

            # Validação extra
            if not isinstance(dados_ia, dict):
                dados_ia = {"emocao": "neutro", "texto_resposta": str(dados_ia)}

            texto_dados_ia = dados_ia.get("texto_resposta", "Sem resposta vocal.")
            self._registrar_memoria(texto_dados_ia, "REGISTRO")
            
            return dados_ia
            
        except Exception as e:
            print(f"Erro CRÍTICO no cérebro: {e}")
            traceback.print_exc()
            return {"texto_resposta": "Erro fatal no processamento lógico.", "emocao": "confuso"}
        
    def _carregar_modelo_seguro(self, ignorar_modelos=None):
        '''Inicializa a IA com as configurações e testa os modelos disponíveis'''
        if ignorar_modelos is None:
            ignorar_modelos = []

        config_json = {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 40
        }
        
        tools = config.LISTA_FERRAMENTAS
        
        for nome_modelo in config.LISTA_MODELOS:
            if nome_modelo in ignorar_modelos:
                continue 

            try:
                print(f"TENTANDO CONEXÃO - {nome_modelo}")
                
                modelo_teste = genai.GenerativeModel(
                    nome_modelo,
                    generation_config=config_json,
                    tools=tools
                )
                
                historico_completo = self.carregar_memoria()
                
                chat_pronto = modelo_teste.start_chat(history=historico_completo)

                # Teste rápido (Ping) usando o modelo para não sujar histórico
                modelo_teste.generate_content("Teste")
                
                print(f"CONECTADO AO {nome_modelo}")
                
                self.modelo_atual_nome = nome_modelo 
                
                return chat_pronto, modelo_teste

            except Exception as e:
                print(f"⚠️ Falha no {nome_modelo}: {e}")
                time.sleep(3)
                continue
        
        raise Exception("Todos os modelos falharam.")

    def carregar_memoria(self):
        '''Carrega a memória da IA do arquivo JSONL'''
        historico = []
        
        # 1. Injeta Personalidade (Sempre primeiro)
        historico.append({
            "role": "user", 
            "parts": [config.PROMPT_PERSONALIDADE]
        })
        historico.append({
            "role": "model", 
            "parts": ['{"emocao": "neutro", "texto_resposta": "Sistemas online."}']
        })
        
        # 2. Lê do arquivo
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
                # Pega só as últimas 20 para economizar tokens
                ultimas_linhas = linhas[-20:]
                
                for linha in ultimas_linhas:
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
            pass # Arquivo não existe ainda
            
        return historico

    def gerar_texto_aleatorio(self, lembrete_bruto):
        '''Gera um texto criativo para o alarme (sem sujar o histórico principal)'''
        prompt_especifico = f"""
        CONTEXTO: O usuário pediu um lembrete sobre: "{lembrete_bruto}".
        TAREFA: Escreva uma única frase curta e sarcástica avisando o usuário sobre isso.
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
            return f"Atenção: {lembrete_bruto}" 