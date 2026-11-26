# AGENTS.md — Módulo de cálculos antropométricos y nutricionales

Guía técnica permanente para cualquier agente de IA (o persona) que trabaje en este módulo.
**Leé este archivo completo antes de tocar código.** Si algo de acá choca con lo que ves en el repo, frená y preguntá: no improvises.

> Estado actual: **implementación en curso**. La arquitectura vigente es Django + Django REST Framework; esta guía debe mantenerse alineada con el código y con `SPEC.md`.

---

## 0. Cómo leer este documento

El módulo se rige por dos principios que no se mezclan:

| | Principio | Qué abarca | Fuente de verdad |
|---|---|---|---|
| **A** | **Herencia técnica** | Arquitectura, capas, configuración, convenciones, estilo, manejo de errores, tests, despliegue | Proyecto de referencia **TaskFlow** (`progIV-Taskflow`) |
| **B** | **Independencia funcional** | Entidades, esquemas, fórmulas, contrato JSON, lógica de negocio | **Solo este módulo** (sección 4 en adelante) |

TaskFlow es **solo una referencia técnica y estructural**. No se copia nada de su dominio: ni `Project`, `Task`, `Tag`, `ProjectMembership`, `SecurityLog`, ni sus servicios, permisos, notificaciones, importadores o reglas de negocio.

---

## 1. Análisis del proyecto de referencia (TaskFlow)

### 1.1 Qué es

API REST de gestión de tareas y proyectos. **Python 3.12, Django 6.1 + Django REST Framework**, servida con **Daphne (ASGI)**. Incluye WebSockets (Channels + Redis), GraphQL (Graphene), JWT (SimpleJWT), PostgreSQL/SQLite, Docker y tests con pytest. Es una app Django única (`core`) más un paquete de proyecto (`config`).

### 1.2 Estructura observada

```
progIV-Taskflow/
├── config/                 # configuración del proyecto
│   ├── settings.py         #   variables de entorno con python-dotenv, LOGGING, REST_FRAMEWORK
│   ├── urls.py             #   enrutado raíz (/api/, /graphql/)
│   └── asgi.py / wsgi.py   #   puntos de entrada del servidor
├── core/                   # una sola app, módulos PLANOS por responsabilidad
│   ├── models.py           #   entidades (ORM)
│   ├── serializers.py      #   validación + (de)serialización
│   ├── services.py         #   lógica de negocio (clases con métodos estáticos/de clase)
│   ├── repositories.py     #   acceso a datos (queries reutilizables)
│   ├── views.py            #   endpoints delgados (ViewSets / APIView)
│   ├── urls.py             #   rutas (DefaultRouter)
│   ├── permissions.py / throttles.py
│   ├── exceptions.py       #   handler de errores centralizado
│   └── tests/              #   test_services.py, test_endpoints.py
├── conftest.py             # fixtures globales de pytest
├── pytest.ini
├── requirements.txt
├── Dockerfile / .dockerignore / .gitignore
└── manage.py
```

### 1.3 Convenciones y patrones detectados

