#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Dossier partagé avec le notebook V29d (cellule 0 : YARISK_APP_ROOT) — doivent être identiques.
export YARISK_DATA_DIR="${YARISK_DATA_DIR:-$(pwd)/data}"   # = /mnt/YARISK_DEMO/V2/data
mkdir -p "$YARISK_DATA_DIR"
exec streamlit run app.py --server.address 0.0.0.0 --server.port "${PORT:-8888}" --server.headless true
