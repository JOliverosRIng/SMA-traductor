"""
Agente TRADUCTOR / RAZONADOR con LLM (Qwen vía Ollama), ANCLADO al diccionario.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Idea central (y principio del proyecto): el LLM NO sabe nasa yuwe y NO debe
inventarlo. El diccionario es la única fuente de verdad del nasa yuwe. El LLM
solo RAZONA en la lengua de alto recurso (español): elige el significado
correcto cuando hay polisemia y redacta una salida natural, usando SOLO los
candidatos que le entrega el diccionario (grounding).

Dos funciones públicas:
  - traducir(prompt, direccion, items, no_resueltos) -> {"traduccion", "valido"}
  - explicar(prompt, direccion, items)               -> {"respuesta",  "valido"}

Ambas lanzan excepción si Ollama no responde; el que llama (componentes.py)
atrapa el error y usa un respaldo determinista. Así el sistema nunca se cae.

Entorno: Qwen local vía Ollama. Modelo: qwen3:1.7b (mismo del Detector).
"""

import json
import re
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "qwen3:4b"


# ----------------------------------------------------------------------
# Llamada genérica a Ollama (reutilizable)
# ----------------------------------------------------------------------
def llamar_ollama(system: str, user: str, num_predict: int = 400,
                  timeout: int = 300) -> str:
    """Envía (system + user) a Ollama y devuelve el texto crudo de la respuesta."""
    cuerpo = {
        "model": MODELO,
        "system": system,
        "prompt": user,
        "stream": False,
        "think": False,              # sin razonamiento interno: más rápido en CPU
        "options": {
            "temperature": 0,        # determinista -> reproducible
            "num_predict": num_predict,
        },
    }
    datos = json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        OLLAMA_URL, data=datos, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(peticion, timeout=timeout) as resp:
        respuesta = json.loads(resp.read().decode("utf-8"))
    return respuesta.get("response", "")


def _extraer_json(texto: str) -> dict:
    """Quita <think> y devuelve el primer objeto JSON del texto (o {})."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    match = re.search(r"\{.*?\}", texto, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _glosario(items: list) -> str:
    """Convierte los candidatos del diccionario en un glosario legible.
    items: [{"origen": palabra, "candidatos": [sig1, sig2, ...]}, ...]
    """
    if not items:
        return "(ninguna palabra encontrada en el diccionario)"
    lineas = []
    for it in items:
        cands = "; ".join(it["candidatos"]) if it["candidatos"] else "(sin dato)"
        lineas.append(f'- "{it["origen"]}" = {cands}')
    return "\n".join(lineas)


# ----------------------------------------------------------------------
# Prompts del sistema (uno por dirección y tarea)
# ----------------------------------------------------------------------
SYS_TRAD_NY_ES = """Eres un TRADUCTOR de nasa yuwe (NY) a español (ES).
Te doy la frase del usuario, un GLOSARIO con el significado en español de cada palabra nasa yuwe (de un diccionario validado) y EJEMPLOS de frases parecidas ya traducidas (de un corpus).

Reglas estrictas:
- Traduce al español SOLO el contenido en nasa yuwe. Ignora las instrucciones del usuario ("traduce", "al español", ":", etc.).
- Usa EXCLUSIVAMENTE los significados del glosario. Si una palabra tiene varios significados, elige el que mejor encaje en el contexto (resuelve la polisemia).
- Usa los EJEMPLOS como guía de estructura, orden y estilo de la traducción; NO copies un ejemplo si no corresponde a la frase.
- Usa las REGLAS GRAMATICALES para interpretar palabras flexionadas o afijos que no estén en el glosario (negación, tiempos, aspecto, subordinadores, etc.); no inventes más allá de lo que digan.
- NO inventes significados que no estén en el glosario ni en los ejemplos.
- Si una palabra aparece en "palabras sin equivalente", déjala tal cual entre ⟨ ⟩.
- Redacta una sola oración natural y gramatical en español.

Responde ÚNICAMENTE con JSON, sin texto extra: {"traduccion": "..."}
"""

SYS_TRAD_ES_NY = """Eres un ENSAMBLADOR de español (ES) a nasa yuwe (NY).
NO sabes nasa yuwe por tu cuenta: SOLO puedes usar las palabras nasa yuwe del GLOSARIO y de los EJEMPLOS que te doy.
Te doy la frase del usuario, por cada palabra española de contenido su(s) equivalente(s) en nasa yuwe, y EJEMPLOS de frases parecidas ya traducidas.

