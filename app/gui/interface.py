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
        self.caixa_texto.place(relx=0.5, rely=0.9, anchor="center")
        

        self.atualizar_texto("Inicializando...")
        

    def atualizar_texto(self, novo_texto):
        self.caixa_texto.configure(state="normal") 
        self.caixa_texto.delete("0.0", "end")      
        self.caixa_texto.insert("0.0", novo_texto) 
        self.caixa_texto.configure(state="disabled") 
