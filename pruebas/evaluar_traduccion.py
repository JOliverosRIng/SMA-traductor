"""
EVALUADOR DE TRADUCCIÓN (NY -> ES) con chrF + exactitud.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace:
  - Lee pruebas/casos_traduccion.json (frases NY con su traducción de oro).
  - HOLD-OUT: aparta esas frases del RAG y de la memoria (vía recuperador_frases.EXCLUIR)
    para medir GENERALIZACIÓN, no memorización.
  - Para cada caso traduce con el sistema (Detector/Ollama NO hace falta: se fija
    intención=traducir, dirección=NY-ES y se corre segmentador -> traductor -> ensamblador).
  - Calcula chrF y coincidencia exacta.
  - Compara contra una LÍNEA BASE (ensamblaje palabra por palabra, sin LLM): la
    diferencia es lo que aporta el LLM + los RAG (ablación).

Para números reales del LLM, ten OLLAMA corriendo. Sin Ollama, el sistema cae a
respaldo y el resultado coincide con la línea base (sirve para probar el script).

Uso:
  python pruebas/evaluar_traduccion.py
"""

import os
import sys
import json
import collections

# --- permite importar los módulos del proyecto (carpeta padre) ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from estado import ContextoTraduccion
import componentes
import recuperador_frases


# ----------------------------------------------------------------------
# Métrica chrF (F-score de n-gramas de caracteres, beta=2). Aproxima a sacrebleu.
# ----------------------------------------------------------------------
def chrf(hyp: str, ref: str, nmax: int = 6, beta: float = 2.0) -> float:
    def grams(s, n):
        s = "".join(s.lower().split())        # minúsculas, sin espacios
        return collections.Counter(s[i:i + n] for i in range(len(s) - n + 1))
    precs, recs = [], []
    for n in range(1, nmax + 1):
        h, r = grams(hyp, n), grams(ref, n)
        if not h or not r:
            continue
        inter = sum((h & r).values())
        precs.append(inter / sum(h.values()))
        recs.append(inter / sum(r.values()))
    if not precs:
        return 0.0
    P, R = sum(precs) / len(precs), sum(recs) / len(recs)
    if P + R == 0:
        return 0.0
    b2 = beta * beta
    return 100.0 * (1 + b2) * P * R / (b2 * P + R)


def exacta(hyp: str, ref: str) -> bool:
    return hyp.strip().lower() == ref.strip().lower()


# ----------------------------------------------------------------------
# Traducción de una frase: con el sistema completo o solo la línea base.
# ----------------------------------------------------------------------
def traducir(frase_ny: str, linea_base: bool = False) -> str:
    ctx = ContextoTraduccion(prompt=frase_ny)
    ctx.intencion = "traducir"
    ctx.direccion = "NY-ES"
    componentes.c_segmentador(ctx)
    componentes.c_traductor(ctx)
    if linea_base:
        componentes._ensamblar_respaldo(ctx)      # palabra por palabra, sin LLM
    else:
        componentes.c_ensamblador(ctx)            # memoria / LLM + RAG
    return ctx.texto_ensamblado or ""


def main():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos_traduccion.json")
    casos = json.load(open(ruta, encoding="utf-8"))

    # HOLD-OUT: que el RAG y la memoria NO vean las frases de prueba.
    recuperador_frases.EXCLUIR = {recuperador_frases._norm(c["ny"]) for c in casos}

    print(f"Evaluando {len(casos)} frases (hold-out, NY->ES)...\n")
    chrf_sys, chrf_base, exactas = [], [], 0

    for i, c in enumerate(casos, 1):
        ref = c["es"]
        hyp = traducir(c["ny"], linea_base=False)
        base = traducir(c["ny"], linea_base=True)
        cs, cb = chrf(hyp, ref), chrf(base, ref)
        ok = exacta(hyp, ref)
        chrf_sys.append(cs); chrf_base.append(cb); exactas += ok
        print(f"[{i:02d}] chrF={cs:5.1f} (base {cb:4.1f}) {'EXACTA' if ok else '      '}  "
              f"{c['ny'][:28]:28s} -> {hyp[:40]}")

    n = len(casos)
    print("\n" + "=" * 60)
    print("RESULTADOS (NY->ES, frases novedosas)")
    print("=" * 60)
    print(f"chrF promedio (sistema)      : {sum(chrf_sys)/n:5.1f}")
    print(f"chrF promedio (línea base)   : {sum(chrf_base)/n:5.1f}")
    print(f"Aporte del LLM + RAG (chrF)  : {(sum(chrf_sys)-sum(chrf_base))/n:+5.1f}")
    print(f"Coincidencia exacta          : {exactas}/{n} = {100*exactas/n:.1f}%")
    print("\nNota: si 'sistema' == 'línea base', Ollama no estaba corriendo.")


if __name__ == "__main__":
    main()