import json
import logging
import os
import time
import random
import threading
import traceback
import config
import settings
from datetime import datetime, date
<<<<<<< HEAD
from app.core.errors import classificar, para_rosto, do_catalogo
from app.core.palace import get_palace

=======
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
from google import genai
from google.genai import types
from app.core.palace import palace_compartilhado
from app.core.quota import QuotaError, eh_erro_quota, esperar_retry_after, extrair_retry_after
from app.core.roteador import (
    chave_gemini_unica,
    groq_modelo,
    groq_ok,
    ollama_host,
    ollama_modelo,
    ordem_provedores,
)
from app.core.resposta import (
    WINGS_VALIDAS,
    ROOMS_VALIDAS,
    classificar_memoria_heuristica,
    deve_persistir_memoria,
    eh_perfil_resposta_llm,
    mesclar_perfil_usuario,
    parsear_objeto_json,
    parsear_resposta_json,
    sanitizar_wing_room,
)

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMADB_TELEMETRY"] = "False"

logger = logging.getLogger(__name__)

_MAX_TURNOS_HISTORICO = 12
_MAX_CACHE_MEMORIA = 24


def _eh_falha_de_rede(erro) -> bool:
    texto = str(erro or "").lower()
    return any(x in texto for x in (
        "connection", "refused", "timed out", "timeout", "unreachable",
        "indisponivel", "ausente", "nameresolution", "failed to establish",
        "http 404", "http 502", "http 503", "http 504",
    ))


class Brain:
    def __init__(self, conectar=True, palace=None):
        _raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.caminho_perfil = os.path.join(_raiz, "data", "perfil.json")
        self.caminho_usuario = os.path.join(_raiz, "data", "usuario.json")
        self.caminho_memoria_recente = os.path.join(_raiz, "data", "memoria_recente.json")
        self.palace = palace if palace is not None else palace_compartilhado()
        self.modelo_nome = ""
        self.contador_requisicoes = 0
        self.chamadas_ultimo_minuto = []
        self.client = None
        self._perfil_dirty = False
        self._memoria_cache = self._carregar_memoria_recente()
        self._perfil = self._carregar_perfil()
        self._sessao_atual = []
<<<<<<< HEAD
        self._ultimo_resumo_sessao = ""
        self.palace = get_palace()

        self._log_chaves()
        self.chat = self._encontrar_combinacao_funcional()
        self.sistema = None
        self.supervisor = None

=======
        self._sistema = None
        self._log_chaves()
        self.chat = None
        if conectar:
            self._preparar_provedores()
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        self._callback_espontaneo = None
        self._thread_espontaneo = None
        self._ultimo_espontaneo = 0
        self._ultima_interacao = time.time()
        self._requisicoes_sessao = 0
        self._ultimo_update_usuario = 0

    @property
    def sistema(self):
        return self._sistema

    @sistema.setter
    def sistema(self, valor):
        self._sistema = valor
        if valor:
            print("Conectando ...")
            self._preparar_provedores()

    def _log_chaves(self):
        gemini = chave_gemini_unica()
        n_gemini = 1 if gemini else 0
        extras = max(0, len(config.API_KEYS) - 1) if config.API_KEYS else 0
        print(f"\n{'='*60}")
        print(f"GROQ: {'sim' if groq_ok() else 'nao'} | GEMINI: {n_gemini} chave(s) efetiva(s) | OLLAMA CPU: {ollama_modelo()}")
        if extras:
            print("AVISO: chaves extras no mesmo projeto Gemini nao aumentam cota.")
        print(f"{'='*60}\n")

    def _chaves_disponiveis(self):
        k = chave_gemini_unica()
        return [k] if k else []

    def _ordem_efetiva(self):
        tem_gemini = bool(chave_gemini_unica()) or bool(self.chat) or bool(self.client)
        return ordem_provedores(tem_groq=groq_ok(), tem_gemini=tem_gemini)

    def _preparar_provedores(self):
        ordem = self._ordem_efetiva()
        print("[LLM] Roteador: " + " -> ".join(ordem) + " (8B so na CPU)")
        if groq_ok():
            print(f"[LLM] Groq diario: {groq_modelo()}")
        if chave_gemini_unica():
            print("[LLM] Gemini sob demanda (cota por projeto; sem ping de cota na subida).")
        print(f"[LLM] Ollama fallback CPU: {ollama_modelo()} @ {ollama_host()} (num_gpu=0)")

    def _tools_gemini(self):
        if self._sistema and getattr(self._sistema, "skills", None):
            return list(self._sistema.skills.values())
        return None

    def _config_geracao(self, *, max_output_tokens=None, temperature=0.7, tools=True, json_final=False):
        kwargs = {
            "temperature": temperature,
            "top_p": 0.9,
            "top_k": 40,
            "safety_settings": [
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            ],
            "system_instruction": self._instrucao_sistema(),
        }
        if max_output_tokens:
            kwargs["max_output_tokens"] = max_output_tokens
        tools_ativos = self._tools_gemini() if tools else None
        if tools_ativos:
            kwargs["tools"] = tools_ativos
            try:
                kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=8
                )
            except Exception:
                pass
        elif json_final:
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs)

    def _conectar_gemini(self):
        chave = chave_gemini_unica()
        if not chave:
            print("[API] Nenhuma chave Gemini (GEMINI_API_KEY).")
            return None
        preferido = settings.get("modelo")
        todos_modelos = list(config.LISTA_MODELOS)
        if preferido:
            todos_modelos = [preferido] + [m for m in todos_modelos if m != preferido]
        config_obj = self._config_geracao()
        client = genai.Client(api_key=chave)
        print("[API] Gemini: uma chave (cota por projeto, nao por rotacao). Sem ping de cota.")
        for modelo in todos_modelos:
            try:
                print(f"  [{modelo}]...", end=" ", flush=True)
                chat = client.chats.create(
                    model=modelo,
                    config=config_obj,
                    history=self.carregar_memoria(),
                )
                self.client = client
                self.modelo_nome = modelo
                self.chat = chat
                print("OK")
                return chat
            except Exception as e:
                if eh_erro_quota(e):
                    print("SEM COTA")
                    print("[API] Gemini 429 — Groq/Ollama cobrem o dia. Sem espera de 60s.")
                    return None
                print(f"ERRO: {e}")
        return None

