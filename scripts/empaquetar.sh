#!/usr/bin/env bash
# Arma el entregable para Windows: dist/shelfie-lite-<versión>.zip con
#   backend/      (sin .env, entornos virtuales, __pycache__, tests ni cachés)
#   frontend/out/ (compilado aquí con npm ci && npm run build)
#   instalacion/  (instalar.ps1, iniciar.ps1, restaurar.ps1, comun.ps1 y LEEME.md)
# Uso, desde cualquier carpeta del repo:  scripts/empaquetar.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
VERSION="$(git describe --tags --always)"
ZIP="$RAIZ/dist/shelfie-lite-$VERSION.zip"

TEMPORAL="$(mktemp -d)"
# next build reescribe frontend/next-env.d.ts (.next/dev/types ↔ .next/types): al terminar,
# pase lo que pase, se deja como estaba para no ensuciar el árbol de trabajo.
NEXT_ENV="$RAIZ/frontend/next-env.d.ts"
[ -f "$NEXT_ENV" ] && cp -p "$NEXT_ENV" "$TEMPORAL/next-env.d.ts"
limpiar() {
    [ -f "$TEMPORAL/next-env.d.ts" ] && cp -p "$TEMPORAL/next-env.d.ts" "$NEXT_ENV"
    rm -rf "$TEMPORAL"
}
trap limpiar EXIT

echo "== Compilando el frontend (frontend/out)"
(cd frontend && npm ci && npm run build)
test -f frontend/out/index.html || { echo "ERROR: next build no dejó frontend/out/index.html" >&2; exit 1; }

echo "== Armando el paquete"
PAQUETE="$TEMPORAL/paquete"
mkdir -p "$PAQUETE/frontend"
tar -C "$RAIZ" \
    --exclude='.env' --exclude='.env.local' --exclude='.env.*.local' \
    --exclude='.venv' --exclude='venv' \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='backend/tests' --exclude='.pytest_cache' --exclude='.ruff_cache' \
    --exclude='node_modules' --exclude='.next' \
    --exclude='backend/correo_saliente' \
    -cf - backend instalacion | tar -C "$PAQUETE" -xf -
cp -r frontend/out "$PAQUETE/frontend/out"

# Nada secreto ni de desarrollo puede ir en el zip.
if find "$PAQUETE" \( -name '.env' -o -name '__pycache__' -o -name 'tests' -o -name '.venv' \) | grep -q .; then
    echo "ERROR: el paquete trae archivos que no deben ir:" >&2
    find "$PAQUETE" \( -name '.env' -o -name '__pycache__' -o -name 'tests' -o -name '.venv' \) >&2
    exit 1
fi

mkdir -p "$RAIZ/dist"
rm -f "$ZIP"
(cd "$PAQUETE" && zip -qrX "$ZIP" backend frontend instalacion)
(cd "$RAIZ/dist" && sha256sum "$(basename "$ZIP")" > "$(basename "$ZIP").sha256")

echo "== Listo: dist/$(basename "$ZIP") ($(du -h "$ZIP" | cut -f1))"
