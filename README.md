# Traductor Nasa Yuwe ↔ Español — Sistema multiagente (adelanto)

Sistema que traduce entre **nasa yuwe (NY)** y **español (ES)** mediante un
conjunto de agentes y herramientas coordinados. Este paquete es un **adelanto
ejecutable**: corre de punta a punta y ya traduce de verdad (NY→ES) usando un
diccionario construido desde un corpus de ~8.000 pares.

## Cómo ejecutarlo (rápido)

Solo necesitas **Python 3.8+**. No hay que instalar nada para el sistema base.

```
python main.py
```
Escribe una frase y Enter. Ejemplos para probar:
- `qué significa aka`      → aka = dolor
- `qué significa akh`      → muestra sus varios significados
- `traduce ewa`
- `idx tata jĩi`

O en modo directo:
```
python main.py qué significa aka
```

## Qué hace cada archivo

**Núcleo del sistema (se necesita para correr):**
- `main.py` — punto de entrada; lee lo que escribes y muestra el resultado.
- `orquestador.py` — coordina el flujo entre componentes.
- `estado.py` — el "contexto de traducción" que viaja entre componentes.
- `componentes.py` — adaptadores de cada agente/herramienta sobre el estado.
- `segmentador.py` — tokeniza y etiqueta cada palabra (ES/NY/SIGNO/DESCONOCIDO).
- `traductor.py` — traduce por diccionario (coincidencia exacta, ambas direcciones).
- `detector.py` — agente que decide intención y dirección (usa Ollama; ver abajo).

**Datos:**
- `diccionario_ny_es.json` — palabra NY → lista de significados.
- `vocab_ny.txt`, `vocab_es.txt` — vocabularios para el segmentador.
- `corpus_limpio.csv`, `frases_ny_es.csv` — corpus procesado (trazabilidad).
- `corpus_v3.xlsx` — corpus original (fuente de todo).

**Pruebas (opcionales), en `pruebas/`:**
- `probar_segmentador.py` — escribe frases y ve el etiquetado.
- `evaluar_segmentador.py` + `casos_segmentador.json` — precisión del segmentador.
- `probar_detector.py` + `evaluar_detector.py` + `casos_detector.json` — el detector (requiere Ollama).

**Preparación de datos (opcional), en `preparacion/`:**
- regenera diccionario y vocabularios desde el Excel.

## Estado de cada pieza (honesto)

- **Segmentador:** real y funcional (determinista).
- **Traductor NY→ES:** real por diccionario, funciona bien.
- **Traductor ES→NY:** básico (los significados del diccionario son frases, no
  palabras sueltas); se completará con el LLM + recuperación difusa.
- **Detector:** en este adelanto va como heurística (STUB) para correr sin
  Ollama. El detector real (Qwen/Ollama) está en `detector.py` y se activa
  cambiando una línea en `componentes.py`.
- **Ensamblador / Revisor / Razonador:** versión base.

El corpus **no está validado por hablantes** (`validado = no`): es un punto de
partida, no una verdad verificada.

## Activar el Detector real (con Ollama)

1. Instala Ollama (ollama.com) y baja el modelo: `ollama pull qwen3:4b`.
2. En `componentes.py`, reemplaza el cuerpo de `c_detector` por una llamada a
   `detector.detectar(ctx.prompt)` y escribe `intencion`/`direccion` en el estado.
3. Prueba el detector solo: `python pruebas/probar_detector.py`.

Qwen3 es Apache 2.0 (uso comercial y académico libre).
