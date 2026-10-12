# Ya-Risk - lancement de l'App (sans ligne #! : fonctionne meme en fins de ligne Windows) #
# Chaque ligne finit par " #" : un eventuel \r tombe dans le commentaire et ne gene pas. #
cd "$(dirname "$0")" || exit 1 #
export YARISK_DATA_DIR=/domino/datasets/local/YaRisk/yarisk_app #
mkdir -p "$YARISK_DATA_DIR" #
echo "== YaRisk Demo == dossier : $(pwd) | Donnees partagees : $YARISK_DATA_DIR" #
ls -l app.py bilan_view.py bilan_grid/index.html bilan_grid/grid.js #
PY=/opt/conda/envs/yarisk_demo/bin/python #
exec "$PY" -m streamlit run app.py --server.fileWatcherType none --browser.gatherUsageStats false --server.enableCORS false --server.enableXsrfProtection false --server.maxUploadSize 200 --server.address 0.0.0.0 --server.port 8888 #
