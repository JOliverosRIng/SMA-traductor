# Plan de trabajo — Traductor Nasa Yuwe (para continuar)

> Lee primero `ROADMAP.md` para el contexto del proyecto. Este archivo tiene las
> dos tareas siguientes: (A) que el LLM aporte, y (B) un MVP. Principio innegociable:
> **el LLM nunca inventa nasa yuwe**; el diccionario, el corpus y la gramática son la
> fuente de verdad.

## Estado actual (nov 2026)
- Pipeline funciona: Detector → Segmentador → Traductor(diccionario + **analizador
  morfológico**) → Memoria → RAG frases → RAG gramática → Ensamblador(LLM) → Razonador.
- La morfología subió el chrF de **14.4 a 22.7** (NY→ES, hold-out).
- Problema abierto: el **LLM casi no aporta** (cae a respaldo; `sistema ≈ base`).

---

## Tarea A — Que el LLM aporte

**A1. Instrumentar.** Correr `pruebas/evaluar_traduccion.py` (versión con desglose)
y ver la línea "Usaron el modelo (Qwen): X/30". Confirmar que el LLM casi nunca corre.

**A2. Forzar JSON en Ollama (arreglo principal).** En `agente_traductor.py` (y en
`detector.py`), agregar `"format": "json"` al cuerpo de la petición a Ollama. Eso
obliga al modelo a devolver JSON válido y elimina las caídas a respaldo por formato.
```python
cuerpo = {
    "model": MODELO,
    "system": system,
    "prompt": user,
    "stream": False,
    "think": False,
    "format": "json",          # <-- fuerza salida JSON válida
    "options": {"temperature": 0, "num_predict": 800},
}
```

**A3. Selección de sentido (polisemia).** La morfología entrega la **raíz**, pero una
raíz puede tener varios significados (ej. `yuu` = "venir"/"llegar a ser"). El Ensamblador
debe recibir TODOS los candidatos de cada raíz + los ejemplos del RAG, y **elegir el
sentido que mejor encaje** en el contexto. No inventar significados fuera de los candidatos.

**A4. Verificar.** Volver a correr el evaluador. Meta: que suba "Usaron Qwen" y que el
`aporte del LLM+RAG` deje de ser +0.3. Comparar chrF global contra 22.7.

---

## Tarea B — MVP (producto mínimo viable)

**Idea:** no es "un traductor de frases libres" (eso aún es experimental), sino un
**consultor/diccionario bilingüe nasa yuwe ↔ español confiable**, con interfaz web.

**B1. App web con Gradio** (`app.py`): una caja de texto, un botón, y muestra el
resultado + la traza. Instalar: `pip install gradio`.

**B2. Dos modos:**
- **Consultar** (confiable): "qué significa X" / "cómo se dice Y". Usa diccionario +
  memoria + morfología. **Funciona sin Ollama** (la consulta es determinista).
- **Traducir** (marcado como EXPERIMENTAL): frases; usa el LLM si Ollama está.

**B3. Honestidad:** cuando no encuentra una palabra, decir "no está en el diccionario",
nunca inventar ni mostrar `⟨palabra?⟩` crudo al usuario final.

**B4. Demo para el paper/sustentación:** `demo.launch(share=True)` genera un enlace
público temporal, sin montar servidor. Correr offline es una ventaja en contexto comunitario.

---

## Orden sugerido
1. A2 (forzar JSON) — rápido y de alto impacto.
2. A3 (selección de sentido) — donde el LLM debe brillar.
3. B (MVP con Gradio) — para tener algo demostrable y usable.
