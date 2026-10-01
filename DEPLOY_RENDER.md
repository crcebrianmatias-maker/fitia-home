# FitIA Home V5 — Deploy con HTTPS

## Opción recomendada: Render

La app ya quedó preparada para despliegue.

### 1. Subir esta carpeta a GitHub
Creá un repositorio, por ejemplo:
`fitia-home`

Subí todo el contenido de `FitIA_Home_V5_DEPLOY`.

### 2. Crear el servicio en Render
- New > Web Service
- Elegí el repositorio `fitia-home`
- Render debería detectar `render.yaml`.

Si configurás manualmente:
- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --workers 1 --threads 4 --timeout 120 app:app`

Render entrega una URL HTTPS del tipo:
`https://fitia-home.onrender.com`

### 3. Datos persistentes
IMPORTANTE: en el plan gratuito, el filesystem es efímero. SQLite y fotos pueden perderse tras reinicios/deploys.

Para pruebas, está bien.

Para uso real tenés dos caminos:
A) agregar un Persistent Disk de Render y establecer:
`FITIA_DATA_DIR=/opt/render/project/src/storage`

B) migrar la base a PostgreSQL y las fotos a almacenamiento de objetos.

Si agregás disk en Render, montalo en:
`/opt/render/project/src/storage`

y agregá la variable:
`FITIA_DATA_DIR=/opt/render/project/src/storage`

### 4. IA de fotos y entrenador
Opcionalmente agregá variables:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Nunca guardes la clave dentro del código.

### 5. Instalar en Samsung S25 Ultra
Una vez desplegada:
1. Abrí la URL HTTPS en Chrome.
2. Iniciá sesión.
3. Tocá el botón `Instalar`.
4. Si no aparece: menú ⋮ > Agregar a pantalla de inicio / Instalar app.
5. FitIA quedará con icono propio y abrirá en modo app.

## Nota
Para una prueba rápida podés usar el plan gratuito. Para conservar SQLite/fotos de manera fiable necesitás almacenamiento persistente.
