#!/usr/bin/env bash
# Ya-Risk — lancement de l'interface (App Domino ou terminal). Fichier à garder en fins de ligne Unix (LF).
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")"
# Dossier de données partagé avec le notebook (cellule 0 : YARISK_APP_ROOT) — DOIT être identique des deux côtés.
# Priorité : variable YARISK_DATA_DIR > volume partagé /mnt/Risk (visible par l'App ET le workspace) > ./data
if [ -z "${YARISK_DATA_DIR:-}" ]; then
  if [ -d /mnt/Risk ] && [ -w /mnt/Risk ]; then YARISK_DATA_DIR=/mnt/Risk/yarisk_app; else YARISK_DATA_DIR="$(pwd)/data"; fi
fi
export YARISK_DATA_DIR
mkdir -p "$YARISK_DATA_DIR"
echo "== Ya-Risk == dossier appli : $(pwd) | données : $YARISK_DATA_DIR"
ls -l app.py bilan_view.py bilan_grid/index.html bilan_grid/grid.js
exec streamlit run app.py --server.address 0.0.0.0 --server.port "${PORT:-8888}" --server.headless true
