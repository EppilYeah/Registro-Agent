import os
import chromadb
from datetime import datetime
from chromadb.config import Settings

from app.core.resposta import formatar_hit_memoria

# Distância de cosseno no Chroma: 0 = idêntico. Acima disso o hit vira ruído.
_DISTANCIA_MAX = 0.72


class RegistroPalace:
    def __init__(self, db_path=None):
        _raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = db_path or os.path.join(_raiz, "data", "palace")
        os.makedirs(self.db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="registro_core_memory",
            metadata={"hnsw:space": "cosine"}
        )

    def guardar(self, texto, autor, wing="conversa", room="geral"):
        if not texto or not str(texto).strip():
            return
        doc_id = f"{int(datetime.now().timestamp() * 1000)}_{autor}"
        self.collection.add(
            documents=[str(texto).strip()],
            metadatas=[{
                "autor": str(autor),
                "wing": str(wing or "conversa"),
                "room": str(room or "geral"),
                "data": str(datetime.now())
            }],
            ids=[doc_id]
        )

    def recuperar(self, query, limit=5, min_relevance=None):
        hits = self.recuperar_detalhado(query, limit=limit, min_relevance=min_relevance)
        return [h["formatado"] for h in hits if h.get("formatado")]

    def recuperar_detalhado(self, query, limit=5, min_relevance=None):
        if not query or not str(query).strip():
            return []
        try:
            total = self.collection.count()
        except Exception:
            return []
        if total <= 0:
            return []
        n = max(1, min(int(limit), total))
        try:
            resultados = self.collection.query(
                query_texts=[str(query)],
                n_results=n,
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            return []
        docs = (resultados.get("documents") or [[]])[0]
        metas = (resultados.get("metadatas") or [[]])[0]
        dists = (resultados.get("distances") or [[]])[0]
        teto = _DISTANCIA_MAX if min_relevance is None else float(min_relevance)
        hits = []
        for i, doc in enumerate(docs):
            dist = dists[i] if i < len(dists) else None
            if dist is not None:
                try:
                    if float(dist) > teto:
                        continue
                except (TypeError, ValueError):
                    pass
            meta = metas[i] if i < len(metas) else {}
            hits.append({
                "texto": doc,
                "metadata": meta or {},
                "distancia": dist,
                "formatado": formatar_hit_memoria(doc, meta, dist),
            })
        return hits


_PALACE = None


def palace_compartilhado(db_path=None):
    """Uma instância por processo — brain e tools leem o mesmo Chroma."""
    global _PALACE
    if _PALACE is None:
        _PALACE = RegistroPalace(db_path=db_path)
    return _PALACE
