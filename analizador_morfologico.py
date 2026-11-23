"""
ANALIZADOR MORFOLÓGICO (Paso 2 del ROADMAP) — Python puro, sin dependencias.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace y para qué:
  El traductor por diccionario solo resuelve por COINCIDENCIA EXACTA. El cuello
  de botella de la evaluación fue que muchas palabras "desconocidas" no lo eran:
  eran FORMAS CONJUGADAS cuya raíz SÍ está en el diccionario
  (p. ej. yuuça' -> yuu "venir", uuça' -> uu "morir").

  Este analizador, cuando el diccionario NO encuentra una palabra, intenta
  QUITAR afijos conocidos (de afijos.json) y buscar la RAÍZ en el diccionario.
  Si la raíz existe, devuelve la raíz + las MARCAS gramaticales de los afijos
  quitados (pasado, plural, "con", negación, etc.).

Diseño (desacoplado a propósito):
  - No carga el diccionario ni importa traductor.py (evita import circular).
  - Recibe una función `es_raiz(palabra) -> bool` que dice si una cadena es una
    raíz válida (normalmente: "¿está en el diccionario?"). Así el mismo
    analizador sirve para NY->ES, para pruebas con un dicc. de juguete, etc.

Estrategia (v1, la que recomienda el ROADMAP: empezar por prefijos y sufijos):
  - Los SUFIJOS y los INFIJOS con forma concreta se quitan por el FINAL. En la
    palabra verbal, los infijos (aspecto, negación, distancia) quedan entre la
    raíz y el sufijo modopersonal final; al pelar desde el final se van quitando
    en orden inverso hasta llegar a la raíz.
  - Los PREFIJOS se quitan por el INICIO.
  - Se omiten el morfema cero (aoristo -ø-) y el iterativo (reduplicación), que
    no tienen segmento que quitar. El imperfectivo -V- (una vocal) se intenta
    solo como último recurso y con confianza baja (es ambiguo).
  - Búsqueda en anchura: se prefiere la descomposición con MENOS afijos; a igual
    número, se prueban primero los afijos más largos (para preferir -yáwayá-
    sobre -yá-, etc.).

Devuelve, además de la raíz, la traza de afijos para que el Traductor/Ensamblador
pueda anotar las marcas y para trazabilidad en el paper.
"""

import os
import json
import unicodedata
from collections import deque

_CARPETA = os.path.dirname(os.path.abspath(__file__))
_RUTA_AFIJOS = os.path.join(_CARPETA, "afijos.json")

# Normalización coherente con traductor.py / segmentador.py
_APOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t))
    for a, b in _APOS.items():
        t = t.replace(a, b)
    return t.strip().lower()


# ----------------------------------------------------------------------
# Carga de afijos.json y preparación de las tablas de corte
# ----------------------------------------------------------------------
# Formas que NO se pueden quitar como segmento (morfema cero, reduplicación)
_SIN_SEGMENTO = {"", "ø", "0", "v", "(reduplicación)"}


def _formas(entrada):
    """Todas las formas de un afijo (principal + variantes), normalizadas y sin guiones."""
    crudas = [entrada.get("forma", "")] + list(entrada.get("variantes") or [])
    out = []
    for f in crudas:
        f = _norm(f).strip("-").strip()
        if "(" in f or f in _SIN_SEGMENTO:
            continue
        out.append(f)
    return out


def _cargar_afijos(ruta=_RUTA_AFIJOS):
    """Devuelve (prefijos, sufijos_fin, vocales_impf) listas de (forma, info)."""
    prefijos, sufijos_fin, vocales_impf = [], [], []
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return prefijos, sufijos_fin, vocales_impf

    for a in data.get("afijos", []):
        info = {"id": a.get("id"), "glosa": a.get("glosa"),
                "funcion": a.get("funcion"), "categoria": a.get("categoria"),
                "tipo": a.get("tipo")}
        for forma in _formas(a):
            if a.get("tipo") == "prefijo":
                prefijos.append((forma, info))
            elif a.get("id") == "IMPF" or (len(forma) == 1 and forma in "aeiou"):
                # vocal del imperfectivo: ambigua, se intenta al final
                vocales_impf.append((forma, info))
            else:  # sufijo o infijo con forma concreta -> se quita por el final
                sufijos_fin.append((forma, info))

    # Afijos más largos primero (preferimos el corte más específico).
    prefijos.sort(key=lambda x: len(x[0]), reverse=True)
    sufijos_fin.sort(key=lambda x: len(x[0]), reverse=True)
    # vocales: únicas
    vistas, vi = set(), []
    for f, info in vocales_impf:
        if f not in vistas:
            vistas.add(f)
            vi.append((f, info))
    return prefijos, sufijos_fin, vi


PREFIJOS, SUFIJOS_FIN, VOCALES_IMPF = _cargar_afijos()


