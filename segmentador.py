"""
Herramienta: SEGMENTADOR (con detector de idioma por token).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace (determinista, sin LLM):
  1. Tokeniza el prompt: lo parte en palabras, números y signos.
  2. Clasifica CADA token en: ES / NY / SIGNO / DESCONOCIDO.
  3. Calcula porcentajes de cada idioma como metadatos.
  4. Devuelve una lista de segmentos, cada uno con:
     texto, posición, idioma y el método con que se clasificó.

Es la segunda pieza del flujo, después del Detector.
No necesita internet ni modelos. Solo biblioteca estándar de Python.

NOTA sobre la clasificación de idioma:
  Esta versión usa HEURÍSTICAS (reglas) que funcionan sin datos:
   - SIGNO  -> expresiones regulares (puntuación, números).
   - NY     -> marcadores ortográficos del nasa yuwe (ç, glotal ', vocales
               nasales ã ẽ ĩ õ ũ, y grupos consonante+x como çx, tx, nx...).
   - ES     -> lista de palabras frecuentes del español + marcas propias (ñ, tildes).
   - DESCONOCIDO -> no encaja en nada (p. ej. "dhjhdsjja").
  Cuando tengas tus 338 pares, se enchufan dos recursos que suben la precisión:
   - diccionario_ny.txt  (una palabra nasa yuwe por línea)  -> detección NY exacta.
   - palabras_es.txt     (una palabra español por línea)    -> detección ES amplia.
  Si esos archivos existen junto a este script, se cargan automáticamente.
"""

import re
import os
import json
import unicodedata

# ----------------------------------------------------------------------
# 1. TOKENIZADOR
# ----------------------------------------------------------------------
# Tres tipos de token:
#   - numero : secuencias de dígitos (con . o , internos)
#   - palabra: letras (incluye ç, vocales nasales, ñ, tildes) con apóstrofo
#              interno permitido (el apóstrofo marca glotalización en nasa yuwe)
#   - signo  : cualquier otro carácter que no sea espacio
TOKEN_RE = re.compile(
    r"(?P<numero>\d+(?:[.,]\d+)?)"
    r"|(?P<palabra>[^\W\d_]+(?:['’][^\W\d_]+)*)"
    r"|(?P<signo>[^\s\w]|_)",
    re.UNICODE,
)


# ----------------------------------------------------------------------
# 2. RECURSOS (se cargan de archivo si existen; si no, usan lo embebido)
# ----------------------------------------------------------------------
_CARPETA = os.path.dirname(os.path.abspath(__file__))

def _cargar_lista(nombre_archivo):
    """Carga un set de palabras (una por línea, en minúscula) si el archivo existe."""
    ruta = os.path.join(_CARPETA, nombre_archivo)
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return {linea.strip().lower() for linea in f if linea.strip()}
    return set()

# VOCABULARIOS derivados del corpus (conjuntos de palabras conocidas de cada
# idioma, NO significados). Suben mucho la precisión frente a solo heurística.
# Se generan con preparar_vocabularios.py. Si no existen, el Segmentador sigue
# funcionando solo con heurísticas.
VOCAB_NY = _cargar_lista("vocab_ny.txt")

# Lista de español: vocabulario del corpus + lista externa opcional + base embebida
PALABRAS_ES_BASE = {
    # artículos, preposiciones, conjunciones, pronombres frecuentes
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "ante", "con", "contra", "desde", "en", "entre", "hacia", "hasta",
    "para", "por", "segun", "según", "sin", "sobre", "tras", "y", "e", "o", "u",
    "que", "qué", "quien", "quién", "cual", "cuál", "como", "cómo", "cuando",
    "cuándo", "donde", "dónde", "porque", "porqué", "pero", "si", "sí", "no",
    "se", "me", "te", "le", "les", "nos", "lo", "mi", "mis", "tu", "tus", "su",
    "sus", "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso",
    "esta", "aquel", "yo", "tú", "él", "ella", "ellos", "ellas", "nosotros",
    # verbos y palabras del dominio (consultas de traducción)
    "es", "son", "era", "fue", "ser", "estar", "hay", "tiene", "tienen",
    "significa", "significado", "significan", "quiere", "decir", "dice",
    "dicen", "traduce", "traducir", "traduccion", "traducción", "traduzcan",
    "escribe", "escribir", "escribo", "digo", "dice", "pasa", "pasar",
    "convierte", "convertir", "necesito", "quiero", "dime", "aprender",
    "espanol", "español", "castellano", "lengua", "idioma", "palabra",
    "palabras", "frase", "frases", "texto", "oracion", "oración", "nasa",
    "yuwe", "siguiente", "favor", "por_favor",
    # verbos/palabras frecuentes adicionales
    "tengo", "tienes", "tiene", "hay", "hijo", "hijos", "hija", "hijas",
    "casa", "casas", "nada", "algo", "alguien", "todos", "todas", "cada",
    "rápido", "rapido", "lento", "ahora", "aquí", "aqui", "allí", "muy",
    # sustantivos comunes de ejemplo
    "agua", "sol", "dia", "día", "noche", "familia", "nino", "niño",
    "nina", "niña", "perro", "gato", "grande", "pequeno", "pequeño", "corre",
    "buenos", "dias", "días", "gracias", "todo", "mucho", "bien",
}
PALABRAS_ES = PALABRAS_ES_BASE | _cargar_lista("vocab_es.txt") | _cargar_lista("palabras_es.txt")

