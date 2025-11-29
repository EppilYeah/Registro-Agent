import customtkinter as ctk
from face import Rosto # Importando o arquivo novo

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
        self.label = ctk.CTkLabel(self, text="Inicializando...", text_color="#00FF00", 
                                  font=("Courier", 16), bg_color=cor_fundo_rosto)
        self.label.place(relx=0.5, rely=0.9, anchor="center")

        # --- TESTE TEMPORÁRIO DE EMOÇÃO ---
        # Tente mudar para "feliz", "irritado", "sarcasmo_tedio" aqui para ver se muda!
        self.rosto.definir_emocao("arrogante")

if __name__ == "__main__":
    app = Interface()
    app.mainloop()