# BancoPreu

Sube bancos de preguntas preuniversitarios en PDF (200+ páginas, con fórmulas y diagramas). BancoPreu extrae cada pregunta con IA (Gemini Vision), la clasifica por **materia** y **tema** y te deja filtrarlas y buscarlas al instante, con las fórmulas renderizadas con KaTeX.

```
┌──────────┐   /api, /storage   ┌──────────┐  send_task   ┌───────┐   ┌──────────┐
│ frontend │ ─────────────────▶ │ backend  │ ───────────▶ │ redis │ ◀─│  worker  │
│ Nuxt 3   │      (proxy)       │ FastAPI  │              └───────┘   │ Celery   │
└──────────┘                    └────┬─────┘                          │ PyMuPDF  │
                                     │        ┌────────────┐          │ Gemini   │
                                     └──────▶ │ PostgreSQL │ ◀────────┘          │
                                              │ 16 + FTS   │    volumen /storage  │
                                              └────────────┘   (PDF + PNG)        ┘
```

## Arranque rápido

```bash
cp .env.example .env          # y pon tu GEMINI_API_KEY (https://aistudio.google.com/apikey)
docker compose up --build
```

- App: http://localhost:3000
- API + documentación interactiva: http://localhost:8000/docs

Las tablas, la extensión `unaccent`, el trigger de `tsvector` y el índice GIN se crean solos al arrancar el backend (`alembic upgrade head`).

## Cómo funciona la ingesta

1. `POST /api/documents/upload` guarda el PDF en `/storage/pdfs`, crea el documento (`pending`) y encola la tarea en Celery.
2. El worker renderiza cada página a PNG a 150 DPI en `/storage/pages/{doc_id}/page_{n}.png`.
3. Cada imagen va a un modelo de visión: **Gemini** (`gemini-3.8-flash`), **NVIDIA NIM** y/o **OpenRouter** (modelos `:free`, por defecto `nvidia/nemotron-3.5-super-vl:free` con otros de respaldo). Las páginas se reparten entre los proveedores configurados, y cuando uno agota su cuota diaria se sigue con el otro. Se usa con **Structured Outputs** (esquema Pydantic → JSON Schema). Por cada pregunta obtiene número, encabezado de materia visible, tema, enunciado en LaTeX, alternativas y `has_diagram`.
   - Las páginas se envían en paralelo (`GEMINI_CONCURRENCY`), pero se guardan **en orden**, así que:
     - **Herencia de materia:** si una página no muestra encabezado, la pregunta hereda la materia de la anterior.
     - **Preguntas partidas entre páginas:** el fragmento del inicio de una página se añade a la última pregunta de la página anterior.
   - **Límite de solicitudes por minuto** (`GEMINI_RPM`) compartido vía Redis. El plan gratuito permite 5/min, así que un PDF de 227 páginas tarda unos 45 min; con facturación activada pon `GEMINI_RPM=0`.
   - Ante un 429 se espera exactamente el `retryDelay` que indica Google. Si una página falla tras los reintentos se omite y se informa, sin abortar el resto.
   - Errores permanentes (modelo no disponible, clave inválida) abortan de inmediato con un mensaje claro.
   - Si se agota la **cuota diaria**, el documento se pausa conservando lo extraído y aparece el botón **Reanudar** (`POST /api/documents/{id}/reprocess?resume=true`).
   - Se reparan las barras invertidas de LaTeX mal escapadas (`\frac` → carácter de control) antes de guardar.
4. `processed_pages` se actualiza página a página: el frontend muestra *"Procesando página 45 de 227…"* consultando cada 3 s.
5. **Normalización de temas:** al terminar, una llamada al LLM por materia agrupa variantes como *"División algebraica de polinomios"* → *"División de polinomios"*. Reutiliza los nombres canónicos de documentos anteriores para que el catálogo sea coherente entre PDFs.

## API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/documents/upload` | Sube un PDF (multipart, campo `file`) y dispara el procesamiento |
| `GET` | `/api/documents` | Documentos con estado, `processed_pages/total_pages`, `progress` y número de preguntas |
| `GET` | `/api/documents/{id}` | Un documento |
| `POST` | `/api/documents/{id}/reprocess` | Vuelve a extraer desde cero; con `?resume=true` continúa desde la última página guardada |
| `DELETE` | `/api/documents/{id}` | Elimina el documento, sus preguntas, el PDF y los PNG |
| `GET` | `/api/filters?document_id=&has_diagram=` | Materias con conteo y temas agrupados por materia |
| `GET` | `/api/questions` | Búsqueda + filtros: `subject`, `topic`, `q`, `document_id`, `has_diagram`, `page`, `limit` |
| `GET` | `/api/questions/{id}` | Una pregunta |
| `GET` | `/storage/{path}` | PDF originales y PNG de páginas |

