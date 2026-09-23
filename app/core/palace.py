<<<<<<< HEAD
import json
import os
import re
import threading
from datetime import datetime
import settings

_INSTANCIA = None
_LOCK = threading.Lock()


def _raiz():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_palace():
    global _INSTANCIA
    with _LOCK:
        if _INSTANCIA is None:
            _INSTANCIA = Palace()
        return _INSTANCIA


def _slug(valor, padrao):
    t = re.sub(r"[^a-z0-9_]+", "_", (valor or padrao).strip().lower())
    t = t.strip("_")
    return t[:48] or padrao


def classificar_lugar(texto, autor):
    t = (texto or "").lower()
    if autor == "REGISTRO":
        return "conversa", "respostas", "falas"
    if any(x in t for x in ("meu nome", "eu sou", "me chamo", "moro", "cidade", "trabalho em", "projeto")):
        return "usuario", "fatos", "perfil"
    if any(x in t for x in ("gosto", "prefiro", "nao gosto", "odeio", "detesto")):
        return "usuario", "preferencias", "gosto"
    if any(x in t for x in ("lembra", "esqueci", "anota", "guarda isso", "nao esquece")):
        return "usuario", "fatos", "notas"
    if any(x in t for x in ("volume", "tela", "comando", "abre ", "whatsapp", "clipboard", "microfone")):
        return "sistema", "desktop", "acoes"
    return "conversa", "geral", "turnos"


class Palace:
    def __init__(self, caminho=None):
        self.raiz = _raiz()
        self.caminho_local = os.path.join(self.raiz, "data", "palace", "verbatim.jsonl")
        self.caminho_palace = caminho or settings.get("palace_path") or ""
        if not self.caminho_palace:
            self.caminho_palace = os.path.join(self.raiz, "data", "palace")
        os.makedirs(os.path.dirname(self.caminho_local), exist_ok=True)
        os.makedirs(self.caminho_palace, exist_ok=True)
        self._col = None
        self._stack = None
        self._pronto = False
        self._lock = threading.Lock()

    def _max_dist(self):
        try:
            valor = settings.get("palace_max_distancia")
            if valor is None or valor == "":
                return 0.0
            return float(valor)
        except:
            return 0.0

    def _hits(self, bruto):
        if isinstance(bruto, dict):
            itens = bruto.get("results")
            if isinstance(itens, list) and itens:
                return itens
            itens = bruto.get("hits")
            if isinstance(itens, list) and itens:
                return itens
            itens = bruto.get("memories")
            if isinstance(itens, list):
                return itens
            return []
        if isinstance(bruto, list):
            return bruto
        return []

    def _colecao(self):
        with self._lock:
            if self._col is None:
                from mempalace.palace import get_collection
                print("[PALACE] Abrindo palacio em %s" % self.caminho_palace, flush=True)
                self._col = get_collection(self.caminho_palace, create=True)
                self._pronto = True
                print("[PALACE] Alas/salas/gavetas prontas.", flush=True)
            return self._col

    def _append_local(self, texto, autor, wing, room, drawer):
        entry = {
            "data": str(datetime.now())[:19],
            "autor": autor,
            "texto": texto,
            "wing": wing,
            "room": room,
            "drawer": drawer,
        }
        try:
            with open(self.caminho_local, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except:
            pass
        return entry

    def guardar(self, texto, autor="Luis", wing=None, room=None, drawer=None):
        if not texto or not str(texto).strip():
            return
        corpo = str(texto).strip()
        if not wing or not room or not drawer:
            w, r, d = classificar_lugar(corpo, autor)
            wing = wing or w
            room = room or r
            drawer = drawer or d
        wing = _slug(wing, "conversa")
        room = _slug(room, "geral")
        drawer = _slug(drawer, "turnos")
        self._append_local(corpo, autor, wing, room, drawer)
        try:
            from mempalace.miner import add_drawer
            col = self._colecao()
            stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            fonte = "gavetas/%s/%s_%s.txt" % (drawer, stamp, _slug(autor, "luis"))
            add_drawer(col, wing, room, corpo, fonte, 0, str(autor))
        except Exception as e:
            print("[PALACE] Falha ao guardar gaveta: %s" % e, flush=True)

    def _texto_hit(self, hit):
        if isinstance(hit, dict):
            return (hit.get("text") or hit.get("texto") or hit.get("content") or hit.get("document") or "").strip()
        return str(hit).strip()

    def recuperar(self, query, limit=5, wing=None, room=None):
        if not query or not str(query).strip():
            return []
        try:
            from mempalace.searcher import search_memories
            bruto = search_memories(
                str(query),
                self.caminho_palace,
                wing=wing or None,
                room=room or None,
                n_results=int(limit),
                max_distance=self._max_dist(),
            )
            saida = []
            for hit in self._hits(bruto):
                txt = self._texto_hit(hit)
                if txt:
                    saida.append(txt)
            if saida:
                return saida
        except Exception as e:
            print("[PALACE] Busca vetorial: %s" % e, flush=True)
        return self._buscar_lexical(query, limit)

    def _buscar_lexical(self, query, limit):
        tokens = set(re.findall(r"\w+", (query or "").lower())) - {
            "o", "a", "os", "as", "um", "uma", "de", "da", "do", "em", "para", "com",
            "que", "e", "nao", "se", "me", "te", "eu", "voce",
        }
        if not tokens:
            return []
        linhas = []
        try:
            with open(self.caminho_local, "r", encoding="utf-8") as f:
                for linha in f.readlines()[-400:]:
                    try:
                        item = json.loads(linha)
                    except:
                        continue
                    txt = item.get("texto") or ""
                    palavras = set(re.findall(r"\w+", txt.lower()))
                    score = len(tokens & palavras)
                    if score:
                        linhas.append((score, txt))
        except:
            return []
        linhas.sort(key=lambda x: -x[0])
        return [t for _, t in linhas[:limit]]

    def recuperar_texto(self, query, limit=5, wing=None, room=None):
        itens = self.recuperar(query, limit=limit, wing=wing, room=room)
        if not itens:
            return ""
        blocos = ["[PALACIO - trechos fieis]"]
        for i, txt in enumerate(itens, 1):
            blocos.append("%s. %s" % (i, txt[:280]))
        return "\n".join(blocos)

    def buscar(self, query, wing=None, room=None, n=5):
        texto = self.recuperar_texto(query, limit=n, wing=wing, room=room)
        if not texto:
            return "Nada relevante no palacio."
        return texto

    def wake_up(self, wing=None):
        try:
            from mempalace.layers import MemoryStack
            if self._stack is None:
                self._stack = MemoryStack(palace_path=self.caminho_palace)
            texto = self._stack.wake_up(wing=wing)
            if texto and str(texto).strip():
                return str(texto).strip()
        except Exception:
            pass
        return self._wake_local()

    def _wake_local(self):
        try:
            with open(self.caminho_local, "r", encoding="utf-8") as f:
                linhas = f.readlines()[-8:]
        except:
            return ""
        if not linhas:
            return ""
        blocos = ["[PALACIO - recentes]"]
        for linha in linhas:
            try:
                e = json.loads(linha)
            except:
                continue
            txt = e.get("texto") or ""
            if not txt:
                continue
            blocos.append("[%s/%s/%s] %s: %s" % (
                e.get("wing", "?"),
                e.get("room", "?"),
                e.get("drawer", "?"),
                e.get("autor", "?"),
                txt[:180],
            ))
        if len(blocos) == 1:
            return ""
        return "\n".join(blocos)
=======
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
>>>>>>> 8814a4e48fba621b220bc27bf56d9045ef9e3590
