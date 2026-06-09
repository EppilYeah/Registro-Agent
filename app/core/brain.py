import json
import logging
import os
import re
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
from app.core.palace import RegistroPalace

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMADB_TELEMETRY"] = "False"

logger = logging.getLogger(__name__)

EMO_RESPOSTA_VALIDAS = frozenset({
    "neutro", "sarcasmo_tedio", "irritado", "confuso", "arrogante", "desconfiado", "feliz",
})

class Brain:
    def __init__(self):
        _raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.caminho_perfil = os.path.join(_raiz, "data", "perfil.json")
        self.caminho_usuario = os.path.join(_raiz, "data", "usuario.json")
        self.palace = RegistroPalace()
        self.modelo_nome = ""
        self.contador_requisicoes = 0
        self.chamadas_ultimo_minuto = []
        self.client = None
        self._perfil_dirty = False
        self._memoria_cache = []
        self._perfil = self._carregar_perfil()
        self._sessao_atual = []
        self._sistema = None
        self._log_chaves()
        self.chat = self._encontrar_combinacao_funcional()
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
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        ]
        tools_ativos = []
        if self._sistema and hasattr(self._sistema, "skills"):
            tools_ativos = list(self._sistema.skills.values())
        config_obj = types.GenerateContentConfig(
            temperature=1.0,
            top_p=0.95,
            top_k=40,
            safety_settings=safety_settings,
            tools=tools_ativos if tools_ativos else None,
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
            self._aguardar_reset()

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
        except:
            pass
        return padrao

    def _salvar_perfil(self):
        try:
            os.makedirs(os.path.dirname(self.caminho_perfil), exist_ok=True)
            with open(self.caminho_perfil, 'w', encoding='utf-8') as f:
                json.dump(self._perfil, f, indent=2, ensure_ascii=False)
            self._perfil_dirty = False
        except:
            pass

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
        self._memoria_cache.append(entry)
        self._sessao_atual.append(entry)
        if len(self._memoria_cache) > 20:
            self._memoria_cache.pop(0)
        threading.Thread(target=self._classificar_e_guardar_bg, args=(texto, autor), daemon=True).start()

    def _classificar_e_guardar_bg(self, texto, autor):
        wing_calc = "conversa"
        room_calc = "geral"
        if autor == self._autor_usuario_memoria() and self.client:
            try:
                prompt_class = (
                    f"Classifique a entrada do usuario para o banco vetorial.\n"
                    f"Entrada: '{texto}'\n"
                    "Retorne JSON com 'wing' e 'room'."
                )
                res = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt_class,
                    config=types.GenerateContentConfig(temperature=0.1)
                )
                dados = self._parsear_json(res.text)
                wing_calc = dados.get("wing", "conversa").lower().replace(" ", "_")
                room_calc = dados.get("room", "geral").lower().replace(" ", "_")
            except:
                pass
        self.palace.guardar(texto, autor, wing=wing_calc, room=room_calc)

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
        if not isinstance(dados, dict):
            return {"emocao": "neutro", "texto_resposta": str(dados)}
        em = dados.get("emocao", "neutro")
        tx = dados.get("texto_resposta", "")
        if em not in EMO_RESPOSTA_VALIDAS:
            em = "neutro"
        return {"emocao": em, "texto_resposta": str(tx)}

    def _parsear_json(self, texto):
        if not texto:
            return self._normalizar_resposta({"emocao": "confuso", "texto_resposta": "Sem resposta"})
        txt = texto.replace("```json", "").replace("```", "").strip()
        try:
            return self._normalizar_resposta(json.loads(txt))
        except:
            match = re.search(r'\{.*?"emocao".*?"texto_resposta".*?\}', txt, re.DOTALL)
            if match:
                return self._normalizar_resposta(json.loads(match.group(0)))
        return self._normalizar_resposta({"emocao": "confuso", "texto_resposta": txt})

    def _carregar_usuario(self):
        try:
            with open(self.caminho_usuario, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
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
            trecho = "\n".join([d.get("autor","?") + ": " + d.get("texto","")[:80] for d in ultimas])
            prompt = f"Atualize o perfil do usuario em JSON. Atual: {json.dumps(atual)}\nConversa:\n{trecho}"
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=300, temperature=0.2)
            )
            novo = self._parsear_json(response.text)
            novo["ultima_atualizacao"] = str(datetime.now())[:16]
            self._salvar_usuario(novo)
        except:
            pass

    def usuario_para_prompt(self):
        dados = self._carregar_usuario()
        if not dados: return ""
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
                if not settings.get("comportamento_espontaneo"): continue
                agora = time.time()
                if str(date.today()) != self._perfil.get("espontaneo_data"):
                    self._perfil["espontaneo_hoje"] = 0
                    self._perfil["espontaneo_data"] = str(date.today())
                    self._perfil_dirty = True
                if self._perfil["espontaneo_hoje"] >= settings.get("espontaneo_limite_diario"): continue
                if agora - self._ultimo_espontaneo < settings.get("espontaneo_cooldown_min") * 60: continue
                if agora - self._ultima_interacao < 300: continue
                if random.random() > 0.05: continue
                self._disparar_espontaneo()
            except:
                pass

    def _disparar_espontaneo(self):
        try:
            prompt = f"Gere uma observacao curta e espontanea do REGISTRO. Estilo seco. Sem JSON."
            response = self.client.models.generate_content(model=self.modelo_nome, contents=prompt)
            texto = response.text.strip()
            if texto and self._callback_espontaneo:
                self._callback_espontaneo(texto, "neutro")
                self._ultimo_espontaneo = time.time()
                self._perfil["espontaneo_hoje"] += 1
                self._perfil_dirty = True
        except:
            pass

    def marcar_interacao(self):
        self._ultima_interacao = time.time()
        self._requisicoes_sessao += 1

    def iniciar_sessao(self):
        self._sessao_atual = []

    def processar_entrada(self, prompt, on_resposta=None, tentativa=0):
        self.marcar_interacao()
        limite_tentativas = len(config.API_KEYS) * len(config.LISTA_MODELOS) + 1
        if tentativa >= limite_tentativas:
            dados = {"emocao": "confuso", "texto_resposta": "Cotas esgotadas em todos os modelos."}
            if on_resposta: on_resposta(dados)
            return dados
        self._verificar_rate_limit()
        memorias_relevantes = self.palace.recuperar(prompt, limit=5)
        contexto_memoria = " | ".join(memorias_relevantes) if memorias_relevantes else "Sem memorias."
        prompt_efetivo = f"[MEMORIA: {contexto_memoria}]\n\nUsuario: {prompt}"
        if tentativa == 0: self._registrar_memoria(prompt, self._autor_usuario_memoria())
        self.contador_requisicoes += 1
        try:
            res = self.chat.send_message(prompt_efetivo)
            if res.candidates and str(res.candidates[0].finish_reason) in ["SAFETY", "FinishReason.SAFETY", "1", "3"]:
                self.chat = self._encontrar_combinacao_funcional()
                dados = {"emocao": "irritado", "texto_resposta": "Resposta bloqueada por seguranca."}
                if on_resposta: on_resposta(dados)
                return dados
            if not res.text: raise ValueError("Resposta vazia do AFC.")
            dados = self._parsear_json(res.text)
            self._atualizar_perfil_emocao(dados.get("emocao", "neutro"))
            if tentativa == 0: self._registrar_memoria(dados.get("texto_resposta", ""), "REGISTRO")
            if on_resposta: on_resposta(dados)
            return dados
        except Exception as e:
            erro_str = str(e).lower()
            if any(x in erro_str for x in ["429", "quota", "503", "unavailable"]):
                print(f"[RECONECTANDO] Servidor ocupado ou cota excedida. Tentando nova chave...")
                time.sleep(2)
                self.chat = self._encontrar_combinacao_funcional()
                return self.processar_entrada(prompt, on_resposta, tentativa + 1)
            traceback.print_exc()
            dados = {"emocao": "confuso", "texto_resposta": "Falha no processamento interno."}
            if on_resposta: on_resposta(dados)
            return dados

    def gerar_texto_aleatorio(self, tema):
        try:
            response = self.client.models.generate_content(
                model=self.modelo_nome,
                contents=f'Voce e REGISTRO. Lembrete: "{tema}". Frase curta. SEM JSON.',
                config=types.GenerateContentConfig(max_output_tokens=60)
            )
            return response.text.strip()
        except:
            return f"Lembrete: {tema}"