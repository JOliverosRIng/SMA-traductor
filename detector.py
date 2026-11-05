"""
Agente DETECTOR de intención e idioma de salida.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Qué hace: recibe el prompt crudo del usuario y devuelve DOS cosas:
  - intencion : "traducir"  o  "consultar"
  - direccion : "NY-ES" (salida en español) o "ES-NY" (salida en nasa yuwe)

NO traduce nada. Solo clasifica. Es la entrada del flujo.

Entorno: Qwen local vía Ollama (https://ollama.com).
  1. Instala Ollama.
  2. Descarga el modelo:   ollama pull qwen3:1.7b
  3. Pruébalo:             python detector.py

NOTA: esta es la versión afinada (clasificador al ~95% en el set de prueba).
  - Modelo pequeño (qwen3:1.7b): suficiente y rápido para clasificar.
  - "think": False  -> apaga el razonamiento de Qwen3 (evita timeouts en CPU).
  - num_predict bajo -> la respuesta es un JSON corto, no hace falta más.
"""

import json
import re
import urllib.request

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "qwen3:1.7b"        # clasificar es tarea fácil; el modelo pequeño basta

# ----------------------------------------------------------------------
# Prompt del sistema: define el comportamiento del agente
# ----------------------------------------------------------------------
PROMPT_SISTEMA = """Eres un CLASIFICADOR. Tu única tarea es leer el mensaje del usuario y decidir DOS cosas. NO traduces, NO respondes preguntas, NO saludas, NO explicas.

Idiomas del sistema:
- ES = español (también llamado "castellano")
- NY = nasa yuwe (lengua indígena del pueblo Nasa, del Cauca, Colombia)

Debes decidir:

1) intencion (usa EXACTAMENTE una de estas dos palabras, bien escritas):
   - "traducir"  -> el usuario ORDENA traducir algo. Pistas: "traduce", "tradúceme", "traducir", "convierte", "pasa esto a", "escribe ... en", "dame la traducción de".
   - "consultar" -> el usuario PREGUNTA o quiere saber. Pistas: "qué significa", "qué quiere decir", "significado de", "qué es", "cómo se dice", "cómo se escribe", "cómo digo", "quiero decir", "quiero aprender a decir".

2) direccion (usa EXACTAMENTE uno de estos dos códigos):
   - "NY-ES" -> la SALIDA debe estar en ESPAÑOL.
   - "ES-NY" -> la SALIDA debe estar en NASA YUWE.
   REGLA DE ORO: el segundo código es el idioma de la SALIDA (lo que el usuario quiere recibir).

MUY IMPORTANTE para la dirección:
- NO decidas por el idioma en que está escrito el mensaje: casi siempre el mensaje está en español en los dos casos.
- "en castellano" significa lo mismo que "en español".
- Mencionar "nasa yuwe", "lengua nasa" o "texto nasa yuwe" para describir el texto que se ENTREGA NO significa que la salida sea nasa yuwe. Si te dan un texto que YA está en nasa yuwe y piden traducirlo o explicarlo, la salida es español -> "NY-ES".
- Preguntar el significado de una palabra o frase ("qué significa X", "significado de X", "qué quiere decir X", "qué es X") se responde en ESPAÑOL, salvo que pidan explícitamente la respuesta en nasa yuwe -> "NY-ES".
- Pistas de salida:
  * Salida ESPAÑOL  -> "NY-ES": "al español", "en español", "en castellano", "qué significa", "qué quiere decir", "significado de", "qué es".
  * Salida NASA YUWE -> "ES-NY": "en nasa yuwe", "al nasa yuwe", "a la lengua nasa", "cómo se dice/escribe/digo ... en nasa".
- Si de verdad no hay ninguna pista, asume "NY-ES".

Ejemplos:
Mensaje: "qué significa la palabra fxiçxa"                     -> {"intencion": "consultar", "direccion": "NY-ES"}
Mensaje: "traduce este texto que está en nasa yuwe: pkweçx yũu" -> {"intencion": "traducir", "direccion": "NY-ES"}
Mensaje: "tradúceme al español: kwe'sx yuwe"                    -> {"intencion": "traducir", "direccion": "NY-ES"}
Mensaje: "quiero decir 'buenas noches' en nasa yuwe"            -> {"intencion": "consultar", "direccion": "ES-NY"}
Mensaje: "escribe 'tengo hambre' en nasa yuwe"                  -> {"intencion": "traducir", "direccion": "ES-NY"}

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, con esta forma exacta:
{"intencion": "...", "direccion": "..."}
"""

PLANTILLA_USUARIO = 'Mensaje del usuario: "{prompt}"\n\nResponde solo con el JSON.'


# ----------------------------------------------------------------------
# Llamada al modelo vía Ollama
# ----------------------------------------------------------------------
def llamar_modelo(prompt_usuario: str) -> str:
    """Envía el prompt a Ollama y devuelve el texto crudo de la respuesta."""
    cuerpo = {
        "model": MODELO,
        "system": PROMPT_SISTEMA,
        "prompt": prompt_usuario,
        "stream": False,
        "think": False,            # apaga el razonamiento de Qwen3 (clave en CPU)
        "options": {
            "temperature": 0,      # 0 = determinista, clave para reproducibilidad
            "num_predict": 200,    # la respuesta es un JSON corto
        },
    }
    datos = json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        OLLAMA_URL, data=datos, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(peticion, timeout=300) as resp:
        respuesta = json.loads(resp.read().decode("utf-8"))
    return respuesta.get("response", "")


# ----------------------------------------------------------------------
# Extracción robusta del JSON (por si el modelo agrega texto extra)
# ----------------------------------------------------------------------
def extraer_json(texto: str) -> dict:
    """Busca el primer objeto JSON dentro del texto y lo parsea."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    match = re.search(r"\{.*?\}", texto, flags=re.DOTALL)
    if not match:
        return {"intencion": None, "direccion": None, "error": "sin_json", "crudo": texto}
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"intencion": None, "direccion": None, "error": "json_invalido", "crudo": texto}
    return obj


# ----------------------------------------------------------------------
# Validación de la salida
# ----------------------------------------------------------------------
INTENCIONES = {"traducir", "consultar"}
DIRECCIONES = {"NY-ES", "ES-NY"}

def validar(obj: dict) -> dict:
    """Comprueba que la salida tenga valores permitidos."""
    intencion = obj.get("intencion")
    direccion = obj.get("direccion")
    obj["valido"] = (intencion in INTENCIONES) and (direccion in DIRECCIONES)
    return obj


# ----------------------------------------------------------------------
# Función principal del agente
# ----------------------------------------------------------------------
def detectar(prompt_usuario: str) -> dict:
    """Punto de entrada: recibe el prompt y devuelve {intencion, direccion, valido}."""
    texto_modelo = llamar_modelo(PLANTILLA_USUARIO.format(prompt=prompt_usuario))
    obj = extraer_json(texto_modelo)
    return validar(obj)


# ----------------------------------------------------------------------
# Prueba rápida al ejecutar directamente
# ----------------------------------------------------------------------
if __name__ == "__main__":
    ejemplos = [
        "¿qué significa çxhãçxha?",
        "cómo se dice buenos días en nasa yuwe",
        "traduce al español: ũskatã",
        "quiero decir 'gracias' en nasa yuwe",
    ]
    for e in ejemplos:
        resultado = detectar(e)
        print(f"\nEntrada : {e}")
        print(f"Salida  : {resultado}")