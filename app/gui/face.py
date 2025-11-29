import customtkinter as ctk
import math

class Rosto(ctk.CTkCanvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, highlightthickness=0, **kwargs)
        
        self.cor_led = "#00FF00"
        self.tamanho_ponto = 5        # Tamanho da bolinha
        self.quantidade_pontos = 20   # Quantas bolinhas formam o olho

        self.emocoes = {
            "neutro": {
                "abertura_olho": 90,   
                "pupila_x": 0, "pupila_y": 0,
                "boca_curvatura": 10   # Leve sorriso
            },
            
            "sarcasmo_tedio": {
                "abertura_olho": 45,  
                "pupila_x": 0, "pupila_y": -10, 
                "boca_curvatura": 0   
            },
            
            "irritado": {
                "abertura_olho": 35,   # Fenda agressiva
                "pupila_x": 0, "pupila_y": 5, 
                "boca_curvatura": -40  # Curva pra baixo (U invertido)
            },
            
            "confuso": {
                "abertura_olho": 100,  # Arregalado
                "pupila_x": -15, "pupila_y": 5, # Vesgo (um olho olhando pro nariz)
                "boca_curvatura": 20   # Sorriso nervoso
            },
            
            "arrogante": {
                "abertura_olho": 55,   # Olhos semicerrados de superioridade
                "pupila_x": 0,
                "pupila_y": 15,        # Olhando para baixo 
                
                "boca_curvatura": 40,  # Um sorriso médio
                "boca_offset_x": 15,   # Empurra o centro da boca para a direita
                "boca_offset_y": -5    # Sobe um pouquinho o centro
            },
            
            "desconfiado": {
                "abertura_olho": 40,   # Olhos apertados
                "pupila_x": 25, "pupila_y": 0, # Olhando MUITO de lado
                "boca_curvatura": 10   # Sorrisinho de canto
            },
            
            "feliz": {
                "abertura_olho": 100,
                "pupila_x": 0, "pupila_y": 0,
                "boca_curvatura": 100  # Sorriso máximo (U)
            }
        }
        self.estado_atual = self.emocoes["neutro"].copy()
        self.desenhar()

    def definir_emocao(self, nome_emocao):
        if nome_emocao in self.emocoes:
            self.estado_atual = self.emocoes[nome_emocao].copy()
            self.desenhar()
        else:
            self.estado_atual = self.emocoes["neutro"].copy()
            self.desenhar()

    def _desenhar_olho_pontilhado(self, centro_x, centro_y, largura, altura):
        """Desenha bolinhas individuais em formato oval usando matemática."""
        raio_x = largura / 2
        raio_y = altura / 2
        
        # Loop para criar cada bolinha
        for i in range(self.quantidade_pontos):
            # Calcula o ângulo de cada ponto 
            angulo = (2 * math.pi / self.quantidade_pontos) * i
            
            # Fórmula do Círculo/Elipse
            x = centro_x + raio_x * math.cos(angulo)
            y = centro_y + raio_y * math.sin(angulo)
            
            # Desenha a bolinha nesse ponto exato
            raio_ponto = self.tamanho_ponto / 2
            self.create_oval(
                x - raio_ponto, y - raio_ponto, 
                x + raio_ponto, y + raio_ponto, 
                fill=self.cor_led, outline=""
            )

    def desenhar(self):
        self.delete("all")
        
        abertura = self.estado_atual["abertura_olho"]
        pupila_x = self.estado_atual["pupila_x"]
        pupila_y = self.estado_atual["pupila_y"]
        curvatura = self.estado_atual["boca_curvatura"]

        centro_olho_esq_x = 110
        centro_olho_esq_y = 110
        
        centro_olho_dir_x = 280
        centro_olho_dir_y = 110

        largura_olho = 90

        # --- 1. OLHO ESQUERDO (Usando o novo método matemático) ---
        self._desenhar_olho_pontilhado(centro_olho_esq_x, centro_olho_esq_y, largura_olho, abertura)
        
        # Pupila Esquerda
        self.create_oval(
            centro_olho_esq_x - 7 + pupila_x, centro_olho_esq_y - 7 + pupila_y,
            centro_olho_esq_x + 7 + pupila_x, centro_olho_esq_y + 7 + pupila_y,
            fill=self.cor_led, outline=self.cor_led
        )

        # OLHO DIREITO 
        self._desenhar_olho_pontilhado(centro_olho_dir_x, centro_olho_dir_y, largura_olho, abertura)

        # Pupila Direita
        self.create_oval(
            centro_olho_dir_x - 7 + pupila_x, centro_olho_dir_y - 7 + pupila_y,
            centro_olho_dir_x + 7 + pupila_x, centro_olho_dir_y + 7 + pupila_y,
            fill=self.cor_led, outline=self.cor_led
        )

        # --- 3. BOCA ---
        
        # Coordenadas Base (Onde a boca fica normalmente)
        base_boca_x = 195
        base_boca_y = 230
        
        # Tenta pegar os offsets da emoção atual. Se não existirem, usa 0.
        off_x = self.estado_atual.get("boca_offset_x", 0)
        off_y = self.estado_atual.get("boca_offset_y", 0)

        # Calcula o centro final aplicando o deslocamento
        centro_boca_x = base_boca_x + off_x
        centro_boca_y = base_boca_y + off_y
        
        largura_boca = 50
        espacamento_boca = (1, 5)

        if curvatura == 0:
            # ... (o resto do código da boca continua igual) ...
            self.create_line(
                centro_boca_x - (largura_boca // 2), centro_boca_y,
                centro_boca_x + (largura_boca // 2), centro_boca_y,
                fill=self.cor_led, width=self.tamanho_ponto, 
                dash=espacamento_boca, capstyle="round"
            )
        else:
            ajuste_y = -15 if curvatura > 0 else -15
            self.create_arc(
                centro_boca_x - (largura_boca // 2), centro_boca_y + ajuste_y, 
                centro_boca_x + (largura_boca // 2), centro_boca_y + ajuste_y + 30, 
                start=180, 
                extent=curvatura, 
                style="arc", 
                outline=self.cor_led, width=self.tamanho_ponto, 
                dash=espacamento_boca
            )