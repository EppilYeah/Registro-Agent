import time
import threading


class RegistroErro(Exception):
    def __init__(self, codigo, emocao="confuso", texto_resposta="", recuperavel=True):
        super().__init__(texto_resposta or codigo)
        self.codigo = codigo
        self.emocao = emocao
        self.texto_resposta = texto_resposta
        self.recuperavel = recuperavel


def _item(codigo, emocao, texto, recuperavel=True):
    return RegistroErro(codigo, emocao, texto, recuperavel)


CATALOGO = {
    "cota": lambda: _item("cota", "confuso", "Cota da API esgotada. Recalibrando."),
    "json_rosto": lambda: _item("json_rosto", "confuso", "Resposta fora do contrato."),
    "mic": lambda: _item("mic", "confuso", "Microfone indisponivel."),
    "stt": lambda: _item("stt", "confuso", "Reconhecimento de fala falhou."),
    "tts": lambda: _item("tts", "confuso", "Sintese de voz instavel."),
    "visao": lambda: _item("visao", "confuso", "Camera indisponivel."),
    "volume_com": lambda: _item("volume_com", "confuso", "Controle de volume falhou."),
    "janela": lambda: _item("janela", "confuso", "Janela do REGISTRO nao encontrada."),
    "tool": lambda: _item("tool", "confuso", "Ferramenta falhou."),
    "palace": lambda: _item("palace", "neutro", "Nada relevante no palacio."),
    "api_ocupada": lambda: _item("api_ocupada", "neutro", "API ocupada. Recalibrando."),
    "desconhecido": lambda: _item("desconhecido", "confuso", "Falha interna.", False),
}


def do_catalogo(codigo):
    factory = CATALOGO.get(codigo) or CATALOGO["desconhecido"]
    return factory()


def classificar(exc):
    if isinstance(exc, RegistroErro):
        return exc
    texto = str(exc).lower()
    if any(x in texto for x in ("429", "quota", "resource_exhausted")):
        return do_catalogo("cota")
    if any(x in texto for x in (
        "503", "502", "504", "unavailable", "high demand", "overloaded",
        "try again later", "timeout", "timed out", "deadline_exceeded",
        "readtimeout", "connecttimeout", "deadline",
    )):
        return do_catalogo("api_ocupada")
    if any(x in texto for x in ("finish_reason", "valid part")):
        erro = do_catalogo("json_rosto")
        erro.emocao = "irritado"
        erro.texto_resposta = "Historico reiniciado."
        return erro
    if any(x in texto for x in ("json", "emocao", "texto_resposta")):
        return do_catalogo("json_rosto")
    if any(x in texto for x in ("pyaudio", "pa_invalid", "input overflow", "stream closed", "stream is stopped", "-9999", "-9996")):
        return do_catalogo("mic")
    if any(x in texto for x in ("whisper", "realtimestt", "transcri")):
        return do_catalogo("stt")
    if any(x in texto for x in ("kokoro", "edge_tts", "edge-tts")):
        return do_catalogo("tts")
    if any(x in texto for x in ("videocapture", "opencv", "camera", "cap.read")):
        return do_catalogo("visao")
    if any(x in texto for x in ("pycaw", "coinitialize", "comerror", "endpointvolume", "rpc_e", "-214")):
        return do_catalogo("volume_com")
    if any(x in texto for x in ("hwnd", "win32", "pywin32")):
        return do_catalogo("janela")
    return do_catalogo("desconhecido")


def para_rosto(erro):
    if not isinstance(erro, RegistroErro):
        erro = classificar(erro)
    return {"emocao": erro.emocao, "texto_resposta": erro.texto_resposta}


class Supervisor:
    def __init__(self, audio=None, visao=None, brain=None, sistema=None):
        self.audio = audio
        self.visao = visao
        self.brain = brain
        self.sistema = sistema
        self._max_reparos = 3
        self._janela_s = 60.0
        self._historico = {}
        self._handlers = {
            "cota": self._reparar_cota,
            "json_rosto": self._reparar_json,
            "mic": self._reparar_mic,
            "stt": self._reparar_stt,
            "tts": self._reparar_tts,
            "visao": self._reparar_visao,
            "volume_com": self._reparar_volume,
            "janela": self._reparar_janela,
            "tool": self._reparar_tool,
            "api_ocupada": self._reparar_api_ocupada,
        }
        if audio is not None:
            audio.supervisor = self
        if visao is not None:
            visao.supervisor = self
        if brain is not None:
            brain.supervisor = self
        if sistema is not None:
            sistema.supervisor = self

    def _breaker_ok(self, codigo):
        agora = time.time()
        lista = [t for t in self._historico.get(codigo, []) if agora - t < self._janela_s]
        if len(lista) >= self._max_reparos:
            self._historico[codigo] = lista
            print(f"[SUPERVISOR] Breaker aberto: {codigo}")
            return False
        lista.append(agora)
        self._historico[codigo] = lista
        return True

    def reparar(self, codigo):
        if not self._breaker_ok(codigo):
            return False
        fn = self._handlers.get(codigo)
        if fn is None:
            return False
        try:
            ok = bool(fn())
            print(f"[SUPERVISOR] {codigo}: {'ok' if ok else 'falhou'}")
            return ok
        except Exception as e:
            print(f"[SUPERVISOR] {codigo} explodiu: {e}")
            return False

    def tratar(self, exc, turno_ativo=False):
        erro = classificar(exc)
        print(f"[SUPERVISOR] {erro.codigo}: {exc}")
        ok = False
        if erro.recuperavel:
            ok = self.reparar(erro.codigo)
        if ok:
            return None
        if turno_ativo:
            return para_rosto(erro)
        return None

    def _reparar_cota(self):
        if not self.brain:
            return False
        self.brain.chat = self.brain._encontrar_combinacao_funcional()
        return self.brain.chat is not None

    def _reparar_api_ocupada(self):
        if not self.brain:
            return False
        morto = getattr(self.brain, "modelo_nome", None)
        print(f"[SUPERVISOR] API ocupada em {morto}. Rotacionando.")
        self.brain.chat = self.brain._encontrar_combinacao_funcional(
            excluir={morto} if morto else None
        )
        return self.brain.chat is not None

    def _reparar_json(self):
        return True

    def _reparar_mic(self):
        if not self.audio:
            return False
        return bool(self.audio.reiniciar_mic())

    def _reparar_stt(self):
        if not self.audio:
            return False
        if getattr(self.audio, "_stt_cuda_morto", False):
            return bool(self.audio.recarregar_stt())
        threading.Thread(target=self.audio.recarregar_stt, daemon=True).start()
        return True

    def _reparar_tts(self):
        if not self.audio:
            return False
        self.audio._carregar_kokoro()
        return True

    def _reparar_visao(self):
        if not self.visao:
            return False
        if not self.visao.rodando:
            self.visao.iniciar()
            return bool(self.visao.rodando)
        return bool(self.visao.reabrir_cap())

    def _reparar_volume(self):
        if not self.sistema or not getattr(self.sistema, "media", None):
            return False
        return bool(self.sistema.media._inicializar_audio())

    def _reparar_janela(self):
        try:
            import janela
            return janela.resetar_cache() is not None
        except Exception:
            return False

    def _reparar_tool(self):
        return False
