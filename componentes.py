"""
COMPONENTES del sistema multiagente (adaptadores sobre el estado compartido).
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Estado de cada componente en esta versión (pipeline de traducción completo):
  - DETECTOR    -> REAL (Qwen vía Ollama) con respaldo heurístico.
  - SEGMENTADOR -> REAL (determinista).
  - TRADUCTOR   -> REAL: herramienta de diccionario que entrega CANDIDATOS.
  - ENSAMBLADOR -> AGENTE con LLM: redacta la traducción eligiendo el sentido
                   correcto (polisemia), anclado al diccionario; respaldo
                   determinista si Ollama no está.
  - REVISOR     -> base (aprueba).
  - RAZONADOR   -> AGENTE con LLM: responde consultas en español, anclado al
                   diccionario; respaldo determinista si Ollama no está.

Principio: el LLM nunca inventa nasa yuwe. El diccionario es la fuente de verdad;
el LLM solo razona en español y ensambla usando los candidatos que recibe.

Si Ollama no está disponible, TODO sigue corriendo con los respaldos.
"""

import re
from estado import ContextoTraduccion
from segmentador import segmentar
from traductor import traducir_token
from detector import detectar as detectar_llm      # Detector real (Qwen)
import agente_traductor                            # Ensamblador/Razonador (Qwen)
try:
    import recuperador_frases                      # RAG de frases (ejemplos); requiere scikit-learn
except Exception:
    recuperador_frases = None


# ======================================================================
# DETECTOR — REAL (Qwen) con respaldo heurístico
# ======================================================================
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
        r = detectar_llm(ctx.prompt)                 # pregunta al modelo real
    except Exception as e:
        r = {"valido": False, "error": str(e)}       # Ollama apagado, timeout, etc.
    if r.get("valido"):
        ctx.intencion = r["intencion"]
        ctx.direccion = r["direccion"]
        ctx.registrar("detector(Qwen)", f"{ctx.intencion} / {ctx.direccion}")
    else:
        _detector_heuristico(ctx)                    # respaldo
        motivo = r.get("error", "salida inválida del modelo")
        ctx.registrar("detector(respaldo)", f"{ctx.intencion} / {ctx.direccion} [{motivo}]")
    return ctx


# ======================================================================
# SEGMENTADOR — REAL
# ======================================================================
def c_segmentador(ctx: ContextoTraduccion) -> ContextoTraduccion:
    ctx.segmentos = segmentar(ctx.prompt)["segmentos"]
    ctx.registrar("segmentador", f"{len(ctx.segmentos)} tokens etiquetados")
    return ctx


# ======================================================================
# TRADUCTOR — herramienta de diccionario (entrega CANDIDATOS por token)
# ======================================================================
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
    ctx.registrar("traductor", f"{ok} con candidatos, {pend} sin resolver")
    return ctx


def _items_para_llm(ctx: ContextoTraduccion):
    """Arma el glosario (candidatos del diccionario) para los tokens del idioma origen."""
    direccion = ctx.direccion or "NY-ES"
    origen = "NY" if direccion == "NY-ES" else "ES"
    items = []
    for s in ctx.segmentos:
        if s.get("idioma") == origen and s.get("resuelto"):
            candidatos = [s["traduccion"]] + list(s.get("alternativas") or [])
            items.append({"origen": s["texto"], "candidatos": candidatos})
    return items


def _texto_origen(ctx: ContextoTraduccion) -> str:
    """Une los tokens del idioma de origen (el contenido a traducir), para el RAG de frases."""
    direccion = ctx.direccion or "NY-ES"
    origen = "NY" if direccion == "NY-ES" else "ES"
    return " ".join(s["texto"] for s in ctx.segmentos if s.get("idioma") == origen)


# ======================================================================
# ENSAMBLADOR — AGENTE con LLM (respaldo determinista)
# ======================================================================
def _unir(partes):
    texto = " ".join(p for p in partes if p)
    texto = re.sub(r"\s+([,.;:!?])", r"\1", texto)
    texto = re.sub(r"([¿¡])\s+", r"\1", texto)
    return texto.strip()


