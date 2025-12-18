import threading
import time
from app.core.brain import Brain
from app.gui.interface import Interface
from app.core.audio import AudioHandler
from app.services.system import Systemhandler


audio = AudioHandler()
brain = Brain()
sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio
)
app_visual = Interface()
brain.sistema = sistema

def ciclo_principal():
    audio.falar("REGISTRO INICIADO", "neutro")
    app_visual.rosto.definir_emocao("neutro")
    app_visual.atualizar_texto("Aguardando 'REGISTRO'...")

    while True:
        try:
            if audio.ouvir_wake_word():
                print("\n--- [WAKE WORD] ATIVADO ---")
                

                modo_conversa = True
                tentativas_silencio = 0
                comando_atual = None 
                
                while modo_conversa:
                    app_visual.rosto.definir_emocao("ouvindo")
                    app_visual.atualizar_texto("Ouvindo...")
                    

                    if not comando_atual:
                        comando_atual = audio.ouvir_comando()


                    if comando_atual:
                        print(f"VOCÊ: {comando_atual}")
                        tentativas_silencio = 0 # Reset de inatividade
                        
                        if any(x in comando_atual.lower() for x in ["tchau", "desligar", "dormir"]):
                            audio.falar("Hibernando.", "neutro")
                            modo_conversa = False
                            break

                        app_visual.rosto.definir_emocao("confuso") 
                        app_visual.atualizar_texto("Processando...")
                        
                        resposta = brain.processar_entrada(comando_atual)
                        

                        app_visual.rosto.definir_emocao(resposta["emocao"])
                        app_visual.atualizar_texto(resposta["texto_resposta"])


                        foi_interrompido = audio.falar(resposta["texto_resposta"], resposta["emocao"])
                        
                        comando_atual = None 

                        if foi_interrompido:
                            print("--- [INTERRUPÇÃO] OUVINDO IMEDIATAMENTE ---")
                            app_visual.atualizar_texto("Interrompido! Ouvindo...")
                            app_visual.rosto.definir_emocao("irritado") 
                            

                            comando_atual = audio.ouvir_comando()
                            
                            if comando_atual:
                                continue 
                            else:
                                pass

                    else:
                        tentativas_silencio += 1
                        print(f"[SILÊNCIO] Tentativa {tentativas_silencio}/2")
                        
                        if tentativas_silencio >= 2:
                            print("--- [TIMEOUT] Voltando a dormir ---")
                            app_visual.atualizar_texto("Dormindo...")
                            app_visual.rosto.definir_emocao("neutro")
                            modo_conversa = False 
                        else:
                            app_visual.atualizar_texto("...")
            
            time.sleep(0.1)

        except Exception as e:
            print(f"[CRASH LOOP] Erro: {e}")
            modo_conversa = False 
            time.sleep(1)

if __name__ == "__main__":
    thread_alma = threading.Thread(target=ciclo_principal)
    thread_alma.daemon = True
    thread_alma.start()
    
    app_visual.mainloop() 