# Módulo de cálculos antropométricos y nutricionales

API sin estado construida con Django y Django REST Framework para validar
mediciones antropométricas y devolver indicadores según las fórmulas
documentadas en [SPEC.md](SPEC.md).

## Desarrollo local

1. Creá un entorno con Python 3.12 e instalá las dependencias:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copiá `.env.example` a `.env`. En desarrollo, `DEBUG=True` permite ejecutar
   sin token; para probar la autenticación, configurá `API_TOKEN`.
3. Iniciá el servidor de desarrollo de Django:

   ```powershell
   python manage.py runserver 127.0.0.1:8000
   ```

El endpoint `GET /health` no requiere autenticación. El endpoint
`POST /calcular-antropometria` exige `X-API-Key` con el valor de `API_TOKEN`,
salvo que `DEBUG=True` y el token esté vacío.

## Despliegue público en Render

Creá un **Web Service**, elegí el plan gratuito si está disponible y seleccioná
**Docker** como runtime. Usá el `Dockerfile` de la raíz; instala las
dependencias e inicia Daphne en el puerto `PORT` que Render asigna. No hacen
falta una base de datos ni migraciones.

Configurá estas variables en el servicio de Render:

- `DEBUG=False`
- `API_TOKEN`: secreto compartido con el backend Node; no lo expongas al frontend.
- `DJANGO_SECRET_KEY`: clave secreta independiente de `API_TOKEN`.
- `ALLOWED_HOSTS`: hostname público exacto que Render asigna al servicio, por
  ejemplo `mi-servicio.onrender.com`, sin `https://` ni rutas.
- `LOG_LEVEL=INFO` (opcional).

No configures `PORT` manualmente en Render y no subas el archivo `.env`.
Configurá `/health` como health check. La URL del servicio y `GET /health` son
públicos; `POST /calcular-antropometria` requiere `X-API-Key`. Guardá el token
solo en el backend Node y en las variables de Render, nunca en el frontend. Si
Node también está en Render, puede llamar a Python usando la dirección interna
de **Connect → Internal** para el tráfico entre servicios.

## Privacidad y alcance

El servicio no persiste datos ni se conecta con MongoDB. No registres ni envíes
datos identificables del paciente en los logs. `grVisceral` es el índice de
conicidad, no una escala de bioimpedancia. `bodyAge` es una estimación
heurística no clínica, disponible solo para mujeres de 30–39 años cuando se
puede calcular `%MG`; en los demás casos queda en `null`.

## Pruebas

```powershell
pytest
```
