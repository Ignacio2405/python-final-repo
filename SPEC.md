# SPEC.md — Módulo de cálculos nutricionales y antropométricos

| | |
|---|---|
| **Versión** | 0.4 |
| **Fecha** | 2026-11-25 |
| **Estado** | Especificación cerrada para implementar, salvo las propuestas P-7 y P-8. `bodyAge` tiene una heurística autorizada, explícitamente no clínica ni validada. |
| **Fuente de arquitectura** | `AGENTS.md` (este documento no la redefine, la referencia) |
| **Fuente de verdad funcional** | Este documento |

> **Convención de estados.** ✅ **Definido** (se puede implementar), 🟡 **Propuesto** (hay una propuesta concreta pendiente de ratificación), ⛔ **Pendiente** (falta método; no se implementa y el indicador devuelve `null`), ⚠ **Heurística autorizada** (se implementa solo en el alcance aprobado y nunca se presenta como clínicamente validada).
> Los identificadores `P-n` remiten a la sección 18.

> **Origen de las decisiones.** El responsable del proyecto delegó la elección de métodos y la definición de validaciones. Las ecuaciones clínicas de la sección 8 se transcriben de la bibliografía citada, no de un archivo entregado. **Antes del primer merge de cada fórmula clínica hay que contrastar los coeficientes con la fuente primaria** y dejar el cálculo manual de verificación en el test. `bodyAge` es una excepción aprobada expresamente por el responsable (P-13): no tiene fuente bibliográfica ni validación clínica.

---

## 1. Introducción

Este documento especifica el módulo independiente de cálculos nutricionales y antropométricos. Es un servicio HTTP en Python que recibe las mediciones físicas de un paciente y devuelve indicadores de composición corporal y metabolismo en JSON.

- `AGENTS.md` define **cómo** se construye. Este documento define **qué** hace el módulo: contratos, fórmulas, reglas de negocio, validaciones y criterios de aceptación.
- El stack HTTP vigente es **Django + Django REST Framework**, servido por Daphne. Se eligió para alinearlo con el stack de referencia TaskFlow; no se configura persistencia Django.
- **TaskFlow** se usa solo como referencia técnica y estructural. Nada de su dominio forma parte del módulo.
- Los valores del ejemplo de la sección 7.1 se calcularon a mano con las ecuaciones y la heurística autorizada de la sección 8 para el payload de la sección 6.2.

## 2. Objetivo del módulo

Procesar mediciones antropométricas y calcular de forma determinista, trazable y documentada los siete indicadores de la sección 7, informando `null` en los que no puedan calcularse por falta de datos o de metodología validada.

## 3. Alcance funcional

**Dentro del alcance**

1. Recibir datos del paciente y mediciones por HTTP/JSON.
2. Autenticar al llamador con un token compartido.
3. Validar la entrada (estructura, tipos, rangos, consistencia, cobertura).
4. Determinar qué indicadores son calculables.
5. Aplicar fórmulas documentadas, con conversión de unidades y redondeo centralizados.
6. Devolver siempre las siete claves.
7. Informar errores sin exponer detalles internos.
8. Exponer un endpoint de salud.

**Fuera del alcance**

- Persistencia (la hace Node.js en MongoDB).
- Usuarios, permisos, sesiones.
- Gasto energético total y niveles de actividad física.
- Diagnóstico o interpretación clínica.
- Cálculos en el frontend o fórmulas duplicadas en Node.js.

## 4. Descripción general de la arquitectura

```
Frontend ──(antropometria.mediciones)──▶ Node.js ──POST {paciente, mediciones} + X-API-Key──▶ Python (Django + DRF)
                                            │                                                    │
                                            │◀──────────────── {ok, resultados} ────────────────┘
                                            ▼
                                        MongoDB (antropometria.mediciones + antropometria.resultados)
```

Capas internas (detalle en `AGENTS.md` §3): `views → services → formulas → math_utils`. Los endpoints DRF no contienen matemática; los serializers validan el contrato; las fórmulas son funciones puras `calcular_<indicador>`; el redondeo ocurre una sola vez en el servicio. El servicio es **sin estado** y **sin base de datos**. Se despliega como Render Web Service público para usar el plan gratuito; el cálculo sigue protegido por `X-API-Key`.

### 4.1 Verificación contra el backend existente

El análisis del backend Node.js y de MongoDB **no pudo realizarse**: no se dispuso del repositorio. Ningún nombre de modelo, servicio o campo del backend se da por verificado. Deben verificarse antes de integrar:

| Elemento | Origen | Qué verificar |
|---|---|---|
| `AntropometriaSchema` con subdocumento `resultados` | Material previo | Que exista y que sus claves coincidan con las siete del contrato. |
| `crearConsultaService` / `actualizarConsultaService` | Material previo | Nombres reales y dónde se arma el payload hacia Python. |
| Modelo `Paciente` con `sexo` y `fechaNacimiento` | Material previo | Nombres de campos, tipo de `sexo` en Mongoose y valores posibles. |
| Cálculo de `edad` en Node | `AGENTS.md` §7.1 | Dónde y cómo se calcula (zona horaria, fecha de referencia). |
| Tipo de `grVisceral` y `bodyAge` | Contrato | Que el esquema admita `grVisceral` decimal y `bodyAge` entero; ambos pueden ser `null`. |
| Envío del header `X-API-Key` | Sección 12 | Que Node lea el token de su configuración y lo envíe. |