def _ensamblar_respaldo(ctx: ContextoTraduccion) -> None:
    """Ensamblaje determinista palabra por palabra (sin LLM)."""
    direccion = ctx.direccion or "NY-ES"
    idioma_origen = "NY" if direccion == "NY-ES" else "ES"
    partes = []
    for s in ctx.segmentos:
        if s.get("idioma") == idioma_origen:
            if s.get("resuelto"):
                partes.append(s["traduccion"])
            else:
                partes.append(f"⟨{s['texto']}?⟩")
        else:
            partes.append(s["texto"])
    ctx.texto_ensamblado = _unir(partes)


def c_ensamblador(ctx: ContextoTraduccion) -> ContextoTraduccion:
    # En consultas no gastamos el LLM aquí: el Razonador produce la respuesta.
    if ctx.intencion == "consultar":
        _ensamblar_respaldo(ctx)
        ctx.registrar("ensamblador", "ensamblaje base (la consulta la responde el razonador)")
        return ctx

    # Traducción: el agente LLM redacta, anclado al diccionario + ejemplos del RAG.
    direccion = ctx.direccion or "NY-ES"
    items = _items_para_llm(ctx)

    # RAG de frases: recuperar ejemplos parecidos del corpus (si está disponible).
    ejemplos = ""
    if recuperador_frases is not None:
        try:
            consulta = _texto_origen(ctx) or ctx.prompt
            ejemplos = recuperador_frases.ejemplos_para_prompt(consulta, direccion, k=3)
            if ejemplos:
                ctx.registrar("recuperador_frases",
                              f"{ejemplos.count(chr(10)) + 1} ejemplo(s) recuperado(s)")
        except Exception as e:
            ctx.registrar("recuperador_frases", f"no disponible: {e}")

    try:
        r = agente_traductor.traducir(ctx.prompt, direccion, items,
                                      ctx.no_resueltos, ejemplos)
    except Exception as e:
        r = {"valido": False, "error": str(e)}
    if r.get("valido"):
        ctx.texto_ensamblado = r["traduccion"]
        ctx.registrar("ensamblador(Qwen)", "traducción redactada por el modelo")
    else:
        _ensamblar_respaldo(ctx)
        ctx.registrar("ensamblador(respaldo)", r.get("error", "modelo no disponible"))
    return ctx


# ======================================================================
# REVISOR — base
# ======================================================================
def c_revisor(ctx: ContextoTraduccion) -> ContextoTraduccion:
    ctx.veredicto = "ok"
    ctx.registrar("revisor", "aprobado")
    return ctx


# ======================================================================
# RAZONADOR — AGENTE con LLM (rama de consulta), respaldo determinista
# ======================================================================
def _razonar_respaldo(ctx: ContextoTraduccion) -> None:
    """Respuesta determinista: lista 'palabra = significado(s)'."""
    direccion = ctx.direccion or "NY-ES"
    origen = "NY" if direccion == "NY-ES" else "ES"
    piezas = []
    for s in ctx.segmentos:
        if s.get("idioma") == origen and s.get("resuelto"):
            alt = f" (otros: {', '.join(s['alternativas'])})" if s.get("alternativas") else ""
            piezas.append(f"{s['texto']} = {s['traduccion']}{alt}")
    ctx.respuesta_final = "; ".join(piezas) if piezas else (ctx.texto_ensamblado or "Sin resultados.")


def c_razonador(ctx: ContextoTraduccion) -> ContextoTraduccion:
    items = _items_para_llm(ctx)
    try:
        r = agente_traductor.explicar(ctx.prompt, ctx.direccion or "NY-ES", items)
    except Exception as e:
        r = {"valido": False, "error": str(e)}
    if r.get("valido"):
        ctx.respuesta_final = r["respuesta"]
        ctx.registrar("razonador(Qwen)", "explicación redactada por el modelo")
    else:
        _razonar_respaldo(ctx)
        ctx.registrar("razonador(respaldo)", r.get("error", "modelo no disponible"))
    return ctx