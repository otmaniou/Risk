#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "== YaRisk Demo =="
echo "Repertoire courant : $(pwd)"
echo "--- Volumes visibles par l'App (diagnostic stockage partage) ---"
ls -d /domino/datasets/*/* /domino/datasets/* /mnt/data/* 2>/dev/null || echo "(aucun dataset monte)"
df -h 2>/dev/null | grep -E "datasets|edv|nfs|/mnt" || true
echo "---"

# Dossier de donnees partage avec le notebook : variable YARISK_DATA_DIR, sinon premier Dataset Domino trouve,
# sinon dossier local (dans ce cas le moteur du workspace ne verra PAS les dossiers deposes).
if [ -z "${YARISK_DATA_DIR:-}" ]; then
  DS="$(ls -d /domino/datasets/local/* 2>/dev/null | head -1)"
  [ -z "$DS" ] && DS="$(ls -d /mnt/data/* 2>/dev/null | head -1)"
  if [ -n "$DS" ] && [ -w "$DS" ]; then YARISK_DATA_DIR="$DS/yarisk_app"; else YARISK_DATA_DIR="$(pwd)/data"; fi
fi
export YARISK_DATA_DIR
mkdir -p "$YARISK_DATA_DIR"
echo "Donnees partagees  : $YARISK_DATA_DIR"
ls -l app.py bilan_view.py bilan_grid/index.html bilan_grid/grid.js
exec /opt/conda/envs/yarisk_demo/bin/python -m streamlit run app.py \
    --server.fileWatcherType none --browser.gatherUsageStats false \
    --server.enableCORS false --server.enableXsrfProtection false --server.maxUploadSize 200 \
    --server.address 0.0.0.0 --server.port 8888