| Aspecto | Qué hace TaskFlow |
|---|---|
| **Capas** | `views` (HTTP) → `services` (negocio) → `repositories` (datos) → `models`. Las vistas casi no tienen lógica: delegan. |
| **Servicios** | Clases agrupadoras sin estado: `TaskService`, `MembershipService`, `HolidayService`, `NotificationService`. Métodos `@staticmethod` / `@classmethod`. Nunca se instancian. |
| **Nombres de archivos** | `snake_case`, un archivo por responsabilidad, nombres en inglés (`services.py`, `serializers.py`, `exceptions.py`). |
| **Nombres de clases** | `PascalCase` con sufijo de rol: `...Service`, `...Repository`, `...ViewSet`, `...Serializer`, `Is...OrReadOnly`. |
| **Funciones/variables** | `snake_case`. Constantes de clase en `MAYUSCULAS` (`API_URL`, `TIMEOUT`). Helpers internos con prefijo `_`. |
| **Idioma** | Identificadores técnicos en inglés; **comentarios, docstrings, mensajes de error, nombres de tests y fixtures en español rioplatense** (voseo). |
| **Validación** | En serializers: `validate_<campo>` para reglas de un campo y `validate()` para reglas cruzadas. Los errores de negocio se lanzan como excepciones de validación con mensaje en español. |
| **Errores** | Handler único (`custom_exception_handler`) que normaliza **toda** respuesta de error a `{"error": true, "detail": ...}`. Excepciones no previstas → `500` con mensaje genérico, sin filtrar detalles internos. |
| **Servicios externos** | `HolidayService`: `requests.get` con `TIMEOUT = 5`, `raise_for_status()`, captura acotada (`RequestException, KeyError, ValueError`), **fallback seguro** (lista vacía) y caché. El error de red nunca rompe al llamador. |
| **Logging** | `logging.getLogger(__name__)`; `LOGGING` en settings con formato `[{asctime}] {levelname} {name}: {message}` a stdout; `logger.exception(...)` en los bordes. |
| **Configuración** | `python-dotenv` + `os.getenv` con defaults seguros (`DEBUG` falso por defecto, listas separadas por coma). Nada sensible hardcodeado. `.env` ignorado, `.env.example` versionado. |
| **Dependencias** | Un único `requirements.txt` con versiones fijadas (`==`); dependencias de test incluidas en el mismo archivo. |
| **Tests** | `pytest` (`pytest.ini` con `testpaths`, `python_files`). Funciones `test_...` sueltas, sin clases. Comentarios `# 1) ...` describiendo cada caso. Fixtures en `conftest.py` (`autouse` para aislar el entorno: sin Redis, sin internet, sin throttling). Servicios externos se reemplazan con `monkeypatch`. |
| **Docker** | `python:3.12-slim`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `WORKDIR /app`, copiar `requirements.txt` primero (caché de capas), puerto vía `${PORT:-8000}`, comentarios explicativos en español. |
| **Health check** | Endpoint `GET /api/health/` → `{"status": "ok", "service": "..."}`. |
| **Documentación** | Comentarios breves en español que explican el *por qué*; docstrings solo donde aclaran una regla no obvia. |

### 1.4 Lo que **no** se hereda (y por qué)

Esto es específico de TaskFlow o no lo necesita este módulo:

- ORM, `models.py`, migraciones, `repositories.py`, base de datos relacional → **el módulo no persiste nada** (persiste Node/MongoDB); Django se usa sin configurar una base de datos.
- `ViewSet`, `DefaultRouter`, paginación y filtros → no se necesitan para los dos endpoints del contrato; se usan vistas DRF delgadas.
- JWT, allauth, permisos, throttling, `SecurityLog`, sesiones, CSRF, admin → fuera de alcance.
- Channels/WebSockets, Redis, GraphQL/Graphene, WhiteNoise/`collectstatic`, CORS, comando `import_task`, datos de ejemplo.

### 1.5 Defectos de TaskFlow que **no** hay que replicar

Se detectaron al analizar; son deuda del proyecto de referencia, no convenciones:

- Archivos vacíos o de compatibilidad sin función (`config/schema.py`, `core/tests/test_views.py`, `core/url.py` como alias de `urls.py`). **No crear archivos vacíos ni alias.**
- Valores de entorno hardcodeados en `settings.py` (hosts permitidos, orígenes CORS).
- Importadores que escriben campos inexistentes en el modelo (`source`) y comentarios que referencian "Clase 4/6" (contexto de cursada).
- Finales de línea CRLF en el repo de referencia: en el módulo usar **un solo estilo (LF)** y no mezclar.
- Importaciones sin uso. Mantener el código sin imports muertos.

---

## 2. Decisiones de herencia y adaptaciones mínimas

El módulo adopta Django + DRF como framework HTTP, de acuerdo con la decisión del responsable. Se conserva el servicio sin estado y sin persistencia: no se agregan modelos ni configuración de base de datos.

| Tema | Referencia | Este módulo | Justificación |
|---|---|---|---|
| Framework HTTP | Django + DRF | **Django + DRF** | Mantiene el stack del proyecto de referencia y usa serializers para validar el contrato. |
| Validación | Serializers DRF | **Serializers DRF** | Reutiliza el mecanismo de validación nativo de la API. |
| Servidor ASGI | Daphne | **Daphne** | Sirve la aplicación ASGI de Django sin agregar Channels. |
| Tests de endpoints | `APIClient` | **`rest_framework.test.APIClient`** | Cliente de pruebas nativo de Django REST Framework. |
| Persistencia | ORM + repositories | **Ninguna** | Python solo valida y calcula; Node/MongoDB persisten. |
| Fórmulas | (no existía) | Paquete `core/formulas/` | El requisito de separar endpoints, servicios y fórmulas obliga a una capa nueva. Es la única capa agregada. |
| Nombre del paquete | `core` | `core` | Se mantiene para conservar la estructura. |