<<<<<<< HEAD
    def _novo_client(self, chave, timeout_ms):
        try:
            return genai.Client(api_key=chave, http_options={"timeout": timeout_ms})
        except Exception:
            try:
                return genai.Client(
                    api_key=chave,
                    http_options=types.HttpOptions(timeout=timeout_ms),
                )
            except Exception:
                return genai.Client(api_key=chave)

    def _encontrar_combinacao_funcional(self, excluir=None):
        todas_chaves = list(config.API_KEYS) if config.API_KEYS else [config.API_KEY]
        todos_modelos = list(config.LISTA_MODELOS)

        safety_settings = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,       threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,       threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        ]

        config_obj = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            max_output_tokens=320,
            safety_settings=safety_settings,
            tools=getattr(config, 'LISTA_FERRAMENTAS', [])
        )

        tentativas_reset = 0
        pulados = {m for m in (excluir or []) if m}
        while True:
            for idx_chave, chave in enumerate(todas_chaves):
                ping = self._novo_client(chave, 8000)
                print(f"\n[API] Chave {idx_chave + 1}/{len(todas_chaves)}: ...{chave[-4:]}")
                for modelo in todos_modelos:
                    if modelo in pulados:
                        print(f"  [{modelo}]... PULA")
                        continue
                    try:
                        print(f"  [{modelo}]...", end=" ", flush=True)
                        ping.models.generate_content(
                            model=modelo,
                            contents=".",
                            config=types.GenerateContentConfig(max_output_tokens=1)
                        )
                        client = self._novo_client(chave, 45000)
                        chat = client.chats.create(
                            model=modelo,
                            config=config_obj,
                            history=self.carregar_memoria()
                        )
                        self.client = client
                        self.modelo_nome = modelo
                        print("OK")
                        print(f"[API] Ativo: chave {idx_chave + 1} + {modelo}")
                        return chat
                    except Exception as e:
                        erro = str(e).lower()
                        if any(x in erro for x in ("404", "not_found", "no longer available")):
                            print("FORA")
                        elif any(x in erro for x in (
                            "timeout", "timed out", "deadline", "504", "503", "unavailable",
                        )):
                            print("TIMEOUT")
                        elif any(x in erro for x in ("429", "quota", "resource_exhausted")):
                            print("SEM COTA")
                        else:
                            print(f"ERRO: {str(e)[:140]}")

            if pulados:
                print("[API] Sem alternativa. Tentando modelos pulados.")
                pulados = set()
                continue

            tentativas_reset += 1
            print(f"\n{'='*60}\nAVISO: NENHUMA COMBINACAO FUNCIONOU (tentativa {tentativas_reset})\n{'='*60}")
            self._aguardar_reset()

    def _carregar_resumos_disco(self):
        resultado = []
        try:
            with open(self.caminho_resumos, 'r', encoding='utf-8') as f:
                for linha in f.readlines()[-15:]:
                    resultado.append(json.loads(linha))
        except:
            pass
        return resultado

    def _carregar_memoria_disco(self):
        resultado = []
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                for linha in f.readlines()[-30:]:
                    resultado.append(json.loads(linha))
        except:
            pass
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
            try:
                self.palace.guardar(resumo, "REGISTRO", wing="conversa", room="resumos", drawer="sessoes")
            except Exception:
                pass
        except Exception as e:
            print(f"[RESUMO] Erro: {e}")
