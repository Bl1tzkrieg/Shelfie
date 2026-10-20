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
FALLO_AL_DEVOLVER=0
devolver_env() {
    local f destino
    for f in "$APARTADOS"/.env*; do
        [ -e "$f" ] || continue
        destino="$RAIZ/frontend/$(basename "$f")"
        if [ -e "$destino" ]; then
            # Apareció otro archivo con ese nombre durante la compilación: no se pisa.
            destino="$destino.apartado-$(date +%Y%m%d-%H%M%S)"
            echo "AVISO: ya existe $RAIZ/frontend/$(basename "$f"); su copia original quedó en $destino" >&2
        fi
        if ! mv "$f" "$destino"; then
            echo "ERROR: no se pudo devolver $(basename "$f"); sigue en $f" >&2
            FALLO_AL_DEVOLVER=1
        fi
    done
}
limpiar() {
    devolver_env
    # Si algo no volvió, se conserva la carpeta temporal para no perder el archivo.
    [ "$FALLO_AL_DEVOLVER" -eq 0 ] && rm -rf "$TEMPORAL"
    return 0
}
trap limpiar EXIT
for f in "$RAIZ"/frontend/.env.local "$RAIZ"/frontend/.env.*.local; do
    [ -e "$f" ] && mv "$f" "$APARTADOS/$(basename "$f")"
done

echo "== Compilando el frontend (frontend/out)"
(cd frontend && npm ci && env -u NEXT_PUBLIC_API_URL npm run build)
test -f frontend/out/index.html || { echo "ERROR: next build no dejó frontend/out/index.html" >&2; exit 1; }
"$RAIZ/scripts/verificar_sin_url_dev.sh" frontend/out

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