Cualquier diferencia se documenta en la sección 18.2 con una adaptación compatible.

## 5. Actores y responsabilidades

| Actor | Responsabilidades | No debe |
|---|---|---|
| **Frontend** | Enviar `antropometria.mediciones`. Rotular `grVisceral` como índice de conicidad. | Calcular indicadores ni enviar resultados. |
| **Node.js** | Consultar al paciente; obtener `sexo` y `fechaNacimiento`; calcular `edad`; mapear `sexo` a `"M"`/`"F"`; construir el payload; enviar `X-API-Key`; llamar a Python con timeout; manejar caídas y respuestas inválidas; persistir mediciones y resultados. | Duplicar fórmulas. Persistir resultados corruptos o desfasados. |
| **Python (este módulo)** | Autenticar, validar, calcular, redondear; devolver siempre las siete claves; `422` con mensajes claros; `401`; `500` genérico. | Conectarse a MongoDB, llamar a Node, guardar datos del paciente, loguear el payload. |
| **MongoDB** | Conservar mediciones y resultados. | — |
| **Responsable del proyecto** | Ratificar P-7 y P-8; autorizó la heurística no clínica de `bodyAge` (P-13). | — |

## 6. Contrato de entrada

### 6.1 Endpoint

`POST /calcular-antropometria` — `Content-Type: application/json` — header `X-API-Key` obligatorio (sección 12.1).

### 6.2 Estructura

```json
{
  "paciente": { "sexo": "F", "edad": 32, "fechaNacimiento": "1994-05-12" },
  "mediciones": {
    "peso": 68.5, "talla": 165, "cuello": 33, "brazo": 29,
    "cintura": 76, "cadera": 98,
    "pTricipital": 18, "pBicipital": 10, "pSubescapular": 16, "pSuprailiaco": 15
  }
}
```

- `mediciones` es **obligatorio** y debe tener al menos una medición informada.
- `paciente` es **opcional**. Sin él, los indicadores que necesitan sexo o edad devuelven `null`.
- El request **solo admite** las claves `paciente` y `mediciones`. Cualquier otra (por ejemplo `resultados`) ⇒ `422`.

### 6.3 Campo `paciente`

| Campo | Tipo | Restricciones | Obligatorio |
|---|---|---|---|
| `sexo` | String | Exactamente `"M"` o `"F"`. | No |
| `edad` | Integer | 0 a 120, años cumplidos. | No |
| `fechaNacimiento` | Date (ISO `YYYY-MM-DD`) | Fecha real del calendario; no futura. | No |

Claves desconocidas dentro de `paciente` ⇒ `422`.

**Regla edad / fechaNacimiento (P-4, ✅ cerrada):**

1. `edad` manda. Es la que calcula Node.
2. Si llegan **ambas** y la edad calculada desde `fechaNacimiento` (a la fecha del servidor) difiere de `edad` en **más de 1 año** ⇒ `422` con clave `paciente.edad`. La tolerancia de 1 año absorbe diferencias de zona horaria o de fecha de referencia entre Node y Python.
3. Si llega solo `fechaNacimiento`, la edad se deriva de ella (años cumplidos). Si resulta fuera de 0–120 ⇒ `422`.
4. Si no llega ninguna, la edad es "no disponible" y los indicadores que la requieren devuelven `null`.

### 6.4 Campo `mediciones`

| Campo | Tipo | Unidad | Rango aceptado (P-6, ✅ cerrada) |
|---|---|---|---|
| `peso` | Float | kg | > 0 y 2 a 500 |
| `talla` | Float | cm | > 0 y 30 a 272 |
| `cuello` | Float | cm | > 0 y 10 a 80 |
| `brazo` | Float | cm | > 0 y 5 a 80 |
| `cintura` | Float | cm | > 0 y 20 a 250 |
| `cadera` | Float | cm | > 0 y 30 a 250 |
| `pTricipital` | Float | mm | 0 a 80 |
| `pBicipital` | Float | mm | 0 a 80 |
| `pSubescapular` | Float | mm | 0 a 80 |
| `pSuprailiaco` | Float | mm | 0 a 80 |

- Todas las mediciones son individualmente opcionales, pero debe venir al menos una (no `null`). Un objeto `mediciones` vacío ⇒ `422`.
- Sin `NaN` ni infinitos.
- Claves desconocidas (por ejemplo `pTriciptal`) ⇒ `422` (P-9, ✅ cerrada: los serializers rechazan claves extra en raíz, `paciente` y `mediciones`).
- Los rangos son constantes con nombre en `core/serializers.py` y se pueden ajustar sin cambiar la lógica.

## 7. Contrato de salida

### 7.1 Respuesta exitosa (`200`)

Resultado para el payload de la sección 6.2 (cálculo manual en cada indicador de la sección 8):

```json
{
  "ok": true,
  "resultados": {
    "imc": 25.16,
    "porcentajeMG": 30.4,
    "porcentajeMM": 32.1,
    "mBasal": 1395.3,
    "bodyAge": 35,
    "grVisceral": 1.08,
    "icc": 0.78
  }
}
```

### 7.2 Reglas del objeto `resultados`

- Siempre **exactamente siete claves**, sin omitir ni agregar.
- No disponible ⇒ `null` (nunca `0`, `NaN`, `Infinity` ni string vacío).
- Los indicadores clínicos se redondean una sola vez, en el servicio, con `ROUND_HALF_UP`. La heurística `bodyAge` redondea su ajuste a años con ese mismo modo.
- Un `200` implica que **al menos un** indicador tiene valor (sección 9.9).