Todo lo demás se hereda tal cual: capas, servicios como clases estáticas, handler de errores centralizado, `python-dotenv`, logging, pytest, Docker, idioma de comentarios y mensajes.

---

## 3. Estructura del módulo

Estructura vigente del repositorio, adaptada de TaskFlow a Django + DRF:

```
<raiz>/
├── AGENTS.md
├── README.md
├── requirements.txt
├── pytest.ini
├── conftest.py
├── Dockerfile
├── docker-compose.yml        # un solo servicio "web"; sin db ni redis
├── .dockerignore
├── .gitignore
├── .env.example
├── config/
│   ├── __init__.py
│   ├── settings.py           # ajustes Django, entorno, DRF y logging
│   ├── urls.py               # enrutamiento raíz
│   ├── asgi.py / wsgi.py     # puntos de entrada del servidor
├── core/
    ├── __init__.py
    ├── apps.py               # configuración de la aplicación Django
    ├── views.py              # APIView delgados, sin matemática
    ├── urls.py               # rutas de la aplicación
    ├── serializers.py        # validación y serialización del contrato DRF
    ├── services.py           # AntropometriaService: orquesta validación → fórmulas → resultados
    ├── exceptions.py         # excepciones propias + handlers centralizados
    ├── security.py           # permiso DRF para el token compartido X-API-Key
    ├── math_utils.py         # conversiones de unidad, redondeo, división segura
    ├── formulas/
    │   ├── __init__.py
    │   ├── imc.py
    │   ├── masa_grasa.py
    │   ├── masa_muscular.py
    │   ├── metabolismo_basal.py
    │   ├── edad_corporal.py
    │   ├── grasa_visceral.py
    │   └── icc.py
    └── tests/
        ├── __init__.py
        ├── test_formulas.py
        ├── test_math_utils.py
        ├── test_services.py
        └── test_endpoints.py
└── manage.py
```

Reglas de la estructura:

- Cada capa solo conoce a la de abajo: `views → services → formulas → math_utils`. Las `formulas` **no** importan nada de `views`, `serializers` ni Django/DRF.
- `views.py` **nunca** contiene fórmulas ni redondeos.
- No crear archivos vacíos "por si acaso" ni alias de compatibilidad.
- No agregar `models.py`, `repositories.py`, `permissions.py` ni `throttles.py`: no hay persistencia ni usuarios.

---

## 4. Contrato del servicio (independencia funcional)

### 4.1 Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/calcular-antropometria` | Valida el payload y devuelve los siete indicadores. |
| `GET` | `/health` | `{"status": "ok", "service": "Calculos Nutricionales"}` (mismo patrón que `health_check` de TaskFlow). |

> La ruta sale del contrato ya acordado con Node, por eso **no** lleva el prefijo `/api/` que usa TaskFlow ni barra final. Decisión cerrada (P-10): la ruta es fija y el servicio exige token compartido (ver 4.6).

### 4.2 Request

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

### 4.3 Response exitosa (`200`)

```json
{
  "ok": true,
  "resultados": {
    "imc": 25.16, "porcentajeMG": 30.4, "porcentajeMM": 32.1,
    "mBasal": 1395.3, "bodyAge": 35, "grVisceral": 1.08, "icc": 0.78
  }
}
```

> Los valores del ejemplo se calcularon **a mano** con las ecuaciones y la heurística autorizada del `SPEC.md` §8 para este payload (ver los pasos en cada indicador). `bodyAge` es una estimación heurística no clínica y solo aplica a mujeres de 30–39 años con `%MG` calculable (SPEC §8.5). Un test puede usar esos valores solo si el cálculo manual está documentado en el propio test. `grVisceral` es el índice de conicidad (SPEC §8.6), **no** la escala de grasa visceral de una balanza de bioimpedancia; el frontend debe rotularlo así.

### 4.4 Response de error

Se hereda el envelope de TaskFlow (`{"error": true, "detail": ...}`) y se le agrega `ok: false` para que Node distinga con un solo campo en éxito y error:

```json
{ "ok": false, "error": true, "detail": { "mediciones.peso": ["Debe ser mayor que 0."] } }
```

