"""
Prepara los recursos del TRADUCTOR a partir del corpus en Excel.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Lee el Excel (todas las hojas), limpia y normaliza, y genera:
  1. diccionario_ny_es.json  -> { palabra_ny: [significados...] }  (nivel = palabra)
  2. frases_ny_es.csv        -> pares de frases (nivel = frase), para RAG/evaluación
  3. corpus_limpio.csv       -> tabla completa limpia (trazabilidad para el paper)

Uso:
  python preparar_diccionario.py corpus_frases_palabras_nasayuwe_v1_1.xlsx

Requisitos: pandas, openpyxl   (pip install pandas openpyxl)
"""

import sys
import json
import re
import unicodedata
import pandas as pd

COLUMNAS = ["id", "nivel", "nasayuwe", "espanol", "categoria",
            "fuente", "variante", "validado", "notas"]


# ----------------------------------------------------------------------
# Normalización
# ----------------------------------------------------------------------
# Unifica las variantes de apóstrofo (glotal) a una sola: ' (U+0027)
APOSTROFOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}

def normalizar_texto(t: str) -> str:
    """Normaliza un texto: NFC, unifica apóstrofos, colapsa espacios, recorta."""
    t = unicodedata.normalize("NFC", str(t))
    for viejo, nuevo in APOSTROFOS.items():
        t = t.replace(viejo, nuevo)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def clave_ny(palabra: str) -> str:
    """Clave normalizada para el diccionario: minúsculas y sin guion de lema final."""
    p = normalizar_texto(palabra).lower()
    p = p.rstrip("-").strip()
    return p


# ----------------------------------------------------------------------
# Carga y limpieza del Excel
# ----------------------------------------------------------------------
def cargar_corpus(ruta_excel: str) -> pd.DataFrame:
    xl = pd.ExcelFile(ruta_excel)
    frames = []
    for hoja in xl.sheet_names:
        df = pd.read_excel(ruta_excel, sheet_name=hoja)
        # conserva solo las columnas estándar que existan
        cols = [c for c in COLUMNAS if c in df.columns]
        df = df[cols].copy()
        df["hoja"] = hoja
        frames.append(df)

    corpus = pd.concat(frames, ignore_index=True)

    # descarta filas sin par nasayuwe/espanol
    corpus = corpus.dropna(subset=["nasayuwe", "espanol"])
    corpus["nasayuwe"] = corpus["nasayuwe"].apply(normalizar_texto)
    corpus["espanol"] = corpus["espanol"].apply(normalizar_texto)
    corpus = corpus[(corpus["nasayuwe"] != "") & (corpus["espanol"] != "")]

    # normaliza la etiqueta de nivel
    corpus["nivel"] = corpus["nivel"].astype(str).str.strip().str.lower()

    # quita duplicados exactos de par
    corpus = corpus.drop_duplicates(subset=["nasayuwe", "espanol"]).reset_index(drop=True)
    return corpus


# ----------------------------------------------------------------------
# Construcción de los recursos
# ----------------------------------------------------------------------
def construir_diccionario(corpus: pd.DataFrame) -> dict:
    """palabra_ny (clave normalizada) -> lista de significados únicos (orden preservado)."""
    palabras = corpus[corpus["nivel"] == "palabra"]
    dic = {}
    for _, fila in palabras.iterrows():
        k = clave_ny(fila["nasayuwe"])
        if not k:
            continue
        significado = fila["espanol"].strip()
        dic.setdefault(k, [])
        if significado not in dic[k]:
            dic[k].append(significado)
    return dic


def main():
    if len(sys.argv) < 2:
        print("Uso: python preparar_diccionario.py <archivo.xlsx>")
        sys.exit(1)
    ruta = sys.argv[1]

    corpus = cargar_corpus(ruta)
    print(f"Pares únicos cargados: {len(corpus)}")
    print(f"  palabras: {(corpus['nivel']=='palabra').sum()}")
    print(f"  frases  : {(corpus['nivel']=='frase').sum()}")

    # 1) Diccionario de palabras
    dic = construir_diccionario(corpus)
    with open("diccionario_ny_es.json", "w", encoding="utf-8") as f:
        json.dump(dic, f, ensure_ascii=False, indent=1, sort_keys=True)
    multi = sum(1 for v in dic.values() if len(v) > 1)
    print(f"\ndiccionario_ny_es.json  -> {len(dic)} palabras NY "
          f"({multi} con 2+ significados)")

    # 2) Frases (para RAG / evaluación)
    frases = corpus[corpus["nivel"] == "frase"][["nasayuwe", "espanol", "fuente", "variante"]]
    frases.to_csv("frases_ny_es.csv", index=False, encoding="utf-8")
    print(f"frases_ny_es.csv        -> {len(frases)} frases")

    # 3) Corpus limpio completo (trazabilidad)
    corpus.to_csv("corpus_limpio.csv", index=False, encoding="utf-8")
    print(f"corpus_limpio.csv       -> {len(corpus)} filas (todas las columnas)")

    # Muestra
    print("\nEjemplos del diccionario (palabra -> significados):")
    for k in list(dic)[:5]:
        print(f"   {k!r}: {dic[k]}")


if __name__ == "__main__":
    main()
