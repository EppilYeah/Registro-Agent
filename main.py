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
                print("--- WAKE WORD DETECTADA ---")
                

                modo_conversa_ativo = True
                tentativas_silencio = 0 
                
                while modo_conversa_ativo:
                    app_visual.rosto.definir_emocao("ouvindo")
                    
                    comando_pendente = None
                    if comando_pendente:
                        comando = comando_pendente
                        comando_pendente = None
                    else:
                        comando = audio.ouvir_comando()
                    if comando:
                        tentativas_silencio = 0
                        
                        if "tchau" in comando.lower() or "obrigado" in comando.lower():
                            audio.falar("Até mais.", "neutro")
                            modo_conversa_ativo = False
                            break

                        app_visual.rosto.definir_emocao("confuso")
                        
                        resposta = brain.processar_entrada(comando)
                        
                        app_visual.rosto.definir_emocao(resposta["emocao"])
                        

                        audio.falar(resposta["texto_resposta"], resposta["emocao"])
                        if audio.interrompido:
                            print("INTERRUPÇÃO DETECTADA")
                            comando_pendente = audio.ouvir_comando()
                            tentativas_silencio = 0
                        

                        
                    else:
                        tentativas_silencio += 1
                        
                        if tentativas_silencio >= 1: 
                            print("Silêncio detectado. Voltando a dormir.")
                            app_visual.atualizar_texto("Dormindo...")
                            app_visual.rosto.definir_emocao("neutro")
                            modo_conversa_ativo = False 
                        else:
                            app_visual.atualizar_texto("Não ouvi...")
            

            time.sleep(0.1)

        except Exception as e:
            print(f"Erro: {e}")
            modo_conversa_ativo = False 
            

if __name__ == "__main__":
    thread_alma = threading.Thread(target=ciclo_principal)
    thread_alma.daemon = True
    thread_alma.start()
    
    app_visual.mainloop()