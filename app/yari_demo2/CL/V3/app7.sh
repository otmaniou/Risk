#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Dossier de données partagé avec le notebook (cellule 0 : YARISK_APP_ROOT) — doit être identique des deux côtés
export YARISK_DATA_DIR="${YARISK_DATA_DIR:-/mnt/Risk/yarisk_app}"
mkdir -p "$YARISK_DATA_DIR"

echo "== YaRisk Demo =="
echo "Repertoire courant : $(pwd)"
echo "Donnees partagees  : $YARISK_DATA_DIR"
echo "Verification app.py :"
ls -l app.py bilan_view.py bilan_grid/index.html bilan_grid/grid.js
exec /opt/conda/envs/yarisk_demo/bin/python -m streamlit run app.py \
    --server.fileWatcherType none --browser.gatherUsageStats false \
    --server.enableCORS false --server.enableXsrfProtection false --server.maxUploadSize 200 \
    --server.address 0.0.0.0 --server.port 8888