| Situación | HTTP | Notas |
|---|---|---|
| Datos válidos (aun con indicadores en `null`) | `200` | Que falten datos opcionales **no** es error. |
| Valor mal formado, fuera de rango o clave desconocida | `422` | `detail` = diccionario `campo → [mensajes]` (mismo estilo que DRF). Mensajes en español. |
| Datos válidos pero sin datos suficientes para calcular **ningún** indicador | `422` | `DatosInsuficientesError`. `detail` = `"No hay datos suficientes para calcular ningún indicador."` (decisión P-11). |
| Falta o es incorrecto el token (`X-API-Key`) | `401` | `detail: "No autorizado."` Sin pistas sobre el motivo. |
| Error no previsto | `500` | `detail: "Error interno del servidor."` Sin trazas ni datos del paciente. |

### 4.5 Serializers DRF (`core/serializers.py`)

Nombres **obligatorios**: `DatosPacienteInput`, `MedicionesInput`, `CalculoAntropometriaRequest`, `ResultadosAntropometria`, `CalculoAntropometriaResponse`.

Reglas de diseño:

- Los **campos mantienen el nombre camelCase del contrato JSON** (`pTricipital`, `fechaNacimiento`, `porcentajeMG`, ...). Es una excepción consciente a PEP 8: el contrato con Node manda.
- En los serializers, los campos opcionales usan `required=False`, `allow_null=True` y valor predeterminado `None`. Solo `mediciones` es obligatorio en el request; `paciente` es opcional.
- `sexo`: restringir a `"M"` o `"F"` con `ChoiceField`.
- Numéricos: `peso`, `talla`, `cuello`, `brazo`, `cintura`, `cadera` deben ser mayores que cero; pliegues admiten cero; `edad` entre 0 y 120. Rechazar `NaN` e infinitos.
- `mediciones` rechaza claves desconocidas: una clave mal escrita (`pTriciptal`) debe dar `422` y no un resultado silenciosamente en `null`. Misma regla para `paciente` y para el nivel raíz del request (por ejemplo, un campo `resultados` enviado por el cliente se rechaza). Decisión P-9 cerrada: validación estricta en los tres niveles.
- `fechaNacimiento` en formato ISO `YYYY-MM-DD`, validada como fecha real y **no futura**.
- **Consistencia `edad` / `fechaNacimiento` (P-4 cerrada):** `edad` manda. Si llegan ambas y la edad calculada desde `fechaNacimiento` (a la fecha del servidor) difiere de `edad` en **más de 1 año**, `422` con clave `paciente.edad`. Si solo llega `fechaNacimiento`, la edad se deriva de ella; si el resultado queda fuera de 0–120, `422`.
- **Rangos de plausibilidad (P-6 cerrada)**, constantes con nombre en `serializers.py`: `peso` 2–500 kg; `talla` 30–272 cm; `cuello` 10–80 cm; `brazo` 5–80 cm; `cintura` 20–250 cm; `cadera` 30–250 cm; cada pliegue 0–80 mm. Fuera de rango ⇒ `422`.
- `mediciones` no puede venir vacío: al menos una medición informada (no `null`). Si no, `422`.
- Validaciones de un campo en `validate_<campo>`; reglas cruzadas en `validate()`. Mensajes de error en español.
- `ResultadosAntropometria` **siempre incluye las siete claves**; la que no se pudo calcular va en `null` (no se omite).

### 4.6 Autenticación entre Node y Python (P-10 cerrada)

- Header obligatorio `X-API-Key` con el valor de la variable de entorno `API_TOKEN`, comparado con `hmac.compare_digest`. Aplica a `POST /calcular-antropometria`; `GET /health` queda exento.
- Falta o no coincide ⇒ `401` (envelope de 4.4).
- Si `DEBUG` es falso y `API_TOKEN` está vacío, **el servicio no arranca** (falla rápido con un error explícito). Con `DEBUG=True` y token vacío la autenticación se desactiva y se registra una advertencia.
- El despliegue acordado es un Render Web Service con URL pública para usar el plan gratuito. `POST /calcular-antropometria` exige `X-API-Key`; `GET /health` es público y no requiere token.
- `API_TOKEN` se guarda solo en el backend Node y en las variables privadas de Render; nunca se envía desde el frontend. Si Node también está en Render, se prefiere la dirección interna entre servicios del mismo workspace y región.
- El token nunca se loguea ni se devuelve en respuestas.
- Implementación en `core/security.py` como permiso DRF aplicado a `/calcular-antropometria`.

