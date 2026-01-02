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

        self.chaves_disponiveis = getattr(
            config, 'API_KEYS', []).copy() if hasattr(config, 'API_KEYS') else []
        self.chaves_esgotadas = []
        self.indice_chave_atual = 0

        self._log_chaves()
        self._configurar_api_key()
        self.chat, self.modelo = self._carregar_modelo_seguro()
        self.sistema = None

    def _log_chaves(self):
        """Debug inicial de chaves"""
        print(
            f"\n{'='*60}\nCHAVES: {len(self.chaves_disponiveis) or 'NENHUMA (única)'}")
        for i, key in enumerate(self.chaves_disponiveis, 1):
            print(f"  {i}. ...{key[-8:]}")
        print(f"{'='*60}\n")

    def _configurar_api_key(self, proxima=False):
        """Configura chave atual ou próxima"""
        if len(self.chaves_disponiveis) <= 1:
            genai.configure(api_key=config.API_KEY)
            print(f"[API] Única: ...{config.API_KEY[-4:]}")
            return

        if proxima:
            self.indice_chave_atual = (
                self.indice_chave_atual + 1) % len(self.chaves_disponiveis)

        key = self.chaves_disponiveis[self.indice_chave_atual]
        genai.configure(api_key=key)
        print(
            f"[API] [{self.indice_chave_atual + 1}/{len(self.chaves_disponiveis)}]: ...{key[-4:]}")

    def _marcar_chave_esgotada(self):
        """Move chave atual para esgotadas e troca"""
        if len(self.chaves_disponiveis) <= 1:
            self._aguardar_reset()
            return True

        chave = self.chaves_disponiveis.pop(self.indice_chave_atual)
        self.chaves_esgotadas.append(chave)
        print(
            f"[API] ...{chave[-4:]} esgotada ({len(self.chaves_esgotadas)}/{len(config.API_KEYS)})")

        if not self.chaves_disponiveis:
            print(f"\n{'='*60}\nAVISO: TODAS AS CHAVES ESGOTARAM\n{'='*60}")
            self._aguardar_reset()
            self.chaves_disponiveis = config.API_KEYS.copy()
            self.chaves_esgotadas.clear()

        self.indice_chave_atual = 0
        self._configurar_api_key()
        return True

    def _aguardar_reset(self):
        """Countdown de 60s"""
        print("\n[QUOTA] Aguardando reset (60s)...")
        for i in range(60, 0, -1):
            sys.stdout.write(f"\rReset em: {i//60:02d}:{i % 60:02d} ")
            sys.stdout.flush()
            time.sleep(1)
        print("\nQuota resetada. \n")

    def _registrar_memoria(self, texto, autor):
        """Salva no JSONL"""
        try:
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"data": str(
                    datetime.now()), "autor": autor, "texto": texto}, ensure_ascii=False) + "\n")
        except:
            pass

    def carregar_memoria(self):
        """Carrega últimas 20 mensagens"""
        hist = [
            {"role": "user", "parts": [config.PROMPT_PERSONALIDADE]},
            {"role": "model", "parts": [
                '{"emocao": "neutro", "texto_resposta": "Sistemas online."}']}
        ]
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                for linha in f.readlines()[-20:]:
                    d = json.loads(linha)
                    hist.append(
                        {"role": "model" if d["autor"] == "REGISTRO" else "user", "parts": [d["texto"]]})
        except:
            pass
        return hist

    def _carregar_modelo_seguro(self, ignorar=None):
        """Tenta conectar em modelo disponível"""
        ignorar = ignorar or []

        if len(ignorar) >= len(config.LISTA_MODELOS):
            if len(self.chaves_disponiveis) > 1:
                self._configurar_api_key(proxima=True)
                return self._carregar_modelo_seguro([])
            raise Exception("AVISO: Sem cota ")

        for nome in config.LISTA_MODELOS:
            if nome in ignorar:
                continue

            try:
                print(f"[CONEXAO] {nome}...", end=" ")
                model = genai.GenerativeModel(
                    nome,
                    tools=getattr(config, 'LISTA_FERRAMENTAS', []),
                    generation_config={"temperature": 1.0,
                                       "top_p": 0.95, "top_k": 40}
                )
                chat = model.start_chat(history=self.carregar_memoria())
                self.modelo_nome = nome
                print("OK")
                return chat, model
            except Exception as e:
                if any(x in str(e).lower() for x in ["429", "quota"]):
                    print("SEM COTA")
                    ignorar.append(nome)
                else:
                    print(f"ERRO: {e}")
                    time.sleep(1)

        return self._carregar_modelo_seguro(ignorar)

    def _verificar_rate_limit(self):
        """Controla 15 RPM"""
        agora = time.time()
        self.chamadas_ultimo_minuto = [
            t for t in self.chamadas_ultimo_minuto if agora - t < 60]

        if len(self.chamadas_ultimo_minuto) >= 12:
            espera = 61 - (agora - self.chamadas_ultimo_minuto[0])
            print(
                f"AVISO: Rate limit {len(self.chamadas_ultimo_minuto)}/15. Aguardando {espera:.1f}s...")
            time.sleep(espera)
            self.chamadas_ultimo_minuto.clear()

        self.chamadas_ultimo_minuto.append(agora)

    def _executar_ferramentas(self, res, tentativa):
        """Loop de function calling"""
        turnos = 0
        ultimo_retorno = None

        while res.parts and any(getattr(p, 'function_call', None) for p in res.parts) and turnos < 5:
            turnos += 1
            partes = []

            for part in res.parts:
                if fc := getattr(part, 'function_call', None):
                    print(f"[TOOL] {fc.name}({dict(fc.args)})")

                    if self.sistema and hasattr(self.sistema, fc.name):
                        try:
                            retorno = getattr(self.sistema, fc.name)(
                                **dict(fc.args))
                            ultimo_retorno = retorno
                        except Exception as e:
                            retorno = f"Erro: {e}"
                    else:
                        retorno = f"'{fc.name}' não existe"

                    print(f"[RESULT] {str(retorno)[:80]}")
                    partes.append(content.Part(function_response=content.FunctionResponse(
                        name=fc.name, response={'result': str(retorno)}
                    )))

            try:
                res = self.chat.send_message(partes)
            except Exception as e:
                if any(x in str(e).lower() for x in ["429", "quota"]):
                    print("[QUOTA] Sem cota pós-tool.  fallback.")
                    if tentativa == 0 and ultimo_retorno:
                        self._registrar_memoria(ultimo_retorno, "REGISTRO")
                    return {"emocao": "neutro", "texto_resposta": ultimo_retorno or "Tarefa executada."}, True
                raise

        return res, False

    def _parsear_json(self, texto):
        """Extrai e parseia JSON da resposta"""
        txt = texto.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            pass

        try:
            import re
            match = re.search(
                r'\{.*?"emocao".*?"texto_resposta".*?\}', txt, re.DOTALL)
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

                txt_corrigido = correcao.text.replace(
                    "```json", "").replace("```", "").strip()

                try:
                    return json.loads(txt_corrigido)
                except:
                    match = re.search(
                        r'\{.*?"emocao".*?"texto_resposta".*?\}', txt_corrigido, re.DOTALL)
                    if match:
                        return json.loads(match.group(0))
            except Exception as e:
                print(f"[JSON] Tentativa {tentativa+1}/2 falhou: {e}")
                continue

        print("[JSON] Falha total. Usando texto bruto como fallback.")
        return {
            "emocao": "confuso",
            "texto_resposta": texto[:500]  # Limita tamanho
        }

    def processar_entrada(self, prompt, tentativa=0):
        """Processa prompt com IA"""
        if tentativa >= 2:
            return {"emocao": "confuso", "texto_resposta": "AVISO: Todas cotas esgotadas. Aguardei reset."}

        if getattr(config, 'MODO_DEBUG', False):
            return {"emocao": "neutro", "texto_resposta": "Debug ativo"}

        self._verificar_rate_limit()

        if tentativa == 0:
            self._registrar_memoria(prompt, "Luis")

        self.contador_requisicoes += 1
        print(
            f"[REQ #{self.contador_requisicoes}] Tent. {tentativa+1}/2 | Chamadas: {len(self.chamadas_ultimo_minuto)}")

        try:
            res = self.chat.send_message(prompt)

            if res.candidates and (reason := res.candidates[0].finish_reason) != 1:
                msgs = {3: "Bloqueado por segurança",
                        2: "Muito longa. Reformule."}
                if reason in msgs:
                    return {"emocao": "confuso" if reason == 3 else "irritado", "texto_resposta": msgs[reason]}

            res, usou_fallback = self._executar_ferramentas(res, tentativa)
            if usou_fallback:
                return res

            if not res.text:
                raise ValueError("Resposta vazia")

            dados = self._parsear_json(res.text)
            if not isinstance(dados, dict):
                dados = {"emocao": "neutro", "texto_resposta": str(dados)}

            if tentativa == 0:
                self._registrar_memoria(
                    dados.get("texto_resposta", ""), "REGISTRO")

            return dados

        except Exception as e:
            if any(x in str(e).lower() for x in ["429", "quota", "resource_exhausted"]):
                print(f"[QUOTA] {self.modelo_nome} esgotado")

                if tentativa == 0 and self._marcar_chave_esgotada():
                    try:
                        self.chat, self.modelo = self._carregar_modelo_seguro()
                        return self.processar_entrada(prompt, tentativa + 1)
                    except Exception as e2:
                        print(f"[ERRO] Reconexão: {e2}")

                return {"emocao": "confuso", "texto_resposta": "AVISO: Todas chaves esgotadas"}

            traceback.print_exc()
            return {"emocao": "confuso", "texto_resposta": "Erro fatal. Veja logs."}

    def gerar_texto_aleatorio(self, tema):
        """Gera texto sarcástico para lembretes"""
        try:
            return self.modelo.generate_content(
                f'Você é REGISTRO (GLaDOS). Lembrete: "{tema}". Frase bem curta, não necessarimente sarcasticas sarcástica. SEM JSON.'
            ).text.strip()
        except:
            return f"Lembrete: {tema}"
