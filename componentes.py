"""
COMPONENTES del sistema multiagente (adaptadores sobre el estado compartido).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Estado de cada componente en esta versión base:
  - SEGMENTADOR -> REAL  (determinista)
  - TRADUCTOR   -> REAL por diccionario (coincidencia exacta, ambas direcciones)
  - DETECTOR    -> STUB (heurística; el definitivo usa Qwen/Ollama)
  - ENSAMBLADOR -> base (reconstruye la oración)
  - REVISOR     -> base (aprueba)
  - RAZONADOR   -> base (presenta la respuesta de una consulta)

Todo corre SIN Ollama. El Detector real se activa cambiando c_detector por una
llamada a detector.detectar() cuando tengas Ollama.
"""

import re
from estado import ContextoTraduccion
from segmentador import segmentar
from traductor import traducir_token
from detector import detectar as detectar_llm   # Detector real (Qwen vía Ollama)

# ----------------------------------------------------------------------
# DETECTOR — REAL (Qwen vía Ollama) con respaldo heurístico
# ----------------------------------------------------------------------
def _detector_heuristico(ctx: ContextoTraduccion) -> ContextoTraduccion:
    """Respaldo: se usa solo si el modelo falla o no está disponible."""
    t = ctx.prompt.lower()
    if any(p in t for p in ["significa", "significado", "qué es", "que es",
                            "cómo se dice", "como se dice", "cómo digo", "como digo",
                            "qué quiere decir", "que quiere decir"]):
        ctx.intencion = "consultar"
    else:
        ctx.intencion = "traducir"
    if any(p in t for p in ["en nasa", "al nasa", "en nasayuwe", "a nasa"]):
        ctx.direccion = "ES-NY"
    elif any(p in t for p in ["en español", "al español", "en espanol", "al espanol",
                              "significa", "qué significa", "que significa"]):
        ctx.direccion = "NY-ES"
    else:
        ctx.direccion = "NY-ES"
    return ctx


def c_detector(ctx: ContextoTraduccion) -> ContextoTraduccion:
    try:
        r = detectar_llm(ctx.prompt)          # pregunta al modelo real
    except Exception as e:
        r = {"valido": False, "error": str(e)}  # Ollama apagado, timeout, etc.
    if r.get("valido"):
        ctx.intencion = r["intencion"]
        ctx.direccion = r["direccion"]
        ctx.registrar("detector(Qwen)", f"{ctx.intencion} / {ctx.direccion}")
    else:
        _detector_heuristico(ctx)             # respaldo
        motivo = r.get("error", "salida inválida del modelo")
        ctx.registrar("detector(respaldo)", f"{ctx.intencion} / {ctx.direccion} [{motivo}]")
    return ctx

# ----------------------------------------------------------------------
# SEGMENTADOR — REAL
# ----------------------------------------------------------------------
def c_segmentador(ctx: ContextoTraduccion) -> ContextoTraduccion:
    ctx.segmentos = segmentar(ctx.prompt)["segmentos"]
    ctx.registrar("segmentador", f"{len(ctx.segmentos)} tokens etiquetados")
    return ctx


# ----------------------------------------------------------------------
# TRADUCTOR — REAL por diccionario (ambas direcciones)
# ----------------------------------------------------------------------
def c_traductor(ctx: ContextoTraduccion) -> ContextoTraduccion:
    direccion = ctx.direccion or "NY-ES"
    idioma_origen = "NY" if direccion == "NY-ES" else "ES"
    ok = pend = 0
    for s in ctx.segmentos:
        if s.get("idioma") != idioma_origen:
            continue
        r = traducir_token(s["texto"], direccion)
        if r["resuelto"]:
            s["traduccion"] = r["traduccion"]
            s["alternativas"] = r["alternativas"]
            s["confianza"] = r["confianza"]
            s["resuelto"] = True
            ok += 1
        else:
            s["traduccion"] = None
            s["resuelto"] = False
            ctx.no_resueltos.append(s["texto"])
            pend += 1
    ctx.registrar("traductor", f"{ok} traducidos, {pend} sin resolver")
    return ctx


# ----------------------------------------------------------------------
# ENSAMBLADOR — base
# ----------------------------------------------------------------------
def _unir(partes):
    texto = " ".join(partes)
    texto = re.sub(r"\s+([,.;:!?])", r"\1", texto)
    texto = re.sub(r"([¿¡])\s+", r"\1", texto)
    return texto.strip()


def c_ensamblador(ctx: ContextoTraduccion) -> ContextoTraduccion:
    direccion = ctx.direccion or "NY-ES"
    idioma_origen = "NY" if direccion == "NY-ES" else "ES"
    partes = []
    for s in ctx.segmentos:
        if s.get("idioma") == idioma_origen:
            if s.get("resuelto"):
                partes.append(s["traduccion"])
            else:
                partes.append(f"⟨{s['texto']}?⟩")   # no encontrado
        else:
            partes.append(s["texto"])                # contexto / signos
    ctx.texto_ensamblado = _unir(partes)
    ctx.registrar("ensamblador", "oración reconstruida")
    return ctx


# ----------------------------------------------------------------------
# REVISOR — base
# ----------------------------------------------------------------------
def c_revisor(ctx: ContextoTraduccion) -> ContextoTraduccion:
    ctx.veredicto = "ok"
    ctx.registrar("revisor", "aprobado")
    return ctx


# ----------------------------------------------------------------------
# RAZONADOR — base (rama de consulta)
# ----------------------------------------------------------------------
def c_razonador(ctx: ContextoTraduccion) -> ContextoTraduccion:
    # arma una respuesta mostrando las equivalencias encontradas y sus alternativas
    piezas = []
    origen = "NY" if (ctx.direccion or "NY-ES") == "NY-ES" else "ES"
    for s in ctx.segmentos:
        if s.get("idioma") == origen and s.get("resuelto"):
            alt = f" (otros: {', '.join(s['alternativas'])})" if s.get("alternativas") else ""
            piezas.append(f"{s['texto']} = {s['traduccion']}{alt}")
    if piezas:
        ctx.respuesta_final = "; ".join(piezas)
    else:
        ctx.respuesta_final = ctx.texto_ensamblado
    ctx.registrar("razonador", "respuesta construida")
    return ctx