| Clave | Descripción | Unidad | Decimales (P-5, ✅ cerrada) |
|---|---|---|---|
| `imc` | Índice de Masa Corporal | kg/m² | 2 |
| `porcentajeMG` | Porcentaje de masa grasa | % | 1 |
| `porcentajeMM` | Porcentaje de masa muscular esquelética | % | 1 |
| `mBasal` | Metabolismo basal | kcal/día | 1 |
| `bodyAge` | Edad corporal estimada (heurística no clínica) | años | entero |
| `grVisceral` | Índice de conicidad (indicador antropométrico de adiposidad abdominal) | adimensional | 2 |
| `icc` | Índice cintura-cadera | adimensional | 2 |

El nombre `grVisceral` se mantiene por compatibilidad con el esquema de Node, pero **no es la escala de grasa visceral de una balanza de bioimpedancia** (por ejemplo 1–59). El frontend debe rotularlo como "índice de conicidad".

### 7.3 Respuesta de error

```json
{ "ok": false, "error": true, "detail": { "mediciones.peso": ["Debe ser mayor que 0."] } }
```

`ok: false` permite a Node distinguir éxito de error con un solo campo. Los mensajes están en español.

## 8. Especificación de indicadores

Regla general: **no se inventan fórmulas ni se presentan estimaciones como clínicamente validadas**. Una heurística solo puede implementarse con autorización expresa, alcance delimitado y rotulación no clínica; CALC-005 es la única autorizada actualmente.

### 8.0 Resumen de estado

| ID | Clave | Método | Estado |
|---|---|---|---|
| CALC-001 | `imc` | Quetelet | ✅ |
| CALC-002 | `porcentajeMG` | Durnin-Womersley 1974 + Siri 1961 | ✅ |
| CALC-003 | `porcentajeMM` | Heymsfield 1982 (músculo esquelético) | ✅ |
| CALC-004 | `mBasal` | Mifflin-St Jeor 1990 | ✅ |
| CALC-005 | `bodyAge` | Heurística autorizada, no clínica (P-13) | ⚠ |
| CALC-006 | `grVisceral` | Índice de conicidad, Valdez 1991 | ✅ |
| CALC-007 | `icc` | Cociente cintura/cadera | ✅ |

Orden de implementación: CALC-001 y CALC-007; luego CALC-004, CALC-006, CALC-002 y CALC-003, de a uno por vez y con sus tests. Cada fórmula se implementa con la cita completa en su docstring y el cálculo manual en el test.

### 8.1 CALC-001 — Índice de Masa Corporal (`imc`) ✅

| Aspecto | Definición |
|---|---|
| **Descripción / objetivo** | Relación entre peso y cuadrado de la estatura; indicador general peso-talla. |
| **Fórmula** | `IMC = peso / talla_m²`, con `talla_m = talla / 100`. |
| **Variables** | `peso` (kg), `talla` (cm). |
| **Salida** | kg/m². |
| **Se ejecuta si** | Llegan `peso` y `talla`. |
| **`null` si** | Falta alguno, o `talla_m` es 0. |
| **Fuente** | Quetelet (índice de peso/estatura²). WHO. *Obesity: preventing and managing the global epidemic.* WHO Technical Report Series 894. Geneva; 2000. |
| **Validación** | `68.5 / 1.65² = 25.1607 → 25.16`. |

### 8.2 CALC-002 — Porcentaje de masa grasa (`porcentajeMG`) ✅

Método: **Durnin-Womersley** (densidad corporal a partir de cuatro pliegues) y conversión a porcentaje con la ecuación de **Siri**. Es el método que coincide con los cuatro pliegues del contrato.

| Aspecto | Definición |
|---|---|
| **Variables** | `sexo`, `edad`, `pBicipital`, `pTricipital`, `pSubescapular`, `pSuprailiaco` (mm). Los cuatro pliegues son obligatorios. |
| **Paso 1** | `S = pBicipital + pTricipital + pSubescapular + pSuprailiaco` (mm). |
| **Paso 2** | `D = c − m · log10(S)`, con `c` y `m` según sexo y edad (tabla abajo). |
| **Paso 3 (Siri)** | `%MG = 495 / D − 450`. |
| **Salida** | % (1 decimal). |
| **Población de aplicabilidad** | Adultos de 17 a 72 años. Fuera de ese rango ⇒ `null`. |
| **`null` si** | Falta cualquier variable; `S ≤ 0`; edad fuera de 17–72; `D ≤ 0`; el `%MG` resultante no está entre 0 y 100. |
| **No mezclar** | No se combinan coeficientes de este método con otros métodos ni con otra ecuación de conversión. |

Coeficientes (`S` en mm, `D` en g/mL):

| Edad (años) | Hombres `c` | Hombres `m` | Mujeres `c` | Mujeres `m` |
|---|---|---|---|---|
| 17–19 | 1.1620 | 0.0630 | 1.1549 | 0.0678 |
| 20–29 | 1.1631 | 0.0632 | 1.1599 | 0.0717 |
| 30–39 | 1.1422 | 0.0544 | 1.1423 | 0.0632 |
| 40–49 | 1.1620 | 0.0700 | 1.1333 | 0.0612 |
| 50–72 | 1.1715 | 0.0779 | 1.1339 | 0.0645 |

