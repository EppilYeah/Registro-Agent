from app.brain import Brain

REGISTRO = Brain()

while True:
    prompt = input("\n\n\nDIGITE O COMANDO DESEJADO: ") 
    if prompt == "sair": 
        break
    resposta = REGISTRO.processar_entrada(prompt)
    print(f"\n\n\n {resposta['texto_resposta']}")