---

## 5. Indicadores y fórmulas

### 5.1 Regla de oro

**No se inventan fórmulas ni se presentan estimaciones como clínicamente validadas.** Una fórmula clínica se implementa solo con referencia exacta (autor, año, ecuación, unidades, rango y población). Una heurística sin validación clínica solo se implementa con autorización explícita del responsable, población e insumos acotados, y documentación inequívoca de que no es clínica. `bodyAge` es la única excepción actualmente autorizada (P-13); no se debe generalizar a otros indicadores.

### 5.2 Estado de cada indicador

| Clave | Indicador | Insumos disponibles en el contrato | Estado |
|---|---|---|---|
| `imc` | Índice de Masa Corporal | `peso` (kg), `talla` (cm → m) | ✅ **Definido** (SPEC §8.1). Decimales: 2. |
| `icc` | Índice Cintura-Cadera | `cintura`, `cadera` (misma unidad) | ✅ **Definido** (SPEC §8.7). Decimales: 2. |
| `porcentajeMG` | % Masa Grasa | 4 pliegues, `sexo`, `edad` | ✅ **Definido** (SPEC §8.2): Durnin-Womersley 1974 + Siri 1961. Decimales: 1. |
| `porcentajeMM` | % Masa Muscular (esquelética) | `peso`, `talla`, `sexo`, `brazo`, `pTricipital` | ✅ **Definido** (SPEC §8.3): Heymsfield 1982. Decimales: 1. |
| `mBasal` | Metabolismo Basal (kcal/día) | `peso`, `talla`, `edad`, `sexo` | ✅ **Definido** (SPEC §8.4): Mifflin-St Jeor 1990. Decimales: 1. |
| `bodyAge` | Edad corporal estimada | `edad`, `sexo`, `%MG` sin redondear | ⚠ Heurística autorizada, no clínica (SPEC §8.5, P-13): solo mujeres de 30–39 años; `null` fuera de alcance o sin `%MG`. |
| `grVisceral` | Indicador antropométrico de grasa visceral (índice de conicidad) | `cintura`, `peso`, `talla` | ✅ **Definido** (SPEC §8.6): Valdez 1991. Decimales: 2. |

Cuando se autorice una fórmula o heurística nueva, actualizar esta tabla y su fundamento **en el mismo cambio** que agrega el código.

### 5.3 Reglas por función

- Una función pública por indicador, con nombre `calcular_<indicador>` (ej. `calcular_imc`), en su propio archivo dentro de `core/formulas/`.
- **Funciones puras**: reciben valores simples (floats, strings), no serializers ni objetos de Django/DRF; no leen entorno, no loguean, no tienen efectos secundarios.
- Devuelven `float | None` (`bodyAge` devuelve `int | None`; ver SPEC §8.5). Devuelven `None` si falta cualquier insumo obligatorio o el caso queda fuera del alcance.
- **Docstring obligatorio** en cada fórmula, en español, con: ecuación, unidades de entrada y salida, **fuente bibliográfica completa**, rango de validez y población a la que aplica. En heurísticas expresamente autorizadas, identificá la autorización y fecha, y declarala sin validación clínica ni fuente bibliográfica. Sin esa distinción no hay merge.
- **Sin divisiones por cero**: usar la división segura de `math_utils` y devolver `None`.
- Constantes y coeficientes de las ecuaciones: constantes con nombre en `MAYUSCULAS` al tope del archivo, nunca números mágicos inline.
- Un indicador **no depende de otro ya redondeado**: `bodyAge` recibe `%MG` sin redondear. Su ajuste se redondea a años con `ROUND_HALF_UP` antes de limitarlo.

### 5.4 Unidades (fijas y documentadas)

| Magnitud | Unidad en el payload |
|---|---|
| `peso` | kg |
| `talla` | **cm** |
| `cuello`, `brazo`, `cintura`, `cadera` | cm |
| pliegues (`pTricipital`, `pBicipital`, `pSubescapular`, `pSuprailiaco`) | mm |
| `edad` | años |

La conversión de talla a metros ocurre **únicamente** dentro de las fórmulas que la requieren, usando `math_utils.cm_a_m`. Nunca se convierten unidades en `views` ni en `schemas`.

### 5.5 Redondeo y nulos