**Fuentes.** Durnin JVGA, Womersley J. *Body fat assessed from total body density and its estimation from skinfold thickness: measurements on 481 men and women aged from 16 to 72 years.* Br J Nutr. 1974;32(1):77-97. Siri WE. *Body composition from fluid spaces and density.* En: Brozek J, Henschel A, eds. Techniques for Measuring Body Composition. National Academy of Sciences; 1961:223-244.

**Validación a mano** (F, 32 años): `S = 10 + 18 + 16 + 15 = 59`; `log10(59) = 1.77085`; `D = 1.1423 − 0.0632 · 1.77085 = 1.03038`; `%MG = 495 / 1.03038 − 450 = 30.404 → 30.4`.

**Límites a documentar en el docstring.** Es una estimación indirecta con error de estimación apreciable respecto de métodos de referencia (densitometría, DXA). Los pliegues deben medirse con técnica estandarizada.

### 8.3 CALC-003 — Porcentaje de masa muscular (`porcentajeMM`) ✅

Método: **Heymsfield et al. (1982)**. Estima **masa muscular esquelética** a partir del área muscular del brazo corregida por hueso. **No** es masa magra ni masa libre de grasa, y no se calcula como `peso − masa grasa`.

| Aspecto | Definición |
|---|---|
| **Variables** | `peso` (kg), `talla` (cm), `brazo` (cm), `pTricipital` (mm → cm), `sexo`, `edad`. |
| **Paso 1** | `TSF_cm = pTricipital / 10`. |
| **Paso 2 (área muscular del brazo corregida, cm²)** | `CAMA = (brazo − π · TSF_cm)² / (4π) − k`, con `k = 10` para `M` y `k = 6.5` para `F`. |
| **Paso 3 (masa muscular esquelética, kg)** | `MME = talla · (0.0264 + 0.0029 · CAMA)`. |
| **Paso 4** | `%MM = MME / peso · 100`. |
| **Salida** | % (1 decimal). |
| **Población de aplicabilidad** | Adultos (≥ 18 años). Con edad menor ⇒ `null`. |
| **`null` si** | Falta cualquier variable; `brazo − π · TSF_cm ≤ 0`; `CAMA ≤ 0`; el `%MM` resultante no está entre 0 y 100. |

**Fuente.** Heymsfield SB, McManus C, Smith J, Stevens V, Nixon DW. *Anthropometric measurement of muscle mass: revised equations for calculating bone-free arm muscle area.* Am J Clin Nutr. 1982;36(4):680-690.

**Validación a mano** (F, 68.5 kg, 165 cm, brazo 29 cm, tricipital 18 mm): `TSF = 1.8`; `π·1.8 = 5.6549`; `29 − 5.6549 = 23.3451`; `23.3451² / 4π = 43.369`; `CAMA = 43.369 − 6.5 = 36.869`; `MME = 165 · (0.0264 + 0.0029 · 36.869) = 21.998 kg`; `%MM = 21.998 / 68.5 · 100 = 32.11 → 32.1`.

**Límites a documentar en el docstring.** Estima músculo esquelético total desde un único sitio (brazo). Verificar la ecuación de `MME` contra la fuente primaria antes del merge.

### 8.4 CALC-004 — Metabolismo basal (`mBasal`) ✅

| Aspecto | Definición |
|---|---|
| **Fórmula** | **Mifflin-St Jeor:** `TMB = 10·peso + 6.25·talla − 5·edad + s`, con `s = +5` para `M` y `s = −161` para `F`. |
| **Variables** | `peso` (kg), `talla` (cm), `edad` (años), `sexo`. |
| **Salida** | kcal/día (1 decimal). |
| **Población de aplicabilidad** | Adultos (≥ 18 años). Con edad menor ⇒ `null`. |
| **`null` si** | Falta cualquier variable o la edad es menor que 18. |
| **Fuente** | Mifflin MD, St Jeor ST, Hill LA, Scott BJ, Daugherty SA, Koh YO. *A new predictive equation for resting energy expenditure in healthy individuals.* Am J Clin Nutr. 1990;51(2):241-247. |
| **Validación a mano** | F, 32 años, 68.5 kg, 165 cm: `685 + 1031.25 − 160 − 161 = 1395.25` ⇒ con `ROUND_HALF_UP`, `1395.3`. |

Harris-Benedict se evaluó y no se usa. El metabolismo basal **no** es el gasto energético total y no incorpora actividad física; un gasto energético total sería un indicador nuevo.

### 8.5 CALC-005 — Edad corporal (`bodyAge`) ⚠

**No es una métrica clínica estandarizada y no se presenta como diagnóstico ni como edad metabólica validada.** Por autorización expresa del responsable (P-13), se implementa una heurística orientativa basada en `%MG`, limitada a mujeres de 30–39 años. No reproduce los algoritmos propietarios de balanzas de bioimpedancia ni tiene validación clínica o fuente bibliográfica.

