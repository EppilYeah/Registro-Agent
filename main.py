from app.brain import Brain

REGISTRO = Brain()


print("INICIAR REGISTRO: \n\n\n")
while True:
    prompt = input("\n\n\nDIGITE O COMANDO DESEJADO: ")
    resposta = REGISTRO.processar_entrada(prompt)
    print("\n\n\n" + resposta)