- Un único helper `redondear(valor, decimales)` en `math_utils.py`, con modo **ROUND_HALF_UP** vía `Decimal` (el `round()` nativo usa redondeo bancario y daría resultados inesperados).
- Decimales (P-5 cerrada): `imc` 2, `icc` 2, `porcentajeMG` 1, `porcentajeMM` 1, `mBasal` 1, `grVisceral` 2, `bodyAge` entero.
- Los indicadores clínicos se redondean **una sola vez**, en `AntropometriaService`, al armar `ResultadosAntropometria`. La heurística `bodyAge` usa `redondear(..., 0)` con `ROUND_HALF_UP` para obtener su ajuste entero, como parte de su ecuación; el resto de indicadores se calcula sin redondeos intermedios.
- Dato insuficiente ⇒ `None` en Python ⇒ `null` en JSON. **Nunca** `0`, `NaN` ni string vacío.

---

## 6. Servicio y orquestación

`core/services.py` define `AntropometriaService`, clase sin estado con métodos `@staticmethod`/`@classmethod` (mismo estilo que `TaskService` y `HolidayService`):

1. Recibe `CalculoAntropometriaRequest` ya validado.
2. Resuelve el insumo `edad` (regla en 4.5 y SPEC §6.3).
3. Invoca cada `calcular_*` de forma **independiente**: si una función falla por falta de datos, devuelve `None` sin afectar a las demás.
4. Si las siete claves quedaron en `None`, lanza `DatosInsuficientesError` (⇒ `422`, ver 4.4).
5. Redondea y arma `ResultadosAntropometria`.

Una excepción inesperada en un indicador **no** debe tumbar los demás por defecto; se registra con `logger.exception` y el indicador queda en `null`. (Confirmar el criterio: P-8.)

---

## 7. Integración con Node.js y MongoDB

### 7.1 Flujo

1. El frontend envía `antropometria.mediciones` (sin cálculos hechos en el cliente).
2. Node busca al paciente y obtiene `sexo` y `fechaNacimiento`; **calcula `edad`**.
3. Node hace `POST /calcular-antropometria` con `{ paciente, mediciones }`.
4. Python valida y calcula; responde `{ ok, resultados }`.
5. Node persiste en MongoDB `antropometria.mediciones` **y** `antropometria.resultados`.

### 7.2 Responsabilidades

| Python (este módulo) | Node.js |
|---|---|
| Validar y calcular | Persistir y exponer al frontend |
| Devolver siempre las siete claves | Obtener datos del paciente y calcular la edad |
| Responder `422` con mensajes claros | Mapear `sexo` de Mongoose a `"M"`/`"F"` |
| No conocer MongoDB | Manejar timeouts, caídas y respuestas inválidas |

Python **no** se conecta a MongoDB, **no** llama a Node, **no** guarda archivos ni datos del paciente. No agregar `pymongo`/`motor` ni equivalentes.

### 7.3 Errores de comunicación (del lado Node, a documentar en el contrato)

Se sigue el patrón de `HolidayService` de TaskFlow: timeout corto explícito (ahí `TIMEOUT = 5` s), captura acotada de errores de red/JSON y un **fallback definido** que nunca rompe al llamador. Casos a cubrir en Node:

- Servicio caído o timeout → error controlado (decisión: P-7).
- `422` → error de validación; se propaga al frontend con el `detail`.
- `500` o cuerpo que no cumple `{ ok, resultados }` → tratar como respuesta inválida, no persistir resultados corruptos.

---

## 8. Convenciones de código

- **Python 3.12**. Type hints en todas las firmas públicas (`float | None`).
- `snake_case` para archivos, funciones y variables; `PascalCase` para clases; `MAYUSCULAS` para constantes.
- Servicios: `...Service`. Excepciones propias: sufijo `Error` (ej. `DatosInsuficientesError`). Schemas: los nombres fijados en 4.5.
- Idioma: **identificadores técnicos en inglés cuando son infraestructura** (`Service`, `handler`), **dominio en español** (`calcular_imc`, `cintura`, `fechaNacimiento`) por ser la lengua del contrato. **Comentarios, docstrings, mensajes de error y nombres de tests en español rioplatense (voseo).**
- Funciones chicas, una responsabilidad, sin duplicación. Sin código muerto ni imports sin usar. Sin archivos vacíos.
- Comentarios: explican el *por qué*, no repiten el *qué*.
- Sin dependencias nuevas sin justificación escrita en el cambio.
- Un solo estilo de fin de línea (LF).

