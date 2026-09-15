import unittest

from app.core.resposta import (
    classificar_memoria_heuristica,
    deve_persistir_memoria,
    eh_perfil_resposta_llm,
    formatar_hit_memoria,
    mesclar_perfil_usuario,
    parsear_objeto_json,
    parsear_resposta_json,
    sanitizar_wing_room,
)


class TestResposta(unittest.TestCase):
    def test_parsear_resposta_json_limpo(self):
        dados = parsear_resposta_json('{"emocao": "feliz", "texto_resposta": "Compilou."}')
        self.assertEqual(dados["emocao"], "feliz")
        self.assertEqual(dados["texto_resposta"], "Compilou.")

    def test_parsear_resposta_json_em_cerca(self):
        bruto = '```json\n{"emocao": "irritado", "texto_resposta": "Pare."}\n```'
        dados = parsear_resposta_json(bruto)
        self.assertEqual(dados["emocao"], "irritado")
        self.assertEqual(dados["texto_resposta"], "Pare.")

    def test_emocao_invalida_vira_neutro(self):
        dados = parsear_resposta_json('{"emocao": "tristeza", "texto_resposta": "Oi."}')
        self.assertEqual(dados["emocao"], "neutro")

    def test_prosa_vira_fala_neutra(self):
        dados = parsear_resposta_json("Volume em 80%.")
        self.assertEqual(dados["emocao"], "neutro")
        self.assertIn("80%", dados["texto_resposta"])

    def test_parsear_objeto_json_nao_forca_schema_de_fala(self):
        dados = parsear_objeto_json('{"nome": "Luis Felipe", "cidade": "Recife"}')
        self.assertEqual(dados["nome"], "Luis Felipe")
        self.assertEqual(dados["cidade"], "Recife")

    def test_perfil_detecta_fala_como_lixo(self):
        self.assertTrue(eh_perfil_resposta_llm({"emocao": "neutro", "texto_resposta": "Ok."}))
        self.assertFalse(eh_perfil_resposta_llm({"nome": "Luis", "cidade": "Recife"}))

    def test_heuristica_identidade(self):
        wing, room = classificar_memoria_heuristica("Meu nome é Luis Felipe", "Luis")
        self.assertEqual(wing, "usuario")
        self.assertEqual(room, "identidade")

    def test_heuristica_preferencia(self):
        wing, room = classificar_memoria_heuristica("Eu prefiro Python pra script", "Luis")
        self.assertEqual(wing, "preferencia")
        self.assertEqual(room, "preferencias")

    def test_nao_persiste_eco_curto(self):
        self.assertFalse(deve_persistir_memoria("Ok.", "Luis"))
        self.assertFalse(deve_persistir_memoria("Feito.", "REGISTRO"))
        self.assertTrue(deve_persistir_memoria("Moro em Recife e trabalho com Python.", "Luis"))

    def test_sanitiza_taxonomia(self):
        wing, room = sanitizar_wing_room("Ala Secreta", "sala inventada")
        self.assertEqual(wing, "conversa")
        self.assertEqual(room, "geral")

    def test_parsear_json_com_texto_ao_redor(self):
        bruto = 'Certo.\n{"emocao": "neutro", "texto_resposta": "Feito."}\nFim.'
        dados = parsear_resposta_json(bruto)
        self.assertEqual(dados["texto_resposta"], "Feito.")

    def test_mesclar_perfil_ignora_fala_e_vazios(self):
        atual = {"nome": "Luis", "cidade": "Recife"}
        misturado = mesclar_perfil_usuario(
            atual,
            {"emocao": "neutro", "texto_resposta": "Ok.", "cidade": "Olinda", "profissao": "  "},
        )
        self.assertEqual(misturado["nome"], "Luis")
        self.assertEqual(misturado["cidade"], "Recife")
        extra = mesclar_perfil_usuario(atual, {"profissao": "dev", "cidade": "Olinda"})
        self.assertEqual(extra["profissao"], "dev")
        self.assertEqual(extra["cidade"], "Olinda")

    def test_formatar_hit_inclui_meta(self):
        hit = formatar_hit_memoria(
            "Mora em Recife",
            {"wing": "usuario", "room": "identidade", "autor": "Luis", "data": "2026-09-15 12:00"},
            distancia=0.21,
        )
        self.assertIn("[usuario/identidade Luis 2026-09-15 12:00 d=0.21]", hit)
        self.assertIn("Mora em Recife", hit)


if __name__ == "__main__":
    unittest.main()
