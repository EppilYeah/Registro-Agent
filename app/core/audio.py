import os
import json
import pyaudio
import speech_recognition as sr
from vosk import Model, KaldiRecognizer
from playsound import playsound
import asyncio
import edge_tts

class AudioHandler:
    def __init__(self):
        # Configuração do VOSK
        pasta_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_modelo = os.path.join(pasta_atual, "modelo_vosk")

        # Verifica se baixou o modelo
        if not os.path.exists(caminho_modelo):
            print(f"Pasta 'modelo_vosk' não encontrada em: {caminho_modelo}")
            print("modelo em: https://alphacephei.com/vosk/models (vosk-model-small-pt-0.3)")
            raise FileNotFoundError("Modelo Vosk não encontrado")

        # Carrega o modelo (pode demorar 1 segundinho)
        print(">> CARREGANDO MODULO DE VOZ ")
        try:
            self.model = Model(caminho_modelo)
            self.rec = KaldiRecognizer(self.model, 16000)
        except Exception as e:
            print(f"ERRO AO CARREGAR: {e}")
            raise e

        # Configuração do Microfone para o Vosk
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=8000
        )
        self.stream.start_stream()

        # google
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 1.0
        self.recognizer.dynamic_energy_threshold = True

    def ouvir_wake_word(self):
        """Loop infinito que espera ouvir 'REGISTRO'"""
        print("AGUARDANDO")
        
        # Garante que o microfone ta ligado
        if self.stream.is_stopped():
            self.stream.start_stream()

        while True:
            # Lê um pedaço do áudio
            data = self.stream.read(4000, exception_on_overflow=False)
            
            # Modo 1: Frase completa (Mais preciso)
            if self.rec.AcceptWaveform(data):
                resultado = json.loads(self.rec.Result())
                texto = resultado["text"]
                if "registro" in texto or "registros" in texto:
                    print("WAKE WORD DETECTADA (Final)!")
                    return True
            
            # Modo 2: Enquanto falo (Mais rápido)
            else:
                parcial = json.loads(self.rec.PartialResult())
                texto_parcial = parcial["partial"]
                if "registro" in texto_parcial:
                    self.rec.Reset() # Limpa o buffer para não disparar 2x
                    print("WAKE WORD DETECTADA (Rápida)!")
                    return True

    def ouvir_comando(self):
        """Pausa o Vosk e usa o Google para entender a frase completa"""
        
        self.stream.stop_stream()
        
        print("OUVINDO")
        try:
            with sr.Microphone() as source:
                # self.recognizer.adjust_for_ambient_noise(source) 
                try:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=None)
                    print("PROCESSANDO")
                    comando = self.recognizer.recognize_google(audio, language="pt-BR")
                    print(f"VOCÊ DISSE: {comando}")
                    return comando
                except sr.WaitTimeoutError:
                    print(". . . ")
                    return None
                except sr.UnknownValueError:
                    print("NÃO ENTENDIDO")
                    return None
                except Exception as e:
                    print(f"ERRO: {e}")
                    return None
        finally:
            #RELIGA o Vosk
            self.stream.start_stream()

    def falar(self, texto, emocao="neutro"):
        """método de fala com Edge-TTS """
        print(f"🔊 Falando: {texto}")
        nome_arquivo = "resposta_temp.mp3"
        
        VOZ = "pt-BR-FranciscaNeural"
        rate = "-5%"
        pitch = "-10Hz"
        

        if emocao == "sarcasmo_tedio":
            rate = "-15%"; pitch = "-5Hz"
        elif emocao == "irritado":
            rate = "+10%"; pitch = "+5Hz"
        elif emocao == "feliz" or emocao == "arrogante":
            rate = "+5%"; pitch = "+2Hz"
        elif emocao == "confuso":
            rate = "-5%"; pitch = "+0Hz"

        try:
            if os.path.exists(nome_arquivo):
                os.remove(nome_arquivo)

            async def gerar():
                comunicar = edge_tts.Communicate(texto, VOZ, rate=rate, pitch=pitch)
                await comunicar.save(nome_arquivo)

            asyncio.run(gerar())
            playsound(nome_arquivo)
            os.remove(nome_arquivo)
            
        except Exception as e:
            print(f"Erro no áudio: {e}")