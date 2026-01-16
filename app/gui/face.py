import customtkinter as ctk
import random
import math

class Rosto(ctk.CTkCanvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, highlightthickness=0, **kwargs)
        
        #CONFIGURAÇÕES VISUAIS
        self.cor_led = "#00FF00"      # Cor do traço
        self.tamanho_ponto = 5        # Espessura da linha
        self.quantidade_pontos = 20   # Quantas bolinhas formam o olho

        # EMOÇÕES
        self.emocoes = {
            "neutro": {
                "abertura_olho": 90,   
                "pupila_x": 0, "pupila_y": 0,
                "boca_curvatura": 0,
                "sobrancelha_y": -10, "sobrancelha_inclinacao": 0
            },
            "sarcasmo_tedio": {
                "abertura_olho": 45,
                "pupila_x": 0, "pupila_y": -10,
                "boca_curvatura": 150,
                "sobrancelha_y": 0, "sobrancelha_inclinacao": -10
            },
            "irritado": {
                "abertura_olho": 35,
                "pupila_x": 0, "pupila_y": 0,
                "boca_curvatura": -100,
                "sobrancelha_y": 10, "sobrancelha_inclinacao": 8
            },
            "confuso": {
                "abertura_olho": 80,
                "pupila_x": -15, "pupila_y": 5,
                "boca_curvatura": -100,
                "sobrancelha_y": -15, "sobrancelha_inclinacao": 0
            },
            "arrogante": {
                "abertura_olho": 35,
                "pupila_x": 0, "pupila_y": 5,
                "boca_curvatura": 120,
                "boca_offset_x": 0, "boca_offset_y": -5,
                "sobrancelha_y": -5, "sobrancelha_inclinacao": -7
            },
            "desconfiado": {
                "abertura_olho": 40,
                "pupila_x": 18, "pupila_y": 0,
                "boca_curvatura": -60,
                "sobrancelha_y": 5, "sobrancelha_inclinacao": 3
            },
            "feliz": {
                "abertura_olho": 100,
                "pupila_x": 0, "pupila_y": 0,
                "boca_curvatura": 160,
                "sobrancelha_y": -15, "sobrancelha_inclinacao": 0
            },
            "ouvindo": {
                "abertura_olho": 100,
                "pupila_x": 0, "pupila_y": 0,
                "boca_curvatura": 30, 
                "sobrancelha_y": -10, "sobrancelha_inclinacao": 0
            }
        }

        # Estado atual
        self.estado_atual = self.emocoes["neutro"].copy()
        self.alvo_atual = self.emocoes["neutro"].copy()
        self.velocidades = {}
        for chave in self.estado_atual:
            self.velocidades[chave] = 0.0
        
        self.rigidez = 0.1
        self.atrito = 0.8
        
        # Desenha a primeira vez
        self.desenhar(jx=0, jy=0)
        self.animar()

    def definir_emocao(self, nome_emocao):
        """Muda o estado atual para uma nova emoção e redesenha."""
        if nome_emocao in self.emocoes:
            self.alvo_atual = self.emocoes[nome_emocao].copy()
            self.desenhar(jx=0, jy=0)
        else:
            print(f"AVISO: Emoção '{nome_emocao}' não encontrada. Usando neutro.")
            self.alvo_atual = self.emocoes["neutro"].copy()
            self.desenhar(jx=0, jy=0)


    def _desenhar_olho_pontilhado(self, centro_x, centro_y, largura, altura, fator_escala):
        raio_x = largura / 2
        raio_y = altura / 2
        
        tamanho_led_base = 3.0
        tamanho_led = max(2, int(tamanho_led_base * fator_escala)) 

        for i in range(self.quantidade_pontos):
            angulo = (2 * math.pi / self.quantidade_pontos) * i
            
            
            raw_x = centro_x + raio_x * math.cos(angulo)
            raw_y = centro_y + raio_y * math.sin(angulo)
            
          
            x = int(raw_x)
            y = int(raw_y)
            
        
            self.create_oval(
                x - tamanho_led, y - tamanho_led, 
                x + tamanho_led, y + tamanho_led, 
                fill=self.cor_led, outline=""
            )

    def desenhar(self, jx=0, jy=0):
        self.delete("all")
        
       
        largura_tela = self.winfo_width()
        altura_tela = self.winfo_height()
        
        if largura_tela < 2: largura_tela = 400
        if altura_tela < 2: altura_tela = 300

        cx = largura_tela / 2
        cy = altura_tela / 2


        LARGURA_BASE = 400.0
        fator = max(largura_tela / LARGURA_BASE, 0.5) # Nunca menor que 0.5x

 
   
        dist = 85.0 * fator
        off_olhos_y = -40.0 * fator
        larg_olho = 90.0 * fator
        
        larg_sob = 40.0 * fator
        dist_sob_y = -50.0 * fator
        
        r_pupila = 7.0 * fator
        
        off_boca_y = 80.0 * fator
        larg_boca = 50.0 * fator
        
   
        grossura_linha = max(1, int(self.tamanho_ponto * fator))

        jx_final = jx * fator
        jy_final = jy * fator

        abertura = self.estado_atual.get("abertura_olho", 100)
        
        pupila_x = (self.estado_atual.get("pupila_x", 0)) * fator + jx_final
        pupila_y = (self.estado_atual.get("pupila_y", 0)) * fator + jy_final
        
        curvatura = self.estado_atual.get("boca_curvatura", 0)
        
        sob_y_offset = (self.estado_atual.get("sobrancelha_y", 0)) * fator + jy_final
        sob_inclinacao = (self.estado_atual.get("sobrancelha_inclinacao", 0)) * (fator * 0.8)
        
        boca_off_x = (self.estado_atual.get("boca_offset_x", 0)) * fator + jx_final
        boca_off_y = (self.estado_atual.get("boca_offset_y", 0)) * fator + jy_final


        centro_olho_esq_x = cx - dist
        centro_olho_esq_y = cy + off_olhos_y
        
        centro_olho_dir_x = cx + dist
        centro_olho_dir_y = cy + off_olhos_y

        #  SOBRANCELHAS
        base_sob_y = centro_olho_esq_y + dist_sob_y + sob_y_offset

        # Esq
        self.create_line(
            int(centro_olho_esq_x - larg_sob), int(base_sob_y - sob_inclinacao),
            int(centro_olho_esq_x + larg_sob), int(base_sob_y + sob_inclinacao),
            fill=self.cor_led, width=grossura_linha, capstyle="round"
        )
        # Dir
        self.create_line(
            int(centro_olho_dir_x - larg_sob), int(base_sob_y + sob_inclinacao),
            int(centro_olho_dir_x + larg_sob), int(base_sob_y - sob_inclinacao),
            fill=self.cor_led, width=grossura_linha, capstyle="round"
        )

        #  OLHOS 
        self._desenhar_olho_pontilhado(centro_olho_esq_x, centro_olho_esq_y, larg_olho, abertura, fator)
        
        # Pupila Esq
        self.create_oval(
            int(centro_olho_esq_x - r_pupila + pupila_x), int(centro_olho_esq_y - r_pupila + pupila_y),
            int(centro_olho_esq_x + r_pupila + pupila_x), int(centro_olho_esq_y + r_pupila + pupila_y),
            fill=self.cor_led, outline=self.cor_led
        )

        self._desenhar_olho_pontilhado(centro_olho_dir_x, centro_olho_dir_y, larg_olho, abertura, fator)
        
        # Pupila Dir
        self.create_oval(
            int(centro_olho_dir_x - r_pupila + pupila_x), int(centro_olho_dir_y - r_pupila + pupila_y),
            int(centro_olho_dir_x + r_pupila + pupila_x), int(centro_olho_dir_y + r_pupila + pupila_y),
            fill=self.cor_led, outline=self.cor_led
        )

        #  BOCA 
        base_boca_x = cx
        base_boca_y = cy + off_boca_y
        
        centro_boca_x = base_boca_x + boca_off_x
        centro_boca_y = base_boca_y + boca_off_y
        

        dash_len = max(1, int(1 * fator))
        dash_gap = max(2, int(5 * fator))
        espacamento_boca = (dash_len, dash_gap)


        if abs(curvatura) < 5:
            self.create_line(
                int(centro_boca_x - (larg_boca / 2)), int(centro_boca_y),
                int(centro_boca_x + (larg_boca / 2)), int(centro_boca_y),
                fill=self.cor_led, width=grossura_linha, 
                dash=espacamento_boca, capstyle="round"
            )
        else:

            ajuste_y = (-15.0 if curvatura > 0 else -15.0) * fator
            altura_arco = 30.0 * fator
            

            extent_final = curvatura 

            self.create_arc(
                int(centro_boca_x - (larg_boca / 2)), int(centro_boca_y + ajuste_y), 
                int(centro_boca_x + (larg_boca / 2)), int(centro_boca_y + ajuste_y + altura_arco), 
                start=180, extent=extent_final, style="arc", 
                outline=self.cor_led, width=grossura_linha, dash=espacamento_boca
            )
            
    def animar(self):
        for chave in self.estado_atual.keys():
            alvo = self.alvo_atual.get(chave,0)
            atual = self.estado_atual.get(chave,0)
            forca = (alvo - atual) * self.rigidez
            
            vel_atual = self.velocidades.get(chave, 0.0)
            nova_velocidade = (vel_atual + forca) * self.atrito
            self.velocidades[chave] = nova_velocidade
            
            self.estado_atual[chave] = atual + nova_velocidade
            
        jx = random.uniform(-0.5, 0.5)
        jy = random.uniform(-0.5, 0.5)
        self.desenhar(jx, jy)
        self.after(33, self.animar)