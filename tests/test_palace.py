import os
import tempfile

from app.core.palace import RegistroPalace


def test_palace_guarda_e_recupera_com_meta():
    with tempfile.TemporaryDirectory() as tmp:
        palace = RegistroPalace(db_path=os.path.join(tmp, "palace"))
        palace.guardar("Luis Felipe mora em Recife e trabalha com Python.", "Luis", wing="usuario", room="identidade")
        palace.guardar("O volume do PC ficou em 40 por cento.", "REGISTRO", wing="sistema", room="tecnico")
        hits = palace.recuperar("onde o usuario mora", limit=3)
        assert hits
        assert any("Recife" in h for h in hits)
        assert any("usuario/identidade" in h for h in hits)


def test_palace_vazio_nao_quebra():
    with tempfile.TemporaryDirectory() as tmp:
        palace = RegistroPalace(db_path=os.path.join(tmp, "palace"))
        assert palace.recuperar("qualquer coisa") == []