**Búsqueda (`q`):** full-text en español (`to_tsvector('spanish', …)` + índice GIN) sin distinguir tildes y ordenada por `ts_rank`. Materia y tema pesan más que el enunciado, y el enunciado más que las alternativas.

- Sin comillas, cada palabra busca **por prefijo**, ideal para la búsqueda instantánea: `ruff` encuentra *Ruffini*.
- Con comillas u operadores se usa `websearch_to_tsquery`: `"plano inclinado"`, `energía -potencial`, `mol or masa`.

Ejemplo de `/api/filters`:

```json
{
  "total": 812,
  "diagram_count": 143,
  "subjects": [{ "subject": "ALGEBRA", "count": 120 }],
  "topics": { "ALGEBRA": [{ "topic": "División de polinomios", "count": 14 }] }
}
```

## Interfaz

- **Cabecera:** botón *Subir PDF* y progreso en vivo del documento que se está procesando.
- **Modal de documentos:** drag & drop de varios PDF con progreso de subida, biblioteca con estado, reprocesar y eliminar.
- **Panel de filtros:** documento, materias en *pills* con contador, temas dinámicos con buscador interno y el interruptor *Solo con gráficos/diagramas*.
- **Resultados:** búsqueda con debounce de 300 ms (atajo `/`), tarjetas con materia, tema, número y página, fórmulas con KaTeX, alternativas alineadas, **Ver página original** (panel lateral con zoom y enlace al PDF en esa página) y **Copiar pregunta** (texto con LaTeX).

`<MathText :content="…" />` acepta `$…$`, `$$…$$`, `\(…\)` y `\[…\]` mezclados con texto normal. Un delimitador sin cerrar se muestra como texto literal y una fórmula inválida se muestra como código, nunca rompe la tarjeta.

## Variables de entorno

