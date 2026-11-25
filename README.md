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

## Docker

Configurá `.env` con un token y `DEBUG=False` para el despliegue. El Compose
incluye solo el servicio `web` y no publica puertos al host; conectalo a la red
privada compartida con Node en el entorno de despliegue.
También configurá `DJANGO_SECRET_KEY` y `ALLOWED_HOSTS`. La imagen sirve
`config.asgi:application` con Daphne.

## Privacidad y alcance

El servicio no persiste datos ni se conecta con MongoDB. No registres ni envíes
datos identificables del paciente en los logs. `grVisceral` es el índice de
conicidad, no una escala de bioimpedancia. `bodyAge` queda en `null` mientras no
haya un método validado.

## Pruebas

```powershell
pytest
```
