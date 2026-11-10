#!/bin/bash
# Dublu-click în Finder: Mac Deck pornește singur la fiecare login și rulează în fundal (fără Terminal).
cd "$(dirname "$0")" || exit 1
python3 -m macdeck --autostart
sleep 3
open "http://localhost:8765/config"
echo
read -r -p "Gata. Apasă Enter pentru a închide fereastra."
