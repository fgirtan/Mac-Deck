#!/bin/bash
# Dublu-click în Finder: pornește Mac Deck (sau doar deschide configuratorul, dacă rulează deja).
cd "$(dirname "$0")" || exit 1
if curl -s -o /dev/null --max-time 2 http://localhost:8765/setup; then
  echo "Mac Deck rulează deja. Deschid configuratorul…"
  open "http://localhost:8765/config"
  sleep 1
  exit 0
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 lipsește. Rulează în Terminal: xcode-select --install"
  read -r -p "Apasă Enter pentru a închide."
  exit 1
fi
(sleep 2; open "http://localhost:8765/config") &
python3 -m macdeck
echo
read -r -p "Serverul s-a oprit. Apasă Enter pentru a închide fereastra."
