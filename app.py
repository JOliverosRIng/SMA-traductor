"""
MVP WEB (Tarea B del PLAN) — Traductor / Consultor Nasa Yuwe (NY) <-> Español (ES).
Proyecto: Traductor Nasa Yuwe, sistema multiagente.

Interfaz web con Gradio. NO es "un traductor de frases libres" (eso sigue siendo
experimental), sino un CONSULTOR/DICCIONARIO bilingüe confiable, con una pestaña
experimental de traducción de frases.

Dos modos (PLAN B2):
  - CONSULTAR (confiable): "qué significa X" / "cómo se dice Y". Usa diccionario +
    memoria de traducción + morfología. Es DETERMINISTA y funciona SIN Ollama: no
    llama al LLM, así que no inventa nasa yuwe ni español.
  - TRADUCIR (EXPERIMENTAL): frases completas. Usa el pipeline con LLM (Ollama) si
    está disponible; si no, cae al ensamblaje determinista.

Honestidad (PLAN B3): cuando una palabra no está, se dice "no está en el
diccionario"; nunca se muestra ⟨palabra?⟩ crudo al usuario final.

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

from estado import ContextoTraduccion
from componentes import c_segmentador, c_traductor, c_ensamblador
try:
    import recuperador_frases
except Exception:
    recuperador_frases = None

OLLAMA_URL_TAGS = "http://localhost:11434/api/tags"

# Direcciones legibles en la UI -> código interno del sistema.
DIR_NY_ES = "Nasa Yuwe → Español"
DIR_ES_NY = "Español → Nasa Yuwe"
_DIRECCION = {DIR_NY_ES: "NY-ES", DIR_ES_NY: "ES-NY"}


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def ollama_disponible(timeout: float = 1.5) -> bool:
    """True si Ollama responde (para avisar al usuario, no para bloquear)."""
    try:
        with urllib.request.urlopen(OLLAMA_URL_TAGS, timeout=timeout):
            return True
    except Exception:
        return False


def _limpiar_para_usuario(texto: str):
    """Quita los ⟨palabra?⟩ crudos (PLAN B3) y devuelve (texto_limpio, [no_encontradas]).

    El pipeline marca lo que no pudo traducir entre ⟨ ⟩. Al usuario final no le
    mostramos ese código: dejamos la palabra tal cual y listamos aparte las que no
    están en el diccionario, con honestidad.
    """
    if not texto:
        return texto, []
    no_encontradas = re.findall(r"⟨\s*([^⟩?]+?)\s*\??\s*⟩", texto)
    limpio = re.sub(r"⟨\s*([^⟩?]+?)\s*\??\s*⟩", r"\1", texto)
    limpio = re.sub(r"\s+([,.;:!?])", r"\1", limpio).strip()
    # de-duplicar conservando orden
    vistas, unicas = set(), []
    for p in no_encontradas:
        p = p.strip()
        if p and p.lower() not in vistas:
            vistas.add(p.lower())
            unicas.append(p)
    return limpio, unicas


def _preparar(prompt: str, direccion: str) -> ContextoTraduccion:
    """Segmenta y busca candidatos en el diccionario (sin detector ni LLM)."""
    ctx = ContextoTraduccion(prompt=prompt)
    ctx.direccion = direccion
    c_segmentador(ctx)
    c_traductor(ctx)
    return ctx


def _traza_md(ctx: ContextoTraduccion) -> str:
    if not ctx.traza:
        return "_(sin traza)_"
    return "\n".join(f"- **{t['componente']}** — {t['detalle']}" for t in ctx.traza)


# ----------------------------------------------------------------------
# MODO CONSULTAR (confiable, determinista, sin LLM)
# ----------------------------------------------------------------------
def consultar(prompt: str, direccion_ui: str):
    """Responde "qué significa / cómo se dice" solo con diccionario + memoria +
    morfología. No llama al LLM: es reproducible y no inventa."""
    direccion = _DIRECCION.get(direccion_ui, "NY-ES")
    origen = "NY" if direccion == "NY-ES" else "ES"
    prompt = (prompt or "").strip()
    if not prompt:
        return "Escribe una palabra o frase para consultar.", "_(sin traza)_"

    ctx = _preparar(prompt, direccion)

    # ¿La frase (casi) está en el corpus? -> traducción conocida (memoria).
    aviso_memoria = ""
    if recuperador_frases is not None:
        try:
            texto_origen = " ".join(
                s["texto"] for s in ctx.segmentos if s.get("idioma") == origen
            ) or prompt
            top = recuperador_frases.buscar(texto_origen, direccion, k=1)
            if top and top[0]["score"] >= 0.92:
                aviso_memoria = (
                    f"📘 **Frase conocida (corpus):** «{top[0]['origen']}» "
                    f"se traduce como **{top[0]['destino']}**.\n\n"
                )
                ctx.registrar("memoria_frases", f"coincidencia {top[0]['score']}")
        except Exception as e:
            ctx.registrar("memoria_frases", f"no disponible: {e}")

    encontradas, faltantes = [], []
    for s in ctx.segmentos:
        if s.get("idioma") != origen:
            continue
        palabra = s["texto"]
        if s.get("resuelto"):
            sentidos = [s["traduccion"]] + list(s.get("alternativas") or [])
            sentidos_txt = "; ".join(sentidos)
            if s.get("via") == "morfologia":
                marcas = ", ".join(s.get("marcas") or []) or "sin marcas"
                encontradas.append(
                    f"- **{palabra}** = {sentidos_txt}  \n"
                    f"  _(forma de la raíz «{s.get('raiz')}»; marcas: {marcas})_"
                )
            else:
                encontradas.append(f"- **{palabra}** = {sentidos_txt}")
        else:
            faltantes.append(palabra)

    partes = [aviso_memoria] if aviso_memoria else []
    if encontradas:
        titulo = "Significado(s):" if direccion == "NY-ES" else "Equivalente(s) en nasa yuwe:"
        partes.append(f"**{titulo}**\n" + "\n".join(encontradas))
    if faltantes:
        lista = ", ".join(f"«{p}»" for p in faltantes)
        donde = "el diccionario" if direccion == "NY-ES" else "el diccionario (sin equivalente)"
        partes.append(f"\n⚠️ No está en {donde}: {lista}.")
    if not encontradas and not faltantes and not aviso_memoria:
        partes.append("No se reconoció ninguna palabra para consultar.")

    return "\n\n".join(partes).strip(), _traza_md(ctx)


# ----------------------------------------------------------------------
# MODO TRADUCIR (experimental, usa LLM si Ollama está)
# ----------------------------------------------------------------------
def traducir(prompt: str, direccion_ui: str):
    """Traduce una frase completa con el pipeline (LLM si hay Ollama; si no,
    ensamblaje determinista). Marcado EXPERIMENTAL."""
    direccion = _DIRECCION.get(direccion_ui, "NY-ES")
    prompt = (prompt or "").strip()
    if not prompt:
        return "Escribe una frase para traducir.", "_(sin traza)_"

    ctx = _preparar(prompt, direccion)
    ctx.intencion = "traducir"
    c_ensamblador(ctx)  # memoria + RAG + LLM, con respaldo determinista interno

    salida = ctx.texto_ensamblado or ""
    limpio, faltantes = _limpiar_para_usuario(salida)

    if not ollama_disponible():
        encabezado = ("ℹ️ _Ollama no está corriendo: traducción determinista "
                      "(palabra por palabra), sin el modelo._\n\n")
    else:
        encabezado = ""

    cuerpo = f"**Traducción (experimental):**\n\n{limpio}" if limpio else \
             "No se pudo construir una traducción."
    if faltantes:
        lista = ", ".join(f"«{p}»" for p in faltantes)
        cuerpo += f"\n\n⚠️ Palabras no encontradas en el diccionario: {lista}."
    return encabezado + cuerpo, _traza_md(ctx)


# ----------------------------------------------------------------------
# Enrutador: según el modo elegido
# ----------------------------------------------------------------------
def responder(modo: str, prompt: str, direccion_ui: str):
    if modo.startswith("Consultar"):
        return consultar(prompt, direccion_ui)
    return traducir(prompt, direccion_ui)


# ----------------------------------------------------------------------
# Interfaz Gradio
# ----------------------------------------------------------------------
def construir():
    import gradio as gr

    estado_ollama = ("🟢 Ollama detectado (traducción con modelo disponible)"
                     if ollama_disponible() else
                     "🔴 Ollama no detectado — Consultar funciona igual; "
                     "Traducir usará el respaldo determinista")

    with gr.Blocks(title="Traductor Nasa Yuwe ↔ Español") as demo:
        gr.Markdown(
            "# Traductor / Consultor Nasa Yuwe ↔ Español\n"
            "Diccionario y consultor **confiable** (no inventa nada: el diccionario, "
            "el corpus y la gramática son la fuente de verdad).\n\n"
            f"{estado_ollama}"
        )
        with gr.Row():
            modo = gr.Radio(
                ["Consultar (confiable)", "Traducir (experimental)"],
                value="Consultar (confiable)", label="Modo",
                info="Consultar: qué significa / cómo se dice (determinista). "
                     "Traducir: frases completas (usa el modelo).",
            )
            direccion = gr.Radio(
                [DIR_NY_ES, DIR_ES_NY], value=DIR_NY_ES, label="Dirección",
            )
        entrada = gr.Textbox(
            label="Texto", lines=2,
            placeholder="Ej.: qué significa yuuça'  ·  cómo se dice casa",
        )
        boton = gr.Button("Procesar", variant="primary")
        salida = gr.Markdown(label="Resultado")
        with gr.Accordion("Ver traza (quién hizo qué)", open=False):
            traza = gr.Markdown()

        boton.click(responder, [modo, entrada, direccion], [salida, traza])
        entrada.submit(responder, [modo, entrada, direccion], [salida, traza])

        gr.Examples(
            examples=[
                ["Consultar (confiable)", "yuuça'", DIR_NY_ES],
                ["Consultar (confiable)", "casa", DIR_ES_NY],
                ["Traducir (experimental)", "Yat kluu", DIR_NY_ES],
            ],
            inputs=[modo, entrada, direccion],
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
