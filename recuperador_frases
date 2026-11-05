"""
RECUPERADOR DE FRASES (RAG de frases, v1 — léxico).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace: dada una frase de entrada, recupera del corpus las frases más
PARECIDAS (por similitud léxica: palabras y raíces compartidas) junto con su
traducción, para dárselas al agente traductor como EJEMPLOS (traducción basada
en ejemplos / example-based MT).

Por qué léxico y no embeddings (por ahora):
  - El nasa yuwe es desconocido para los modelos de embeddings; la señal más
    confiable para "frases parecidas" es compartir palabras/raíces.
  - Corre en CPU, sin descargar modelos pesados, y es 100% reproducible.
  - BGE-M3 (dense) se puede agregar después como mejora semántica.

Herramienta determinista: TF-IDF de n-gramas de caracteres (scikit-learn, BSD).
No usa Ollama.
"""

import os
import csv
import unicodedata
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

_CARPETA = os.path.dirname(os.path.abspath(__file__))
_RUTA = os.path.join(_CARPETA, "frases_ny_es.csv")
_APOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t))
    for a, b in _APOS.items():
        t = t.replace(a, b)
    return t.strip().lower()


# ---- carga del corpus de frases ----
def _cargar():
    ny, es = [], []
    if not os.path.exists(_RUTA):
        return ny, es
    with open(_RUTA, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            a, b = r.get("nasayuwe", "").strip(), r.get("espanol", "").strip()
            if a and b:
                ny.append(a)
                es.append(b)
    return ny, es


FRASES_NY, FRASES_ES = _cargar()

# ---- índices TF-IDF (uno por idioma de consulta) ----
# n-gramas de caracteres (2-4): capturan raíces y afijos compartidos.
def _construir_indice(textos):
    if not textos:
        return None, None
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                          preprocessor=_norm)
    matriz = vec.fit_transform(textos)
    return vec, matriz


_VEC_NY, _MAT_NY = _construir_indice(FRASES_NY)   # para consultas en nasa yuwe
_VEC_ES, _MAT_ES = _construir_indice(FRASES_ES)   # para consultas en español


def buscar(texto: str, direccion: str = "NY-ES", k: int = 3,
           umbral: float = 0.05, excluir_identica: bool = False):
    """
    Recupera las k frases más parecidas a `texto`.
    direccion "NY-ES": busca por el lado NASA YUWE  -> devuelve (ny, es).
    direccion "ES-NY": busca por el lado ESPAÑOL    -> devuelve (es, ny).
    Devuelve: lista de dicts {origen, destino, score} ordenada por score desc.
    """
    if direccion == "NY-ES":
        vec, mat, orig, dest = _VEC_NY, _MAT_NY, FRASES_NY, FRASES_ES
    else:
        vec, mat, orig, dest = _VEC_ES, _MAT_ES, FRASES_ES, FRASES_NY
    if vec is None:
        return []
    q = vec.transform([texto])
    sims = linear_kernel(q, mat)[0]
    idx = sims.argsort()[::-1]
    salida = []
    for i in idx:
        if sims[i] < umbral:
            break
        if excluir_identica and _norm(orig[i]) == _norm(texto):
            continue
        salida.append({"origen": orig[i], "destino": dest[i],
                       "score": round(float(sims[i]), 3)})
        if len(salida) >= k:
            break
    return salida


def ejemplos_para_prompt(texto: str, direccion: str = "NY-ES", k: int = 3) -> str:
    """Formatea los ejemplos recuperados para inyectarlos en el prompt del traductor."""
    res = buscar(texto, direccion, k=k)
    if not res:
        return ""
    if direccion == "NY-ES":
        return "\n".join(f'- NY: "{r["origen"]}"  =  ES: "{r["destino"]}"' for r in res)
    return "\n".join(f'- ES: "{r["origen"]}"  =  NY: "{r["destino"]}"' for r in res)


if __name__ == "__main__":
    print(f"Corpus de frases: {len(FRASES_NY)}")
    pruebas = ["aka yuuk", "wala aka", "kiwe"]
    for p in pruebas:
        print(f"\nConsulta NY: {p!r}")
        for r in buscar(p, "NY-ES", k=3, excluir_identica=True):
            print(f"   [{r['score']}] {r['origen']}  ->  {r['destino']}")