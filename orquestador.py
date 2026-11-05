"""
PASO 3 del sistema multiagente — ORQUESTADOR.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

El orquestador es el CONTROL: toma el estado y lo pasa por los componentes en
el orden del diagrama, sin interpretar contenido. Expone una sola función,
procesar(prompt), que corre todo el flujo y devuelve el estado final.

Flujo (según la arquitectura):
  Detector -> Segmentador -> Traductor -> Ensamblador -> Revisor
     -> si veredicto = corregir y quedan reintentos: volver a Ensamblador
     -> si intencion = consultar: Razonador  -> respuesta_final
     -> si intencion = traducir : traducción directa (texto ensamblado)
"""

from estado import ContextoTraduccion
from componentes import (
    c_detector, c_segmentador, c_traductor,
    c_ensamblador, c_revisor, c_razonador,
)

MAX_REINTENTOS = 2


def procesar(prompt: str) -> ContextoTraduccion:
    ctx = ContextoTraduccion(prompt=prompt)
    ctx.registrar("orquestador", "inicio")

    # 1. Interpretación y segmentación
    c_detector(ctx)
    c_segmentador(ctx)

    # 2. Traducción de los segmentos nasa yuwe
    c_traductor(ctx)

    # 3. Ensamblaje + revisión con reintentos
    reintentos = 0
    c_ensamblador(ctx)
    c_revisor(ctx)
    while ctx.veredicto == "corregir" and reintentos < MAX_REINTENTOS:
        reintentos += 1
        ctx.registrar("orquestador", f"reintento {reintentos}")
        c_ensamblador(ctx)
        c_revisor(ctx)

    # 4. Bifurcación final según la intención
    if ctx.intencion == "consultar":
        c_razonador(ctx)                       # respuesta_final la pone el razonador
    else:
        ctx.respuesta_final = ctx.texto_ensamblado   # traducción directa

    ctx.registrar("orquestador", "fin")
    return ctx


# ----------------------------------------------------------------------
# Prueba rápida
# ----------------------------------------------------------------------
if __name__ == "__main__":
    for p in ["¿qué significa çxhãçxha?", "traduce kĩwe"]:
        ctx = procesar(p)
        print(f"\nPrompt : {p}")
        print(f"Salida : {ctx.respuesta_final}")
