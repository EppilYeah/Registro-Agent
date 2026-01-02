import json
import time
import traceback
import sys
import config
from datetime import datetime
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content


class Brain:
    def __init__(self):
        self.caminho_memoria = "data/brain.jsonl"
        self.modelo_nome = ""
        self.contador_requisicoes = 0
        self.chamadas_ultimo_minuto = []

        self.chaves_disponiveis = config.API_KEYS.copy() if hasattr(
            config, 'API_KEYS') and config.API_KEYS else []
        self.chaves_esgotadas = []
        self.indice_chave_atual = 0
        self.tempo_ultimo_esgotamento_total = 0

        print("\n" + "="*60)
        print("CHAVES:")
        if self.chaves_disponiveis:
            for i, key in enumerate(self.chaves_disponiveis, 1):
                print(f"  {i}. ...{key[-2:]}")
        else:
            print(" NENHUMA CHAVE ENCONTRADA")
        print("="*60 + "\n")

        self._configurar_api_key()
        self.chat, self.modelo = self._carregar_modelo_seguro()

        self.sistema = None

    def _configurar_api_key(self, forcar_proxima=False):
        if not self.chaves_disponiveis or len(self.chaves_disponiveis) <= 1:
            key = config.API_KEY
            genai.configure(api_key=key)
            print(f"[API] Chave única: ...{key[-4:]}")
            return

        if forcar_proxima or self.indice_chave_atual >= len(self.chaves_disponiveis):
            self.indice_chave_atual = (
                self.indice_chave_atual + 1) % len(self.chaves_disponiveis)

        key = self.chaves_disponiveis[self.indice_chave_atual]
        genai.configure(api_key=key)
        print(
            f"[API] Chave [{self.indice_chave_atual + 1}/{len(self.chaves_disponiveis)}]: ...{key[-4:]}")

    def _marcar_chave_esgotada(self):
        if not self.chaves_disponiveis or len(self.chaves_disponiveis) <= 1:
            print("Chave única esgotada. Aguardando reset...")
            self._aguardar_reset_quota()
            return True

        chave_atual = self.chaves_disponiveis[self.indice_chave_atual]

        if chave_atual not in self.chaves_esgotadas:
            self.chaves_esgotadas.append(chave_atual)
            print(
                f"[API] Chave ...{chave_atual[-4:]} esgotada ({len(self.chaves_esgotadas)}/{len(config.API_KEYS)})")

        self.chaves_disponiveis.remove(chave_atual)

        if self.chaves_disponiveis:
            self.indice_chave_atual = 0
            self._configurar_api_key()
            return True

        print("\n" + "="*60)
        print("TODAS AS CHAVES ESGOTARAM!")
        print("="*60)

        self.tempo_ultimo_esgotamento_total = time.time()
        self._aguardar_reset_quota()

        self.chaves_disponiveis = config.API_KEYS.copy()
        self.chaves_esgotadas = []
        self.indice_chave_atual = 0
        self._configurar_api_key()

        return True

    def _aguardar_reset_quota(self):
        print("\n[QUOTA] reset da cota (60 segundos)...")

        for i in range(60, 0, -1):
            mins = i // 60
            secs = i % 60
            sys.stdout.write(f"\rReset em: {mins:02d}:{secs:02d} ")
            sys.stdout.flush()
            time.sleep(1)

        print("\nQuota resetada\n")

    def _registrar_memoria(self, texto, autor):
        try:
            msg = {"data": str(datetime.now()), "autor": autor, "texto": texto}
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        except:
            pass

    def carregar_memoria(self):
        hist = [
            {"role": "user", "parts": [config.PROMPT_PERSONALIDADE]},
            {"role": "model", "parts": [
                '{"emocao": "neutro", "texto_resposta": "Sistemas online."}']}
        ]
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                for linha in f.readlines()[-20:]:
                    d = json.loads(linha)
                    role = "model" if d["autor"] == "REGISTRO" else "user"
                    hist.append({"role": role, "parts": [d["texto"]]})
        except:
            pass
        return hist

    def _carregar_modelo_seguro(self, ignorar_modelos=None):
        ignorar_modelos = ignorar_modelos or []
        tools = getattr(config, 'LISTA_FERRAMENTAS', [])

        max_tentativas = len(config.LISTA_MODELOS) * 2
        tentativas_atuais = len(ignorar_modelos)

        if tentativas_atuais >= max_tentativas:
            raise Exception("Limite de tentativas de conexão atingido.")

        if len(ignorar_modelos) >= len(config.LISTA_MODELOS):
            if hasattr(config, 'API_KEYS') and len(config.API_KEYS) > 1:
                print("[INFO] Trocando Key ")
                self._configurar_api_key(forcar_proxima=True)
                return self._carregar_modelo_seguro(ignorar_modelos=[])
            raise Exception("Falha total: Sem cota")

        for nome in config.LISTA_MODELOS:
            if nome in ignorar_modelos:
                continue
            try:
                print(f"[CONEXÃO] Tentando {nome}...")
                model = genai.GenerativeModel(
                    nome, tools=tools,
                    generation_config={"temperature": 1.0,
                                       "top_p": 0.95, "top_k": 40}
                )
                chat = model.start_chat(history=self.carregar_memoria())
                self.modelo_nome = nome
                print(f"[CONEXÃO] Conectado em {nome}")
                return chat, model
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    print(f"[QUOTA] {nome} sem cota")
                    ignorar_modelos.append(nome)
                else:
                    print(f"[ERRO] {nome}: {e}")
                    time.sleep(1)

        return self._carregar_modelo_seguro(ignorar_modelos)

    def processar_entrada(self, prompt, tentativa=0):
        if tentativa >= 2:
            return {
                "texto_resposta": "Todas as cotas esgotadas. Já aguardei o reset.",
                "emocao": "confuso"
            }

        if getattr(config, 'MODO_DEBUG', False):
            return {"emocao": "neutro", "texto_resposta": "Modo debug ativo."}

        agora = time.time()
        self.chamadas_ultimo_minuto = [
            t for t in self.chamadas_ultimo_minuto if agora - t < 60]

        if len(self.chamadas_ultimo_minuto) >= 12:
            tempo_espera = 60 - (agora - self.chamadas_ultimo_minuto[0])
            print(
                f"Rate limit: {len(self.chamadas_ultimo_minuto)}/15 chamadas. Aguardando {tempo_espera:.1f}s...")
            time.sleep(tempo_espera + 1)
            self.chamadas_ultimo_minuto = []

        self.chamadas_ultimo_minuto.append(agora)

        if tentativa == 0:
            self._registrar_memoria(prompt, "Luis")

        self.contador_requisicoes += 1
        print(f"[REQ #{self.contador_requisicoes}] Tentativa {tentativa + 1}/2")
        print(
            f"[DEBUG] Chamadas no último minuto: {len(self.chamadas_ultimo_minuto)}")

        try:
            res = self.chat.send_message(prompt)

            if res.candidates and res.candidates[0].finish_reason != 1:
                reason = res.candidates[0].finish_reason
                motivos = {
                    1: "STOP (sucesso)",
                    2: "MAX_TOKENS",
                    3: "SAFETY (bloqueado por segurança)",
                    4: "RECITATION (plágio detectado)",
                    5: "OTHER"
                }
                print(
                    f"[AVISO] Resposta bloqueada: {motivos.get(reason, 'desconhecido')}")

                if reason == 3:
                    return {"emocao": "confuso", "texto_resposta": "Desculpe, não posso responder isso."}
                elif reason == 2:
                    return {"emocao": "irritado", "texto_resposta": "Resposta muito longa. Reformule."}

            turnos = 0
            ultimo_retorno = None

            while res.parts and any(hasattr(p, 'function_call') and p.function_call for p in res.parts) and turnos < 5:
                turnos += 1
                partes_tool = []

                for part in res.parts:
                    fc = getattr(part, 'function_call', None)
                    if fc:
                        print(f"[TOOL] {fc.name} | Args: {dict(fc.args)}")

                        retorno = "ERRO: Ferramenta desconhecida."
                        if self.sistema and hasattr(self.sistema, fc.name):
                            try:
                                retorno = getattr(self.sistema, fc.name)(
                                    **dict(fc.args))
                                ultimo_retorno = retorno
                            except Exception as e:
                                retorno = f"Erro interno: {e}"
                        else:
                            retorno = f"Método '{fc.name}' não existe no sistema."

                        print(f"[TOOL] Resultado: {str(retorno)[:80]}...")
                        partes_tool.append(content.Part(
                            function_response=content.FunctionResponse(
                                name=fc.name,
                                response={'result': str(retorno)}
                            )
                        ))

                try:
                    res = self.chat.send_message(partes_tool)
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        print(
                            f"[QUOTA] Sem cota para gerar resposta textual após executar ferramenta.")

                        if tentativa == 0 and ultimo_retorno:
                            self._registrar_memoria(ultimo_retorno, "REGISTRO")

                        return {
                            "emocao": "neutro",
                            "texto_resposta": ultimo_retorno or "Tarefa executada com sucesso."
                        }

                    raise

            if not res.text:
                raise ValueError("Resposta vazia sem function_call")

            txt = res.text.replace("```json", "").replace("```", "").strip()

            try:
                dados = json.loads(txt)
            except json.JSONDecodeError:
                print("[JSON] Falha ao parsear. Pedindo correção...")
                try:
                    res = self.chat.send_message(
                        "Protocolo incorreto. Retorne APENAS o JSON válido.")
                    txt = res.text.replace(
                        "```json", "").replace("```", "").strip()
                    dados = json.loads(txt)
                except:
                    dados = {"emocao": "confuso", "texto_resposta": res.text}

            if not isinstance(dados, dict):
                dados = {"emocao": "neutro", "texto_resposta": str(dados)}

            if tentativa == 0:
                self._registrar_memoria(
                    dados.get("texto_resposta", ""), "REGISTRO")

            return dados

        except Exception as e:
            erro_str = str(e)

            if "429" in erro_str or "quota" in erro_str.lower() or "resource_exhausted" in erro_str.lower():
                print(f"[QUOTA] {self.modelo_nome} sem cota na chave atual.")

                if tentativa == 0:
                    if self._marcar_chave_esgotada():
                        print("[QUOTA] Tentando com próxima chave...")
                        try:
                            self.chat, self.modelo = self._carregar_modelo_seguro(
                                ignorar_modelos=[])
                            return self.processar_entrada(prompt, tentativa + 1)
                        except Exception as e2:
                            print(f"[ERRO] Falha ao reconectar: {e2}")

                return {
                    "emocao": "confuso",
                    "texto_resposta": "⚠️ Todas as chaves esgotadas. Já aguardei o reset."
                }

            print(f"[ERRO] Exceção não tratada:")
            traceback.print_exc()
            return {
                "texto_resposta": "Erro fatal no processamento. Verifique os logs.",
                "emocao": "confuso"
            }

    def gerar_texto_aleatorio(self, tema):
        prompt = f"""
Você é o REGISTRO (estilo GLaDOS). Lembrete sobre: "{tema}".
Frase curta e sarcástica. APENAS texto puro, SEM JSON.
        """
        try:
            return self.modelo.generate_content(prompt).text.strip()
        except:
            return f"Lembrete: {tema}"