| Aspecto | Definición |
|---|---|
| **Fórmula** | `ajuste = limitar(ROUND_HALF_UP((porcentajeMG - 24) × 0.5), -8, 12)`; `bodyAge = max(18, edad + ajuste)`. |
| **Variables** | `edad` (años), `sexo` (`"F"`), `porcentajeMG` (%) calculado sin redondear. |
| **Salida** | Años enteros. |
| **Población de aplicabilidad** | Solo mujeres de 30–39 años, inclusive. |
| **`null` si** | Falta la edad o `%MG`; el sexo no es `"F"`; la edad queda fuera de 30–39; o `%MG` no es finito. |
| **Redondeo** | El ajuste usa `ROUND_HALF_UP`, no `round()` de Python; luego se limita a −8/+12 años. |
| **Fundamento** | Heurística propuesta por el responsable y autorizada el 25/11/2026 (P-13). No se atribuye a una publicación ni se considera clínicamente validada. |
| **Validación a mano** | Ejemplo de la sección 6.2: `%MG` sin redondear ≈ `30.4043`; `(30.4043 − 24) × 0.5 = 3.20215` ⇒ ajuste `3` ⇒ `32 + 3 = 35`. |

El `bodyAge` resultante es orientativo y no debe mostrarse aislado de esta advertencia. Si `%MG` no se puede calcular, `bodyAge` también queda en `null`.

### 8.6 CALC-006 — Grasa visceral: índice de conicidad (`grVisceral`) ✅

Método: **índice de conicidad (C-index)**, de Valdez. Es un indicador antropométrico de adiposidad abdominal derivado de la cintura, el peso y la talla. Es una **estimación antropométrica** y no una medición directa de grasa visceral.

| Aspecto | Definición |
|---|---|
| **Fórmula** | `C = cintura_m / (0.109 · √(peso / talla_m))`, con `cintura_m = cintura / 100` y `talla_m = talla / 100`. |
| **Variables** | `cintura` (cm), `peso` (kg), `talla` (cm). |
| **Salida** | Adimensional (2 decimales). |
| **`null` si** | Falta cualquier variable; el denominador es 0. |
| **Fuente** | Valdez R. *A simple model-based index of abdominal adiposity.* J Clin Epidemiol. 1991;44(9):955-956. |
| **Validación a mano** | `cintura_m = 0.76`; `√(68.5 / 1.65) = 6.4432`; `0.109 · 6.4432 = 0.70231`; `C = 0.76 / 0.70231 = 1.0821 → 1.08`. |

Reglas: no se presenta como diagnóstico ni como medición con equipamiento médico. Usa el sexo y la edad solo si en el futuro se agregan puntos de corte; hoy no los usa.

### 8.7 CALC-007 — Índice cintura-cadera (`icc`) ✅

| Aspecto | Definición |
|---|---|
| **Fórmula** | `ICC = cintura / cadera`. |
| **Variables** | `cintura` (cm), `cadera` (cm). |
| **Salida** | Adimensional (2 decimales). |
| **`null` si** | Falta alguna. Un `cadera = 0` ya fue rechazado con `422` por el schema; la fórmula igualmente usa división segura y devuelve `None`. |
| **Fuente** | WHO. *Waist circumference and waist-hip ratio: report of a WHO expert consultation, Geneva, 8-11 December 2008.* Geneva: WHO; 2011. |
| **Validación** | `76 / 98 = 0.7755 → 0.78`. |

## 9. Reglas de negocio

1. **Independencia.** Cada indicador se calcula por separado; un dato faltante solo anula los que dependen de él.
2. **Dependencias.** Si un indicador usa a otro, usa el valor sin redondear; si el insumo es `null`, el dependiente es `null`.
3. **Unidades.** Fijas (sección 6.4). Las conversiones viven solo en `math_utils`.
4. **Redondeo.** `ROUND_HALF_UP` con `Decimal`; los indicadores clínicos se redondean una sola vez en el servicio. `bodyAge` redondea solo su ajuste a años como parte de la heurística. Prohibido `round()` nativo.
5. **Metabolismo basal.** No incluye actividad física.
6. **Masa muscular.** `porcentajeMM` es masa muscular esquelética; no se equipara con masa magra ni masa libre de grasa.
7. **Estimaciones.** No son diagnósticos ni mediciones con equipamiento clínico.
8. **Sin resultados como entrada.** `resultados` no es un campo del request.
9. **Cobertura mínima (P-11, ✅ cerrada).** Si la entrada es válida pero **ningún** indicador puede calcularse (las siete claves serían `null`), el servicio lanza `DatosInsuficientesError` y responde `422` con `detail: "No hay datos suficientes para calcular ningún indicador."`. Nunca se devuelve un `200` con todo en `null`.
10. **Fallo de un indicador (P-8, 🟡).** Una excepción inesperada deja en `null` solo ese indicador, se registra con `logger.exception` sin datos del paciente y no afecta a los demás. Si por eso quedan las siete claves en `null`, aplica la regla 9.

## 10. Validaciones

| Nivel | Regla | Resultado |
|---|---|---|
| Autenticación | Header `X-API-Key` presente y correcto. | `401` |
| Estructura | `mediciones` presente y es objeto. | `422` |
| Claves desconocidas | En raíz, `paciente` y `mediciones`. | `422` |
| Tipos | Numéricos como número, `sexo` string, fecha ISO. | `422` |
| Valores no finitos | `NaN` e infinitos. | `422` |
| Rangos | Tablas 6.3 y 6.4. | `422` |
| Fecha | Real y no futura. | `422` |
| Edad cruzada | `edad` vs `fechaNacimiento` difieren en más de 1 año. | `422` |
| Mediciones vacías | `mediciones` sin ninguna medición informada. | `422` |
| Cobertura | Ningún indicador calculable. | `422` (`DatosInsuficientesError`) |
| JSON | Cuerpo malformado o `Content-Type` no JSON. | `422` / `415` según el framework |

