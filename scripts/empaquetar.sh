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
# Next hornea en el JS todo lo que lea de frontend/.env.local (p. ej. NEXT_PUBLIC_API_URL=
# http://localhost:8000 de desarrollo): en las PC de la biblioteca la API es del mismo origen.
# Esos archivos se apartan durante la compilación y, pase lo que pase, se devuelven al terminar.
APARTADOS="$TEMPORAL/env-apartados"
mkdir -p "$APARTADOS"
devolver_env() {
    for f in "$APARTADOS"/.env*; do
        [ -e "$f" ] && mv "$f" "$RAIZ/frontend/$(basename "$f")"
    done
    return 0
}
limpiar() {
    devolver_env
    rm -rf "$TEMPORAL"
}
trap limpiar EXIT
for f in "$RAIZ"/frontend/.env.local "$RAIZ"/frontend/.env.*.local; do
    [ -e "$f" ] && mv "$f" "$APARTADOS/$(basename "$f")"
done

echo "== Compilando el frontend (frontend/out)"
(cd frontend && npm ci && env -u NEXT_PUBLIC_API_URL npm run build)
test -f frontend/out/index.html || { echo "ERROR: next build no dejó frontend/out/index.html" >&2; exit 1; }
if grep -rq "localhost:8000" frontend/out; then
    echo "ERROR: frontend/out trae la URL de desarrollo (localhost:8000); no se empaqueta." >&2
    exit 1
fi

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
