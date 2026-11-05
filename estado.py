"""
PASO 1 del sistema multiagente — ESTADO COMPARTIDO.
Proyecto: Traductor Nasa Yuwe (NY) <-> Español (ES).

Este es el "contexto de traducción" de la arquitectura (el blackboard):
un único objeto que el ORQUESTADOR transporta entre todos los componentes.
Cada componente LEE lo que necesita y ESCRIBE su parte. Así el sistema no
necesita que los agentes se hablen entre sí: todos trabajan sobre este estado.

No usa LLM ni librerías externas. Solo Python estándar.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import json


@dataclass
class ContextoTraduccion:
    # ---- Entrada ----
    prompt: str                                  # el texto crudo del usuario

    # ---- Lo que escribe el DETECTOR ----
    intencion: Optional[str] = None              # "traducir" | "consultar"
    direccion: Optional[str] = None              # "NY-ES" | "ES-NY"

    # ---- Lo que escribe el SEGMENTADOR ----
    # cada segmento: {texto, posicion, idioma, metodo, ...}
    segmentos: List[Dict[str, Any]] = field(default_factory=list)

    # ---- Lo que escribe el TRADUCTOR (más adelante) ----
    # se irán añadiendo a cada segmento NY: traduccion, confianza, resuelto
    no_resueltos: List[str] = field(default_factory=list)

    # ---- Lo que escribe el ENSAMBLADOR ----
    texto_ensamblado: Optional[str] = None

    # ---- Lo que escribe el REVISOR ----
    veredicto: Optional[str] = None              # "ok" | "corregir"

    # ---- Salida final (traducción directa o respuesta de consulta) ----
    respuesta_final: Optional[str] = None

    # ---- Traza auditable: quién hizo qué (clave para reproducibilidad) ----
    traza: List[Dict[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def registrar(self, componente: str, detalle: str = "") -> None:
        """Deja constancia de que un componente actuó (para depurar y auditar)."""
        self.traza.append({"componente": componente, "detalle": detalle})

    def segmentos_ny(self) -> List[Dict[str, Any]]:
        """Devuelve solo los segmentos en nasa yuwe (los que irán al Traductor)."""
        return [s for s in self.segmentos if s.get("idioma") == "NY"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ----------------------------------------------------------------------
# Demostración: crear un contexto y ver cómo luce (sin procesar nada aún)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    ctx = ContextoTraduccion(prompt="¿qué significa çxhãçxha?")
    ctx.registrar("sistema", "contexto creado")

    # Simulamos lo que escribirían el Detector y el Segmentador:
    ctx.intencion = "consultar"
    ctx.direccion = "NY-ES"
    ctx.registrar("detector", "intencion+direccion asignadas")

    ctx.segmentos = [
        {"texto": "¿", "posicion": 0, "idioma": "SIGNO", "metodo": "regex"},
        {"texto": "qué", "posicion": 1, "idioma": "ES", "metodo": "vocab_es"},
        {"texto": "significa", "posicion": 2, "idioma": "ES", "metodo": "vocab_es"},
        {"texto": "çxhãçxha", "posicion": 3, "idioma": "NY", "metodo": "ortografia_ny"},
        {"texto": "?", "posicion": 4, "idioma": "SIGNO", "metodo": "regex"},
    ]
    ctx.registrar("segmentador", "5 tokens etiquetados")

    print("Segmentos en nasa yuwe a traducir:", ctx.segmentos_ny())
    print("\nEstado completo:")
    print(ctx.to_json())
