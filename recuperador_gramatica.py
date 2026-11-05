"""
RECUPERADOR DE GRAMÁTICA (RAG de gramática, v1 — léxico).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace: dada una frase/palabra en nasa yuwe, recupera de la gramática
(rag/gramatica_por_temas.md) las SECCIONES más relacionadas (reglas sobre
afijos, morfemas, orden, etc.), para dárselas al agente traductor como REGLAS
de referencia. Ayuda con palabras flexionadas que el diccionario no resuelve
(morfología) y con la construcción de frases.

Enfoque (v1): TF-IDF de n-gramas de caracteres sobre cada sección temática.
Los trozos contienen ejemplos en nasa yuwe y sus glosas, así que una palabra de
entrada que comparta raíz/afijo con un ejemplo hace aflorar la regla.
Determinista, en CPU, sin descargar modelos. BGE-M3 se puede agregar como v2.

Nota: la fuente es OCR; las palabras nasa yuwe pueden tener errores. Las reglas
en español (lo que más guía al LLM) están limpias.
"""

import os
import re
import unicodedata
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

_CARPETA = os.path.dirname(os.path.abspath(__file__))
_RUTA = os.path.join(_CARPETA, "rag", "gramatica_por_temas.md")
_APOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t))
    for a, b in _APOS.items():
        t = t.replace(a, b)
    return t.strip().lower()


def _cargar_chunks():
    """Parte la gramática en trozos por sección (encabezados '## ')."""
    if not os.path.exists(_RUTA):
        return []
    lineas = open(_RUTA, encoding="utf-8").read().splitlines()
    # el cuerpo empieza después del primer separador '---'
    try:
        ini = lineas.index("---") + 1
    except ValueError:
        ini = 0
    chunks = []
    tema, cap, buf = None, None, []

    def cerrar():
        if tema and buf:
            cuerpo = "\n".join(buf).strip()
            if len(cuerpo) > 30:
                chunks.append({"tema": tema, "capitulo": cap or "", "texto": cuerpo})

    for l in lineas[ini:]:
        if l.startswith("# "):                      # capítulo
            cap = l[2:].strip()
            continue
        if l.startswith("## "):                     # nueva sección
            cerrar()
            tema = l[3:].strip()
            buf = []
            continue
        buf.append(l)
    cerrar()
    return chunks


CHUNKS = _cargar_chunks()
_TEXTOS = [f'{c["tema"]} . {c["texto"]}' for c in CHUNKS]


def _indice(textos):
    if not textos:
        return None, None
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), preprocessor=_norm)
    return vec, vec.fit_transform(textos)


_VEC, _MAT = _indice(_TEXTOS)


def buscar(texto: str, k: int = 2, umbral: float = 0.03):
    """Recupera las k secciones de gramática más relacionadas con `texto`."""
    if _VEC is None:
        return []
    q = _VEC.transform([texto])
    sims = linear_kernel(q, _MAT)[0]
    out = []
    for i in sims.argsort()[::-1]:
        if sims[i] < umbral:
            break
        out.append({"tema": CHUNKS[i]["tema"], "capitulo": CHUNKS[i]["capitulo"],
                    "texto": CHUNKS[i]["texto"], "score": round(float(sims[i]), 3)})
        if len(out) >= k:
            break
    return out


def _resumir(texto: str, limite: int = 600) -> str:
    """Acorta un trozo de gramática para no inflar el prompt."""
    t = re.sub(r"<!--.*?-->", "", texto)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t[:limite] + (" […]" if len(t) > limite else "")


def reglas_para_prompt(texto: str, k: int = 2) -> str:
    """Formatea las reglas gramaticales recuperadas para inyectarlas en el prompt."""
    res = buscar(texto, k=k)
    if not res:
        return ""
    bloques = [f'### {r["tema"]}\n{_resumir(r["texto"])}' for r in res]
    return "\n\n".join(bloques)


if __name__ == "__main__":
    print(f"Secciones de gramática indexadas: {len(CHUNKS)}")
    for q in ["nasameth no soy", "aka yuuk", "pa'ka porque", "deícticos abajo arriba"]:
        print(f"\nConsulta: {q!r}")
        for r in buscar(q, k=2):
            print(f"   [{r['score']}] {r['tema']}  ({r['capitulo']})")