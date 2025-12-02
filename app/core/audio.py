import speech_recognition as sr  # Transcrever o que eu falo (Google)
import pvporcupine               # Wake word
import pyaudio                   # Driver pra conectar o mic
import struct                    # Conversor de audio pro porcupine
import os                        # pra apagar o mp3 temporario
from gtts import gTTS            # voz TTS
from playsound import playsound  # tocador de audio
import asyncio
import edge_tts
import config                    # chaves API


class AudioHandler:
    def __init__(self):
        caminho_keyword = "app/core/REGISTRO_pt_windows_v3_0_0.ppn"
        caminho_modelo = "app/core/porcupine_params_pt.pv"
        
        self.pvporcupine = pvporcupine.create(keyword_paths=[caminho_keyword], access_key=config.PICOVOICE_KEY, model_path=caminho_modelo)
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            rate=self.pvporcupine.sample_rate,
            frames_per_buffer=self.pvporcupine.frame_length,
            channels=1,
            format=pyaudio.paInt16,
            input=True
        )
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300  # Sensibilidade 
        self.recognizer.pause_threshold = 1.5   # Espera 1.5s de silêncio antes de cortar
        self.recognizer.dynamic_energy_threshold = True
        
    def ouvir_wake_word(self):
        while True:
            listening = self.stream.read(self.pvporcupine.frame_length)
            listening = struct.unpack_from("h" * self.pvporcupine.frame_length, listening)
            resultado = self.pvporcupine.process(listening)
            if resultado >= 0:
                return True
    
    def ouvir_comando(self):
        if self.stream.is_active():
            self.stream.stop_stream()
        with sr.Microphone() as source:
            # self.recognizer.adjust_for_ambient_noise(source, duration = 0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5)
                comando = self.recognizer.recognize_google(audio, language="pt-BR")
                print(f"COMANDO: {comando}")
                return comando
            except sr.WaitTimeoutError:
                print(" Ninguém falou nada.")
                return None
            except sr.UnknownValueError:
                print(" Não entendi o áudio.")
                return None
            except sr.RequestError:
                print(" Sem internet ou erro no Google.")
                return None
            except Exception as e:
                print(f"Erro genérico: {e}")
                return None
            
            finally:
                if self.stream.is_stopped():
                    self.stream.start_stream()
            
    def falar(self, texto, emocao="neutro"):
        print(f"🔊 Falando: {texto}")
        nome_arquivo = "resposta_temp.mp3"
        
        
        VOZ = "pt-BR-FranciscaNeural" 

        rate = "+0%"
        pitch = "+0Hz"

        if emocao == "sarcasmo_tedio":
            rate = "-15%"  # Fala arrastado
            pitch = "-5Hz" # Tom mais grave/tédio
        
        elif emocao == "irritado":
            rate = "+10%"  # Fala rápido/agressivo
            pitch = "+5Hz" # Tom mais tenso
            
        elif emocao == "feliz" or emocao == "arrogante":
            rate = "+5%"   # Energético
            pitch = "+2Hz" 
            
        elif emocao == "confuso":
            rate = "-5%"
            pitch = "+0Hz"

        try:
            if os.path.exists(nome_arquivo):
                os.remove(nome_arquivo)

            # Função assíncrona com parâmetros SSML
            async def gerar_audio():
                comunicar = edge_tts.Communicate(
                    texto, 
                    VOZ, 
                    rate=rate, 
                    pitch=pitch
                )
                await comunicar.save(nome_arquivo)

            asyncio.run(gerar_audio())
            
            playsound(nome_arquivo)
            os.remove(nome_arquivo)
            
        except Exception as e:
            print(f"Erro no áudio: {e}")