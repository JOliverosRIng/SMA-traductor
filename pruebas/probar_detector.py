"""
Probador INTERACTIVO del Detector real (usa Qwen vía Ollama).

Prerrequisito: Ollama corriendo y el modelo bajado (ollama pull qwen3:4b).

Uso:
  python probar_detector.py                      -> interactivo (escribes frases)
  python probar_detector.py como digo hola en nasa  -> directo (una frase)

Para cada frase muestra lo que el Detector decide: intención y dirección.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from detector import detectar, MODELO


def mostrar(prompt: str):
    r = detectar(prompt)
    print(f"\n  Prompt    : {prompt}")
    print(f"  Intención : {r.get('intencion')}")
    print(f"  Dirección : {r.get('direccion')}")
    print(f"  Válido    : {r.get('valido')}")
    if not r.get("valido"):
        print(f"  (salida cruda del modelo: {r})")


def main():
    print(f"Detector real — modelo: {MODELO} (vía Ollama).")

    if len(sys.argv) > 1:                       # modo directo
        mostrar(" ".join(sys.argv[1:]))
        return

    print("Modo interactivo. Escribe una frase y Enter (vacío para salir).")
    while True:
        try:
            linea = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not linea:
            break
        mostrar(linea)
    print("\nListo.")


if __name__ == "__main__":
    main()
