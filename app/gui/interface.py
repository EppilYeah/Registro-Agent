import customtkinter as ctk

class Interface(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("REGISTRO")
        # Ajuste a posição X e Y aqui no final (+100+100)
        self.geometry('400x300+1200+200') 
        self.overrideredirect(True)
        self.attributes('-topmost', True)

        # Transparência geral (Vidro fumê)
        self.attributes('-alpha', 0.90) 

        # ### DEFINIÇÃO DE CORES (Ajustadas) ###
        cor_led = "#00FF00"           # O verde neon brilhante (Traço)
        cor_fundo_rosto = "#072007"   # Verde MUITO escuro (Fundo do rosto)
        cor_borda = "#131111"         # Preto total (A borda)

        # 1. A Janela principal é a BORDA (Preta)
        self.configure(fg_color=cor_borda)

        # 2. O Canvas é o ROSTO (Verde Escuro)
        self.canvas = ctk.CTkCanvas(self, width=390, height=290, bg=cor_fundo_rosto, highlightthickness=0)
        
        # O padx/pady é a espessura da borda preta (4 pixels)
        self.canvas.pack(padx=4, pady=4, fill="both", expand=True)

        # Configurações do estilo LED
        tamanho_ponto = 5  
        espacamento = (1, 3) 

        # --- DESENHANDO ---
        # Olho Esquerdo
        self.canvas.create_oval(
            50, 50, 150, 150, 
            outline=cor_led, width=tamanho_ponto, dash=espacamento
        )
        # Pupila
        self.canvas.create_oval(95, 95, 105, 105, fill=cor_led, outline=cor_led)

        # Olho Direito
        self.canvas.create_oval(
            250, 70, 330, 150, 
            outline=cor_led, width=tamanho_ponto, dash=espacamento
        )
        # Pupila
        self.canvas.create_oval(285, 105, 295, 115, fill=cor_led, outline=cor_led)

        # Boca
        self.canvas.create_line(
            120, 220, 280, 220, 
            fill=cor_led, width=tamanho_ponto, dash=espacamento, capstyle="round"
        )

        # 3. Label combinando com o fundo verde escuro
        self.label = ctk.CTkLabel(
            self, 
            text="Inicializando...", 
            text_color=cor_led, 
            font=("Courier", 16), 
            bg_color=cor_fundo_rosto # Importante: Mesma cor do canvas
        )
        self.label.place(relx=0.5, rely=0.9, anchor="center")

if __name__ == "__main__":
    app = Interface()
    app.mainloop()