Validaciones de un campo en `validate_<campo>`; cruzadas en `validate()` de los serializers DRF; mensajes en español.

## 11. Manejo de errores

| Situación | HTTP | Respuesta |
|---|---|---|
| Datos válidos con al menos un indicador calculado | `200` | `{ok: true, resultados}` |
| Entrada inválida o sin datos suficientes | `422` | `{ok: false, error: true, detail}` |
| Token ausente o incorrecto | `401` | `{ok: false, error: true, detail: "No autorizado."}` |
| Error no previsto | `500` | `{ok: false, error: true, detail: "Error interno del servidor."}` |

Handlers centralizados en `core/exceptions.py`. Nunca se devuelven trazas ni mensajes internos. No se loguea el payload completo ni datos identificables del paciente; solo eventos, tipos de error y nombres de campo.

## 12. Endpoints

### 12.1 `POST /calcular-antropometria`

| Aspecto | Definición |
|---|---|
| Responsabilidad | Autenticar, validar y devolver los siete indicadores. |
| Ruta | `/calcular-antropometria` (sin `/api/` ni barra final; P-10 ✅ cerrada). |
| Content-Type | `application/json` |
| Autenticación | Header `X-API-Key` igual a `API_TOKEN`, comparado en tiempo constante (`hmac.compare_digest`). |
| Request | Sección 6. |
| Respuestas | `200`, `401`, `422`, `500` (sección 11). |

**Token (P-10, ✅ cerrada).**

- Si `DEBUG` es falso y `API_TOKEN` está vacío, **el servicio no arranca**.
- Con `DEBUG=True` y token vacío, la autenticación se desactiva y se registra una advertencia.
- El token no se loguea ni se devuelve.
- El servicio tiene una URL pública. `POST /calcular-antropometria` requiere `X-API-Key`, mientras que `GET /health` es público. El token se guarda únicamente en el backend Node y en Render; nunca se expone al frontend. Si ambos servicios están en Render, Node puede usar la dirección interna para comunicarse con Python.

### 12.2 `GET /health`

Exento de autenticación. Respuesta `200`:

```json
{ "status": "ok", "service": "Calculos Nutricionales" }
```

### 12.3 Implementación HTTP

La aplicación se configura en `config/settings.py`, registra las rutas Django en
`config/urls.py` y expone `config.asgi:application` para Daphne. En desarrollo se
puede ejecutar con `python manage.py runserver`. No se configura una base de
datos Django ni se ejecutan migraciones; el módulo no persiste información.
`DJANGO_SECRET_KEY` y `ALLOWED_HOSTS` son obligatorias con `DEBUG=False`.
Cuando `DEBUG=True` y falta `DJANGO_SECRET_KEY`, se genera una clave efímera
solo para ese proceso.

## 13. Integración con Node.js

### 13.1 Flujo de creación de consulta

1. El frontend envía `antropometria.mediciones`.
2. Node recibe la solicitud y consulta al paciente en MongoDB.
3. Recupera `sexo` y `fechaNacimiento`; calcula o recupera `edad`; mapea `sexo` a `"M"`/`"F"`.
4. Construye `{paciente, mediciones}` y envía `POST /calcular-antropometria` con `X-API-Key` y timeout explícito.
5. Python autentica, valida y calcula; responde `{ok, resultados}`.
6. Node verifica el formato de la respuesta y persiste mediciones y resultados.

### 13.2 Flujo de actualización de consulta

Mismo contrato. Si cambian las mediciones, Node vuelve a pedir los cálculos. Mediciones y resultados se escriben juntos; nunca queda una combinación desfasada.

### 13.3 Política ante fallas (🟡 P-7, a ratificar en el repo de Node)

| Situación | Comportamiento de Node |
|---|---|
| Python no disponible o timeout | **No guardar.** Error controlado al frontend (`503`) que permite reintentar. |
| `422` de Python (incluye "sin datos suficientes") | **No guardar.** Propagar el `detail` al frontend. |
| `401` de Python | **No guardar.** Error controlado (`502`) y alerta de configuración: el token de Node no coincide. |
| `500` de Python | **No guardar.** Error controlado (`502`). |
| Respuesta sin formato `{ok, resultados}`, sin alguna de las siete claves, con tipos inválidos, `NaN`/`Infinity` o claves extra | Respuesta inválida: **no guardar**, error controlado (`502`). |
| Respuesta válida con algunos resultados `null` | Caso normal: guardar tal cual. |
| Actualización con falla del servicio | **No aplicar la actualización**; se conservan mediciones y resultados anteriores, consistentes entre sí. |

Implicancia para el frontend: una consulta con mediciones que no alcanzan para ningún indicador (por ejemplo solo `cuello`) recibe `422`. Conviene que el formulario exija al menos `peso` y `talla`, o `cintura` y `cadera`.

Alternativa evaluada y no propuesta: guardar con `resultados` en `null` y recalcular después. Se descarta porque requiere un mecanismo de reintento no especificado.

## 14. Persistencia en MongoDB

Estructura **conceptual** compatible con Mongoose; debe adaptarse al esquema real una vez verificado (4.1).

