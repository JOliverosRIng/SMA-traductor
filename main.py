"""
EL MAIN LO QUE HACE ES:
Lee lo que el usuario escribe por teclado, lo pasa por el orquestador y
muestra el resultado y la traza. Es la parte del codigo que tiene contacto
con el usuario.

NOTA: por ahora el Detector, Traductor, Ensamblador, Revisor y Razonador son
STUBS
Stubs: Version provisional, que permite probar antes de terminar todo el flujo
(omite Ollama)
Como salida es provisional del STUB (las palabras NY salen entre ⟨⟩).
Corre solo con VS Code; no necesita Ollama todavía.
"""

import sys
from orquestador import procesar

# FUNCIONES
def mostrar(ctx):
    print("\n *********************")
    print("\n ****  RESULTADO  ****")
    print("\n *********************")
    print("")
    print("Intención :", ctx.intencion)
    print("Dirección :", ctx.direccion)
    print("Salida    :", ctx.respuesta_final)
    if ctx.no_resueltos:
        print("No resueltos:", ctx.no_resueltos)
    print("\nTraza (quién hizo qué):")
    for t in ctx.traza:
        print(f"  - {t['componente']:20s} {t['detalle']}")

# PRINCIPAL
def main():
    if len(sys.argv) > 1:                       # modo directo
        mostrar(procesar(" ".join(sys.argv[1:])))
        return

    print("=================================================================================")
    print("===                                                                           ===")
    print("===  B I E N V E N I D O S  a LegadoLM - sistema multiagente (esqueleto) V.2  ===")
    print("===                                                                           ===")
    print("=================================================================================")
    print("")
    print("Escribe la traducir, luego dale ENTER. Cuando termines simplemente dale ENTER.")
    print("")

    while True:
        try:
            prompt = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not prompt:
            break
        mostrar(procesar(prompt))
    print("\nHasta luego.")


if __name__ == "__main__":
    main()
