"""
Herramienta/Agente: TRADUCTOR por diccionario (versión base, sin LLM).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Carga diccionario_ny_es.json y traduce por COINCIDENCIA EXACTA en ambas
direcciones:
  - NY -> ES : busca la palabra nasa yuwe y devuelve su(s) significado(s).
  - ES -> NY : busca la palabra española y devuelve su(s) equivalente(s) NY.

Como hay polisemia (una palabra con varios significados), devuelve TODOS los
candidatos y marca el principal. El agente Traductor real (con LLM) usará esto
como herramienta y elegirá el mejor candidato según el contexto; esta versión
base elige el primero.

No usa Ollama. Solo Python estándar.
"""

import os
import json
import unicodedata

_CARPETA = os.path.dirname(os.path.abspath(__file__))
_APOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t))
    for a, b in _APOS.items():
        t = t.replace(a, b)
    return t.strip().lower()

def _clave_ny(t: str) -> str:
    return _norm(t).rstrip("-").strip()


# ---- carga del diccionario ----
_RUTA = os.path.join(_CARPETA, "diccionario_ny_es.json")
try:
    with open(_RUTA, encoding="utf-8") as f:
        DICC_NY_ES = json.load(f)          # { palabra_ny: [significados...] }
except FileNotFoundError:
    DICC_NY_ES = {}

# índice inverso ES -> [palabras NY]
DICC_ES_NY = {}
for ny, sentidos in DICC_NY_ES.items():
    for s in sentidos:
        DICC_ES_NY.setdefault(_norm(s), [])
        if ny not in DICC_ES_NY[_norm(s)]:
            DICC_ES_NY[_norm(s)].append(ny)


def traducir_token(token: str, direccion: str) -> dict:
    """
    Traduce una palabra. direccion: "NY-ES" o "ES-NY".
    Devuelve: {resuelto, traduccion, alternativas, confianza}
    """
    if direccion == "NY-ES":
        k = _clave_ny(token)
        candidatos = DICC_NY_ES.get(k, [])
    else:  # ES-NY
        k = _norm(token)
        candidatos = DICC_ES_NY.get(k, [])

    if candidatos:
        return {
            "resuelto": True,
            "traduccion": candidatos[0],          # principal
            "alternativas": candidatos[1:],       # otros significados
            "confianza": 1.0 if len(candidatos) == 1 else 0.5,
        }
    return {"resuelto": False, "traduccion": None, "alternativas": [], "confianza": 0.0}


if __name__ == "__main__":
    print("Diccionario cargado:", len(DICC_NY_ES), "palabras NY")
    for t, d in [("aka", "NY-ES"), ("akh", "NY-ES"), ("hola", "ES-NY"), ("agua", "ES-NY")]:
        print(f"\n{t} ({d}):", traducir_token(t, d))
