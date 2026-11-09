"""
RECUPERADOR DE GRAMÁTICA (RAG de gramática, v1 — léxico, SIN dependencias).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace: dada una frase/palabra, recupera de la gramática
(rag/gramatica_por_temas.md) las SECCIONES más relacionadas (reglas sobre
afijos, morfemas, orden, etc.), para dárselas al agente traductor como REGLAS.

Usa indice_tfidf (Python puro). Antes dependía de scikit-learn; ya no.
Nota: la fuente es OCR; las palabras nasa yuwe pueden tener errores. Las reglas
en español (lo que más guía al LLM) están limpias.
"""

import os
import re
from indice_tfidf import IndiceTFIDF

_CARPETA = os.path.dirname(os.path.abspath(__file__))
_RUTA = os.path.join(_CARPETA, "rag", "gramatica_por_temas.md")


def _cargar_chunks():
    """Parte la gramática en trozos por sección (encabezados '## ')."""
    if not os.path.exists(_RUTA):
        return []
    lineas = open(_RUTA, encoding="utf-8").read().splitlines()
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
        if l.startswith("# "):
            cap = l[2:].strip()
            continue
        if l.startswith("## "):
            cerrar()
            tema = l[3:].strip()
            buf = []
            continue
        buf.append(l)
    cerrar()
    return chunks


CHUNKS = _cargar_chunks()
_TEXTOS = [f'{c["tema"]} . {c["texto"]}' for c in CHUNKS]
_IDX = IndiceTFIDF(_TEXTOS) if _TEXTOS else None


def buscar(texto, k=2, umbral=0.10):
    """Recupera las k secciones de gramática más relacionadas con `texto`."""
    if _IDX is None:
        return []
    sims = _IDX.similitudes(texto)
    orden = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
    out = []
    for i in orden:
        if sims[i] < umbral:
            break
        out.append({"tema": CHUNKS[i]["tema"], "capitulo": CHUNKS[i]["capitulo"],
                    "texto": CHUNKS[i]["texto"], "score": round(float(sims[i]), 3)})
        if len(out) >= k:
            break
    return out


def _resumir(texto, limite=280):
    t = re.sub(r"<!--.*?-->", "", texto)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t[:limite] + (" […]" if len(t) > limite else "")


def reglas_para_prompt(texto, k=2):
    """Formatea las reglas gramaticales recuperadas para inyectarlas en el prompt."""
    res = buscar(texto, k=k)
    if not res:
        return ""
    return "\n\n".join(f'### {r["tema"]}\n{_resumir(r["texto"])}' for r in res)


if __name__ == "__main__":
    print(f"Secciones de gramática indexadas: {len(CHUNKS)}")
    for q in ["nasameth no soy paez", "deícticos abajo arriba", "aka yuuk dolor"]:
        print(f"\nConsulta: {q!r}")
        for r in buscar(q, k=2):
            print(f"   [{r['score']}] {r['tema']}  ({r['capitulo']})")