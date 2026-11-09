"""
Índice TF-IDF de n-gramas de caracteres — Python puro (sin dependencias).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Reemplaza a scikit-learn para la recuperación léxica (RAG de frases y de
gramática). Calcula similitud coseno entre una consulta y un conjunto de
documentos, usando n-gramas de caracteres (2-4) ponderados por TF-IDF.

Solo usa la biblioteca estándar: funciona con Python 3.8+ sin instalar nada.
"""

import math
import re
import collections
import unicodedata

_APOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t))
    for a, b in _APOS.items():
        t = t.replace(a, b)
    return t.strip().lower()


def ngramas(texto: str, nmin: int = 2, nmax: int = 4):
    """N-gramas de caracteres sobre el texto normalizado (espacios colapsados)."""
    s = re.sub(r"\s+", " ", normalizar(texto))
    grams = []
    L = len(s)
    for n in range(nmin, nmax + 1):
        for i in range(L - n + 1):
            grams.append(s[i:i + n])
    return grams


class IndiceTFIDF:
    """Índice de documentos para búsqueda por similitud coseno (TF-IDF)."""

    def __init__(self, documentos, nmin: int = 2, nmax: int = 4):
        self.documentos = list(documentos)
        self.nmin, self.nmax = nmin, nmax
        conteos = [collections.Counter(ngramas(d, nmin, nmax)) for d in self.documentos]
        df = collections.Counter()
        for c in conteos:
            for g in c:
                df[g] += 1
        N = max(len(self.documentos), 1)
        # idf suavizado (estilo sklearn): log((N+1)/(df+1)) + 1
        self.idf = {g: math.log((N + 1) / (v + 1)) + 1.0 for g, v in df.items()}
        self.vectores = [self._vector(c) for c in conteos]

    def _vector(self, conteo):
        v = {g: cnt * self.idf.get(g, 0.0) for g, cnt in conteo.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norma for g, x in v.items()}

    def _vector_consulta(self, texto):
        conteo = collections.Counter(ngramas(texto, self.nmin, self.nmax))
        v = {g: cnt * self.idf[g] for g, cnt in conteo.items() if g in self.idf}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norma for g, x in v.items()}

    def similitudes(self, texto):
        """Devuelve la lista de similitudes coseno (0-1) consulta vs cada documento."""
        q = self._vector_consulta(texto)
        if not q:
            return [0.0] * len(self.vectores)
        sims = []
        for vec in self.vectores:
            chico, grande = (q, vec) if len(q) <= len(vec) else (vec, q)
            sims.append(sum(w * grande.get(g, 0.0) for g, w in chico.items()))
        return sims