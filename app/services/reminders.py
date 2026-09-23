import threading


class RemindersService:
    def __init__(self, funcao_falar=None, funcao_gerar_texto=None):
        self.funcao_falar = funcao_falar
        self.funcao_gerar_texto = funcao_gerar_texto
        self._timers = []

    def agendar_lembrete(self, tempo_segundos, mensagem):
        try:
            tempo = int(float(tempo_segundos))
            if tempo < 1:
                return "Erro: o tempo precisa ser pelo menos 1 segundo."
            t = threading.Timer(tempo, self._disparar_alerta, args=[mensagem])
            t.daemon = True
            t.start()
            self._timers.append(t)
            return f"Lembrete agendado para daqui a {tempo} segundos."
        except (TypeError, ValueError):
            return "Erro: O tempo precisa ser um número em segundos."
        except Exception as e:
            return f"Erro: {e}"

    def _disparar_alerta(self, mensagem_bruta):
        print(f"\n[ALERTA] {mensagem_bruta}")
        texto_final = f"Lembrete: {mensagem_bruta}"
        if self.funcao_gerar_texto:
            try:
                texto_final = self.funcao_gerar_texto(mensagem_bruta)
            except Exception as e:
                print(f"[ALERTA] Falha ao gerar texto: {e}")
        if self.funcao_falar:
            try:
                self.funcao_falar(texto_final, "arrogante")
            except Exception as e:
                print(f"[ALERTA] Falha ao falar: {e}")
