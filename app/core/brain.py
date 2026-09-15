import json
import logging
import os
import time
import random
import threading
import traceback
import sys
import config
import settings
from datetime import datetime, date
from google import genai
from google.genai import types
from app.core.palace import palace_compartilhado
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

_MAX_RESETS_QUOTA = 2
_MAX_TURNOS_HISTORICO = 12
_MAX_CACHE_MEMORIA = 24


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
        self.chat = self._encontrar_combinacao_funcional() if conectar else None
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
            self.chat = self._encontrar_combinacao_funcional()

    def _log_chaves(self):
        n = len(config.API_KEYS) if config.API_KEYS else (1 if config.API_KEY else 0)
        print(f"\n{'='*60}\nCHAVES API CARREGADAS: {n}\n{'='*60}\n")

    def _chaves_disponiveis(self):
        if config.API_KEYS:
            return [k for k in config.API_KEYS if k]
        if config.API_KEY:
            return [config.API_KEY]
        return []

    def _aguardar_reset(self):
        print("\n[QUOTA] Aguardando reset (60s)...")
        for i in range(60, 0, -1):
            sys.stdout.write(f"\rReset em: {i//60:02d}:{i % 60:02d} ")
            sys.stdout.flush()
            time.sleep(1)
        print("\nQuota resetada.\n")

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

    def _encontrar_combinacao_funcional(self):
        todas_chaves = self._chaves_disponiveis()
        if not todas_chaves:
            print("[API] Nenhuma chave Gemini configurada (GEMINI_KEYS_ROTATION / GEMINI_API_KEY).")
            return None
        preferido = settings.get("modelo")
        todos_modelos = list(config.LISTA_MODELOS)
        if preferido:
            todos_modelos = [preferido] + [m for m in todos_modelos if m != preferido]
        config_obj = self._config_geracao()
        tentativas_reset = 0
        while tentativas_reset <= _MAX_RESETS_QUOTA:
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
                        chat = client.chats.create(
                            model=modelo,
                            config=config_obj,
                            history=self.carregar_memoria(),
                        )
                        self.client = client
                        self.modelo_nome = modelo
                        print("OK")
                        return chat
                    except Exception as e:
                        erro = str(e).lower()
                        if any(x in erro for x in ["429", "quota", "resource_exhausted"]):
                            print("SEM COTA")
                        else:
                            print(f"ERRO: {e}")
            tentativas_reset += 1
            if tentativas_reset <= _MAX_RESETS_QUOTA:
                self._aguardar_reset()
        print("[API] Falha ao conectar após tentativas de quota.")
        return None

    def gerar_despedida(self):
        try:
            if not self.client or not self.modelo_nome:
                return "Ate logo."
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
            return (response.text or "Ate logo.").strip()
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
        if self._requisicoes_sessao < 3 or not self.client or not self.modelo_nome:
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
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=300, temperature=0.2)
            )
            novo = parsear_objeto_json(getattr(response, "text", "") or "")
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
            if not self.client or not self.modelo_nome:
                return
            prompt = "Gere uma observacao curta e espontanea do REGISTRO. Estilo seco. Sem JSON."
            response = self.client.models.generate_content(model=self.modelo_nome, contents=prompt)
            texto = (getattr(response, "text", "") or "").strip()
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

    def processar_entrada(self, prompt, on_resposta=None, tentativa=0):
        self.marcar_interacao()
        n_chaves = max(1, len(self._chaves_disponiveis()))
        limite_tentativas = n_chaves * len(config.LISTA_MODELOS) + 1
        if tentativa >= limite_tentativas:
            dados = {"emocao": "confuso", "texto_resposta": "Cotas esgotadas em todos os modelos."}
            if on_resposta:
                on_resposta(dados)
            return dados
        if not self.chat or not self.client:
            self.chat = self._encontrar_combinacao_funcional()
        if not self.chat:
            dados = {"emocao": "confuso", "texto_resposta": "Sem conexao com o modelo Gemini."}
            if on_resposta:
                on_resposta(dados)
            return dados
        self._verificar_rate_limit()
        prompt_efetivo = self._montar_prompt_turno(prompt)
        if tentativa == 0:
            self._registrar_memoria(prompt, self._autor_usuario_memoria())
        self.contador_requisicoes += 1
        try:
            res = self.chat.send_message(prompt_efetivo)
            if res.candidates and str(res.candidates[0].finish_reason) in ["SAFETY", "FinishReason.SAFETY", "1", "3"]:
                self.chat = self._encontrar_combinacao_funcional()
                dados = {"emocao": "irritado", "texto_resposta": "Resposta bloqueada por seguranca."}
                if on_resposta:
                    on_resposta(dados)
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
            self._atualizar_perfil_emocao(dados.get("emocao", "neutro"))
            if tentativa == 0:
                self._registrar_memoria(dados.get("texto_resposta", ""), "REGISTRO")
            if on_resposta:
                on_resposta(dados)
            return dados
        except Exception as e:
            erro_str = str(e).lower()
            if any(x in erro_str for x in ["429", "quota", "503", "unavailable"]):
                print("[RECONECTANDO] Servidor ocupado ou cota excedida. Tentando nova chave...")
                time.sleep(2)
                self.chat = self._encontrar_combinacao_funcional()
                return self.processar_entrada(prompt, on_resposta, tentativa + 1)
            traceback.print_exc()
            dados = {"emocao": "confuso", "texto_resposta": "Falha no processamento interno."}
            if on_resposta:
                on_resposta(dados)
            return dados

    def gerar_texto_aleatorio(self, tema):
        try:
            if not self.client or not self.modelo_nome:
                return f"Lembrete: {tema}"
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=f'Voce e REGISTRO. Lembrete: "{tema}". Frase curta. SEM JSON.',
                config=types.GenerateContentConfig(max_output_tokens=60)
            )
            return (getattr(response, "text", None) or f"Lembrete: {tema}").strip()
        except Exception:
            return f"Lembrete: {tema}"
