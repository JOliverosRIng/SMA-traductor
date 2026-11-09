"""
RECUPERADOR DE FRASES (RAG de frases, v1 — léxico, SIN dependencias).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace: dada una frase de entrada, recupera del corpus las frases más
PARECIDAS (similitud léxica: palabras y raíces compartidas) con su traducción,
para dárselas al agente traductor como EJEMPLOS (traducción basada en ejemplos).

Usa indice_tfidf (Python puro, biblioteca estándar). Antes dependía de
scikit-learn; ya no, para evitar problemas de instalación (scipy/DLL en Windows).
BGE-M3 (dense) se puede agregar después como mejora semántica.
"""

import os
import csv
from indice_tfidf import IndiceTFIDF, normalizar as _norm

_CARPETA = os.path.dirname(os.path.abspath(__file__))
_RUTA = os.path.join(_CARPETA, "frases_ny_es.csv")

# Frases (normalizadas) a EXCLUIR de la recuperación. Para la evaluación con
# hold-out: se excluyen las frases de prueba. En producción queda vacío.
EXCLUIR = set()


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
_IDX_NY = IndiceTFIDF(FRASES_NY) if FRASES_NY else None   # consultas en nasa yuwe
_IDX_ES = IndiceTFIDF(FRASES_ES) if FRASES_ES else None   # consultas en español


def buscar(texto, direccion="NY-ES", k=3, umbral=0.05, excluir_identica=False):
    """
    Recupera las k frases más parecidas a `texto`.
    "NY-ES": busca por el lado NASA YUWE -> devuelve (ny, es).
    "ES-NY": busca por el lado ESPAÑOL   -> devuelve (es, ny).
    Devuelve: lista de {origen, destino, score} ordenada por score desc.
    """
    if direccion == "NY-ES":
        idx, orig, dest = _IDX_NY, FRASES_NY, FRASES_ES
    else:
        idx, orig, dest = _IDX_ES, FRASES_ES, FRASES_NY
    if idx is None:
        return []
    sims = idx.similitudes(texto)
    orden = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
    salida = []
    for i in orden:
        if sims[i] < umbral:
            break
        if excluir_identica and _norm(orig[i]) == _norm(texto):
            continue
        if _norm(orig[i]) in EXCLUIR:                 # hold-out de evaluación
            continue
        salida.append({"origen": orig[i], "destino": dest[i],
                       "score": round(float(sims[i]), 3)})
        if len(salida) >= k:
            break
    return salida


def ejemplos_para_prompt(texto, direccion="NY-ES", k=3):
    """Formatea los ejemplos recuperados para inyectarlos en el prompt del traductor."""
    res = buscar(texto, direccion, k=k)
    if not res:
        return ""
    if direccion == "NY-ES":
        return "\n".join(f'- NY: "{r["origen"]}"  =  ES: "{r["destino"]}"' for r in res)
    return "\n".join(f'- ES: "{r["origen"]}"  =  NY: "{r["destino"]}"' for r in res)


if __name__ == "__main__":
    print(f"Corpus de frases: {len(FRASES_NY)}")
    for p in ["aka yuuk", "wala aka yuuk", "yu' ate"]:
        print(f"\nConsulta NY: {p!r}")
        for r in buscar(p, "NY-ES", k=3, excluir_identica=True):
            print(f"   [{r['score']}] {r['origen']}  ->  {r['destino']}")