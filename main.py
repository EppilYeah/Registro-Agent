import eel
import threading
import time
from app.core.brain import Brain
from app.core.audio import AudioHandler
from app.core.vision import VisionHandler 
from app.services.system import Systemhandler

print("INICIANDO REGISTRO")

audio = AudioHandler()
brain = Brain()
visao = VisionHandler() 
sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio
)
brain.sistema = sistema

eel.init('ui/web')

def ciclo_principal():
    time.sleep(3) 
    
    print("REGISTRO INICIADO")
    audio.falar("REGISTRO INICIADO", "neutro")
    
    visao.iniciar()
    
    try:
        eel.jsAtualizarRosto("neutro", False)
    except:
        pass
    
    while True:
        try:
            if audio.ouvir_wake_word():
                
                modo_conversa = True
                tentativas_silencio = 0
                comando_atual = None
                
                while modo_conversa:
                    try: eel.jsAtualizarRosto("ouvindo", False)
                    except: pass
                    
                    if not comando_atual:
                        comando_atual = audio.ouvir_comando()
                    
                    if comando_atual:
                        print(f"VOCÊ: {comando_atual}")
                        tentativas_silencio = 0
                        
                        if any(x in comando_atual.lower() for x in ["tchau", "desligar", "dormir"]):
                            audio.falar("Até logo.", "neutro")
                            modo_conversa = False
                            eel.jsAtualizarRosto("neutro", False)
                            break
                        
                        eel.jsAtualizarRosto("confuso", False)
                        
                        resposta = brain.processar_entrada(comando_atual)
                        texto = resposta["texto_resposta"]
                        emocao = resposta["emocao"]
                        
                        eel.jsAtualizarRosto(emocao, True)
                        foi_interrompido = audio.falar(texto, emocao)
                        eel.jsAtualizarRosto(emocao, False)
                        
                        comando_atual = None
                        
                        if foi_interrompido:
                            eel.jsAtualizarRosto("irritado", False)
                            comando_atual = audio.ouvir_comando()
                            if comando_atual: continue 
                            
                    else:
                        tentativas_silencio += 1
                        print(f"SILÊNCIO {tentativas_silencio}/2")
                        if tentativas_silencio >= 2:
                            eel.jsAtualizarRosto("neutro", False)
                            modo_conversa = False
                        
            time.sleep(0.1)
        
        except Exception as e:
            print(f"[ERRO CRÍTICO] {e}")
            modo_conversa = False 
            time.sleep(1)

if __name__ == "__main__":
    thread_alma = threading.Thread(target=ciclo_principal)
    thread_alma.daemon = True
    thread_alma.start()
    
    eel.start(
        'index.html',
        mode='chrome',
        size=(500, 500),
        position=(100, 100),
        cmdline_args=['--disable-gpu']
    )