# ----------------------------------------------------------------------
# Analizador
# ----------------------------------------------------------------------
def analizar(palabra, es_raiz, max_afijos=4, min_raiz=2, usar_impf=True):
    """
    Intenta explicar `palabra` como RAÍZ + afijos conocidos.

    Parámetros:
      palabra   : str, la palabra NY a analizar.
      es_raiz   : callable(str) -> bool. True si la cadena es raíz válida
                  (normalmente: está en el diccionario).
      max_afijos: tope de afijos a quitar (profundidad de búsqueda).
      min_raiz  : longitud mínima de la raíz candidata (evita raíces basura);
                  se ignora si la raíz es exactamente una entrada válida.
      usar_impf : si True, como último recurso intenta quitar la vocal del
                  imperfectivo (ambigua, confianza menor).

    Devuelve un dict:
      {resuelto: True, raiz, marcas:[glosas], afijos:[info...],
       descomposicion:str, n_afijos:int, confianza:float}
      o {resuelto: False} si no encontró ninguna raíz válida.
    """
    pal = _norm(palabra).strip("-").strip()
    if not pal:
        return {"resuelto": False}

    # Si ya es raíz, no hay nada que analizar (el llamador debería haberlo
    # resuelto antes; lo contemplamos por robustez).
    if es_raiz(pal):
        return {"resuelto": True, "raiz": pal, "marcas": [], "afijos": [],
                "descomposicion": pal, "n_afijos": 0, "confianza": 1.0}

    # Estado de búsqueda: (cadena_actual, afijos_quitados[list de info], uso_impf_bool)
    # BFS por número de afijos: la primera solución tiene el MENOR número de cortes.
    inicio = (pal, (), 0)
    cola = deque([inicio])
    vistos = {pal}

    mejor = None
    while cola:
        actual, quitados, impf_usado = cola.popleft()
        n = len(quitados)
        if n >= max_afijos:
            continue

        # Generar vecinos quitando un afijo (sufijo/infijo por el final, prefijo por el inicio)
        vecinos = []  # (nueva_cadena, info, es_impf)

        for forma, info in SUFIJOS_FIN:
            if actual.endswith(forma) and len(actual) - len(forma) >= 1:
                vecinos.append((actual[: -len(forma)], info, 0))

        for forma, info in PREFIJOS:
            if actual.startswith(forma) and len(actual) - len(forma) >= 1:
                vecinos.append((actual[len(forma):], info, 0))

        # Imperfectivo (vocal final): solo como último recurso y una sola vez.
        if usar_impf and impf_usado == 0:
            for forma, info in VOCALES_IMPF:
                if actual.endswith(forma) and len(actual) - len(forma) >= 1:
                    vecinos.append((actual[: -len(forma)], info, 1))

        for nueva, info, es_impf in vecinos:
            # ¿Es raíz válida?
            if es_raiz(nueva) and (len(nueva) >= min_raiz or es_raiz(nueva)):
                cand = {
                    "resuelto": True,
                    "raiz": nueva,
                    "afijos": list(quitados) + [info],
                    "n_afijos": n + 1,
                    "uso_impf": impf_usado or es_impf,
                }
                # Primera solución encontrada = menor número de afijos (BFS). La devolvemos.
                return _finalizar(cand)
            # Encolar para seguir pelando
            if nueva not in vistos:
                vistos.add(nueva)
                cola.append((nueva, tuple(quitados) + (info,), impf_usado or es_impf))

    return mejor or {"resuelto": False}


def _finalizar(cand):
    """Completa marcas, descomposición y confianza."""
    afijos = cand["afijos"]
    cand["marcas"] = [a.get("glosa") for a in afijos if a.get("glosa")]
    # descomposición legible: raiz-GLOSA1-GLOSA2...
    cand["descomposicion"] = "-".join([cand["raiz"]] + cand["marcas"])
    # confianza: baja con el nº de afijos y si usó la vocal ambigua del imperfectivo
    conf = max(0.3, 0.9 - 0.15 * (cand["n_afijos"] - 1))
    if cand.get("uso_impf"):
        conf -= 0.1
    cand["confianza"] = round(conf, 2)
    return cand


# ----------------------------------------------------------------------
# Prueba rápida (con un diccionario de juguete) al ejecutar directamente
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Afijos cargados: {len(PREFIJOS)} prefijos, {len(SUFIJOS_FIN)} sufijos/infijos, "
          f"{len(VOCALES_IMPF)} vocales IMPF")

    # Mini-diccionario de prueba (raíces reales del diccionario del proyecto)
    RAICES = {"yuu", "uu", "yat", "misx", "nasa", "um", "wala", "kite", "deh"}
    es_raiz = lambda w: w in RAICES

    pruebas = ["yuuça'", "uuça'", "yatte", "misxa's", "nasameth",
               "yatkwe", "umuth", "walag", "kitek", "dehg"]
    for w in pruebas:
        r = analizar(w, es_raiz)
        if r["resuelto"]:
            print(f"  {w:12} -> {r['descomposicion']:22} "
                  f"(raíz={r['raiz']}, marcas={r['marcas']}, conf={r['confianza']})")
        else:
            print(f"  {w:12} -> (sin raíz conocida)")