# Normalización de palabra para comparar contra los vocabularios
_APOSTROFOS = {"’": "'", "‘": "'", "ʼ": "'", "ʻ": "'"}
def _normalizar(p: str) -> str:
    p = unicodedata.normalize("NFC", p)
    for viejo, nuevo in _APOSTROFOS.items():
        p = p.replace(viejo, nuevo)
    return p.lower()


# ----------------------------------------------------------------------
# 3. DETECTOR DE IDIOMA POR TOKEN
# ----------------------------------------------------------------------
# Marcadores ortográficos del nasa yuwe
VOCALES_NASALES_NY = set("ãẽĩõũ")          # vocales nasalizadas (tilde)
CARACTERES_NY = set("çÇ")                  # la ç es típica del nasa yuwe
# Grupos consonante + x (muy característicos: çx, tx, zx, vx, px, kx, nx, sx...)
CLUSTER_X_RE = re.compile(r"[bcçdfgjklmnpqrstvwz]x", re.UNICODE)
# Pre-aspiración / aspiración que el español no usa: kh, th, ph
# (se excluye "dh" por ser un marcador demasiado débil que da falsos positivos)
CLUSTER_ASP_RE = re.compile(r"(kh|th|ph)", re.UNICODE)

# Marcadores propios del español
CARACTERES_ES = set("ñÑ")
VOCALES_TILDE_ES = set("áéíóúÁÉÍÓÚ")

# Cualquier vocal (oral, con tilde, o nasal). Una palabra real SIEMPRE tiene vocal.
VOCALES_TODAS = set("aeiouáéíóúãẽĩõũ")


def _tiene_marcadores_ny(p: str) -> bool:
    """True si la palabra tiene rasgos ortográficos del nasa yuwe."""
    if any(c in CARACTERES_NY for c in p):
        return True
    if any(c in VOCALES_NASALES_NY for c in p):
        return True
    if "'" in p or "’" in p:               # glotalización
        return True
    if CLUSTER_X_RE.search(p):             # consonante + x
        return True
    if CLUSTER_ASP_RE.search(p):           # kh/th/ph/dh
        return True
    return False


def _parece_espanol(p: str) -> bool:
    """True si la palabra parece español (marcas propias), sin rasgos nasa yuwe."""
    if any(c in CARACTERES_ES for c in p):     # ñ
        return True
    if any(c in VOCALES_TILDE_ES for c in p):  # tildes á é í ó ú
        return True
    return False


def clasificar_palabra(palabra: str) -> tuple:
    """
    Clasifica una palabra. Devuelve (idioma, metodo).
    Orden de decisión: diccionario NY -> rasgos NY -> español -> desconocido.
    """
    p = _normalizar(palabra)

    # 1) Palabras CONOCIDAS por vocabulario del corpus (coincidencia exacta)
    if p in VOCAB_NY:
        return "NY", "vocab_ny"
    if p in PALABRAS_ES:
        return "ES", "vocab_es"

    # 2) Guarda lingüística: una palabra desconocida y SIN vocales no es real
    #    (atrapa cadenas tipo "zzxkptr"). Va después de las listas para no
    #    descartar palabras válidas sin vocal como "y".
    if not any(c in VOCALES_TODAS for c in p):
        return "DESCONOCIDO", "sin_vocales"

    # 3) Rasgos ortográficos del nasa yuwe
    if _tiene_marcadores_ny(p):
        return "NY", "ortografia_ny"

    # 4) Marcas propias del español (ñ, tildes)
    if _parece_espanol(p):
        return "ES", "ortografia_es"

    # 5) No encaja en nada conocido
    return "DESCONOCIDO", "ninguno"


# ----------------------------------------------------------------------
# 4. SEGMENTADOR (función principal)
# ----------------------------------------------------------------------
def segmentar(prompt: str) -> dict:
    """
    Recibe el prompt crudo y devuelve:
      {
        "segmentos": [ {texto, posicion, idioma, metodo}, ... ],
        "metadatos": { total_tokens, conteo{...}, porcentajes{...} }
      }
    """
    segmentos = []
    conteo = {"ES": 0, "NY": 0, "SIGNO": 0, "DESCONOCIDO": 0}

    for pos, m in enumerate(TOKEN_RE.finditer(prompt)):
        texto = m.group(0)
        if m.lastgroup == "numero" or m.lastgroup == "signo":
            idioma, metodo = "SIGNO", "regex"
        else:  # palabra
            idioma, metodo = clasificar_palabra(texto)

        conteo[idioma] += 1
        segmentos.append({
            "texto": texto,
            "posicion": pos,
            "idioma": idioma,
            "metodo": metodo,
        })

    total = len(segmentos)
    porcentajes = {
        k: round(100 * v / total, 1) if total else 0.0
        for k, v in conteo.items()
    }

    return {
        "segmentos": segmentos,
        "metadatos": {
            "total_tokens": total,
            "conteo": conteo,
            "porcentajes": porcentajes,
        },
    }


# ----------------------------------------------------------------------
# 5. Prueba rápida al ejecutar directamente
# ----------------------------------------------------------------------
if __name__ == "__main__":
    ejemplos = [
        "¿qué significa çxhãçxha?",
        "cómo se dice buenos días en nasa yuwe",
        "traduce al español: ũskatã",
        "dhjhdsjja que significa",
    ]
    for e in ejemplos:
        r = segmentar(e)
        print(f"\nPrompt: {e}")
        for s in r["segmentos"]:
            print(f"   [{s['posicion']}] {s['texto']!r:20s} -> {s['idioma']:12s} ({s['metodo']})")
        print(f"   Porcentajes: {r['metadatos']['porcentajes']}")
