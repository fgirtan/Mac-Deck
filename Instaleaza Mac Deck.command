#!/bin/bash
# Dublu-click în Finder, o singură dată: instalează Mac Deck pe acest Mac.
#  - serverul pornește singur la login și rulează în fundal
#  - aplicația „Mac Deck” apare în Launchpad / Spotlight (actualizare + configurator)
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 lipsește. Rulează: xcode-select --install"; read -r -p "Enter pentru închidere."; exit 1
fi
python3 -m macdeck --autostart
python3 -m macdeck --install-app
sleep 2
open -R "$HOME/Applications/Mac Deck.app"
open "http://127.0.0.1:8765/config"
echo
echo "Gata. De acum deschide „Mac Deck” din Launchpad sau cu ⌘ Space. Poți trage aplicația în Dock."
read -r -p "Apasă Enter pentru a închide fereastra."