```json
{
  "antropometria": {
    "mediciones": { "peso": 68.5, "talla": 165, "cintura": 76, "cadera": 98 },
    "resultados": {
      "imc": 25.16,
      "porcentajeMG": null,
      "porcentajeMM": null,
      "mBasal": 1395.3,
      "bodyAge": null,
      "grVisceral": 1.08,
      "icc": 0.78
    }
  }
}
```

(En este ejemplo no se enviaron pliegues ni brazo, por eso `porcentajeMG` y `porcentajeMM` son `null`; y no hay `sexo` en las mediciones, así que `mBasal` supone que Node lo envió en `paciente`.)

- `resultados` contiene las siete claves.
- Se persiste lo que devolvió Python, sin recalcular.
- Python no escribe en MongoDB.

## 15. Requisitos no funcionales

**Rendimiento.** Aritmética simple en memoria, sin I/O externo en el cálculo. Funciones puras e independientes.

**Mantenibilidad.** Un archivo por indicador. Docstring obligatorio con ecuación, unidades, fuente completa, rango de validez y población. Coeficientes como constantes con nombre (por ejemplo la tabla de Durnin-Womersley). Agregar un indicador no exige cambiar la arquitectura.

**Seguridad.** Autenticación por token en el cálculo, validación de toda la entrada y ausencia de trazas o datos del paciente en errores y logs. La URL del servicio y `/health` son públicos; el token nunca se expone al frontend.

**Consistencia.** Nombres de campo estables, unidades fijas, siempre siete claves. Un cambio de clave, unidad o código de estado requiere acuerdo previo con Node y se anota en `AGENTS.md`.

**Calidad.** Cada indicador exige tests unitarios con valor calculado a mano (los pasos de la sección 8 sirven de base).

## 16. Criterios de aceptación

| ID | Criterio |
|---|---|
| CA-001 | El servicio recibe correctamente el payload JSON del contrato. |
| CA-002 | Valida los datos del paciente (sexo, edad, fecha no futura, consistencia `edad`/`fechaNacimiento`). |
| CA-003 | Valida las mediciones (tipos, rangos de 6.4, `NaN`/infinitos, claves desconocidas). |
| CA-004 | IMC: payload de ejemplo ⇒ `25.16`. |
| CA-005 | ICC: payload de ejemplo ⇒ `0.78`. |
| CA-006 | Metabolismo basal con Mifflin-St Jeor: `F, 32, 68.5 kg, 165 cm` ⇒ `1395.25` antes de redondeo, `1395.3` después. |
| CA-007 | Los indicadores sin datos suficientes devuelven `null`. |
| CA-008 | La respuesta `200` contiene siempre las siete claves, sin extras. |
| CA-009 | Los resultados respetan unidades y decimales de 7.2, con `ROUND_HALF_UP` (incluye un caso exacto en `.5`; `1395.25 → 1395.3` lo cubre). |
| CA-010 | Un dato faltante no impide calcular otros indicadores independientes. |
| CA-011 | Node.js se comunica correctamente con Python, enviando `X-API-Key`. |
| CA-012 | Node.js almacena mediciones y resultados en MongoDB. |
| CA-013 | Las actualizaciones de mediciones generan resultados actualizados; no quedan resultados desfasados. |
| CA-014 | Hay pruebas unitarias para cada fórmula implementada (nominal, dato faltante, divisor cero, variante por sexo, redondeo, edad fuera de la población de aplicabilidad). |
| CA-015 | Los errores de comunicación están controlados según 13.3. |
| CA-016 | Una clave desconocida en la raíz, `paciente` o `mediciones` devuelve `422`. |
| CA-017 | Un error inesperado devuelve `500` genérico sin trazas ni datos del paciente. |
| CA-018 | Nunca se devuelve `NaN` ni `Infinity`. |
| CA-019 | Los logs no contienen el payload completo ni datos identificables. |
| CA-020 | `GET /health` responde `200` con `status` y `service`, sin token. |
| CA-021 | `bodyAge` estima `35` para el ejemplo de sección 6.2; solo aplica a mujeres de 30–39 años con `%MG` disponible y usa el ajuste limitado −8/+12 con `ROUND_HALF_UP`. En otro sexo, edad fuera del rango o sin `%MG`, devuelve `null`; se declara siempre como heurística no clínica. |
| CA-022 | Sin `X-API-Key` o con uno incorrecto, `POST /calcular-antropometria` devuelve `401`. |
| CA-023 | Con `DEBUG` falso y `API_TOKEN` vacío, el servicio no arranca. |
| CA-024 | `edad` y `fechaNacimiento` que difieren en más de 1 año devuelven `422`. |
| CA-025 | Un payload válido sin datos para ningún indicador (por ejemplo solo `cuello`) devuelve `422`, no `200` con todo en `null`. |
| CA-026 | `mediciones` vacío devuelve `422`. |
| CA-027 | Un valor fuera de los rangos de plausibilidad (por ejemplo `talla = 5000`) devuelve `422`. |
| CA-028 | `porcentajeMG` y `porcentajeMM` devuelven `null` para edades fuera de su población de aplicabilidad. |

## 17. Restricciones