---

## 9. Manejo de errores y logging

- **Handler centralizado** en `core/exceptions.py`, registrado en `REST_FRAMEWORK["EXCEPTION_HANDLER"]` desde `config/settings.py`: errores de validación → `422`; excepciones propias → código que corresponda; excepciones no previstas → `500` genérico.
- Todos los errores usan el envelope de 4.4. **Nunca** devolver trazas ni mensajes internos.
- No usar `except Exception: pass`. Capturas **acotadas** y siempre con `logger.exception` o un re-raise con contexto. El `except Exception` amplio solo se admite en el handler global.
- Logging con `logging.getLogger(__name__)` y `LOGGING` en `config/settings.py` (mismo formato y salida a stdout que TaskFlow).
- **Privacidad:** son datos de salud. **No loguear el payload completo ni datos identificables del paciente.** Loguear solo eventos, tipos de error y nombres de campo.

---

## 10. Configuración, dependencias y despliegue

**Configuración** (`config/settings.py`): `load_dotenv()` + `os.getenv` con defaults seguros, igual que TaskFlow. Sin secretos ni hosts hardcodeados. Se versiona `.env.example`; `.env` y `.env.*` quedan ignorados.

Variables previstas (nombres tentativos, solo las que hagan falta):

| Variable | Default | Uso |
|---|---|---|
| `DEBUG` | `False` (`== "True"`) | Modo desarrollo |
| `PORT` | `8000` | Puerto del servidor |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `API_TOKEN` | *(vacío)* | Token compartido con Node (header `X-API-Key`). Obligatorio si `DEBUG` es falso: sin él el servicio no arranca (ver 4.6) |
| `DJANGO_SECRET_KEY` | *(vacío)* | Obligatoria fuera de desarrollo; en desarrollo vacío genera una clave efímera |
| `ALLOWED_HOSTS` | *(vacío)* | Hosts permitidos por Django, separados por coma; configurar para el entorno |

**Dependencias** (`requirements.txt`, único archivo, versiones fijadas con `==`): `Django`, `djangorestframework`, `daphne`, `python-dotenv`, `pytest` y `pytest-cov`. Fijar versiones estables compatibles con Python 3.12. **No** agregar Channels, Redis, Graphene, drivers de base de datos ni clientes de MongoDB.

**Docker y Render:** usar el `Dockerfile` existente con `python:3.12-slim`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `WORKDIR /app`, instalación desde `requirements.txt` y Daphne sirviendo `config.asgi:application` en `${PORT:-8000}`. En Render se crea un **Web Service** con runtime Docker y plan gratuito; Render proporciona `PORT`. No ejecutar `collectstatic` ni `migrate`, porque el módulo no usa archivos estáticos ni base de datos. No se requiere `docker-compose.yml`.

---

## 11. Pruebas

- **pytest**, funciones sueltas `test_<unidad>_<condicion>_<resultado>` en español, con comentarios `# 1) ...` por caso (estilo TaskFlow). Sin clases.
- `pytest.ini`: `testpaths = core/tests`, `python_files = tests.py test_*.py *_tests.py`.
- `conftest.py` raíz con fixtures en español (`cliente`, `paciente_mujer`, `mediciones_completas`, ...).
- **Cada indicador implementado exige tests unitarios**, como mínimo:
  1. Caso nominal con valor calculado **a mano** y comparado con `pytest.approx`.
  2. Dato faltante ⇒ `None`.
  3. Divisor cero o valor límite ⇒ `None`, sin excepción.
  4. Variante por `sexo` cuando la fórmula distinga.
  5. Redondeo (incluyendo un caso exacto en `.5`).
- Tests de endpoint con `rest_framework.test.APIClient`: `200` completo, `200` con nulos, `422` por valor inválido, `422` por clave desconocida, `500` generado con un `monkeypatch` que fuerce una excepción (verificando que el envelope no filtre detalles).
- Prohibido derivar valores esperados ejecutando la propia fórmula bajo prueba, o desde los números ilustrativos del contrato.
- No crear archivos de test vacíos.

---

## 12. Reglas de comportamiento del agente

**Antes de implementar cualquier cosa:**

