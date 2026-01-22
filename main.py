import threading
import time
from app.core.brain import Brain
from app.core.audio import AudioHandler
from app.services.system import Systemhandler
from ui.server import SocketIO, app


audio = AudioHandler()
brain = Brain()
sistema = Systemhandler(
    funcao_falar=audio.falar,
    funcao_gerar_texto=brain.gerar_texto_aleatorio
)
brain.sistema = sistema

def ciclo_principal():
    pass


if __name__ == "__main__":
    thread_alma = threading.Thread(target=ciclo_principal)
    thread_alma.daemon = True
    thread_alma.start()
    
    SocketIO.run(app)