- Python es responsable de los cálculos; Node.js, de la integración y la persistencia; MongoDB conserva mediciones y resultados.
- El frontend no calcula indicadores. No se duplican fórmulas en Node.js.
- No se modifica la estructura general del proyecto sin justificación escrita.
- No se usan fórmulas clínicas sin documentación ni cita bibliográfica.
- `bodyAge` es la única heurística autorizada y debe describirse siempre como no clínica, limitada y no validada.
- No se confunde metabolismo basal con gasto energético total, ni masa muscular con masa magra o libre de grasa.
- No se presentan estimaciones antropométricas como diagnósticos.
- No se agregan dependencias de persistencia ni componentes de TaskFlow que no se usan (Channels, Redis, Graphene, drivers de base de datos o MongoDB).
- No se copia nada del dominio de TaskFlow.

## 18. Decisiones técnicas y discrepancias

### 18.1 Estado de las decisiones

| # | Decisión | Estado |
|---|---|---|
| P-1 | `porcentajeMG`: Durnin-Womersley + Siri (8.2) | ✅ |
| P-2 | `porcentajeMM`: Heymsfield, masa muscular esquelética (8.3) | ✅ |
| P-3 | `mBasal`: Mifflin-St Jeor (8.4) | ✅ |
| P-4 | `edad` manda; `422` si difiere de `fechaNacimiento` en más de 1 año (6.3) | ✅ |
| P-5 | `grVisceral` = índice de conicidad, 2 decimales (8.6) | ✅ |
| P-6 | Rangos de plausibilidad (6.4) | ✅ |
| P-7 | Política de Node ante fallas (13.3) | 🟡 Ratificar en el repo de Node |
| P-8 | Fallo de un indicador ⇒ `null` solo en ese indicador (9.10) | 🟡 |
| P-9 | Rechazo de claves desconocidas en raíz, `paciente` y `mediciones` | ✅ |
| P-10 | Ruta fija y token `X-API-Key` obligatorio (12.1) | ✅ |
| P-11 | Todo `null` ⇒ `422` (9.9) | ✅ |
| P-12 | Citas de IMC e ICC, decimales 2 y 2 (8.1, 8.7) | ✅ |
| P-13 | `bodyAge` usa heurística autorizada, solo mujeres de 30–39 años, con ajuste por `%MG` limitado −8/+12; no validada ni clínica (8.5) | ✅ Autorizada, no clínica |

Pendiente real: ratificar P-7 y P-8, y **contrastar los coeficientes de 8.2, 8.3 y 8.6 con las fuentes primarias antes del merge**.

### 18.2 Discrepancias detectadas y adaptación adoptada

| Tema | Diferencia | Adaptación |
|---|---|---|
| Ejemplo del contrato | `AGENTS.md` original y el material previo mostraban `bodyAge: 34` y `grVisceral: 6`, y valores de `porcentajeMG`, `porcentajeMM` y `mBasal` ilustrativos. | Se reemplazaron por los valores calculados a mano (7.1). `bodyAge: 35` resulta de la heurística autorizada (8.5). |
| `grVisceral` | El material previo lo mostraba como entero (6), con escala no definida. | Pasa a ser el índice de conicidad con 2 decimales. Node y el frontend deben aceptar decimales y rotularlo. |
| Framework HTTP | La especificación inicial no coincidía con el stack elegido para el módulo. | Se establece Django + DRF, servido por Daphne; no cambia el contrato HTTP ni los cálculos. |
| `bodyAge` entero o decimal | El serializer DRF lo define como entero; los ejemplos, entero. | Se devuelve como entero únicamente cuando cumple el alcance de la heurística autorizada; si no, `null`. |
| `cadera = 0` | El enunciado admitía `null` o error. | `422` en el schema; `None` en la fórmula por defensa. |
| Fecha de nacimiento | `AGENTS.md` pedía fecha real. | Además se rechazan fechas futuras. |
| Todo `null` | El enunciado admitía `200` con nulos. | `422` con `DatosInsuficientesError` (9.9). |
| Autenticación | El material previo no definía token. | Header `X-API-Key` + variable `API_TOKEN` (12.1); `core/security.py` y fila nueva en la tabla de variables de `AGENTS.md`. |
| Backend Node.js | No se pudo inspeccionar. | Sección 4.1: lista de verificaciones; no se inventaron nombres. |

## 19. Referencias bibliográficas

1. Mifflin MD, St Jeor ST, Hill LA, Scott BJ, Daugherty SA, Koh YO. A new predictive equation for resting energy expenditure in healthy individuals. Am J Clin Nutr. 1990;51(2):241-247.
2. Durnin JVGA, Womersley J. Body fat assessed from total body density and its estimation from skinfold thickness: measurements on 481 men and women aged from 16 to 72 years. Br J Nutr. 1974;32(1):77-97.
3. Siri WE. Body composition from fluid spaces and density. En: Brozek J, Henschel A, eds. Techniques for Measuring Body Composition. Washington, DC: National Academy of Sciences; 1961:223-244.
4. Heymsfield SB, McManus C, Smith J, Stevens V, Nixon DW. Anthropometric measurement of muscle mass: revised equations for calculating bone-free arm muscle area. Am J Clin Nutr. 1982;36(4):680-690.
5. Valdez R. A simple model-based index of abdominal adiposity. J Clin Epidemiol. 1991;44(9):955-956.
6. World Health Organization. Obesity: preventing and managing the global epidemic. WHO Technical Report Series 894. Geneva: WHO; 2000.
7. World Health Organization. Waist circumference and waist-hip ratio: report of a WHO expert consultation, Geneva, 8-11 December 2008. Geneva: WHO; 2011.
8. `AGENTS.md` del proyecto: arquitectura, convenciones y reglas de comportamiento del agente.
