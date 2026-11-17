#!/usr/bin/env bash
# Exporta la base de datos y las imágenes de las páginas para llevarlas a producción.
# Por defecto NO incluye el PDF original (producción no lo publica).
#   bash scripts/export.sh [carpeta_destino] [--con-pdf]      (carpeta por defecto: ./export)
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash en Windows: no reescribir rutas como /storage
cd "$(dirname "$0")/.."

OUT="export"
WITH_PDF=0
for arg in "$@"; do
  case "$arg" in
    --con-pdf) WITH_PDF=1 ;;
    *) OUT="$arg" ;;
  esac
done
mkdir -p "$OUT"

echo "→ Comprobando que no haya documentos en proceso…"
busy=$(docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM documents WHERE status IN ('"'"'pending'"'"','"'"'processing'"'"')"')
if [ "${busy//[[:space:]]/}" != "0" ]; then
  echo "  Hay $busy documento(s) procesándose. Espera a que terminen antes de exportar." >&2
  exit 1
fi

echo "→ Base de datos → $OUT/bancopreu.dump"
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
  > "$OUT/bancopreu.dump"

if [ "$WITH_PDF" = 1 ]; then
  echo "→ Imágenes de páginas + PDF originales → $OUT/storage.tar.gz"
  docker compose exec -T backend tar -C /storage -czf - pages pdfs > "$OUT/storage.tar.gz"
else
  echo "→ Imágenes de páginas (sin PDF) → $OUT/storage.tar.gz"
  docker compose exec -T backend tar -C /storage -czf - pages > "$OUT/storage.tar.gz"
fi

docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) || '"'"' documentos, '"'"' || (SELECT count(*) FROM questions) || '"'"' preguntas'"'"' FROM documents"'
ls -lh "$OUT"
echo "✓ Exportación lista. Súbela al VPS (scp -r $OUT usuario@vps:~/bancopreu/) y allí ejecuta: bash scripts/import.sh $OUT"
