"""
MVP WEB (Tarea B del PLAN) — Traductor / Consultor Nasa Yuwe (NY) <-> Español (ES).
Proyecto: Traductor Nasa Yuwe, sistema multiagente.

Interfaz web con Gradio. UNA sola caja de texto: el usuario escribe en español
con naturalidad ("¿qué significa yuuça'?", "¿cómo se dice casa en nasa yuwe?",
"traduce Yat kluu") y el SISTEMA decide solo:
  - la INTENCIÓN  (consultar / traducir)  -> Detector (Qwen, con respaldo heurístico)
  - la DIRECCIÓN  (NY->ES / ES->NY)        -> Detector
No se le pide nada manual al usuario: esa es la gracia del sistema multiagente.

Qué hace con cada intención (lo decide el pipeline, no la UI):
  - CONSULTAR: responde en español el significado / el equivalente, anclado al
    diccionario (Razonador; respaldo determinista si Ollama no está).
  - TRADUCIR: arma la frase con el Ensamblador (LLM si Ollama está; si no, respaldo).

Honestidad (PLAN B3): nunca se muestra ⟨palabra?⟩ crudo; las palabras que no están
en el diccionario se listan aparte con claridad.

Cómo correr:
    pip install gradio
    python app.py                 # local (http://127.0.0.1:7860)
    python app.py --share         # enlace público temporal (demo/sustentación)

Principio innegociable: el LLM nunca inventa nasa yuwe. El diccionario, el corpus
y la gramática son la fuente de verdad.
"""

import sys
import re
import urllib.request

# --- consola UTF-8 (Windows cp1252 no imprime ũ, ç, etc.) ---
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from orquestador import procesar

OLLAMA_URL_TAGS = "http://localhost:11434/api/tags"

_INTENCION_TXT = {"consultar": "consulta", "traducir": "traducción"}
_DIRECCION_TXT = {"NY-ES": "Nasa Yuwe → Español", "ES-NY": "Español → Nasa Yuwe"}


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def ollama_disponible(timeout: float = 1.5) -> bool:
    """True si Ollama responde (solo para avisar al usuario, no bloquea nada)."""
    try:
        with urllib.request.urlopen(OLLAMA_URL_TAGS, timeout=timeout):
            return True
    except Exception:
        return False


def _limpiar_para_usuario(texto: str):
    """Quita los ⟨palabra?⟩ crudos (PLAN B3) y devuelve (texto_limpio, [no_encontradas])."""
    if not texto:
        return texto, []
    no_encontradas = re.findall(r"⟨\s*([^⟩?]+?)\s*\??\s*⟩", texto)
    limpio = re.sub(r"⟨\s*([^⟩?]+?)\s*\??\s*⟩", r"\1", texto)
    limpio = re.sub(r"\s+([,.;:!?])", r"\1", limpio).strip()
    vistas, unicas = set(), []
    for p in no_encontradas:
        p = p.strip()
        if p and p.lower() not in vistas:
            vistas.add(p.lower())
            unicas.append(p)
    return limpio, unicas


def _palabras_reconocidas(ctx):
    """Glosario de lo que el diccionario SÍ resolvió (transparencia)."""
    direccion = ctx.direccion or "NY-ES"
    origen = "NY" if direccion == "NY-ES" else "ES"
    lineas = []
    for s in ctx.segmentos:
        if s.get("idioma") == origen and s.get("resuelto"):
            sentidos = "; ".join([s["traduccion"]] + list(s.get("alternativas") or []))
            if s.get("via") == "morfologia":
                marcas = ", ".join(s.get("marcas") or []) or "sin marcas"
                lineas.append(f"- **{s['texto']}** = {sentidos}  "
                              f"_(raíz «{s.get('raiz')}»; marcas: {marcas})_")
            else:
                lineas.append(f"- **{s['texto']}** = {sentidos}")
    return lineas