Reglas estrictas:
- Construye la frase en nasa yuwe usando SOLO los equivalentes del glosario. Si hay varios, elige el más general.
- NO inventes ninguna palabra nasa yuwe. Si falta el equivalente de una palabra, déjala en español entre ⟨ ⟩.
- Usa las REGLAS GRAMATICALES para ordenar y afijar correctamente (p. ej. qué sufijo marca negación o subordinación); no inventes afijos que no aparezcan.
- Ignora las instrucciones del usuario ("traduce", "en nasa yuwe", ":", etc.).
- Une los equivalentes en el orden de la frase original; no garantizas la gramática del nasa yuwe.

Responde ÚNICAMENTE con JSON, sin texto extra: {"traduccion": "..."}
"""

SYS_CONSULTA = """Eres un ASISTENTE que explica, EN ESPAÑOL, el significado de palabras nasa yuwe.
Te doy la pregunta del usuario y un GLOSARIO con los significados de cada palabra (de un diccionario validado).

Reglas estrictas:
- Responde en español, breve y claro (1 o 2 frases).
- Usa SOLO la información del glosario; NO inventes significados.
- Si una palabra tiene varios significados, menciónalos todos.
- Si el glosario está vacío, di que esa palabra no está en el diccionario.

Responde ÚNICAMENTE con JSON, sin texto extra: {"respuesta": "..."}
"""

PLANTILLA_TRAD = (
    'Frase del usuario: "{prompt}"\n\n'
    "GLOSARIO (significados permitidos del diccionario):\n{glosario}\n\n"
    "EJEMPLOS de frases parecidas ya traducidas (guía de estructura):\n{ejemplos}\n\n"
    "REGLAS GRAMATICALES de referencia (afijos, morfemas, orden):\n{reglas}\n\n"
    "Palabras sin equivalente: {faltan}\n\n"
    "Responde solo con el JSON."
)

PLANTILLA_CONSULTA = (
    'Pregunta del usuario: "{prompt}"\n\n'
    "GLOSARIO (única fuente permitida):\n{glosario}\n\n"
    "Responde solo con el JSON."
)


# ----------------------------------------------------------------------
# Funciones públicas
# ----------------------------------------------------------------------
def traducir(prompt: str, direccion: str, items: list, no_resueltos: list,
             ejemplos: str = "", reglas: str = "") -> dict:
    """Traduce la frase usando el glosario del diccionario, ejemplos de frases
    parecidas (RAG de frases) y reglas gramaticales (RAG de gramática).
    Devuelve {traduccion, valido}."""
    system = SYS_TRAD_NY_ES if direccion == "NY-ES" else SYS_TRAD_ES_NY
    faltan = ", ".join(no_resueltos) if no_resueltos else "ninguna"
    user = PLANTILLA_TRAD.format(
        prompt=prompt, glosario=_glosario(items),
        ejemplos=ejemplos or "(no hay frases parecidas en el corpus)",
        reglas=reglas or "(no se recuperaron reglas)",
        faltan=faltan)
    crudo = llamar_ollama(system, user, num_predict=400)
    obj = _extraer_json(crudo)
    trad = obj.get("traduccion")
    return {"traduccion": trad, "valido": isinstance(trad, str) and bool(trad.strip())}


def explicar(prompt: str, direccion: str, items: list) -> dict:
    """Explica en español el significado de las palabras consultadas. Devuelve {respuesta, valido}."""
    user = PLANTILLA_CONSULTA.format(prompt=prompt, glosario=_glosario(items))
    crudo = llamar_ollama(SYS_CONSULTA, user, num_predict=300)
    obj = _extraer_json(crudo)
    resp = obj.get("respuesta")
    return {"respuesta": resp, "valido": isinstance(resp, str) and bool(resp.strip())}


# ----------------------------------------------------------------------
# Prueba directa (requiere Ollama corriendo)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    items_demo = [{"origen": "aka", "candidatos": ["dolor"]}]
    print("TRAD NY-ES:", traducir("traduce aka al español", "NY-ES", items_demo, []))
    print("CONSULTA  :", explicar("qué significa aka", "NY-ES", items_demo))