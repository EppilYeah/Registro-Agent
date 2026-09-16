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
        self._sistema = None
        self._log_chaves()
        self.chat = None
        if conectar:
            self._preparar_provedores()
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

    def _encontrar_combinacao_funcional(self):
        return self._conectar_gemini()

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
        if deve_persistir_memoria(texto, autor):
            threading.Thread(target=self._classificar_e_guardar_bg, args=(texto, autor), daemon=True).start()

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
        return hist

    def _verificar_rate_limit(self):
        agora = time.time()
        self.chamadas_ultimo_minuto = [t for t in self.chamadas_ultimo_minuto if agora - t < 60]
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
        ordem = self._ordem_efetiva()
        if tentativa == 0:
            self._registrar_memoria(prompt, self._autor_usuario_memoria())
        self.contador_requisicoes += 1
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
            dados["texto_resposta"] = "Falha no processamento interno."
        if on_resposta:
            on_resposta(dados)
        return dados

    def gerar_texto_aleatorio(self, tema):
        try:
            texto = self._completar_texto(
                f'Voce e REGISTRO. Lembrete: "{tema}". Frase curta. SEM JSON.',
                max_tokens=60,
            )
            return texto or f"Lembrete: {tema}"
        except Exception:
            return f"Lembrete: {tema}"
