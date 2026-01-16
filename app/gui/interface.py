import customtkinter as ctk
from app.gui.face import Rosto 

class Interface(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("REGISTRO")
        self.geometry('400x300+1200+200')
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.90)
        self.x_mouse = 0
        self.y_mouse = 0
        self.fullscreen = False
        
        self.bind("<ButtonPress-1>", self.iniciar_movimento)
        self.bind("<B1-Motion>", self.mover_janela)
        self.bind("<Double-Button-1>", self.alternar_fullscreen)

        # Cores
        cor_fundo_rosto = "#051505"
        cor_borda = "#000000"
        self.configure(fg_color=cor_borda)
        self.rosto = Rosto(self, width=390, height=290, bg=cor_fundo_rosto)
        self.rosto.pack(padx=4, pady=4, fill="both", expand=True)

        # Label
        self.caixa_texto = ctk.CTkTextbox(
            self, 
            width=380, 
            height=60,         
            fg_color=cor_fundo_rosto,
            text_color="#00FF00",
            font=("Courier", 14),
            wrap="word",        
            activate_scrollbars=False 
        )


    def atualizar_texto(self, novo_texto):
        self.caixa_texto.configure(state="normal") 
        self.caixa_texto.delete("0.0", "end")      
        self.caixa_texto.insert("0.0", novo_texto) 
        self.caixa_texto.configure(state="disabled") 
        
    def iniciar_movimento(self, event):
        """Guarda a posição exata onde você clicou dentro da janela"""
        self.x_mouse = event.x
        self.y_mouse = event.y

    def mover_janela(self, event):
        """Calcula a nova posição da janela baseado no movimento do mouse"""
        if self.fullscreen:
            return

        x_novo = event.x_root - self.x_mouse
        y_novo = event.y_root - self.y_mouse
        
        # Move a janela
        self.geometry(f"+{x_novo}+{y_novo}")

    def alternar_fullscreen(self, event=None):
        """Alterna entre Tela Cheia e Tamanho Normal ao dar clique duplo"""
        self.fullscreen = not self.fullscreen 
        
        if self.fullscreen:
            # Modo Tela Cheia 
            largura_tela = self.winfo_screenwidth()
            altura_tela = self.winfo_screenheight()
            self.geometry(f"{largura_tela}x{altura_tela}+0+0")
        else:
            self.geometry('400x300')
