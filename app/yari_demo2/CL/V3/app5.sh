# Ya-Risk — script de lancement (sans ligne #! volontairement : compatible fins de ligne Windows) #
# Chaque ligne se termine par " #" : le script fonctionne meme si un editeur Windows le repasse en CRLF. #
cd "$(dirname "$0")" || exit 1 #
if [ -z "${YARISK_DATA_DIR:-}" ]; then #
  if [ -d /mnt/Risk ] && [ -w /mnt/Risk ]; then YARISK_DATA_DIR=/mnt/Risk/yarisk_app; else YARISK_DATA_DIR="$(pwd)/data"; fi #
fi #
export YARISK_DATA_DIR #
mkdir -p "$YARISK_DATA_DIR" #
echo "== Ya-Risk == dossier appli : $(pwd) | donnees : $YARISK_DATA_DIR" #
ls -l app.py bilan_view.py bilan_grid/index.html bilan_grid/grid.js #
export PATH="$HOME/.local/bin:$PATH" #
PY="$(command -v python3 || command -v python)" #
echo "Python : $PY" #
if ! "$PY" -c "import streamlit" 2>/dev/null; then #
  echo "Streamlit absent de cet environnement : installation (requirements.txt)..." #
  "$PY" -m pip install --user -q "streamlit>=1.37,<2" || { echo "ECHEC installation streamlit : choisir pour l'App le meme environnement que le workspace"; exit 1; } #
fi #
"$PY" -c "import streamlit; print('Streamlit', streamlit.__version__)" #
export STREAMLIT_SERVER_PORT=8888 STREAMLIT_SERVER_ADDRESS=0.0.0.0 STREAMLIT_SERVER_HEADLESS=true #
export STREAMLIT_SERVER_ENABLE_CORS=false STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false #
echo "Lancement Streamlit sur 0.0.0.0:8888" #
exec "$PY" -m streamlit run app.py #