| Variable | Por defecto | |
|---|---|---|
| `GEMINI_API_KEY` | — | **Obligatoria** para extraer preguntas |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Google retiró `gemini-2.5-flash` para usuarios nuevos |
| `GEMINI_API_KEYS` | — | Claves extra separadas por comas, de **proyectos distintos**. Se rotan al agotar la cuota diaria |
| `OPENROUTER_API_KEY` | — | Clave de OpenRouter (https://openrouter.ai/keys) |
| `OPENROUTER_MODELS` | modelos `:free` con visión | Lista de respaldo en orden de preferencia |
| `OPENROUTER_RPM` | `16` | El plan gratuito permite 20/min y 50/día (1000/día con 10 USD de crédito) |
| `NVIDIA_API_KEY` | — | Clave de NVIDIA NIM (https://build.nvidia.com) |
| `NVIDIA_MODELS` | `nemotron-3.5-super-vl-120b-a12b`, `gemma-4-31b-it` | |
| `LLM_PROVIDERS` | `gemini,openrouter,nvidia` | Proveedores que se reparten las páginas |
| `GEMINI_RPM` | `5` | Solicitudes por minuto (plan gratuito = 5; `0` = sin límite) |
| `GEMINI_CONCURRENCY` | `4` | Páginas en paralelo por documento |
| `GEMINI_THINKING_LEVEL` | `low` | Razonamiento en modelos 3.x (`minimal`, `low`, `medium`, `high`) |
| `GEMINI_THINKING_BUDGET` | `0` | Solo para modelos 2.5 |
| `RENDER_DPI` | `150` | |
| `WORKER_CONCURRENCY` | `2` | Documentos procesados a la vez |
| `MAX_UPLOAD_MB` | `300` | |
| `ALLOW_UPLOADS` | `true` | `false` = solo búsqueda (producción) |
| `FRONTEND_PORT` / `BACKEND_PORT` | `3000` / `8000` | |

## Despliegue en VPS (producción de solo lectura)

El banco se procesa **una sola vez en local**. El VPS solo sirve la búsqueda.

**Qué garantiza `docker-compose.prod.yml`:**

| Riesgo | Protección |
|---|---|
| Modificar o borrar el banco | `ALLOW_UPLOADS=false`: la API responde **403** a subir, reprocesar o eliminar, y el botón de subir no aparece |
| Usar tus API keys | El VPS no las necesita; el compose de producción las **vacía** aunque estén en `.env`, y el worker no arranca |
| Descargar el PDF original | `EXPOSE_PDF=false`: el PDF **no se sube** al VPS, `/storage/pdfs/*` da 404 y la API no expone rutas internas |
| Alterar las imágenes | El volumen se monta **solo lectura** en el backend; solo `import.sh` puede escribir en él |
| Acceso directo a servicios | Nada se publica a internet salvo a través de nginx: Caddy escucha en `127.0.0.1`, y backend, Postgres y Redis quedan en la red interna. `/docs` desactivado |
| Tráfico sin cifrar | HTTPS automático con Let's Encrypt, HSTS y cabeceras de seguridad |

### Pasos

**1. DNS:** crea un registro **A** `isaacpreu` en `pulsarsrl.cloud` → IP del VPS.

**2. VPS** (Ubuntu/Debian) — instalar Docker y abrir el firewall:
```bash
curl -fsSL https://get.docker.com | sh
sudo ufw allow 22,80,443/tcp && sudo ufw allow 443/udp && sudo ufw enable
```

**3. Código** — sube el repo a GitHub/GitLab desde tu PC (`.env`, `export/` y `storage/` están en `.gitignore`) y clónalo en el VPS:
```bash
git clone <url-del-repo> ~/bancopreu && cd ~/bancopreu
cp .env.production.example .env
sed -i "s/CAMBIA_ESTA_CONTRASEÑA/$(openssl rand -hex 24)/" .env    # contraseña de Postgres
```

**4. Datos del banco** — en tu PC (Git Bash), exporta y sube:
```bash
bash scripts/export.sh                       # export/bancopreu.dump + export/storage.tar.gz (sin PDF)
scp -r export usuario@IP-DEL-VPS:~/bancopreu/
```

**5. VPS** — construir, importar y arrancar:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
bash scripts/import.sh export
```
**6. nginx del VPS** (si ya lo usas para otros sitios, como `pulsarsrl.cloud`): Caddy escucha solo en `127.0.0.1:8085` y nginx lo publica con HTTPS:
```bash
sudo grep -rln isaacpreu /etc/nginx/sites-enabled/ /etc/nginx/conf.d/   # si sale alguno, bórralo: causaría un bucle
sudo cp deploy/nginx/isaacpreu.pulsarsrl.cloud.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/isaacpreu.pulsarsrl.cloud.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d isaacpreu.pulsarsrl.cloud --redirect
```
Abre **https://isaacpreu.pulsarsrl.cloud**. Si el VPS no tiene nginx, mira las variables `CADDY_*` de `.env.production.example`: Caddy gestionará el HTTPS directamente.

**Actualizar** después de cambiar código: `git pull` y luego `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
**Actualizar el banco:** reprocesa en local, vuelve a hacer `export.sh` + `scp` y ejecuta `import.sh` en el VPS.
Si en algún caso quieres publicar el PDF: `export.sh --con-pdf` y `EXPOSE_PDF=true`.

> **Cuotas gratuitas:** OpenRouter permite 50 solicitudes al día con modelos `:free` (1000 al día si la cuenta tiene al menos 10 USD de crédito). Gemini: 5 solicitudes/min y unas 20/día por modelo y proyecto. Cada página es una solicitud. Varias claves de un mismo proyecto comparten cuota. Usar varios proyectos para superar los límites gratuitos va contra las condiciones de Google y puede suponer la suspensión de las claves. Activar la facturación cuesta menos de 1 USD por un PDF de unas 200 páginas.

## Desarrollo sin Docker

```bash
# Infraestructura
docker compose up -d postgres redis
# Expón también los puertos 5432/6379, o ajusta POSTGRES_HOST/REDIS_URL

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export POSTGRES_HOST=localhost REDIS_URL=redis://localhost:6379/0 STORAGE_DIR=../storage GEMINI_API_KEY=...
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.worker.celery_app worker -l INFO     # en otra terminal

# Frontend
cd frontend
npm install
NUXT_BACKEND_URL=http://localhost:8000 npm run dev
```

## Estructura

```
backend/
  app/
    main.py              FastAPI + /storage estático
    config.py            Configuración (pydantic-settings)
    models.py            SQLAlchemy: Document, Question
    schemas.py           Pydantic v2
    subjects.py          Normalización de materias/temas y reparación de LaTeX
    routers/             documents.py, questions.py (búsqueda + filtros)
    worker/
      celery_app.py
      tasks.py           Pipeline de ingesta y normalización de temas
      gemini.py          Cliente google-genai con Structured Outputs
      pdf_render.py      PyMuPDF → PNG
  alembic/versions/      Migración inicial (tablas, unaccent, trigger tsvector, GIN)
frontend/
  pages/index.vue        Vista principal
  components/            MathText, QuestionCard, FilterSidebar, UploadModal, PageViewer…
  composables/           Estado de búsqueda, documentos (polling), toasts
  utils/math.ts          Parser de $…$ / $$…$$ + KaTeX
  server/middleware/     Proxy /api y /storage → backend
scripts/
  export.sh / import.sh  Migrar BD + imágenes a producción
docker-compose.prod.yml  Producción: solo lectura, sin claves, sin PDF, Caddy + HTTPS
Caddyfile                Proxy HTTPS del VPS
.env.production.example  .env del VPS (sin claves de IA)
```
