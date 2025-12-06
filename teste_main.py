import os
import sys
import asyncio
from app.core.brain import Brain
from app.services.system import Systemhandler
from app.core.audio import AudioHandler

print("--- MODO HÍBRIDO ---")

try:
    audio = AudioHandler()
    brain = Brain()
    

    sistema = Systemhandler(
        funcao_falar=audio.falar,
        funcao_gerar_texto=brain.gerar_texto_aleatorio
    )
    
    # 3. Conecta
    brain.sistema = sistema
    
    print("SISTEMA PRONTO")

except Exception as e:
    print(f"ERRO: {e}")
    sys.exit()

while True:
    try:
        # input texto
        texto = input("\nVOCÊ: ")

        if texto.strip().lower() in ["sair", "exit"]:
            break

        if not texto.strip():
            continue
            

        print("Pensando...", end="\r")
        resposta = brain.processar_entrada(texto)
        
        # resultado
        print(" " * 20, end="\r")
        print(f"REGISTRO ({resposta['emocao']}): {resposta['texto_resposta']}")
        
        # resultado sonoro
        audio.falar(resposta['texto_resposta'], resposta['emocao'])
        
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"ERRO: {e}")