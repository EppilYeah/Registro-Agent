import threading
import time
from app.brain import Brain
from app.gui.interface import Interface
from app.core.audio import AudioHandler


app_visual = Interface()
brain = Brain()
audio = AudioHandler()

def ciclo_principal():
    app_visual.rosto.definir_emocao("neutro")
    
    while True:
        try:
            if audio.ouvir_wake_word():
                app_visual.rosto.definir_emocao("ouvindo")
                comando = audio.ouvir_comando()
                app_visual.atualizar_texto("Ouvindo...")
                
                if comando:
                    app_visual.rosto.definir_emocao("confuso")
                    app_visual.atualizar_texto("Processando...")
                    resposta = brain.processar_entrada(comando)
                    
                    texto_final = resposta["texto_resposta"]
                    emocao_final = resposta["emocao"]
                    
                    app_visual.rosto.definir_emocao(emocao_final)
                    audio.falar(texto_final, emocao_final)
                else:
                    app_visual.atualizar_texto("Não entendi.")
                    time.sleep(1)
                
                app_visual.rosto.definir_emocao("neutro")
                app_visual.atualizar_texto("Aguardando...")
                
            time.sleep(0.1)
        
        except Exception as e:
            print(f"Erro no ciclo principal: {e}")
            app_visual.atualizar_texto("ERRO CRÍTICO")
            app_visual.rosto.definir_emocao("irritado")
            time.sleep(2)
            app_visual.rosto.definir_emocao("neutro")
            

if __name__ == "__main__":
    thread_alma = threading.Thread(target=ciclo_principal)
    thread_alma.daemon = True
    thread_alma.start()
    
    app_visual.mainloop()