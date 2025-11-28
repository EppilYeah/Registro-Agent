import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from app.brain import Brain

console = Console()

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def cabecalho():
    titulo = Text("REGISTRO v1.0", justify="center", style="bold white")
    subtitulo = Text("CONEXÃO ATIVA • MEMORIA SINCRONIZADA", justify="center", style="dim white")
    
    painel = Panel(
        Text.assemble(titulo, "\n", subtitulo),
        border_style="green",
        padding=(1, 2)
    )
    console.print(painel)

limpar_tela()
cabecalho()

with console.status("[bold yellow]INICIANDO PROTOCOLO NEURAIS...", spinner="dots"):
    try:
        REGISTRO = Brain()
        console.print("[bold green]✓ SISTEMA INICIADO[/bold green]")
    except Exception as e:
        console.print(f"[bold red]ERRO FATAL AO INICIAR:[/bold red] {e}")
        sys.exit()

console.print("") 


while True:
    try:
        prompt = console.input("[bold cyan][VOCÊ] > [/bold cyan]")
        
        if prompt.lower().strip() == "sair":
            console.print(Panel("[bold red]FINALIZANDO REGISTRO.[/]", border_style="red"))
            break
        
        if prompt.strip() == "":
            continue

        with console.status("[bold yellow]PROCESSANDO...", spinner="arc"):
            resposta = REGISTRO.processar_entrada(prompt)
            texto_ia = resposta['texto_resposta']
            emocao = resposta['emocao']

        cor_borda = "green"
        if emocao == "irritado": cor_borda = "red"
        elif emocao == "sarcasmo_tedio": cor_borda = "yellow"
        elif emocao == "confuso": cor_borda = "magenta"

        painel_resposta = Panel(
            texto_ia,
            title=f"[b]REGISTRO[/b] ({emocao})",
            border_style=cor_borda,
            subtitle="FIM DA TRANSMISSAO",
            subtitle_align="right"
        )
        
        console.print(painel_resposta)
        console.print("") 

    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupção forçada.[/]")
        break