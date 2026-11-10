#!/bin/bash
# Dublu-click în Finder: oprește serverul din fundal și pornirea automată la login.
cd "$(dirname "$0")" || exit 1
python3 -m macdeck --no-autostart
read -r -p "Apasă Enter pentru a închide fereastra."
