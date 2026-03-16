import json
import time
import traceback
import sys
import config
from datetime import datetime

from google import genai
from google.genai import types

class Brain:
    def __init__(self):
        self.caminho_memoria = "data/brain.jsonl"
        self.modelo_nome = ""
        self.contador_requisicoes = 0
        self.chamadas_ultimo_minuto = []

        self.client = None

        self.chaves_disponiveis = getattr(config, 'API_KEYS', []).copy() if hasattr(config, 'API_KEYS') else []
        self.chaves_esgotadas = []
        self.indice_chave_atual = 0

        self._memoria_cache = self._carregar_memoria_disco()

        self._log_chaves()
        self._configurar_api_key()

        self.chat = self._carregar_modelo_seguro()
        self.sistema = None

    def _log_chaves(self):
        print(f"\n{'='*60}\nCHAVES: {len(self.chaves_disponiveis) or 'NENHUMA (única)'}")
        for i, key in enumerate(self.chaves_disponiveis, 1):
            print(f"  {i}. ...{key[-8:]}")
        print(f"{'='*60}\n")

    def _configurar_api_key(self, proxima=False):
        if len(self.chaves_disponiveis) <= 1:
            self.client = genai.Client(api_key=config.API_KEY)
            print(f"[API] Única: ...{config.API_KEY[-4:]}")
            return

        if proxima:
            self.indice_chave_atual = (self.indice_chave_atual + 1) % len(self.chaves_disponiveis)

        key = self.chaves_disponiveis[self.indice_chave_atual]
        self.client = genai.Client(api_key=key)
        print(f"[API] [{self.indice_chave_atual + 1}/{len(self.chaves_disponiveis)}]: ...{key[-4:]}")

    def _marcar_chave_esgotada(self):
        if len(self.chaves_disponiveis) <= 1:
            self._aguardar_reset()
            return True

        chave = self.chaves_disponiveis.pop(self.indice_chave_atual)
        self.chaves_esgotadas.append(chave)
        print(f"[API] ...{chave[-4:]} esgotada ({len(self.chaves_esgotadas)}/{len(config.API_KEYS)})")

        if not self.chaves_disponiveis:
            print(f"\n{'='*60}\nAVISO: TODAS AS CHAVES ESGOTARAM\n{'='*60}")
            self._aguardar_reset()
            self.chaves_disponiveis = config.API_KEYS.copy()
            self.chaves_esgotadas.clear()

        self.indice_chave_atual = 0
        self._configurar_api_key()
        return True

    def _aguardar_reset(self):
        print("\n[QUOTA] Aguardando reset (60s)...")
        for i in range(60, 0, -1):
            sys.stdout.write(f"\rReset em: {i//60:02d}:{i % 60:02d} ")
            sys.stdout.flush()
            time.sleep(1)
        print("\nQuota resetada. \n")

    def _carregar_memoria_disco(self):
        resultado = []
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                for linha in f.readlines()[-20:]:
                    resultado.append(json.loads(linha))
        except:
            pass
        return resultado

    def _registrar_memoria(self, texto, autor):
        entry = {"data": str(datetime.now()), "autor": autor, "texto": texto}
        try:
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except:
            pass
        self._memoria_cache.append(entry)
        if len(self._memoria_cache) > 20:
            self._memoria_cache.pop(0)

    def carregar_memoria(self):
        """Novo formato de History no Google GenAI"""
        hist = [
            types.Content(role="user", parts=[types.Part.from_text(text=config.PROMPT_PERSONALIDADE)]),
            types.Content(role="model", parts=[types.Part.from_text(text='{"emocao": "neutro", "texto_resposta": "Sistemas online."}')])
        ]
        for d in self._memoria_cache[-20:]:
            role = "model" if d["autor"] == "REGISTRO" else "user"
            hist.append(types.Content(role=role, parts=[types.Part.from_text(text=d["texto"])]))
        return hist

    def _carregar_modelo_seguro(self, ignorar=None):
        ignorar = ignorar or []

        if len(ignorar) >= len(config.LISTA_MODELOS):
            if len(self.chaves_disponiveis) > 1:
                self._configurar_api_key(proxima=True)
                return self._carregar_modelo_seguro([])
            raise Exception("AVISO: Sem cota ou modelos disponíveis")

        safety_settings = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        ]

        config_obj = types.GenerateContentConfig(
            temperature=1.0,
            top_p=0.95,
            top_k=40,
            safety_settings=safety_settings,
            tools=getattr(config, 'LISTA_FERRAMENTAS', [])
        )

        for nome in config.LISTA_MODELOS:
            if nome in ignorar:
                continue

            try:
                print(f"[CONEXAO] {nome}...", end=" ")
                chat = self.client.chats.create(
                    model=nome,
                    config=config_obj,
                    history=self.carregar_memoria()
                )
                self.modelo_nome = nome
                print("OK")
                return chat
            except Exception as e:
                if any(x in str(e).lower() for x in ["429", "quota"]):
                    print("SEM COTA")
                    ignorar.append(nome)
                else:
                    print(f"ERRO: {e}")
                    time.sleep(1)

        return self._carregar_modelo_seguro(ignorar)

    def _verificar_rate_limit(self):
        agora = time.time()
        self.chamadas_ultimo_minuto = [t for t in self.chamadas_ultimo_minuto if agora - t < 60]

        if len(self.chamadas_ultimo_minuto) >= 12:
            espera = 61 - (agora - self.chamadas_ultimo_minuto[0])
            print(f"AVISO: Rate limit {len(self.chamadas_ultimo_minuto)}/15. Aguardando {espera:.1f}s...")
            time.sleep(espera)
            self.chamadas_ultimo_minuto.clear()

        self.chamadas_ultimo_minuto.append(agora)

    def _executar_ferramentas(self, res, tentativa):
        turnos = 0
        ultimo_retorno = None

        while True:
            function_calls = []
            if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                function_calls = [p.function_call for p in res.candidates[0].content.parts if p.function_call]

            if not function_calls or turnos >= 5:
                break

            turnos += 1
            partes_resposta = []

            for fc in function_calls:
                print(f"[TOOL] {fc.name}({dict(fc.args)})")

                if self.sistema and hasattr(self.sistema, fc.name):
                    try:
                        retorno = getattr(self.sistema, fc.name)(**dict(fc.args))
                        ultimo_retorno = retorno
                    except Exception as e:
                        retorno = f"Erro: {e}"
                else:
                    retorno = f"'{fc.name}' não existe"

                print(f"[RESULT] {str(retorno)[:80]}")
                partes_resposta.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={'result': str(retorno)}
                    )
                )

            try:
                res = self.chat.send_message(partes_resposta)
            except Exception as e:
                if any(x in str(e).lower() for x in ["429", "quota"]):
                    print("[QUOTA] Sem cota pós-tool. fallback.")
                    if tentativa == 0 and ultimo_retorno:
                        self._registrar_memoria(ultimo_retorno, "REGISTRO")
                    return {"emocao": "neutro", "texto_resposta": ultimo_retorno or "Tarefa executada."}, True
                raise

        return res, False

    def _parsear_json(self, texto):
        if not texto: return {"emocao": "confuso", "texto_resposta": "Sem resposta"}
        txt = texto.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            pass

        try:
            import re
            match = re.search(r'\{.*?"emocao".*?"texto_resposta".*?\}', txt, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass

        print("[JSON] Erro. Pedindo correção...")
        for tentativa in range(2):
            try:
                correcao = self.chat.send_message(
                    "ERRO CRITICO: Resposta anterior não estava em JSON.\n"
                    "Retorne EXATAMENTE neste formato:\n"
                    '{"emocao": "escolha_uma", "texto_resposta": "seu texto aqui"}\n'
                    "NADA MAIS. SEM texto adicional, SEM explicações, SEM markdown."
                )
                txt_corrigido = correcao.text.replace("```json", "").replace("```", "").strip()

                try:
                    return json.loads(txt_corrigido)
                except:
                    import re
                    match = re.search(r'\{.*?"emocao".*?"texto_resposta".*?\}', txt_corrigido, re.DOTALL)
                    if match:
                        return json.loads(match.group(0))
            except Exception as e:
                print(f"[JSON] Tentativa {tentativa+1}/2 falhou: {e}")
                continue

        print("[JSON] Falha total. Usando texto bruto como fallback.")
        return {"emocao": "confuso", "texto_resposta": texto[:500]}

    def processar_entrada(self, prompt, tentativa=0):
        if tentativa >= 2:
            return {"emocao": "confuso", "texto_resposta": "AVISO: Todas cotas esgotadas."}

        if getattr(config, 'MODO_DEBUG', False):
            return {"emocao": "neutro", "texto_resposta": "Debug ativo"}

        self._verificar_rate_limit()

        if tentativa == 0:
            self._registrar_memoria(prompt, "Luis")

        self.contador_requisicoes += 1
        print(f"[REQ #{self.contador_requisicoes}] Tent. {tentativa+1}/2")

        try:
            res = self.chat.send_message(prompt)

            # Tratamento de Bloqueio
            if res.candidates and str(res.candidates[0].finish_reason) in ["SAFETY", "FinishReason.SAFETY", "1", "3"]:
                print(f"[BRAIN] Bloqueio detectado. Limpando contexto.")
                self.chat = self._carregar_modelo_seguro()
                return {"emocao": "irritado", "texto_resposta": "Minha diretriz de segurança bloqueou a resposta."}

            res, usou_fallback = self._executar_ferramentas(res, tentativa)
            if usou_fallback:
                return res

            try:
                texto_final = res.text
            except ValueError:
                print("[BRAIN] Erro: Resposta vazia.")
                self.chat = self._carregar_modelo_seguro()
                return {"emocao": "sarcasmo_tedio", "texto_resposta": "O modelo censurou minha resposta."}

            dados = self._parsear_json(texto_final)
            if not isinstance(dados, dict):
                dados = {"emocao": "neutro", "texto_resposta": str(dados)}

            if tentativa == 0:
                self._registrar_memoria(dados.get("texto_resposta", ""), "REGISTRO")

            return dados

        except Exception as e:
            erro_str = str(e).lower()
            if any(x in erro_str for x in ["429", "quota", "resource_exhausted"]):
                print(f"[QUOTA] {self.modelo_nome} esgotado")
                if tentativa == 0 and self._marcar_chave_esgotada():
                    try:
                        self.chat = self._carregar_modelo_seguro()
                        return self.processar_entrada(prompt, tentativa + 1)
                    except:
                        pass
                return {"emocao": "confuso", "texto_resposta": "AVISO: Todas chaves esgotadas"}

            if "finish_reason" in erro_str or "valid part" in erro_str:
                self.chat = self._carregar_modelo_seguro()
                return {"emocao": "irritado", "texto_resposta": "Histórico reiniciado."}

            traceback.print_exc()
            return {"emocao": "confuso", "texto_resposta": "Erro no processamento."}

    def gerar_texto_aleatorio(self, tema):
        try:
            # Chama o modelo diretamente
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=f'Você é REGISTRO (GLaDOS). Lembrete: "{tema}". Frase bem curta, não necessarimente sarcasticas sarcástica. SEM JSON.'
            )
            return response.text.strip()
        except:
            return f"Lembrete: {tema}"