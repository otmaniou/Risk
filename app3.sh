# Ya-Risk — script de lancement (sans ligne #! volontairement : compatible fins de ligne Windows) #
# Ya-Risk - lancement de l'interface. Chaque ligne se termine par " #" : le script fonctionne meme si un #
# editeur Windows le repasse en fins de ligne CRLF (le \r tombe alors dans le commentaire). #
cd "$(dirname "$0")" || exit 1 #
if [ -z "${YARISK_DATA_DIR:-}" ]; then #
  if [ -d /mnt/Risk ] && [ -w /mnt/Risk ]; then YARISK_DATA_DIR=/mnt/Risk/yarisk_app; else YARISK_DATA_DIR="$(pwd)/data"; fi #
fi #
export YARISK_DATA_DIR #
mkdir -p "$YARISK_DATA_DIR" #
echo "== Ya-Risk == dossier appli : $(pwd) | donnees : $YARISK_DATA_DIR" #
ls -l app.py bilan_view.py bilan_grid/index.html bilan_grid/grid.js #
exec streamlit run app.py --server.address 0.0.0.0 --server.port "${PORT:-8888}" --server.headless true #