def _traza_md(ctx) -> str:
    if not ctx.traza:
        return "_(sin traza)_"
    return "\n".join(f"- **{t['componente']}** — {t['detalle']}" for t in ctx.traza)


# ----------------------------------------------------------------------
# Lógica principal: una entrada, el sistema decide todo
# ----------------------------------------------------------------------
def responder(prompt: str):
    prompt = (prompt or "").strip()
    if not prompt:
        return "Escribe una palabra o frase (en español).", "", "_(sin traza)_"

    ctx = procesar(prompt)   # Detector decide intención + dirección; corre todo el pipeline

    intencion = _INTENCION_TXT.get(ctx.intencion, ctx.intencion or "?")
    direccion = _DIRECCION_TXT.get(ctx.direccion, ctx.direccion or "?")
    cabecera = f"**El sistema detectó:** {intencion} · {direccion}\n\n"

    limpio, faltantes = _limpiar_para_usuario(ctx.respuesta_final or "")
    if limpio:
        cuerpo = f"### Respuesta\n{limpio}"
    else:
        cuerpo = "### Respuesta\nNo se pudo construir una respuesta."

    if faltantes:
        lista = ", ".join(f"«{p}»" for p in faltantes)
        cuerpo += f"\n\n⚠️ No está en el diccionario: {lista}."

    # Panel de transparencia: qué palabras reconoció el diccionario.
    reconocidas = _palabras_reconocidas(ctx)
    detalle = ("**Palabras reconocidas en el diccionario:**\n" + "\n".join(reconocidas)) \
        if reconocidas else "_(ninguna palabra encontrada en el diccionario)_"

    return cabecera + cuerpo, detalle, _traza_md(ctx)


# ----------------------------------------------------------------------
# Interfaz Gradio
# ----------------------------------------------------------------------
def construir():
    import gradio as gr

    estado_ollama = ("🟢 Ollama detectado (modelo disponible)"
                     if ollama_disponible() else
                     "🔴 Ollama no detectado — el sistema sigue funcionando con "
                     "el respaldo determinista (diccionario + morfología)")

    with gr.Blocks(title="Traductor Nasa Yuwe ↔ Español") as demo:
        gr.Markdown(
            "# Traductor / Consultor Nasa Yuwe ↔ Español\n"
            "Escribe en **español** con naturalidad: *¿qué significa yuuça'?*, "
            "*¿cómo se dice casa en nasa yuwe?*, *traduce Yat kluu*. "
            "El sistema decide solo si es una **consulta** o una **traducción** y en "
            "qué **dirección** — no inventa nada: el diccionario, el corpus y la "
            "gramática son la fuente de verdad.\n\n"
            f"{estado_ollama}"
        )
        entrada = gr.Textbox(
            label="Tu mensaje (en español)", lines=2,
            placeholder="Ej.: ¿qué significa yuuça'?  ·  ¿cómo se dice casa en nasa yuwe?",
        )
        boton = gr.Button("Enviar", variant="primary")
        salida = gr.Markdown()
        with gr.Accordion("Palabras reconocidas", open=False):
            detalle = gr.Markdown()
        with gr.Accordion("Traza (quién hizo qué)", open=False):
            traza = gr.Markdown()

        boton.click(responder, entrada, [salida, detalle, traza])
        entrada.submit(responder, entrada, [salida, detalle, traza])

        gr.Examples(
            examples=[
                ["¿qué significa yuuça'?"],
                ["¿cómo se dice casa en nasa yuwe?"],
                ["traduce al español: Yat kluu"],
                ["¿qué quiere decir Niisa nuuçxsa?"],
            ],
            inputs=entrada,
        )
    return demo


def main():
    compartir = "--share" in sys.argv
    try:
        demo = construir()
    except ModuleNotFoundError:
        print("Falta Gradio. Instálalo con:  pip install gradio")
        sys.exit(1)
    demo.launch(share=compartir)


if __name__ == "__main__":
    main()
