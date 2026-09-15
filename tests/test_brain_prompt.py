import unittest


class FakePalace:
    def recuperar(self, query, limit=5):
        return ["[usuario/identidade Luis 2026-09-15 d=0.20] Mora em Recife"]


class TestBrainPrompt(unittest.TestCase):
    def test_montar_prompt_turno_sem_memoria_curta(self):
        from app.core.brain import Brain
        cerebro = Brain(conectar=False)
        cerebro.palace = FakePalace()
        cerebro.palace.recuperar = lambda query, limit=5: []
        texto = cerebro._montar_prompt_turno("oi")
        self.assertIn("Usuario: oi", texto)
        self.assertNotIn("[MEMORIA]", texto)
        self.assertIn("texto_resposta", texto)

    def test_montar_prompt_turno_injeta_memoria_e_sessao(self):
        from app.core.brain import Brain
        cerebro = Brain(conectar=False)
        cerebro.palace = FakePalace()
        cerebro._sessao_atual = [
            {"autor": "Luis", "texto": "Moro em Recife e trabalho com Python."},
        ]
        texto = cerebro._montar_prompt_turno("qual minha cidade?")
        self.assertIn("[MEMORIA]", texto)
        self.assertIn("Recife", texto)
        self.assertIn("[SESSAO]", texto)
        self.assertIn("Usuario: qual minha cidade?", texto)

    def test_carregar_memoria_comeca_com_user(self):
        from app.core.brain import Brain
        cerebro = Brain(conectar=False)
        cerebro._memoria_cache = [
            {"autor": "REGISTRO", "texto": "Sistemas online."},
            {"autor": "Luis", "texto": "Aumenta o volume."},
            {"autor": "REGISTRO", "texto": "80%."},
        ]
        hist = cerebro.carregar_memoria()
        self.assertTrue(hist)
        self.assertEqual(hist[0].role, "user")


if __name__ == "__main__":
    unittest.main()
