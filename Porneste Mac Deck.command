#!/bin/bash
# Dublu-click în Finder: pornește serverul Mac Deck și deschide configuratorul.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 lipsește. Rulează în Terminal: xcode-select --install"
  read -r -p "Apasă Enter pentru a închide."
  exit 1
fi
(sleep 2; open "http://localhost:8765/config") &
python3 -m macdeck
echo
read -r -p "Serverul s-a oprit. Apasă Enter pentru a închide fereastra."
