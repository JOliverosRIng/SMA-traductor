"""
Evaluación del agente Detector.
Mide accuracy sobre los casos de prueba etiquetados a mano.

Uso:  python evaluar.py

Reporta:
  - accuracy de intención
  - accuracy de dirección
  - accuracy conjunta (ambas correctas)
  - matriz de errores (qué casos falló)
  - tasa de salidas inválidas (JSON mal formado o valores no permitidos)
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from detector import detectar

ARCHIVO_CASOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos_detector.json")


def main():
    with open(ARCHIVO_CASOS, encoding="utf-8") as f:
        casos = json.load(f)

    total = len(casos)
    ok_intencion = 0
    ok_direccion = 0
    ok_ambas = 0
    invalidos = 0
    errores = []

    print(f"Evaluando {total} casos...\n")

    for i, caso in enumerate(casos, 1):
        prompt = caso["prompt"]
        esperado_int = caso["intencion"]
        esperado_dir = caso["direccion"]

        pred = detectar(prompt)
        pred_int = pred.get("intencion")
        pred_dir = pred.get("direccion")

        if not pred.get("valido"):
            invalidos += 1

        acierto_int = pred_int == esperado_int
        acierto_dir = pred_dir == esperado_dir

        if acierto_int:
            ok_intencion += 1
        if acierto_dir:
            ok_direccion += 1
        if acierto_int and acierto_dir:
            ok_ambas += 1
        else:
            errores.append({
                "prompt": prompt,
                "esperado": f"{esperado_int} / {esperado_dir}",
                "predicho": f"{pred_int} / {pred_dir}",
            })

        estado = "OK " if (acierto_int and acierto_dir) else "FALLO"
        print(f"[{i:02d}] {estado}  {prompt[:45]:45s}  ->  {pred_int} / {pred_dir}")

    # ---- Resumen ----
    print("\n" + "=" * 55)
    print("RESULTADOS")
    print("=" * 55)
    print(f"Accuracy intención : {ok_intencion}/{total} = {ok_intencion/total:.1%}")
    print(f"Accuracy dirección : {ok_direccion}/{total} = {ok_direccion/total:.1%}")
    print(f"Accuracy conjunta  : {ok_ambas}/{total} = {ok_ambas/total:.1%}")
    print(f"Salidas inválidas  : {invalidos}/{total} = {invalidos/total:.1%}")

    if errores:
        print("\n" + "-" * 55)
        print("CASOS FALLIDOS (revisar)")
        print("-" * 55)
        for e in errores:
            print(f"\n  Prompt   : {e['prompt']}")
            print(f"  Esperado : {e['esperado']}")
            print(f"  Predicho : {e['predicho']}")


if __name__ == "__main__":
    main()
