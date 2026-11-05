"""
Probador INTERACTIVO del Segmentador.

Dos formas de usarlo:
  1) Interactivo:  python probar_segmentador.py
     Escribe una frase, Enter, y ves cómo se clasifica cada token.
     Enter vacío (o Ctrl+D) para salir.
  2) Directo:      python probar_segmentador.py ¿qué significa çxhãçxha?

Muestra, por cada token: posición, texto, idioma y el método con que se
clasificó (vocab_ny, vocab_es, ortografia_ny, sin_vocales, regex...), más los
porcentajes por idioma y el JSON completo que el Segmentador entrega al resto
del sistema.
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from segmentador import segmentar, VOCAB_NY, PALABRAS_ES


def mostrar(prompt: str):
    r = segmentar(prompt)
    print()
    for s in r["segmentos"]:
        print(f"  [{s['posicion']:>2}] {s['texto']!r:22s} -> {s['idioma']:12s} ({s['metodo']})")
    print("  Porcentajes:", r["metadatos"]["porcentajes"])
    print("  JSON:", json.dumps(r, ensure_ascii=False))


def main():
    # Aviso útil: cuántas palabras cargó de cada vocabulario
    print(f"Segmentador listo. Vocabulario NY: {len(VOCAB_NY)} palabras | "
          f"ES: {len(PALABRAS_ES)} palabras.")

    if len(sys.argv) > 1:          # modo directo
        mostrar(" ".join(sys.argv[1:]))
        return

    print("Modo interactivo. Escribe una frase y Enter (vacío para salir).")
    while True:
        try:
            linea = input("\n> ").strip()
        except EOFError:
            break
        if not linea:
            break
        mostrar(linea)
    print("\nListo.")


if __name__ == "__main__":
    main()
