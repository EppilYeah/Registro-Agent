import os
import chromadb
from datetime import datetime
from chromadb.config import Settings

class RegistroPalace:
    def __init__(self):
        _raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(_raiz, "data", "palace")
        os.makedirs(self.db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="registro_core_memory",
            metadata={"hnsw:space": "cosine"}
        )

    def guardar(self, texto, autor, wing="default", room="geral"):
        if not texto or not str(texto).strip():
            return
        doc_id = f"{int(datetime.now().timestamp() * 1000)}_{autor}"
        self.collection.add(
            documents=[texto],
            metadatas=[{
                "autor": autor, 
                "wing": wing, 
                "room": room, 
                "data": str(datetime.now())
            }],
            ids=[doc_id]
        )

    def recuperar(self, query, limit=5):
        try:
            resultados = self.collection.query(
                query_texts=[query],
                n_results=limit
            )
            if resultados and resultados.get("documents") and resultados["documents"][0]:
                return resultados["documents"][0]
            return []
        except Exception:
            return []