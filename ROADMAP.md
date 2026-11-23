# Traductor Nasa Yuwe ↔ Español — Estado y plan

> Documento para entender el proyecto sin contexto previo y saber qué sigue.
> Útil para ponerse al día (incluido Claude Code). Actualizado: noviembre 2026.

---

## 1. Qué es

Un **traductor entre nasa yuwe (NY)** —lengua del pueblo Nasa, Cauca, Colombia—
**y español (ES)**, hecho como **sistema multiagente**. El nasa yuwe es de **muy
bajos recursos**: ningún modelo de IA lo "sabe". Por eso el sistema no depende de
que el modelo lo conozca, sino de un **diccionario, un corpus y una gramática
propios**. El LLM (Qwen, local vía Ollama) solo **razona en español** y redacta;
**nunca inventa nasa yuwe** (principio clave).

---

## 2. Cómo funciona hoy (el pipeline)

Al escribir una frase, pasa por estos componentes en orden (se ven en la "traza"):

1. **Detector** (`detector.py`, Qwen `qwen3:1.7b`): decide intención
   (traducir/consultar) y dirección (NY-ES / ES-NY). Validado ~95%.
2. **Segmentador** (`segmentador.py`, determinista): parte y etiqueta cada palabra.
3. **Traductor-diccionario** (`traductor.py`, herramienta): busca cada palabra y
   entrega candidatos de significado.
4. **Memoria de traducción** (en `componentes.py`): si la frase (casi) está en el
   corpus, devuelve su traducción de oro y termina ahí.
5. **RAG de frases** (`recuperador_frases.py`): recupera frases parecidas ya
   traducidas como ejemplos.
6. **RAG de gramática** (`recuperador_gramatica.py`): recupera reglas de
   afijos/morfemas relacionadas.
7. **Ensamblador** (Qwen, en `componentes.py`): redacta la traducción usando
   diccionario + ejemplos + reglas.
8. **Razonador** (Qwen): para consultas de significado, responde en español.

**Todo tiene respaldo:** si Ollama no está, cada agente cae a una versión
determinista y el sistema no se cae. Los recuperadores usan `indice_tfidf.py`
(**Python puro**, sin dependencias externas).

---

## 3. Qué está hecho

- Detector real (Qwen) + respaldo heurístico.
- Segmentador y Traductor-diccionario (4.327 palabras NY) deterministas.
- Memoria de traducción (frases del corpus → traducción exacta).
- RAG de frases (420 frases) y RAG de gramática, ambos en Python puro.
- Gramática digitalizada por OCR y organizada por temas: `rag/gramatica_por_temas.md`.
- Evaluación: `pruebas/evaluar_traduccion.py` (chrF + exactitud, hold-out,
  línea base/ablación, desglose por cobertura).
- **Tabla de afijos `afijos.json`** (79 afijos: 13 prefijos, 14 infijos, 52
  sufijos), con `tipo`/`forma`/`funcion` + glosa, categoría, variantes, ejemplo
  y orden de slots. Ortografía normalizada a la del diccionario (`çx`, no `gx`).
- **Analizador morfológico `analizador_morfologico.py`** (Python puro): quita
  afijos conocidos y recupera la raíz. Enchufado al Traductor (`traductor.py`)
  como respaldo NY→ES cuando falla la coincidencia exacta. Prueba de regresión:
  `pruebas/evaluar_morfologia.py` (14/14).

---

## 4. Hallazgo de la evaluación (importante)

Primera corrida (hold-out, NY→ES, 30 frases): **chrF global ≈ 14.4** vs **14.1** de
la línea base. El desglose reveló lo clave:

- El **cuello de botella es la cobertura léxica**, NO el modelo.
- Donde el diccionario cubre las palabras (cobertura alta) el chrF sube bastante;
  donde no, casi nada se puede traducir.
- La mayoría de los `⟨palabra?⟩` **no eran palabras desconocidas**, sino
  **formas conjugadas** cuya **raíz sí está** en el diccionario
  (p. ej. `yuuça' → yuu`, `uuça' → uu`).

**Conclusión:** la palanca #1 es un **analizador morfológico** que use la gramática
para encontrar la raíz de las palabras conjugadas.

---

## 5. Próximos pasos (en orden de impacto)

### Paso 1 — `afijos.json` (la lista de afijos) · ✅ HECHO (nov. 2026)
Tabla limpia de afijos a partir de la gramática → `afijos.json` (79 afijos: 13
prefijos, 14 infijos, 52 sufijos). Cada afijo con `tipo`/`forma`/`funcion` + glosa,
categoría, variantes (alomorfos), ejemplo, homófonos y orden de slots del verbo y
del nombre. OCR corregido y ortografía llevada a la del diccionario (`çx`, `ç`,
`-khe`). Nota: la estimación previa era 24/39/14; los infijos coinciden exacto (14),
y prefijos/sufijos difieren solo por criterio de conteo (ver `_meta.conteo`).

### Paso 2 — Analizador morfológico (usa `afijos.json`) · ✅ HECHO (nov. 2026)
`analizador_morfologico.py` (Python puro, sin dependencias): cuando el diccionario
no encuentra una palabra, quita afijos conocidos y busca la **raíz**; si la halla,
devuelve el significado de la raíz + las **marcas** gramaticales. Desacoplado (recibe
`es_raiz` como callback, no importa el diccionario). Enchufado a `traductor.py` como
respaldo NY→ES (`via="morfologia"`); las marcas se propagan al estado en
`componentes.c_traductor`. Cubre prefijos, sufijos e infijos con forma concreta
(se omiten el aoristo cero y el iterativo; el imperfectivo `-V-` se intenta último).

**Resultado medido** (hold-out, 30 frases NY→ES, línea base sin LLM):
- Cobertura léxica: **44.4% → 73.0%** (+28.6 pts; 18 formas conjugadas recuperadas).
- chrF (línea base): **14.1 → 22.3** (+8.3).
Confirma el hallazgo: el cuello de botella era la cobertura, no el modelo.
Pendiente de afinar: quitar prefijos cortos (`m-`, `n-`) genera algún falso
positivo (p. ej. `mah→ah`); la confianza baja lo amortigua y el LLM desempata.

### Paso 3 — Coincidencia multi-palabra · SIGUIENTE TAREA
Que el diccionario busque grupos como `aka ũs` como unidad (ya existen como entradas).

### Paso 4 — Evaluación completa para el paper
Reportar exactitud de la memoria aparte (~100%), la ablación (con/sin RAG) y,
opcional, spBLEU (instalar `sacrebleu`).

### Más adelante
Recuperador léxico-difuso (RapidFuzz), reforzar **ES→NY**, mejorar la recuperación
de gramática, y **validación con hablantes** del corpus y de la gramática OCR
(necesario antes de dar traducciones por buenas).

---

## 6. Cómo correrlo

Solo **Python 3.8+** (sin instalar nada para el sistema base):
```
python main.py
```
Para la traducción real con el modelo: tener **Ollama** abierto con
`qwen3:1.7b` (Detector) y el modelo del traductor. Evaluar:
```
python pruebas/evaluar_traduccion.py
```

---

## 7. Notas / principios

- **El LLM no inventa nasa yuwe.** El diccionario, el corpus y la gramática son la
  fuente de verdad; el modelo solo razona en español y ensambla.
- El corpus y la gramática **no están validados por hablantes**: son punto de
  partida, no verdad verificada. La validación con la comunidad Nasa es un paso
  necesario.
- Licencias: Qwen3 = Apache 2.0 (pesos abiertos, uso libre). Código del proyecto:
  sin dependencias externas (solo biblioteca estándar).
