import customtkinter as ctk

class Rosto(ctk.CTkCanvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg='black', highlightthickness=0, **kwargs)
        
        self.olho_esq_y = 100
        self.olho_dir_y = 100
        self.boca_y = 200
        self.altura_olho = 20
        self.largura_boca = 100
        
        self.desenhar()
        
    def desenhar():
        self.delete("all")