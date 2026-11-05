"""
Genera los VOCABULARIOS de idioma para el Segmentador, desde el corpus limpio.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

IMPORTANTE: esto NO es el diccionario (palabra->significado), que es del Traductor.
Aquí solo extraemos CONJUNTOS de palabras conocidas de cada idioma (pertenencia),
para que el Segmentador clasifique por coincidencia exacta antes que por heurística.

Qué hace:
  - Lee corpus_limpio.csv (columnas: nasayuwe, espanol, nivel, ...).
  - Tokeniza AMBOS lados con el MISMO tokenizador del Segmentador.
  - Junta las palabras de cada idioma, normalizadas.
  - Quita del vocabulario NY las palabras que también son españolas (ambiguas),
    para no forzar a NY una palabra que el español ya usa.
  - Escribe vocab_ny.txt y vocab_es.txt (una palabra por línea).

Uso:
  python preparar_vocabularios.py ../traductor/corpus_limpio.csv
"""

import sys
import os
import csv
import re
import unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from segmentador import TOKEN_RE, PALABRAS_ES_BASE, VOCALES_TODAS

APOSTROFOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}

def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t))
    for viejo, nuevo in APOSTROFOS.items():
        t = t.replace(viejo, nuevo)
    return t.strip().lower()

def palabras_de(texto: str):
    """Extrae solo los tokens de tipo 'palabra' (no números ni signos)."""
    salida = []
    for m in TOKEN_RE.finditer(normalizar(texto)):
        if m.lastgroup == "palabra":
            w = m.group(0).strip("-").strip()
            if w and any(c in VOCALES_TODAS for c in w):  # descarta restos sin vocal
                salida.append(w)
    return salida


def main():
    if len(sys.argv) < 2:
        print("Uso: python preparar_vocabularios.py <corpus_limpio.csv>")
        sys.exit(1)
    ruta = sys.argv[1]

    vocab_ny, vocab_es = set(), set()
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            vocab_ny.update(palabras_de(fila.get("nasayuwe", "")))
            vocab_es.update(palabras_de(fila.get("espanol", "")))

    # El español embebido también cuenta como español conocido
    vocab_es |= {normalizar(w) for w in PALABRAS_ES_BASE}

    # Palabras ambiguas (aparecen en los dos idiomas): se quitan de NY
    # para que el español no se confunda; quedarán para las heurísticas.
    ambiguas = vocab_ny & vocab_es
    vocab_ny -= ambiguas

    with open("vocab_ny.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(vocab_ny)))
    with open("vocab_es.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(vocab_es)))

    print(f"vocab_ny.txt -> {len(vocab_ny)} palabras nasa yuwe")
    print(f"vocab_es.txt -> {len(vocab_es)} palabras español")
    print(f"(palabras ambiguas quitadas de NY: {len(ambiguas)})")


if __name__ == "__main__":
    main()
