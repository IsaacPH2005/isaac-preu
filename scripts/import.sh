#!/usr/bin/env bash
# Importa en producción (VPS) lo generado por scripts/export.sh y arranca la app.
# ¡Reemplaza la base de datos y las imágenes existentes en el servidor!
#   bash scripts/import.sh [carpeta_origen]       (por defecto: ./export)
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

IN="${1:-export}"
[ -f "$IN/bancopreu.dump" ] && [ -f "$IN/storage.tar.gz" ] || {
  echo "No encuentro $IN/bancopreu.dump y $IN/storage.tar.gz" >&2
  exit 1
}
[ -f .env ] || { echo "Falta .env (cp .env.production.example .env y edítalo)" >&2; exit 1; }

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

echo "→ Arrancando PostgreSQL…"
"${COMPOSE[@]}" up -d --wait postgres

echo "→ Restaurando base de datos…"
"${COMPOSE[@]}" exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' \
  < "$IN/bancopreu.dump"

echo "→ Cargando imágenes de páginas (el backend solo tiene acceso de lectura)…"
"${COMPOSE[@]}" --profile tools run --rm -T storage-import < "$IN/storage.tar.gz"

echo "→ Arrancando la aplicación…"
"${COMPOSE[@]}" up -d --wait postgres redis backend frontend caddy

"${COMPOSE[@]}" exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) || '"'"' preguntas publicadas'"'"' FROM questions"'
echo "✓ Listo. Abre https://$(grep -E '^DOMAIN=' .env | cut -d= -f2)"
