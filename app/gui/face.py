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


    def desenhar(self, jx=0, jy=0):
        """
        Limpa a tela e desenha o rosto centralizado E ESCALADO dinamicamente.
        Agora o rosto cresce junto com a janela.
        """
        self.delete("all")
        
        # DESCOBRE O TAMANHO ATUAL
        largura_tela = self.winfo_width()
        altura_tela = self.winfo_height()
        
        # Proteção contra inicialização zero
        if largura_tela < 2: largura_tela = 400
        if altura_tela < 2: altura_tela = 300

        #  CALCULA O CENTRO
        cx = largura_tela / 2
        cy = altura_tela / 2

        # CÁLCULO DO FATOR DE MULTIPLICAÇÃO
        LARGURA_BASE = 400.0
        
        # Calcula o fator baseado na largura.
        fator = max(largura_tela / LARGURA_BASE, 0.5)
        
        distancia_olhos_padrao = 85.0
        dist = distancia_olhos_padrao * fator
        
        offset_olhos_y_padrao = -40.0
        off_olhos_y = offset_olhos_y_padrao * fator
        
        largura_olho_padrao = 90.0
        larg_olho = largura_olho_padrao * fator
        
        largura_sob_padrao = 40.0
        larg_sob = largura_sob_padrao * fator
        
        distancia_sob_y_padrao = -50.0
        dist_sob_y = distancia_sob_y_padrao * fator
        
        raio_pupila_padrao = 7.0
        r_pupila = raio_pupila_padrao * fator
        
        offset_boca_y_padrao = 80.0
        off_boca_y = offset_boca_y_padrao * fator
        
        largura_boca_padrao = 50.0
        larg_boca = largura_boca_padrao * fator

        # VARIÁVEIS DE ESTADO
        abertura = self.estado_atual.get("abertura_olho", 100)
        # Os tremores (jx, jy) e movimentos da pupila também precisam escalar para não parecerem pequenos demais na tela grande
        pupila_x = (self.estado_atual.get("pupila_x", 0) + jx) * fator 
        pupila_y = (self.estado_atual.get("pupila_y", 0) + jy) * fator
        curvatura = self.estado_atual.get("boca_curvatura", 0)
        
        sob_y_offset = (self.estado_atual.get("sobrancelha_y", 0) + jy) * fator
        # Inclinacao escala menos para não ficar exagerada
        sob_inclinacao = (self.estado_atual.get("sobrancelha_inclinacao", 0)) * (fator * 0.8) 
        
        boca_off_x = (self.estado_atual.get("boca_offset_x", 0) + jx) * fator
        boca_off_y = (self.estado_atual.get("boca_offset_y", 0) + jy) * fator

        # COORDENADAS FINAIS 
        centro_olho_esq_x = cx - dist
        centro_olho_esq_y = cy + off_olhos_y
        
        centro_olho_dir_x = cx + dist
        centro_olho_dir_y = cy + off_olhos_y

        # SOBRANCELHAS
        base_sob_y = centro_olho_esq_y + dist_sob_y + sob_y_offset
        grossura_linha = self.tamanho_ponto * fator 

        # Esq
        self.create_line(
            centro_olho_esq_x - larg_sob, base_sob_y - sob_inclinacao,
            centro_olho_esq_x + larg_sob, base_sob_y + sob_inclinacao,
            fill=self.cor_led, width=grossura_linha, capstyle="round"
        )
        # Dir
        self.create_line(
            centro_olho_dir_x - larg_sob, base_sob_y + sob_inclinacao,
            centro_olho_dir_x + larg_sob, base_sob_y - sob_inclinacao,
            fill=self.cor_led, width=grossura_linha, capstyle="round"
        )

        #OLHOS
        self._desenhar_olho_pontilhado(centro_olho_esq_x, centro_olho_esq_y, larg_olho, abertura, fator)
        self.create_oval(
            centro_olho_esq_x - r_pupila + pupila_x, centro_olho_esq_y - r_pupila + pupila_y,
            centro_olho_esq_x + r_pupila + pupila_x, centro_olho_esq_y + r_pupila + pupila_y,
            fill=self.cor_led, outline=self.cor_led
        )

        self._desenhar_olho_pontilhado(centro_olho_dir_x, centro_olho_dir_y, larg_olho, abertura, fator)
        self.create_oval(
            centro_olho_dir_x - r_pupila + pupila_x, centro_olho_dir_y - r_pupila + pupila_y,
            centro_olho_dir_x + r_pupila + pupila_x, centro_olho_dir_y + r_pupila + pupila_y,
            fill=self.cor_led, outline=self.cor_led
        )

        #BOCA
        base_boca_x = cx
        base_boca_y = cy + off_boca_y
        
        centro_boca_x = base_boca_x + boca_off_x
        centro_boca_y = base_boca_y + boca_off_y
        
        dash_len = max(1, int(1 * fator))
        dash_gap = max(2, int(5 * fator))
        espacamento_boca = (dash_len, dash_gap)

        if abs(curvatura) < 1:
            self.create_line(
                centro_boca_x - (larg_boca / 2.0), centro_boca_y,
                centro_boca_x + (larg_boca / 2.0), centro_boca_y,
                fill=self.cor_led, width=grossura_linha, dash=espacamento_boca, capstyle="round"
            )
        else:
            ajuste_y_padrao = -15.0 if curvatura > 0 else -15.0
            ajuste_y = ajuste_y_padrao * fator
            altura_arco_padrao = 30.0
            altura_arco = altura_arco_padrao * fator

            self.create_arc(
                centro_boca_x - (larg_boca / 2.0), centro_boca_y + ajuste_y, 
                centro_boca_x + (larg_boca / 2.0), centro_boca_y + ajuste_y + altura_arco, 
                start=180, extent=curvatura, style="arc", 
                outline=self.cor_led, width=grossura_linha, dash=espacamento_boca
            )

    def _desenhar_olho_pontilhado(self, cx, cy, largura_total, abertura_percent, fator_escala):
        """Desenha o contorno do olho usando pequenos pontos (LEDs), também escalado."""
        altura_total = largura_total * 0.6 
        altura_atual = altura_total * (abertura_percent / 100.0)
        
        num_pontos = 16 
        
        
        tamanho_led_base = 3.0
        tamanho_led = tamanho_led_base * fator_escala

        for i in range(num_pontos):
            angulo = (2 * math.pi / num_pontos) * i
            
            px = cx + (largura_total / 2) * math.cos(angulo)
            py = cy + (altura_atual / 2) * math.sin(angulo)
            
            self.create_oval(
                px - (tamanho_led/2), py - (tamanho_led/2), 
                px + (tamanho_led/2), py + (tamanho_led/2), 
                fill=self.cor_led, outline=""
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