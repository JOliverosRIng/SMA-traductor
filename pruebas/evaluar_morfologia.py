"""
EVALUADOR DEL ANALIZADOR MORFOLÓGICO (Paso 2).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Comprueba que, para formas conjugadas cuya RAÍZ está en el diccionario, el
analizador (analizador_morfologico.py) recupera la raíz correcta quitando
afijos conocidos de afijos.json.

Lee pruebas/casos_morfologia.json: cada caso es {palabra, raiz esperada}.
Usa el diccionario real como criterio de raíz válida.

Uso:
  python pruebas/evaluar_morfologia.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traductor
import analizador_morfologico as morf


def main():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos_morfologia.json")
    casos = json.load(open(ruta, encoding="utf-8"))

    es_raiz = lambda w: traductor._clave_ny(w) in traductor.DICC_NY_ES

    print(f"Evaluando {len(casos)} casos de análisis morfológico (NY)...\n")
    aciertos = 0
    for c in casos:
        a = morf.analizar(c["palabra"], es_raiz)
        raiz = a.get("raiz") if a.get("resuelto") else None
        ok = (raiz == c["raiz"])
        aciertos += ok
        marca = "OK  " if ok else "FALLO"
        desc = a.get("descomposicion", "(sin raíz)") if a.get("resuelto") else "(sin raíz)"
        print(f"  [{marca}] {c['palabra']:12s} -> {str(raiz):10s} "
              f"(esperado {c['raiz']:10s})  {desc}")

    n = len(casos)
    print("\n" + "=" * 56)
    print(f"Raíz correcta: {aciertos}/{n} = {100*aciertos/n:.1f}%")
    print("=" * 56)
    return 0 if aciertos == n else 1


if __name__ == "__main__":
    sys.exit(main())
