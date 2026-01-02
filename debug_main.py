import threading
import time
import sys
from app.core.brain import Brain
from app.gui.interface import Interface
from app.core.audio import AudioHandler
from app.services.system import Systemhandler

print(">> Inicializando DEBUG...")
audio = AudioHandler()
brain = Brain()
sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio
)
app_visual = Interface()

brain.sistema = sistema

def ciclo_debug_texto():

    print("\n" + "="*40)
    print("MODO DEBUG - ")
    print("="*40 + "\n")
    
    app_visual.rosto.definir_emocao("neutro")
    app_visual.atualizar_texto("MODO DEBUG: Digite no terminal...")

    while True:
        try:
            comando_atual = input("\nVOCÊ >> ").strip()

            if not comando_atual:
                continue

            if comando_atual.lower() in ["sair", "fechar", "exit"]:
                print("Encerrando...")
                sys.exit()

            app_visual.rosto.definir_emocao("confuso") 
            app_visual.atualizar_texto(f"Processando: {comando_atual}...")

            resposta = brain.processar_entrada(comando_atual)

            print(f"REGISTRO >> {resposta['texto_resposta']} [Emoção: {resposta['emocao']}]")

            app_visual.rosto.definir_emocao(resposta["emocao"])
            app_visual.atualizar_texto(resposta["texto_resposta"])

            audio.falar(resposta["texto_resposta"], resposta["emocao"])

        except KeyboardInterrupt:
            print("\nInterrupção forçada via teclado.")
            break
        except Exception as e:
            print(f"ERRO NO LOOP: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    thread_alma = threading.Thread(target=ciclo_debug_texto)
    thread_alma.daemon = True 
    thread_alma.start()
    
    app_visual.mainloop()