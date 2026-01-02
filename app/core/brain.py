import json
import time
import traceback
import config
from datetime import datetime
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content

class Brain:
    def __init__(self):
        self.caminho_memoria = "data/brain.jsonl"
        self.modelo_nome = ""
        self.contador_requisicoes = 0
        
        self._configurar_api_key()
        self.chat, self.modelo = self._carregar_modelo_seguro()
        
        # Mantendo original: o sistema principal injeta a si mesmo aqui
        self.sistema = None 

    def _configurar_api_key(self):
        """Gerencia rotação de chaves conforme original"""
        if hasattr(config, 'API_KEYS') and len(config.API_KEYS) > 1:
            config.API_KEY_ATUAL = (getattr(config, 'API_KEY_ATUAL', 0) + 1) % len(config.API_KEYS)
            key = config.API_KEYS[config.API_KEY_ATUAL]
            genai.configure(api_key=key)
            print(f" [API] Rotação: ...{key[-4:]}")
        else:
            genai.configure(api_key=config.API_KEY)

    def _registrar_memoria(self, texto, autor):
        """Salva log no JSONL"""
        try:
            msg = {"data": str(datetime.now()), "autor": autor, "texto": texto}
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        except: pass

    def carregar_memoria(self):
        """Lê histórico mantendo estrutura original"""
        hist = [
            {"role": "user", "parts": [config.PROMPT_PERSONALIDADE]},
            {"role": "model", "parts": ['{"emocao": "neutro", "texto_resposta": "Sistemas online."}']}
        ]
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                # Mantém leitura simples das últimas 20 linhas
                for linha in f.readlines()[-20:]:
                    d = json.loads(linha)
                    role = "model" if d["autor"] == "REGISTRO" else "user"
                    hist.append({"role": role, "parts": [d["texto"]]})
        except: pass
        return hist

    def _carregar_modelo_seguro(self, ignorar_modelos=None):
        """Loop de conexão com tratamento de Cota (429)"""
        ignorar_modelos = ignorar_modelos or []
        tools = getattr(config, 'LISTA_FERRAMENTAS', [])
        
        if len(ignorar_modelos) >= len(config.LISTA_MODELOS):
            if hasattr(config, 'API_KEYS') and len(config.API_KEYS) > 1:
                print("[INFO] Trocando Key por falta de modelos...")
                self._configurar_api_key()
                return self._carregar_modelo_seguro(ignorar_modelos=[])
            raise Exception("Falha total: Sem cota em nenhum modelo/key.")

        for nome in config.LISTA_MODELOS:
            if nome in ignorar_modelos: continue
            try:
                print(f"[CONEXÃO] Tentando {nome}...")
                model = genai.GenerativeModel(
                    nome, tools=tools,
                    generation_config={"temperature": 1.0, "top_p": 0.95, "top_k": 40}
                )
                chat = model.start_chat(history=self.carregar_memoria())
                self.modelo_nome = nome
                return chat, model
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    ignorar_modelos.append(nome)
                else:
                    print(f"[ERRO] {nome}: {e}")
                    time.sleep(1)
        
        # Se loop terminar sem sucesso, tenta recursão (vai cair no check de key acima)
        return self._carregar_modelo_seguro(ignorar_modelos)

    def processar_entrada(self, prompt, tentativa=0):
        if tentativa >= 3:
            return {"texto_resposta": "Sistemas indisponíveis. Tente tarde.", "emocao": "confuso"}

        if getattr(config, 'MODO_DEBUG', False):
            return {"emocao": "neutro", "texto_resposta": "Modo debug ativo."}

        if tentativa == 0: self._registrar_memoria(prompt, "Luis")
        self.contador_requisicoes += 1
        print(f"[REQ #{self.contador_requisicoes}] Processando...")

        try:
            res = self.chat.send_message(prompt)

            # --- Loop de Ferramentas (Mantendo lógica original do while) ---
            turnos = 0
            while res.parts and res.parts[0].function_call and turnos < 5:
                turnos += 1
                partes_tool = []
                for part in res.parts:
                    if fc := part.function_call:
                        print(f"[TOOL] {fc.name} | Args: {dict(fc.args)}")
                        retorno = "ERRO: Ferramenta desconhecida."
                        
                        # Verifica self.sistema como no original
                        if self.sistema and hasattr(self.sistema, fc.name):
                            try:
                                retorno = getattr(self.sistema, fc.name)(**dict(fc.args))
                            except Exception as e: retorno = f"Erro interno: {e}"
                        else:
                            retorno = f"Método '{fc.name}' não existe."
                        
                        print(f"[TOOL] Resultado: {str(retorno)[:50]}...")
                        partes_tool.append(content.Part(function_response=content.FunctionResponse(
                            name=fc.name, response={'result': str(retorno)})))
                
                res = self.chat.send_message(partes_tool)

            # --- Tratamento de Resposta (JSON) ---
            if not res.text: raise ValueError("Resposta vazia")
            
            txt = res.text.replace("```json", "").replace("```", "").strip()
            try:
                dados = json.loads(txt)
            except:
                # Tentativa de correção única (comportamento original)
                print("[JSON] Falha. Pedindo correção...")
                res = self.chat.send_message("Protocolo incorreto. Retorne APENAS o JSON.")
                txt = res.text.replace("```json", "").replace("```", "").strip()
                try: dados = json.loads(txt)
                except: dados = {"emocao": "confuso", "texto_resposta": res.text}

            if not isinstance(dados, dict): 
                dados = {"emocao": "neutro", "texto_resposta": str(dados)}

            if tentativa == 0: 
                self._registrar_memoria(dados.get("texto_resposta", ""), "REGISTRO")
            
            return dados

        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"[QUOTA] {self.modelo_nome} esgotado. Trocando...")
                try:
                    # Tenta reconectar ignorando o atual
                    self.chat, self.modelo = self._carregar_modelo_seguro(ignorar_modelos=[self.modelo_nome])
                    return self.processar_entrada(prompt, tentativa + 1)
                except: pass
            
            traceback.print_exc()
            return {"texto_resposta": "Erro fatal no processamento.", "emocao": "confuso"}

    def gerar_texto_aleatorio(self, tema):
        """Gera lembrete sarcástico (texto puro)"""
        prompt = f"""
Você é o REGISTRO (estilo GLaDOS). Lembrete sobre: "{tema}".
Frase curta e sarcástica. APENAS texto puro, SEM JSON.
        """
        try:
            return self.modelo.generate_content(prompt).text.strip()
        except: return f"Lembrete: {tema}"