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

    def _desenhar_olho_pontilhado(self, centro_x, centro_y, largura, altura):
        raio_x = largura / 2
        raio_y = altura / 2
        
        for i in range(self.quantidade_pontos):
            angulo = (2 * math.pi / self.quantidade_pontos) * i
            
            # Calcula e já converte para INTEIRO (int)
            x = int(centro_x + raio_x * math.cos(angulo))
            y = int(centro_y + raio_y * math.sin(angulo))
            
            raio_ponto = self.tamanho_ponto / 2
            
            self.create_oval(
                x - raio_ponto, y - raio_ponto, 
                x + raio_ponto, y + raio_ponto, 
                fill=self.cor_led, outline=""
            )

    def desenhar(self, jx, jy):
        """Limpa a tela e desenha o rosto baseado no self.estado_atual"""
        self.delete("all")
        
        abertura = self.estado_atual.get("abertura_olho", 100)
        pupila_x = self.estado_atual.get("pupila_x", 0)
        pupila_y = self.estado_atual.get("pupila_y", 0)
        curvatura = self.estado_atual.get("boca_curvatura", 0)
        
        sob_y_offset = self.estado_atual.get("sobrancelha_y", 0)
        sob_inclinacao = self.estado_atual.get("sobrancelha_inclinacao", 0)

        #COORDENADAS BASE
        centro_olho_esq_x = 110 + jx
        centro_olho_esq_y = 110 + jy
        
        centro_olho_dir_x = 280 + jx
        centro_olho_dir_y = 110 + jy

        largura_olho = 90

        # SOBRANCELHAS
        largura_sob = 40
        base_sob_y = 60 + sob_y_offset

        # Sobrancelha Esquerda
        self.create_line(
            centro_olho_esq_x - largura_sob, base_sob_y - sob_inclinacao,
            centro_olho_esq_x + largura_sob, base_sob_y + sob_inclinacao,
            fill=self.cor_led, width=self.tamanho_ponto, 
            capstyle="round" # Linhas retas aceitam capstyle!
        )
        # Sobrancelha Direita
        self.create_line(
            centro_olho_dir_x - largura_sob, base_sob_y + sob_inclinacao,
            centro_olho_dir_x + largura_sob, base_sob_y - sob_inclinacao,
            fill=self.cor_led, width=self.tamanho_ponto, 
            capstyle="round"
        )

        # OLHOS 
        self._desenhar_olho_pontilhado(centro_olho_esq_x, centro_olho_esq_y, largura_olho, abertura)
        
        # Pupila Esquerda
        self.create_oval(
            centro_olho_esq_x - 7 + pupila_x, centro_olho_esq_y - 7 + pupila_y,
            centro_olho_esq_x + 7 + pupila_x, centro_olho_esq_y + 7 + pupila_y,
            fill=self.cor_led, outline=self.cor_led
        )

        # Olho Direito
        self._desenhar_olho_pontilhado(centro_olho_dir_x, centro_olho_dir_y, largura_olho, abertura)

        # Pupila Direita
        self.create_oval(
            centro_olho_dir_x - 7 + pupila_x, centro_olho_dir_y - 7 + pupila_y,
            centro_olho_dir_x + 7 + pupila_x, centro_olho_dir_y + 7 + pupila_y,
            fill=self.cor_led, outline=self.cor_led
        )

        # BOCA
        base_boca_x = 195 + jx
        base_boca_y = 230 + jy
        
        # Pega offsets ou usa 0
        off_x = self.estado_atual.get("boca_offset_x", 0)
        off_y = self.estado_atual.get("boca_offset_y", 0)

        centro_boca_x = base_boca_x + off_x
        centro_boca_y = base_boca_y + off_y
        
        largura_boca = 50
        espacamento_boca = (1, 5)

        # Se a curvatura for muito pequena (entre -5 e 5), travamos em 0 para não bugar
        if abs(curvatura) < 5:
            # Desenha RETA
            self.create_line(
                int(centro_boca_x - (largura_boca // 2)), int(centro_boca_y),
                int(centro_boca_x + (largura_boca // 2)), int(centro_boca_y),
                fill=self.cor_led, width=self.tamanho_ponto, 
                dash=espacamento_boca, capstyle="round"
            )
        else:
            # Desenha ARCO
            ajuste_y = -15 if curvatura > 0 else -15
            
            # Proteção: Extent não pode ser 0, senão some.
            extent_final = curvatura
            if abs(extent_final) < 1: extent_final = 1 

            self.create_arc(
                int(centro_boca_x - (largura_boca // 2)), int(centro_boca_y + ajuste_y), 
                int(centro_boca_x + (largura_boca // 2)), int(centro_boca_y + ajuste_y + 30), 
                start=180, 
                extent=extent_final, 
                style="arc", 
                outline=self.cor_led, width=self.tamanho_ponto, 
                dash=espacamento_boca
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
        self.after(20, self.animar)