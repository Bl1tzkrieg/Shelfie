#!/usr/bin/env bash
# Falla (código 1) si la carpeta compilada trae una URL de desarrollo (localhost o 127.0.0.1,
# con cualquier puerto): en las PC de la biblioteca la API es del mismo origen.
# Uso:  scripts/verificar_sin_url_dev.sh frontend/out
set -euo pipefail
CARPETA="${1:?Uso: verificar_sin_url_dev.sh <carpeta>}"
if grep -rEq "localhost:|127\.0\.0\.1:" "$CARPETA"; then
    echo "ERROR: $CARPETA trae una URL de desarrollo (localhost: o 127.0.0.1:); no se empaqueta." >&2
    grep -rEl "localhost:|127\.0\.0\.1:" "$CARPETA" >&2
    exit 1
fi
