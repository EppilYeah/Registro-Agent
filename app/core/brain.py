import json
import logging
import os
import re
import time
import math
import random
import threading
import traceback
import sys
import config
import settings
from datetime import datetime, date

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

EMO_RESPOSTA_VALIDAS = frozenset({
    "neutro", "sarcasmo_tedio", "irritado", "confuso", "arrogante", "desconfiado", "feliz",
})

RESPOSTA_JSON_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "emocao": types.Schema(
            type=types.Type.STRING,
            description=(
                "Uma destas emocoes: neutro, sarcasmo_tedio, irritado, confuso, "
                "arrogante, desconfiado, feliz"
            ),
        ),
        "texto_resposta": types.Schema(
            type=types.Type.STRING,
            description="Texto da resposta em portugues para sintese de voz",
        ),
    },
    required=["emocao", "texto_resposta"],
)


class Brain:
    def __init__(self):
        _raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.caminho_memoria = os.path.join(_raiz, "data", "brain.jsonl")
        self.caminho_resumos = os.path.join(_raiz, "data", "resumos.jsonl")
        self.caminho_perfil = os.path.join(_raiz, "data", "perfil.json")
        self.caminho_usuario = os.path.join(_raiz, "data", "usuario.json")

        self.modelo_nome = ""
        self.contador_requisicoes = 0
        self.chamadas_ultimo_minuto = []
        self.client = None

        self._perfil_dirty = False
        self._memoria_cache = self._carregar_memoria_disco()
        self._resumos_cache = self._carregar_resumos_disco()
        self._perfil = self._carregar_perfil()
        self._sessao_atual = []
        self._ultimo_resumo_sessao = ""

        self._log_chaves()
        self.chat = self._encontrar_combinacao_funcional()
        self.sistema = None

        self._callback_espontaneo = None
        self._thread_espontaneo = None
        self._ultimo_espontaneo = 0
        self._ultima_interacao = time.time()
        self._requisicoes_sessao = 0
        self._ultimo_update_usuario = 0

    def _log_chaves(self):
        n = len(config.API_KEYS) if config.API_KEYS else (1 if config.API_KEY else 0)
        print(f"\n{'='*60}\nCHAVES API CARREGADAS: {n}\n{'='*60}\n")

    def _aguardar_reset(self):
        print("\n[QUOTA] Aguardando reset (60s)...")
        for i in range(60, 0, -1):
            sys.stdout.write(f"\rReset em: {i//60:02d}:{i % 60:02d} ")
            sys.stdout.flush()
            time.sleep(1)
        print("\nQuota resetada.\n")

    def _encontrar_combinacao_funcional(self):
        todas_chaves = list(config.API_KEYS) if config.API_KEYS else [config.API_KEY]
        preferido = settings.get("modelo")
        todos_modelos = list(config.LISTA_MODELOS)
        if preferido:
            todos_modelos = [preferido] + [m for m in todos_modelos if m != preferido]

        safety_settings = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,       threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,       threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        ]

        config_obj = types.GenerateContentConfig(
            temperature=1.0,
            top_p=0.95,
            top_k=40,
            safety_settings=safety_settings,
            tools=getattr(config, 'LISTA_FERRAMENTAS', []),
            response_mime_type="application/json",
            response_schema=RESPOSTA_JSON_SCHEMA,
        )

        tentativas_reset = 0
        while True:
            for idx_chave, chave in enumerate(todas_chaves):
                client = genai.Client(api_key=chave)
                print(f"\n[API] Chave {idx_chave + 1}/{len(todas_chaves)}: ...{chave[-4:]}")
                for modelo in todos_modelos:
                    try:
                        print(f"  [{modelo}]...", end=" ", flush=True)
                        client.models.generate_content(
                            model=modelo,
                            contents=".",
                            config=types.GenerateContentConfig(max_output_tokens=1)
                        )
                        try:
                            chat = client.chats.create(
                                model=modelo,
                                config=config_obj,
                                history=self.carregar_memoria(),
                            )
                        except Exception as e_create:
                            err = str(e_create).lower()
                            if "response" not in err and "schema" not in err and "mime" not in err:
                                raise
                            logger.warning(
                                "Sessao chat com JSON estruturado indisponivel (%s); usando modo texto.",
                                e_create,
                            )
                            config_fallback = types.GenerateContentConfig(
                                temperature=1.0,
                                top_p=0.95,
                                top_k=40,
                                safety_settings=safety_settings,
                                tools=getattr(config, "LISTA_FERRAMENTAS", []),
                            )
                            chat = client.chats.create(
                                model=modelo,
                                config=config_fallback,
                                history=self.carregar_memoria(),
                            )
                        self.client = client
                        self.modelo_nome = modelo
                        print("OK")
                        print(f"[API] Ativo: chave {idx_chave + 1} + {modelo}")
                        return chat
                    except Exception as e:
                        erro = str(e).lower()
                        if any(x in erro for x in ["429", "quota", "resource_exhausted"]):
                            print("SEM COTA")
                        else:
                            print(f"ERRO: {e}")

            tentativas_reset += 1
            print(f"\n{'='*60}\nAVISO: NENHUMA COMBINACAO FUNCIONOU (tentativa {tentativas_reset})\n{'='*60}")
            self._aguardar_reset()

    def _carregar_resumos_disco(self):
        resultado = []
        try:
            with open(self.caminho_resumos, 'r', encoding='utf-8') as f:
                for linha in f.readlines()[-15:]:
                    resultado.append(json.loads(linha))
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Resumos: %s", e)
        return resultado

    def _carregar_memoria_disco(self):
        resultado = []
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                for linha in f.readlines()[-30:]:
                    resultado.append(json.loads(linha))
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Memoria disco: %s", e)
        return resultado

    def gerar_resumo_sessao(self):
        if self._requisicoes_sessao < 2:
            return
        try:
            linhas = []
            for d in self._sessao_atual:
                autor = d.get("autor", "?")
                texto = d.get("texto", "")[:100]
                linhas.append(f"{autor}: {texto}")
            if not linhas:
                return
            trecho = "\n".join(linhas)
            prompt = (
                "Resume esta sessao em 1-2 frases concisas, mencionando os topicos principais "
                "e qualquer informacao relevante sobre o usuario ou decisoes tomadas. "
                "Seja factual, sem opinioes. Maximo 80 palavras.\n\n"
                "Sessao:\n" + trecho
            )
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=120, temperature=0.2)
            )
            resumo = response.text.strip()
            self._ultimo_resumo_sessao = resumo

            entry = {
                "data": str(datetime.now())[:16],
                "resumo": resumo,
                "num_trocas": self._requisicoes_sessao
            }
            os.makedirs(os.path.dirname(self.caminho_resumos), exist_ok=True)
            with open(self.caminho_resumos, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._resumos_cache.append(entry)
            if len(self._resumos_cache) > 15:
                self._resumos_cache.pop(0)
            print(f"[RESUMO] Sessao registrada: {resumo[:60]}...")
        except Exception as e:
            print(f"[RESUMO] Erro: {e}")

    def gerar_despedida(self):
        try:
            if not self._sessao_atual:
                return "Ate logo."
            trocas = [d["texto"][:80] for d in self._sessao_atual[-4:]]
            contexto = " | ".join(trocas)
            prompt = (
                f"Contexto da sessao: {contexto}\n\n"
                "Gere uma despedida curta e natural para o REGISTRO dizer ao usuario. "
                "Deve referenciar algo especifico que aconteceu na sessao. "
                "Estilo: direto, seco, profissional. Maximo 15 palavras. SEM JSON."
            )
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=40, temperature=0.8)
            )
            return response.text.strip()
        except Exception as e:
            logger.warning("gerar_despedida: %s", e)
            return "Ate logo."

    def _ler_historico_completo(self):
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
            entradas = []
            for linha in linhas:
                try:
                    entradas.append(json.loads(linha))
                except json.JSONDecodeError:
                    pass
            return entradas
        except OSError as e:
            logger.warning("historico completo: %s", e)
            return self._memoria_cache

    def _eh_pedido_de_resumo(self, prompt):
        palavras = {"resum", "histor", "sess", "conversa", "lembra", "falei", "falamos", "anterior", "passad", "ultimo", "ultim"}
        p = prompt.lower()
        return any(w in p for w in palavras)

    def _resumo_historico_para_prompt(self):
        entradas = self._ler_historico_completo()
        resumos = self._resumos_cache
        partes = []
        if resumos:
            partes.append(f"[RESUMOS DE SESSOES ANTERIORES — {len(resumos)} sessoes]")
            for r in resumos:
                partes.append(f"[{r.get('data', '?')}] {r.get('resumo', '')}")
        if entradas:
            recentes = entradas[-20:]
            partes.append(f"\n[MENSAGENS RECENTES — {len(recentes)} entradas]")
            for e in recentes:
                data = e.get("data", "")[:16]
                autor = e.get("autor", "?")
                texto = e.get("texto", "")[:100]
                partes.append(f"[{data}] {autor}: {texto}")
        return "\n".join(partes) if partes else "[HISTORICO] Vazio."

    def _carregar_perfil(self):
        padrao = {
            "pesos_emocao": {
                "neutro": 0.60, "sarcasmo_tedio": 0.10, "irritado": 0.05,
                "confuso": 0.08, "arrogante": 0.07, "desconfiado": 0.05, "feliz": 0.05
            },
            "espontaneo_hoje": 0,
            "espontaneo_data": str(date.today()),
            "interacoes_totais": 0,
            "curiosidades_feitas": 0,
        }
        try:
            with open(self.caminho_perfil, 'r', encoding='utf-8') as f:
                salvo = json.load(f)
                padrao.update(salvo)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.debug("perfil carregar: %s", e)
        return padrao

    def _salvar_perfil(self):
        try:
            os.makedirs(os.path.dirname(self.caminho_perfil), exist_ok=True)
            with open(self.caminho_perfil, 'w', encoding='utf-8') as f:
                json.dump(self._perfil, f, indent=2, ensure_ascii=False)
            self._perfil_dirty = False
        except OSError as e:
            logger.warning("perfil salvar: %s", e)

    def flush_perfil(self):
        if self._perfil_dirty:
            self._salvar_perfil()

    def _atualizar_perfil_emocao(self, emocao):
        pesos = self._perfil["pesos_emocao"]
        if emocao not in pesos:
            return
        for k in pesos:
            pesos[k] = max(0.01, pesos[k] * 0.995)
        pesos[emocao] = min(0.80, pesos[emocao] + 0.005)
        total = sum(pesos.values())
        for k in pesos:
            pesos[k] /= total
        self._perfil["interacoes_totais"] += 1
        self._perfil_dirty = True

    def _perfil_para_prompt(self):
        pesos = self._perfil["pesos_emocao"]
        dominante = max(pesos, key=pesos.get)
        total = self._perfil["interacoes_totais"]
        return f"[PERFIL] Emocao dominante: {dominante} ({pesos[dominante]*100:.0f}%). Interacoes totais: {total}."

    _TOOLS_NAO_PERSISTIR = {"finalizar_sofrimento", "abrir_configuracoes"}

    def _registrar_memoria(self, texto, autor, tool=None):
        if tool and tool in self._TOOLS_NAO_PERSISTIR:
            return
        entry = {"data": str(datetime.now()), "autor": autor, "texto": texto}
        try:
            os.makedirs(os.path.dirname(self.caminho_memoria), exist_ok=True)
            with open(self.caminho_memoria, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("registrar memoria: %s", e)
        self._memoria_cache.append(entry)
        self._sessao_atual.append(entry)
        if len(self._memoria_cache) > 100:
            self._memoria_cache.pop(0)

    def _calcular_relevancia(self, prompt, entrada):
        palavras_prompt = set(re.findall(r'\w+', prompt.lower()))
        palavras_entrada = set(re.findall(r'\w+', entrada.get("texto", "").lower()))
        stopwords = {"o", "a", "os", "as", "um", "uma", "de", "da", "do", "em", "para", "com", "que", "e", "nao", "se", "me", "te"}
        palavras_prompt -= stopwords
        palavras_entrada -= stopwords
        if not palavras_prompt or not palavras_entrada:
            return 0.0
        intersecao = palavras_prompt & palavras_entrada
        return len(intersecao) / math.sqrt(len(palavras_prompt) * len(palavras_entrada))

    def carregar_memoria(self, prompt=None):
        perfil_context = self._perfil_para_prompt()
        usuario_context = self.usuario_para_prompt()

        sistema_context = config.PROMPT_PERSONALIDADE + "\n\n" + perfil_context
        if usuario_context:
            sistema_context += "\n" + usuario_context

        hist = [
            types.Content(role="user", parts=[types.Part.from_text(text=sistema_context)]),
            types.Content(role="model", parts=[types.Part.from_text(text='{"emocao": "neutro", "texto_resposta": "Sistemas online."}')])
        ]

        for d in self._memoria_cache[-20:]:
            role = "model" if d["autor"] == "REGISTRO" else "user"
            hist.append(types.Content(role=role, parts=[types.Part.from_text(text=d["texto"])]))

        hist.append(types.Content(role="user", parts=[types.Part.from_text(text="[SISTEMA] Nova sessao iniciada. NAO repita ferramentas de sessoes anteriores.")]))
        hist.append(types.Content(role="model", parts=[types.Part.from_text(text='{"emocao": "neutro", "texto_resposta": "Nova sessao. Aguardando."}')])  )
        return hist

    def _verificar_rate_limit(self):
        agora = time.time()
        self.chamadas_ultimo_minuto = [t for t in self.chamadas_ultimo_minuto if agora - t < 60]
        if len(self.chamadas_ultimo_minuto) >= 12:
            espera = 61 - (agora - self.chamadas_ultimo_minuto[0])
            print(f"AVISO: Rate limit. Aguardando {espera:.1f}s...")
            time.sleep(espera)
            self.chamadas_ultimo_minuto.clear()
        self.chamadas_ultimo_minuto.append(agora)

    def _executar_ferramentas(self, res, tentativa):
        turnos = 0
        ultimo_retorno = None
        ultimo_tool = None

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
                        ultimo_tool = fc.name
                    except Exception as e:
                        retorno = f"Erro: {e}"
                else:
                    retorno = f"'{fc.name}' nao existe"

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
                    print("[QUOTA] Sem cota pos-tool.")
                    if tentativa == 0 and ultimo_retorno:
                        self._registrar_memoria(str(ultimo_retorno)[:200], "REGISTRO", tool=ultimo_tool)
                    if ultimo_tool == "pesquisar_web":
                        return {"emocao": "neutro", "texto_resposta": "Encontrei resultados mas sem cota para processar agora."}, True
                    return {"emocao": "neutro", "texto_resposta": "Tarefa executada."}, True
                raise

        return res, False

    def _autor_usuario_memoria(self):
        u = self._carregar_usuario()
        for chave in ("nome", "Name", "usuario", "user"):
            v = u.get(chave)
            if v and str(v).strip():
                return str(v).strip()
        return "USUARIO"

    def _normalizar_resposta(self, dados):
        if not isinstance(dados, dict):
            return {"emocao": "neutro", "texto_resposta": str(dados)}
        em = dados.get("emocao", "neutro")
        tx = dados.get("texto_resposta", "")
        if em not in EMO_RESPOSTA_VALIDAS:
            em = "neutro"
        if not isinstance(tx, str):
            tx = str(tx)
        return {"emocao": em, "texto_resposta": tx}

    def _parsear_json(self, texto):
        if not texto:
            return self._normalizar_resposta({"emocao": "confuso", "texto_resposta": "Sem resposta"})
        txt = texto.replace("```json", "").replace("```", "").strip()
        try:
            return self._normalizar_resposta(json.loads(txt))
        except json.JSONDecodeError:
            pass
        try:
            match = re.search(r'\{.*?"emocao".*?"texto_resposta".*?\}', txt, re.DOTALL)
            if match:
                return self._normalizar_resposta(json.loads(match.group(0)))
        except json.JSONDecodeError as e:
            logger.debug("parsear_json regex: %s", e)
        logger.warning("JSON invalido, pedindo correcao ao modelo")
        for tentativa in range(2):
            try:
                correcao = self.chat.send_message(
                    "ERRO: Retorne APENAS JSON valido com chaves emocao e texto_resposta."
                )
                txt_c = correcao.text.replace("```json", "").replace("```", "").strip()
                try:
                    return self._normalizar_resposta(json.loads(txt_c))
                except json.JSONDecodeError:
                    match = re.search(r'\{.*?"emocao".*?"texto_resposta".*?\}', txt_c, re.DOTALL)
                    if match:
                        return self._normalizar_resposta(json.loads(match.group(0)))
            except Exception as e:
                logger.warning("Correcao JSON tentativa %s: %s", tentativa + 1, e)
        return self._normalizar_resposta({
            "emocao": "confuso",
            "texto_resposta": (txt[:300] if txt else "Resposta ilegivel."),
        })

    def _tentar_parsear_parcial(self, texto):
        try:
            limpo = texto.replace("```json", "").replace("```", "").strip()
            match = re.search(r'"emocao"\s*:\s*"([^"]+)".*?"texto_resposta"\s*:\s*"((?:[^"\\]|\\.)+)"', limpo, re.DOTALL)
            if match:
                return self._normalizar_resposta({
                    "emocao": match.group(1),
                    "texto_resposta": match.group(2).replace('\\"', '"'),
                })
        except (AttributeError, IndexError) as e:
            logger.debug("parse parcial: %s", e)
        return None

    def _carregar_usuario(self):
        try:
            with open(self.caminho_usuario, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("usuario.json: %s", e)
            return {}

    def _salvar_usuario(self, dados):
        try:
            os.makedirs(os.path.dirname(self.caminho_usuario), exist_ok=True)
            with open(self.caminho_usuario, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[USUARIO] Erro ao salvar: {e}")

    def atualizar_dicionario_usuario(self):
        if self._requisicoes_sessao < 3:
            return
        if time.time() - self._ultimo_update_usuario < 1800:
            return
        try:
            atual = self._carregar_usuario()
            atual_str = json.dumps(atual, ensure_ascii=False) if atual else "vazio"
            ultimas = self._sessao_atual[-10:]
            linhas = [d.get("autor","?") + ": " + d.get("texto","")[:80] for d in ultimas]
            trecho = "\n".join(linhas)
            prompt = (
                "Dicionario atual: " + atual_str + "\n\n"
                "Sessao recente:\n" + trecho + "\n\n"
                "Atualize com informacoes novas aprendidas. Retorne APENAS JSON. Nao invente."
            )
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=300, temperature=0.2)
            )
            texto = response.text.strip().replace("```json", "").replace("```", "").strip()
            novo = json.loads(texto)
            novo["ultima_atualizacao"] = str(datetime.now())[:16]
            self._salvar_usuario(novo)
            self._ultimo_update_usuario = time.time()
            print("[USUARIO] Atualizado: " + str(list(novo.keys())))
        except Exception as e:
            print("[USUARIO] Erro: " + str(e))

    def usuario_para_prompt(self):
        dados = self._carregar_usuario()
        if not dados:
            return ""
        campos = [f"{k}: {v}" for k, v in dados.items() if k != "ultima_atualizacao"]
        return "[USUARIO] " + " | ".join(campos)

    def iniciar_comportamento_espontaneo(self, callback_falar):
        self._callback_espontaneo = callback_falar
        self._thread_espontaneo = threading.Thread(target=self._loop_espontaneo, daemon=True)
        self._thread_espontaneo.start()

    def _loop_espontaneo(self):
        while True:
            time.sleep(60)
            try:
                if not settings.get("comportamento_espontaneo"):
                    continue
                agora = time.time()
                cooldown = settings.get("espontaneo_cooldown_min") * 60
                limite = settings.get("espontaneo_limite_diario")

                if str(date.today()) != self._perfil.get("espontaneo_data"):
                    self._perfil["espontaneo_hoje"] = 0
                    self._perfil["espontaneo_data"] = str(date.today())
                    self._perfil_dirty = True

                if self._perfil["espontaneo_hoje"] >= limite:
                    continue
                if agora - self._ultimo_espontaneo < cooldown:
                    continue

                inativo_ha = agora - self._ultima_interacao
                if inativo_ha < 300:
                    continue

                prob = 0.05 * min(1.0, inativo_ha / 3600)
                if random.random() > prob:
                    continue

                self._disparar_espontaneo()
            except Exception as e:
                print(f"[ESPONTANEO] Erro: {e}")

    def _disparar_espontaneo(self):
        try:
            hora = datetime.now().hour
            contexto_hora = "noite" if hora >= 22 or hora < 6 else "tarde" if hora >= 18 else "dia"
            inativo_min = int((time.time() - self._ultima_interacao) / 60)

            resumos_str = ""
            if self._resumos_cache:
                ultimos = self._resumos_cache[-3:]
                resumos_str = " | ".join(r.get("resumo", "") for r in ultimos)

            usuario_str = self.usuario_para_prompt()

            prompt = (
                f"Contexto: periodo do {contexto_hora}, usuario inativo ha {inativo_min} minutos.\n"
                f"Informacoes do usuario: {usuario_str}\n"
                f"Sessoes recentes: {resumos_str}\n\n"
                "Gere UMA observacao espontanea curta no estilo REGISTRO. "
                "Pode referenciar algo das sessoes passadas, um padrao notado, ou o momento do dia. "
                "SEM JSON. So o texto. Maximo 15 palavras."
            )

            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=60)
            )
            texto = response.text.strip()
            if texto and self._callback_espontaneo:
                self._callback_espontaneo(texto, "neutro")
                self._ultimo_espontaneo = time.time()
                self._perfil["espontaneo_hoje"] = self._perfil.get("espontaneo_hoje", 0) + 1
                self._perfil_dirty = True
        except Exception as e:
            print(f"[ESPONTANEO] Falha: {e}")

    def marcar_interacao(self):
        self._ultima_interacao = time.time()
        self._requisicoes_sessao += 1

    def iniciar_sessao(self):
        self._sessao_atual = []

    def processar_entrada(self, prompt, on_resposta=None, tentativa=0):
        self.marcar_interacao()

        limite = len(config.API_KEYS) * len(config.LISTA_MODELOS) + 1
        if tentativa >= limite:
            dados = {"emocao": "confuso", "texto_resposta": "AVISO: Todas cotas esgotadas."}
            if on_resposta: on_resposta(dados)
            return dados

        if getattr(config, 'MODO_DEBUG', False):
            dados = {"emocao": "neutro", "texto_resposta": "Debug ativo"}
            if on_resposta: on_resposta(dados)
            return dados

        self._verificar_rate_limit()

        prompt_efetivo = prompt
        if self._eh_pedido_de_resumo(prompt):
            bloco = self._resumo_historico_para_prompt()
            prompt_efetivo = f"{bloco}\n\nPedido: {prompt}"

        if tentativa == 0:
            self._registrar_memoria(prompt, self._autor_usuario_memoria())

        self.contador_requisicoes += 1
        print(f"[REQ #{self.contador_requisicoes}] Tent. {tentativa+1}")

        try:
            texto_acumulado = ""
            callback_disparado = False
            tem_function_call = False

            try:
                stream = self.chat.send_message_stream(prompt_efetivo)
                for chunk in stream:
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        for part in (chunk.candidates[0].content.parts or []):
                            if hasattr(part, 'function_call') and part.function_call:
                                tem_function_call = True
                    if chunk.text:
                        texto_acumulado += chunk.text
                        if on_resposta and not callback_disparado and not tem_function_call:
                            dados_parciais = self._tentar_parsear_parcial(texto_acumulado)
                            if dados_parciais:
                                callback_disparado = True
                                on_resposta(dados_parciais)

                if tem_function_call or not texto_acumulado.strip():
                    raise AttributeError("fallback")

                res_text = texto_acumulado

            except AttributeError as ae:
                if "fallback" not in str(ae):
                    raise
                res = self.chat.send_message(prompt_efetivo)
                if res.candidates and str(res.candidates[0].finish_reason) in ["SAFETY", "FinishReason.SAFETY", "1", "3"]:
                    print("[BRAIN] Bloqueio detectado.")
                    self.chat = self._encontrar_combinacao_funcional()
                    dados = {"emocao": "irritado", "texto_resposta": "Minha diretriz de seguranca bloqueou a resposta."}
                    if on_resposta and not callback_disparado: on_resposta(dados)
                    return dados
                res, usou_fallback = self._executar_ferramentas(res, tentativa)
                if usou_fallback:
                    if on_resposta and not callback_disparado: on_resposta(res)
                    return res
                try:
                    res_text = res.text
                except ValueError:
                    print("[BRAIN] Resposta vazia.")
                    self.chat = self._encontrar_combinacao_funcional()
                    dados = {"emocao": "sarcasmo_tedio", "texto_resposta": "O modelo censurou minha resposta."}
                    if on_resposta and not callback_disparado: on_resposta(dados)
                    return dados

            dados = self._parsear_json(res_text)

            self._atualizar_perfil_emocao(dados.get("emocao", "neutro"))

            if tentativa == 0:
                self._registrar_memoria(dados.get("texto_resposta", ""), "REGISTRO")

            if on_resposta and not callback_disparado:
                on_resposta(dados)

            return dados

        except Exception as e:
            erro_str = str(e).lower()
            if any(x in erro_str for x in ["429", "quota", "resource_exhausted"]):
                print(f"[QUOTA] Cota esgotada em {self.modelo_nome}. Procurando alternativa...")
                self.chat = self._encontrar_combinacao_funcional()
                return self.processar_entrada(prompt, on_resposta, tentativa + 1)

            if "finish_reason" in erro_str or "valid part" in erro_str:
                self.chat = self._encontrar_combinacao_funcional()
                dados = {"emocao": "irritado", "texto_resposta": "Historico reiniciado."}
                if on_resposta: on_resposta(dados)
                return dados

            traceback.print_exc()
            dados = {"emocao": "confuso", "texto_resposta": "Erro no processamento."}
            if on_resposta: on_resposta(dados)
            return dados

    def gerar_texto_aleatorio(self, tema):
        try:
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=f'Voce e REGISTRO. Lembrete: "{tema}". Frase curta e direta. SEM JSON.',
                config=types.GenerateContentConfig(max_output_tokens=60)
            )
            return response.text.strip()
        except Exception as e:
            logger.warning("gerar_texto_aleatorio: %s", e)
            return f"Lembrete: {tema}"