=======
    def _encontrar_combinacao_funcional(self):
        return self._conectar_gemini()
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

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
            texto = self._completar_texto(prompt, max_tokens=40)
            return texto or "Ate logo."
        except Exception as e:
            logger.warning("gerar_despedida: %s", e)
            return "Ate logo."

<<<<<<< HEAD
    def _ler_historico_completo(self):
        try:
            with open(self.caminho_memoria, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
            entradas = []
            for linha in linhas:
                try:
                    entradas.append(json.loads(linha))
                except:
                    pass
            return entradas
        except:
            return self._memoria_cache

    def _eh_pedido_de_resumo(self, prompt):
        p = prompt.lower()
        frases = (
            "resumo", "resumir", "historico", "histórico",
            "sessao anterior", "sessão anterior",
            "o que falamos", "o que a gente falou",
            "conversa anterior", "ultima sessao", "última sessão",
            "o que eu falei",
        )
        return any(f in p for f in frases)

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

=======
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
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
        except Exception:
            pass
        return padrao

    def _salvar_perfil(self):
        try:
            os.makedirs(os.path.dirname(self.caminho_perfil), exist_ok=True)
            with open(self.caminho_perfil, 'w', encoding='utf-8') as f:
                json.dump(self._perfil, f, indent=2, ensure_ascii=False)
            self._perfil_dirty = False
        except Exception:
            pass

    def flush_perfil(self):
        if self._perfil_dirty:
            self._salvar_perfil()
        self._salvar_memoria_recente()

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

    def _instrucao_sistema(self):
        partes = [
            config.PROMPT_PERSONALIDADE,
            f"DATA_HOJE: {date.today().isoformat()}",
            self._perfil_para_prompt(),
        ]
        usuario = self.usuario_para_prompt()
        if usuario:
            partes.append(usuario)
        return "\n\n".join(partes)

    _TOOLS_NAO_PERSISTIR = {"finalizar_sofrimento", "abrir_configuracoes"}

    def _carregar_memoria_recente(self):
        try:
            with open(self.caminho_memoria_recente, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            if isinstance(dados, list):
                return dados[-_MAX_CACHE_MEMORIA:]
        except Exception:
            pass
        return []

    def _salvar_memoria_recente(self):
        try:
            os.makedirs(os.path.dirname(self.caminho_memoria_recente), exist_ok=True)
            with open(self.caminho_memoria_recente, 'w', encoding='utf-8') as f:
                json.dump(self._memoria_cache[-_MAX_CACHE_MEMORIA:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.debug("salvar memoria recente: %s", e)

    def _registrar_memoria(self, texto, autor, tool=None):
        if tool and tool in self._TOOLS_NAO_PERSISTIR:
            return
        entry = {"data": str(datetime.now()), "autor": autor, "texto": texto}
        self._memoria_cache.append(entry)
        self._sessao_atual.append(entry)
        if len(self._memoria_cache) > _MAX_CACHE_MEMORIA:
            self._memoria_cache.pop(0)
<<<<<<< HEAD
        def _guardar_bg():
            try:
                self.palace.guardar(texto, autor)
            except Exception as e:
                print("[PALACE] %s" % e, flush=True)
        threading.Thread(target=_guardar_bg, daemon=True).start()
=======
        if deve_persistir_memoria(texto, autor):
            threading.Thread(target=self._classificar_e_guardar_bg, args=(texto, autor), daemon=True).start()
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

    def _classificar_e_guardar_bg(self, texto, autor):
        wing_calc, room_calc = classificar_memoria_heuristica(texto, autor)
        precisa_llm = (
            autor == self._autor_usuario_memoria()
            and self.client
            and self.modelo_nome
            and wing_calc == "conversa"
            and len((texto or "").strip()) >= 40
        )
        if precisa_llm:
            try:
                prompt_class = (
                    "Classifique a entrada do usuario para o banco vetorial.\n"
                    f"Entrada: {texto[:400]!r}\n"
                    f"wing permitido: {', '.join(sorted(WINGS_VALIDAS))}\n"
                    f"room permitido: {', '.join(sorted(ROOMS_VALIDAS))}\n"
                    'Retorne SOMENTE JSON {"wing":"...","room":"..."}.'
                )
                res = self.client.models.generate_content(
                    model=self.modelo_nome,
                    contents=prompt_class,
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=60)
                )
                dados = parsear_objeto_json(getattr(res, "text", "") or "")
                wing_calc, room_calc = sanitizar_wing_room(
                    dados.get("wing", wing_calc),
                    dados.get("room", room_calc),
                )
            except Exception:
                pass
        self.palace.guardar(texto, autor, wing=wing_calc, room=room_calc)

    def carregar_memoria(self, prompt=None):
<<<<<<< HEAD
        perfil_context = self._perfil_para_prompt()
        usuario_context = self.usuario_para_prompt()

        sistema_context = config.PROMPT_PERSONALIDADE + "\n\n" + perfil_context
        if usuario_context:
            sistema_context += "\n" + usuario_context
        try:
            wake = self.palace.wake_up()
            if wake:
                sistema_context += "\n\n" + wake[:900]
        except Exception:
            pass

        hist = [
            types.Content(role="user", parts=[types.Part.from_text(text=sistema_context)]),
            types.Content(role="model", parts=[types.Part.from_text(text='{"emocao": "neutro", "texto_resposta": "Sistemas online."}')])
        ]

        for d in self._memoria_cache[-20:]:
            role = "model" if d["autor"] == "REGISTRO" else "user"
            hist.append(types.Content(role=role, parts=[types.Part.from_text(text=d["texto"])]))

        hist.append(types.Content(role="user", parts=[types.Part.from_text(text="[SISTEMA] Nova sessao iniciada. NAO repita ferramentas de sessoes anteriores.")]))
        hist.append(types.Content(role="model", parts=[types.Part.from_text(text='{"emocao": "neutro", "texto_resposta": "Nova sessao. Aguardando."}')])  )
=======
        """Historico real da conversa. A personalidade vai em system_instruction."""
        hist = []
        for d in self._memoria_cache[-_MAX_TURNOS_HISTORICO:]:
            texto = (d.get("texto") or "").strip()
            if not texto:
                continue
            if d.get("autor") == "REGISTRO":
                payload = json.dumps(
                    {"emocao": "neutro", "texto_resposta": texto},
                    ensure_ascii=False,
                )
                hist.append(types.Content(role="model", parts=[types.Part.from_text(text=payload)]))
            else:
                hist.append(types.Content(role="user", parts=[types.Part.from_text(text=texto)]))
        if hist and hist[0].role != "user":
            hist.insert(0, types.Content(role="user", parts=[types.Part.from_text(text="(inicio de sessao)")]))
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        return hist

    def _verificar_rate_limit(self):
        agora = time.time()
        self.chamadas_ultimo_minuto = [t for t in self.chamadas_ultimo_minuto if agora - t < 60]
<<<<<<< HEAD
        if len(self.chamadas_ultimo_minuto) >= 14:
            print("[API] Rate alto neste minuto. Seguindo sem espera.")
        self.chamadas_ultimo_minuto.append(agora)

    def _contexto_palacio(self, prompt):
        p = (prompt or "").strip()
        if len(p) < 28:
            return ""
        baixo = p.lower()
        if not any(x in baixo for x in (
            "lembra", "esqueci", "anota", "qual era", "o que eu", "meu nome",
            "disse", "combinamos", "guarda",
        )):
            return ""
        box = [""]
        def _buscar():
            try:
                box[0] = self.palace.recuperar_texto(p) or ""
            except Exception as e:
                print("[PALACE] Recuperacao: %s" % e, flush=True)
        t = threading.Thread(target=_buscar, daemon=True)
        t.start()
        t.join(0.4)
        if t.is_alive():
            print("[LAT] palace skip >0.4s")
        return box[0]

    def _executar_ferramentas(self, res, tentativa):
        turnos = 0
        ultimo_retorno = None
        ultimo_tool = None

        while True:
            function_calls = []
            if res and res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                function_calls = [p.function_call for p in res.candidates[0].content.parts if p.function_call]

            if not function_calls or turnos >= 5:
                break

            turnos += 1
            partes_resposta = []

            for fc in function_calls:
                try:
                    args = dict(fc.args) if fc.args else {}
                except Exception:
                    args = {}
                print(f"[TOOL] {fc.name}({args})")
                if self.sistema:
                    retorno = self.sistema.executar(fc.name, **args)
                else:
                    retorno = f"'{fc.name}' não existe"
                ultimo_retorno = retorno
                ultimo_tool = fc.name

                print(f"[RESULT] {str(retorno)[:80]}")
                partes_resposta.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={'result': str(retorno)}
                    )
                )

            try:
                t_tool = time.time()
                res = self.chat.send_message(partes_resposta)
                print(f"[LAT] gemini_tool={time.time() - t_tool:.2f}s")
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

    def _parsear_json(self, texto):
        if not texto: return {"emocao": "confuso", "texto_resposta": "Sem resposta"}
        txt = texto.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            pass
        try:
            match = re.search(r'\{.*?"emocao".*?"texto_resposta".*?\}', txt, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        print("[JSON] Erro. Pedindo correcao...")
        try:
            correcao = self.chat.send_message(
                "ERRO: Retorne APENAS:\n"
                '{"emocao": "escolha_uma", "texto_resposta": "texto"}'
            )
            txt_c = correcao.text.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(txt_c)
            except:
                match = re.search(r'\{.*?"emocao".*?"texto_resposta".*?\}', txt_c, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
        except Exception as e:
            print(f"[JSON] Correcao falhou: {e}")
        return para_rosto(do_catalogo("json_rosto"))

    def _tentar_parsear_parcial(self, texto):
        try:
            limpo = texto.replace("```json", "").replace("```", "").strip()
            match = re.search(r'"emocao"\s*:\s*"([^"]+)".*?"texto_resposta"\s*:\s*"((?:[^"\\]|\\.)+)"', limpo, re.DOTALL)
            if match:
                return {"emocao": match.group(1), "texto_resposta": match.group(2).replace('\\"', '"')}
        except:
            pass
        return None
=======
        if len(self.chamadas_ultimo_minuto) >= 12:
            time.sleep(2)
        self.chamadas_ultimo_minuto.append(agora)

    def _autor_usuario_memoria(self):
        u = self._carregar_usuario()
        for chave in ("nome", "Name", "usuario", "user"):
            v = u.get(chave)
            if v and str(v).strip():
                return str(v).strip()
        return "USUARIO"

    def _normalizar_resposta(self, dados):
        return parsear_resposta_json(json.dumps(dados, ensure_ascii=False) if isinstance(dados, dict) else str(dados))

    def _parsear_json(self, texto):
        return parsear_resposta_json(texto)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

    def _carregar_usuario(self):
        try:
            with open(self.caminho_usuario, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
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
        try:
            atual = self._carregar_usuario()
            ultimas = self._sessao_atual[-10:]
            trecho = "\n".join([d.get("autor", "?") + ": " + d.get("texto", "")[:80] for d in ultimas])
            prompt = (
                "Extraia fatos ESTAVEIS sobre o usuario (nome, cidade, profissao, projetos, preferencias). "
                "Retorne SOMENTE um objeto JSON plano chave/valor. "
                "Nao use as chaves emocao nem texto_resposta. "
                "Preserve chaves atuais se a conversa nao as contradisser.\n"
                f"Perfil atual: {json.dumps(atual, ensure_ascii=False)}\n"
                f"Conversa:\n{trecho}"
            )
            bruto = self._completar_texto(prompt, max_tokens=300)
            novo = parsear_objeto_json(bruto or "")
            if not novo or eh_perfil_resposta_llm(novo):
                return
            atual = mesclar_perfil_usuario(atual, novo)
            atual["ultima_atualizacao"] = str(datetime.now())[:16]
            self._salvar_usuario(atual)
        except Exception:
            pass

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
                if str(date.today()) != self._perfil.get("espontaneo_data"):
                    self._perfil["espontaneo_hoje"] = 0
                    self._perfil["espontaneo_data"] = str(date.today())
                    self._perfil_dirty = True
                if self._perfil["espontaneo_hoje"] >= settings.get("espontaneo_limite_diario"):
                    continue
                if agora - self._ultimo_espontaneo < settings.get("espontaneo_cooldown_min") * 60:
                    continue
                if agora - self._ultima_interacao < 300:
                    continue
                if random.random() > 0.05:
                    continue
                self._disparar_espontaneo()
            except Exception:
                pass

    def _disparar_espontaneo(self):
        try:
            texto = self._completar_texto(
                "Gere uma observacao curta e espontanea do REGISTRO. Estilo seco. Sem JSON."
            )
            if texto and self._callback_espontaneo:
                self._callback_espontaneo(texto, "neutro")
                self._ultimo_espontaneo = time.time()
                self._perfil["espontaneo_hoje"] += 1
                self._perfil_dirty = True
        except Exception:
            pass

    def marcar_interacao(self):
        self._ultima_interacao = time.time()
        self._requisicoes_sessao += 1

    def iniciar_sessao(self):
        self._sessao_atual = []

    def _montar_prompt_turno(self, prompt):
        blocos = []
        memorias = self.palace.recuperar(prompt, limit=5)
        if memorias:
            blocos.append("[MEMORIA]\n" + "\n".join(f"- {m}" for m in memorias))
        sessao = [d for d in self._sessao_atual[-6:] if d.get("texto")]
        if sessao:
            linhas = [f"{d.get('autor', '?')}: {d.get('texto', '')[:120]}" for d in sessao]
            blocos.append("[SESSAO]\n" + "\n".join(linhas))
        blocos.append(f"Usuario: {prompt}")
        blocos.append(
            "Se precisar de ferramenta, chame-a. "
            "A resposta final visivel deve ser JSON {\"emocao\",\"texto_resposta\"}. "
            "texto_resposta sera falado em voz alta: curto, PT-BR, sem markdown."
        )
        return "\n\n".join(blocos)

    def _extrair_texto(self, res):
        try:
            texto = getattr(res, "text", None)
            if isinstance(texto, str) and texto.strip():
                return texto
        except Exception:
            pass
        try:
            for cand in getattr(res, "candidates", None) or []:
                content = getattr(cand, "content", None)
                partes = []
                for part in getattr(content, "parts", None) or []:
                    tx = getattr(part, "text", None)
                    if tx:
                        partes.append(tx)
                if partes:
                    return "\n".join(partes)
        except Exception:
            pass
        return ""

    def _pedir_json_final(self):
        try:
            return self.chat.send_message(
                "As ferramentas ja rodaram (ou nao eram necessarias). "
                "Responda AGORA somente o JSON {\"emocao\": \"...\", \"texto_resposta\": \"...\"}. "
                "texto_resposta e o que sera falado: 1 a 2 frases, PT-BR, sem markdown, sem emojis."
            )
        except Exception as e:
            logger.warning("pedir json final: %s", e)
            return None

    def _processar_gemini(self, prompt_efetivo):
        if not self.chat:
            self.chat = self._encontrar_combinacao_funcional()
        if not self.chat:
            raise RuntimeError("Gemini indisponivel")
        try:
            res = self.chat.send_message(prompt_efetivo)
            if res.candidates and str(res.candidates[0].finish_reason) in ["SAFETY", "FinishReason.SAFETY", "1", "3"]:
                dados = {"emocao": "irritado", "texto_resposta": "Resposta bloqueada por seguranca."}
                return dados
            texto = self._extrair_texto(res)
            if not texto:
                follow = self._pedir_json_final()
                texto = self._extrair_texto(follow) if follow is not None else ""
            if not texto:
                raise ValueError("Resposta vazia do AFC.")
            dados = self._parsear_json(texto)
            if not dados.get("texto_resposta"):
                follow = self._pedir_json_final()
                extra = self._extrair_texto(follow) if follow is not None else ""
                if extra:
                    dados = self._parsear_json(extra)
            return dados
        except QuotaError:
            raise
        except Exception as e:
            if eh_erro_quota(e):
                raise QuotaError(str(e), retry_after=extrair_retry_after(e), provedor="gemini") from e
            raise

    def _processar_groq(self, prompt_efetivo):
        from app.core.chat_compat import completar_com_tools, tools_para_openai
        if not groq_ok():
            raise RuntimeError("GROQ_API_KEY ausente")
        skills = self._sistema.skills if self._sistema else {}
        return completar_com_tools(
            provedor="groq",
            system=self._instrucao_sistema(),
            user=prompt_efetivo,
            skills=skills,
            tools_openai=tools_para_openai(config.LISTA_FERRAMENTAS) if skills else [],
            modelo=groq_modelo(),
            api_key=config.GROQ_API_KEY,
        )

    def _processar_ollama(self, prompt_efetivo):
        from app.core.chat_compat import completar_com_tools, tools_para_openai
        skills = self._sistema.skills if self._sistema else {}
        return completar_com_tools(
            provedor="ollama",
            system=self._instrucao_sistema(),
            user=prompt_efetivo,
            skills=skills,
            tools_openai=tools_para_openai(config.LISTA_FERRAMENTAS) if skills else [],
            modelo=ollama_modelo(),
            host=ollama_host(),
        )

    def _completar_texto(self, prompt, max_tokens=80):
        from app.core.chat_compat import groq_chat, ollama_chat
        for provedor in self._ordem_efetiva():
            try:
                if provedor == "groq" and groq_ok():
                    texto, _ = groq_chat(
                        [{"role": "user", "content": prompt}],
                        modelo=groq_modelo(),
                        api_key=config.GROQ_API_KEY,
                    )
                    return (texto or "").strip()
                if provedor == "gemini":
                    if not (self.client and self.modelo_nome):
                        self._conectar_gemini()
                    if self.client and self.modelo_nome:
                        response = self.client.models.generate_content(
                            model=self.modelo_nome,
                            contents=prompt,
                            config=types.GenerateContentConfig(max_output_tokens=max_tokens, temperature=0.8),
                        )
                        return (getattr(response, "text", None) or "").strip()
                if provedor == "ollama":
                    texto, _ = ollama_chat(
                        [{"role": "user", "content": prompt}],
                        host=ollama_host(),
                        modelo=ollama_modelo(),
                    )
                    return (texto or "").strip()
            except QuotaError as e:
                esperar_retry_after(e, provedor=provedor)
            except Exception as e:
                if eh_erro_quota(e):
                    esperar_retry_after(e, provedor=provedor)
                    continue
                logger.debug("completar_texto %s: %s", provedor, e)
        return ""

    def processar_entrada(self, prompt, on_resposta=None, tentativa=0):
        self.marcar_interacao()
<<<<<<< HEAD

        limite = len(config.API_KEYS) * len(config.LISTA_MODELOS) + 1
        if tentativa >= limite:
            dados = para_rosto(do_catalogo("cota"))
            dados["texto_resposta"] = "AVISO: Todas cotas esgotadas."
            if on_resposta: on_resposta(dados)
            return dados

        if settings.get("modo_debug"):
            dados = {"emocao": "neutro", "texto_resposta": "Debug ativo"}
            if on_resposta: on_resposta(dados)
            return dados

        self._verificar_rate_limit()

        prompt_efetivo = prompt
        t_pal = time.time()
        palacio = self._contexto_palacio(prompt)
        if palacio:
            prompt_efetivo = palacio + "\n\nUsuario: " + prompt
        print(f"[LAT] palace={time.time() - t_pal:.2f}s")
        if self._eh_pedido_de_resumo(prompt):
            bloco = self._resumo_historico_para_prompt()
            prompt_efetivo = f"{bloco}\n\n{prompt_efetivo}"

=======
        ordem = self._ordem_efetiva()
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
        if tentativa == 0:
            self._registrar_memoria(prompt, self._autor_usuario_memoria())
        self.contador_requisicoes += 1
<<<<<<< HEAD
        print(f"[REQ #{self.contador_requisicoes}] Tent. {tentativa+1}")

        try:
            texto_acumulado = ""
            callback_disparado = False
            tem_function_call = False
            ultimo_fc_chunk = None
            t_api = time.time()

            stream = self.chat.send_message_stream(prompt_efetivo)
            for chunk in stream:
                if hasattr(chunk, "candidates") and chunk.candidates:
                    content = chunk.candidates[0].content
                    parts = content.parts if content and getattr(content, "parts", None) else []
                    for part in parts:
                        if getattr(part, "function_call", None):
                            tem_function_call = True
                            ultimo_fc_chunk = chunk
                if tem_function_call:
                    continue
                try:
                    trecho = chunk.text
                except (ValueError, AttributeError):
                    trecho = None
                if trecho:
                    texto_acumulado += trecho
                    if on_resposta and not callback_disparado:
                        dados_parciais = self._tentar_parsear_parcial(texto_acumulado)
                        if dados_parciais:
                            callback_disparado = True
                            on_resposta(dados_parciais)

            print(f"[LAT] gemini_stream={time.time() - t_api:.2f}s fc={tem_function_call}")

            res = None
            if tem_function_call:
                res = ultimo_fc_chunk or self.chat.send_message(prompt_efetivo)
            elif not texto_acumulado.strip():
                res = self.chat.send_message(prompt_efetivo)

            if res is not None:
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
            else:
                res_text = texto_acumulado

            dados = self._parsear_json(res_text)
            if not isinstance(dados, dict):
                dados = {"emocao": "neutro", "texto_resposta": str(dados)}

            self._atualizar_perfil_emocao(dados.get("emocao", "neutro"))

            if tentativa == 0:
                self._registrar_memoria(dados.get("texto_resposta", ""), "REGISTRO")

            if on_resposta and not callback_disparado:
                on_resposta(dados)

            return dados

        except Exception as e:
            erro = classificar(e)
            if erro.codigo == "cota":
                print(f"[QUOTA] Cota esgotada em {self.modelo_nome}. Procurando alternativa...")
                if self.supervisor:
                    ok = self.supervisor.reparar("cota")
                else:
                    self.chat = self._encontrar_combinacao_funcional()
                    ok = True
                if ok:
                    return self.processar_entrada(prompt, on_resposta, tentativa + 1)
                dados = para_rosto(erro)
                if on_resposta: on_resposta(dados)
                return dados

            if erro.codigo == "api_ocupada":
                print(f"[API] Timeout/503 em {self.modelo_nome}.")
                if self.supervisor:
                    ok = self.supervisor.reparar("api_ocupada")
                else:
                    time.sleep(3)
                    ok = True
                if ok:
                    return self.processar_entrada(prompt, on_resposta, tentativa + 1)
                dados = para_rosto(erro)
                if on_resposta: on_resposta(dados)
                return dados

            if "finish_reason" in str(e).lower() or "valid part" in str(e).lower():
                if self.supervisor:
                    self.supervisor.reparar("cota")
                else:
                    self.chat = self._encontrar_combinacao_funcional()
                dados = para_rosto(erro)
                if on_resposta: on_resposta(dados)
=======
        prompt_efetivo = self._montar_prompt_turno(prompt)
        ultimo_erro = None
        for provedor in ordem:
            try:
                print(f"[LLM] provedor={provedor}")
                if provedor == "groq":
                    dados = self._processar_groq(prompt_efetivo)
                elif provedor == "gemini":
                    dados = self._processar_gemini(prompt_efetivo)
                else:
                    dados = self._processar_ollama(prompt_efetivo)
                self._atualizar_perfil_emocao(dados.get("emocao", "neutro"))
                if tentativa == 0:
                    self._registrar_memoria(dados.get("texto_resposta", ""), "REGISTRO")
                if on_resposta:
                    on_resposta(dados)
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
                return dados
            except QuotaError as e:
                ultimo_erro = e
                esperar_retry_after(e, provedor=provedor)
            except Exception as e:
                ultimo_erro = e
                if eh_erro_quota(e):
                    esperar_retry_after(e, provedor=provedor)
                    continue
                logger.warning("provedor %s falhou (%s); tentando o proximo", provedor, e)
                continue
        dados = {
            "emocao": "confuso",
            "texto_resposta": "Sem conexao com Groq, Gemini ou Ollama.",
        }
        if ultimo_erro and eh_erro_quota(ultimo_erro):
            dados["texto_resposta"] = "Cota esgotada em Groq e Gemini. Ollama CPU tambem falhou."
        elif ultimo_erro and not _eh_falha_de_rede(ultimo_erro):
            traceback.print_exc()
<<<<<<< HEAD
            if self.supervisor and erro.recuperavel:
                self.supervisor.reparar(erro.codigo)
            dados = para_rosto(erro)
            if on_resposta: on_resposta(dados)
            return dados
=======
            dados["texto_resposta"] = "Falha no processamento interno."
        if on_resposta:
            on_resposta(dados)
        return dados
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590

    def gerar_texto_aleatorio(self, tema):
        try:
            texto = self._completar_texto(
                f'Voce e REGISTRO. Lembrete: "{tema}". Frase curta. SEM JSON.',
                max_tokens=60,
            )
            return texto or f"Lembrete: {tema}"
        except Exception:
            return f"Lembrete: {tema}"