1. Releé este `AGENTS.md`.
2. Revisá la estructura real del repo y confirmá que coincide con la sección 3.
3. Identificá las convenciones vigentes (secciones 8 a 11).
4. Verificá qué se puede reutilizar técnicamente del patrón de TaskFlow (nunca su lógica).
5. **Planificá los cambios y enumerá los archivos a tocar antes de modificar nada.**

**Durante el desarrollo:**

- No reestructures el proyecto ni cambies tecnologías sin razón técnica escrita.
- No copies lógica de negocio, entidades ni nombres de dominio de TaskFlow.
- No modifiques archivos ajenos al módulo ni dupliques configuración existente.
- **No inventes fórmulas.** Si falta una referencia, dejá el indicador en `null`, documentalo en la tabla 5.2 y preguntá.
- Mantené compatibilidad con el contrato de la sección 4: **cambiar una clave, una unidad o un código de estado rompe a Node**. Cualquier cambio de contrato se acuerda antes y se anota en este archivo.
- Implementá de a un indicador por vez, con sus tests, empezando por los que ya tienen fórmula confirmada.
- Si una instrucción nueva contradice este archivo, señalá el conflicto en lugar de elegir en silencio.

---

## 13. Decisiones (estado al 2026-11-26)

El responsable delegó la elección de métodos y la definición de validaciones. Las referencias y ecuaciones completas están en `SPEC.md` §8. **Antes del primer merge de cada fórmula clínica conviene contrastar los coeficientes con la fuente primaria citada** (el SPEC los transcribe de la bibliografía, no de un archivo entregado). `bodyAge` es la excepción autorizada P-13: una heurística explícitamente no clínica y sin fuente bibliográfica.

| # | Decisión | Estado |
|---|---|---|
| P-1 | `porcentajeMG`: Durnin-Womersley 1974 + Siri 1961 | ✅ Cerrada |
| P-2 | `porcentajeMM`: masa muscular esquelética por Heymsfield 1982 | ✅ Cerrada |
| P-3 | `mBasal`: Mifflin-St Jeor 1990 | ✅ Cerrada |
| P-4 | `edad` manda; rechazo `422` si difiere de `fechaNacimiento` en más de 1 año | ✅ Cerrada (validación en 4.5) |
| P-5 | `grVisceral` = índice de conicidad (2 decimales) | ✅ Cerrada |
| P-6 | Rangos de plausibilidad | ✅ Cerrada (4.5) |
| P-7 | Falla de Python: Node no guarda y devuelve error controlado (SPEC §13.3) | 🟡 Propuesta, a ratificar en el repo de Node |
| P-8 | Excepción inesperada en un indicador ⇒ `null` solo en ese indicador | 🟡 Propuesta vigente |
| P-9 | Rechazo de claves desconocidas en raíz, `paciente` y `mediciones` | ✅ Cerrada |
| P-10 | Ruta `/calcular-antropometria` y token `X-API-Key` obligatorio | ✅ Cerrada (4.6) |
| P-11 | Todo `null` ⇒ `422` (`DatosInsuficientesError`) | ✅ Cerrada |
| P-12 | Citas de IMC e ICC (SPEC §8.1 y §8.7); decimales 2 y 2 | ✅ Cerrada |
| P-13 | Heurística de `bodyAge`: mujeres de 30–39, ajuste basado en `%MG`, límites −8/+12; explícitamente no clínica | ✅ Autorizada, no validada clínicamente (SPEC §8.5) |
| P-14 | Despliegue público como Render Web Service para usar el plan gratuito; `POST` protegido por `X-API-Key` y `/health` público | ✅ Autorizada (2026-11-26) |

---

## 14. Checklist de revisión antes de dar algo por terminado

- [ ] Respeta la estructura y capas de la sección 3; ninguna fórmula en `views.py`.
- [ ] Ninguna fórmula nueva sin cita bibliográfica; toda heurística autorizada está identificada como no clínica y tiene entrada actualizada en la tabla 5.2.
- [ ] Las siete claves salen siempre; los datos insuficientes son `null`.
- [ ] Sin divisiones por cero ni conversiones de unidad fuera de `math_utils`.
- [ ] Errores con el envelope de 4.4; sin trazas ni datos del paciente en respuestas ni logs.
- [ ] Tests unitarios por indicador y de endpoint; `pytest` en verde.
- [ ] Sin dependencias, archivos vacíos ni imports muertos agregados.
- [ ] Nada heredado del dominio de TaskFlow.
