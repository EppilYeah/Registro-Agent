from app.core.palace import get_palace


class MemoryService:
    def buscar_memoria(self, query, ala="", sala=""):
        palacio = get_palace()
        wing = (ala or "").strip() or None
        room = (sala or "").strip() or None
        return palacio.buscar(query, wing=wing, room=room)
