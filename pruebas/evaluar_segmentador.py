"""
Evaluación del SEGMENTADOR.
Mide accuracy a nivel de TOKEN: compara el idioma predicho de cada token
contra la etiqueta esperada (hecha a mano en casos_prueba_segmentador.json).

Uso:  python evaluar_segmentador.py

Reporta:
  - accuracy global por token
  - accuracy por clase (ES, NY, SIGNO, DESCONOCIDO)
  - matriz de confusión simple (qué se confundió con qué)
  - detalle de los tokens mal clasificados
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from segmentador import segmentar

ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos_segmentador.json")
CLASES = ["ES", "NY", "SIGNO", "DESCONOCIDO"]


def main():
    with open(ARCHIVO, encoding="utf-8") as f:
        casos = json.load(f)

    total = 0
    aciertos = 0
    por_clase_total = {c: 0 for c in CLASES}
    por_clase_ok = {c: 0 for c in CLASES}
    confusion = {}   # (esperado, predicho) -> cuenta
    errores = []

    for caso in casos:
        prompt = caso["prompt"]
        esperado = caso["esperado"]
        pred = [s["idioma"] for s in segmentar(prompt)["segmentos"]]

        # Si el número de tokens no coincide, lo reportamos (fallo de tokenización)
        if len(pred) != len(esperado):
            errores.append(
                f"[TOKENIZACIÓN] '{prompt}': esperados {len(esperado)} tokens, "
                f"obtenidos {len(pred)} -> {pred}"
            )
            continue

        for texto_token, esp, prd in zip(
            [s["texto"] for s in segmentar(prompt)["segmentos"]], esperado, pred
        ):
            total += 1
            por_clase_total[esp] += 1
            if esp == prd:
                aciertos += 1
                por_clase_ok[esp] += 1
            else:
                confusion[(esp, prd)] = confusion.get((esp, prd), 0) + 1
                errores.append(
                    f"  '{prompt}'  token {texto_token!r}: esperado {esp}, predicho {prd}"
                )

    # ---- Resumen ----
    print("=" * 55)
    print("RESULTADOS DEL SEGMENTADOR (accuracy por token)")
    print("=" * 55)
    if total:
        print(f"Accuracy global: {aciertos}/{total} = {aciertos/total:.1%}\n")
    print("Accuracy por clase:")
    for c in CLASES:
        t = por_clase_total[c]
        ok = por_clase_ok[c]
        pct = f"{ok/t:.1%}" if t else "s/d"
        print(f"   {c:12s}: {ok}/{t} = {pct}")

    if confusion:
        print("\nConfusiones (esperado -> predicho):")
        for (esp, prd), n in sorted(confusion.items(), key=lambda x: -x[1]):
            print(f"   {esp:12s} -> {prd:12s}: {n}")

    if errores:
        print("\nDetalle de errores:")
        for e in errores:
            print(e)
    else:
        print("\n¡Sin errores! Todos los tokens se clasificaron como se esperaba.")


if __name__ == "__main__":
    main()
