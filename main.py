import eel
import threading
import time
from app.core.brain import Brain
from app.core.audio import AudioHandler
from app.services.system import Systemhandler

audio = AudioHandler()
brain = Brain()
sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio
)
brain.sistema = sistema

def ciclo_principal():
    audio.falar("REGISTRO INICIADO", "neutro")
    eel.jsAtualizarRosto("neutro", False)
    
    while True:
        try:
            if audio.ouvir_wake_word():
                
                modo_conversa = True
                tentativas_silencio = 0
                comando_atual = None
                
                while modo_conversa:
                    eel.jsAtualizarRosto("ouvindo", False)
                    
                    if not comando_atual:
                        comando_atual = audio.ouvir_comando()
                        
                    if comando_atual():
                        print(f"VOCÊ: {comando_atual}")
                        tentativas_silencio = 0
                        
                        if any(x in comando_atual.lower() for x in ["tchau", "desligar", "dormir"]):
                            audio.falar("REGISTRO ENCERRADO", "neutro")
                            modo_conversa = False
                            break
                        
                        eel.jsAtualizarRosto("confuso", False)
                        
                        resposta = brain.processar_entrada(comando_atual)
                        
                        eel.jsAtualizarRosto(resposta["emocao"], True)
                        foi_interrompido = audio.falar(resposta["texto_resposta"], resposta["emocao"])
                        eel.jsAtualizarRosto(resposta["emocao"], False)
                        
                        comando_atual = None
                        
                        if foi_interrompido:
                            print("--- INTERROMPIDO ---")
                            eel.jsAtualizarRosto("irritado") 
                            

                            comando_atual = audio.ouvir_comando()
                            
                            if comando_atual:
                                continue 
                            else:
                                pass
                            
                    else:
                        tentativas_silencio += 1
                        
                        print(F"TENTATIVA {tentativas_silencio}/2")
                        
                        if tentativas_silencio >= 2:
                            print("--- TIMEOUT ---")
                            
                            eel.jsAtualizarRosto("neutro")
                            modo_conversa = False
                        else:
            time.sleep(0.1)
        
        except Exception as e:
            print(f"[CRASH LOOP] Erro: {e}")
            modo_conversa = False 
            time.sleep(1)


eel.init('ui/web')
if __name__ == "__main__":
    thread_alma = threading.Thread(target=ciclo_principal)
    thread_alma.daemon = True
    thread_alma.start()
    
    eel.start('index.html', size=(500, 400))