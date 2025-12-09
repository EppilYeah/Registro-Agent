import json
from datetime import datetime
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
import config
import traceback
import time

class Brain:
    
    def __init__(self):
        self.caminho_memoria = "data/brain.jsonl"
        self.modelo_atual_nome = "" 
        self.contador_requisicoes = 0
        
        self._configurar_api_key()
        
        self.chat, self.modelo = self._carregar_modelo_seguro()
        
        self.sistema = None
    
    def _configurar_api_key(self):
        if hasattr(config, 'API_KEYS') and len(config.API_KEYS) > 1:
            config.API_KEY_ATUAL = (config.API_KEY_ATUAL + 1) % len(config.API_KEYS)
            key_atual = config.API_KEYS[config.API_KEY_ATUAL]
            genai.configure(api_key=key_atual)
            print(f"[API] Usando key #{config.API_KEY_ATUAL + 1}/{len(config.API_KEYS)}")
        else:
            genai.configure(api_key=config.API_KEY)
            print(f"[API] Usando key única")

    def _registrar_memoria(self, texto, quem_falou):
        mensagem = {
            "data": str(datetime.now()),
            "autor": quem_falou,
            "texto": texto,
        }

        try:
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps(mensagem, ensure_ascii=False) + "\n")
        except FileNotFoundError:
            pass

    def processar_entrada(self, prompt_usuario, _tentativa_recursiva=0):
        
        if _tentativa_recursiva >= 3:
            print(f"[ERRO] Limite de tentativas atingido (3). Abortando.")
            return {
                "texto_resposta": "Todos os modelos e API keys estão sem cota. Tente novamente mais tarde.",
                "emocao": "confuso"
            }
        
        if hasattr(config, 'MODO_DEBUG') and config.MODO_DEBUG:
            print(f"[DEBUG] Simulando resposta para: {prompt_usuario}")
            return {
                "emocao": "neutro",
                "texto_resposta": "Modo debug ativo. Sem consumo de API."
            }
        
        self._registrar_memoria(prompt_usuario, "Luis")
        
        try:
            self.contador_requisicoes += 1
            print(f"[REQ #{self.contador_requisicoes}] Enviando prompt inicial")
            
            response = self.chat.send_message(prompt_usuario)
            
            turnos_funcao = 0
            
            while response.parts and response.parts[0].function_call and turnos_funcao < 5:
                turnos_funcao += 1
                partes_resposta_ferramenta = []
                
                for part in response.parts:
                    if part.function_call:
                        fname = part.function_call.name
                        fargs = dict(part.function_call.args)
                        print(f"[TOOL] {fname} | Args: {fargs}")
                        
                        resultado_acao = "ERRO: Ferramenta desconhecida."
                        
                        if hasattr(self, 'sistema') and self.sistema:
                            if hasattr(self.sistema, fname):
                                try:
                                    metodo = getattr(self.sistema, fname)
                                    resultado_acao = metodo(**fargs)
                                    print(f"[TOOL] Resultado: {resultado_acao}")
                                except TypeError as e:
                                    resultado_acao = f"Erro de Assinatura: {e}"
                                except Exception as e:
                                    resultado_acao = f"Erro interno: {e}"
                            else:
                                resultado_acao = f"Método '{fname}' não existe."
                        
                        partes_resposta_ferramenta.append(
                            content.Part(
                                function_response=content.FunctionResponse(
                                    name=fname,
                                    response={'result': str(resultado_acao)}  
                                )
                            )
                        )
                
                self.contador_requisicoes += 1
                print(f"[REQ #{self.contador_requisicoes}] Devolvendo resultado da ferramenta")
                response = self.chat.send_message(partes_resposta_ferramenta)

            try:
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                dados_ia = json.loads(texto_limpo)
            except (ValueError, json.JSONDecodeError) as e:
                print(f"[WARN] JSON inválido: {e}")
                
                tentativa_correcao = False
                if not tentativa_correcao:
                    tentativa_correcao = True
                    self.contador_requisicoes += 1
                    print(f"[REQ #{self.contador_requisicoes}] Corrigindo formato JSON")
                    
                    try:
                        response = self.chat.send_message("Protocolo de Saída incorreto. Retorne APENAS o JSON final.")
                        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                        dados_ia = json.loads(texto_limpo)
                    except:
                        dados_ia = {
                            "emocao": "confuso", 
                            "texto_resposta": response.text
                        }
                else:
                    dados_ia = {
                        "emocao": "confuso", 
                        "texto_resposta": response.text
                    }

            if not isinstance(dados_ia, dict):
                dados_ia = {"emocao": "neutro", "texto_resposta": str(dados_ia)}

            texto_dados_ia = dados_ia.get("texto_resposta", "Sem resposta vocal.")
            self._registrar_memoria(texto_dados_ia, "REGISTRO")
            
            return dados_ia
            
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"[ERRO] Cota esgotada no modelo {self.modelo_atual_nome}")
                
                if hasattr(config, 'API_KEYS') and len(config.API_KEYS) > 1:
                    print(f"[INFO] Tentando trocar API key...")
                    self._configurar_api_key()
                
                try:
                    ignorar = [self.modelo_atual_nome]
                    self.chat, self.modelo = self._carregar_modelo_seguro(ignorar_modelos=ignorar)
                    print(f"[INFO] Trocado para {self.modelo_atual_nome}. Tentando novamente...")
                    return self.processar_entrada(prompt_usuario, _tentativa_recursiva + 1)
                except Exception as retry_error:
                    print(f"[ERRO] Todas as alternativas falharam: {retry_error}")
                    return {
                        "texto_resposta": "Sistema de IA temporariamente indisponível. Cota esgotada.",
                        "emocao": "confuso"
                    }
                    
            print(f"[ERRO CRÍTICO] {e}")
            traceback.print_exc()
            return {"texto_resposta": "Erro fatal no processamento lógico.", "emocao": "confuso"}
        
    def _carregar_modelo_seguro(self, ignorar_modelos=None, _tentativa_key=0):
        if ignorar_modelos is None:
            ignorar_modelos = []
        
        if _tentativa_key >= len(config.API_KEYS) if hasattr(config, 'API_KEYS') else 1:
            raise Exception("Todas as API keys foram testadas sem sucesso.")

        config_json = {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 40
        }
        
        tools = config.LISTA_FERRAMENTAS
        
        modelos_testados = 0
        
        for nome_modelo in config.LISTA_MODELOS:
            if nome_modelo in ignorar_modelos:
                continue 
            
            modelos_testados += 1

            try:
                print(f"[CONEXÃO] Tentando {nome_modelo}...")
                
                modelo_teste = genai.GenerativeModel(
                    nome_modelo,
                    generation_config=config_json,
                    tools=tools
                )
                
                historico_completo = self.carregar_memoria()
                
                chat_pronto = modelo_teste.start_chat(history=historico_completo)
                
                print(f"[OK] Conectado ao {nome_modelo}")
                
                self.modelo_atual_nome = nome_modelo 
                
                return chat_pronto, modelo_teste

            except Exception as e:
                print(f"[FALHA] {nome_modelo}: {e}")
                
                if "429" in str(e) or "quota" in str(e).lower():
                    ignorar_modelos.append(nome_modelo)
                    print(f"[INFO] {nome_modelo} sem cota disponível")
                    continue
                
                time.sleep(2)
                continue
        
        if modelos_testados >= len(config.LISTA_MODELOS):
            if hasattr(config, 'API_KEYS') and len(config.API_KEYS) > 1:
                print(f"[INFO] Todos os modelos falharam com esta key. Tentando próxima...")
                self._configurar_api_key()
                return self._carregar_modelo_seguro(ignorar_modelos=[], _tentativa_key=_tentativa_key + 1)
        
        raise Exception("Todos os modelos falharam.")

    def carregar_memoria(self):
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
            pass
            
        return historico

    def gerar_texto_aleatorio(self, lembrete_bruto):
        prompt_especifico = f"""
Você é o REGISTRO, uma IA sarcástica estilo GLaDOS.
O usuário pediu um lembrete sobre: "{lembrete_bruto}".

Escreva UMA frase curta e sarcástica avisando sobre isso.
IMPORTANTE: Responda APENAS o texto puro para ser falado, SEM JSON, SEM formatação.

Exemplo:
Entrada: "tomar remédio"
Saída: Está na hora de ingerir suas substâncias químicas. Espero que não se esqueça novamente.
        """
        try:
            self.contador_requisicoes += 1
            print(f"[REQ #{self.contador_requisicoes}] Gerando texto de lembrete")
            
            response = self.modelo.generate_content(
                prompt_especifico,
                generation_config={
                    "response_mime_type": "text/plain",
                    "temperature": 1.2
                } 
            )
            
            texto = response.text.strip()
            
            if texto.startswith("{") or texto.startswith("```"):
                print("[WARN] IA retornou JSON no lembrete. Usando fallback.")
                return f"Lembrete: {lembrete_bruto}"
            
            return texto
            
        except Exception as e:
            print(f"[ERRO] Falha ao gerar lembrete: {e}")
            return f"Atenção: {lembrete_bruto}"