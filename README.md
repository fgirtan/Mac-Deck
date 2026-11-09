# Mac Deck

iPhone-ul (13 mini, orizontal) devine un deck de control pentru Mac: grilă de butoane cu logo-uri, slidere pentru volum și luminozitate, pagini dedicate pentru aplicații.

Specificațiile complete sunt în [SPEC.md](SPEC.md).

## Status

| Etapă | Conținut | Status |
|---|---|---|
| 1 | Nucleu: grilă 5×3 cu swipe, slidere, deschidere aplicații/site-uri, profil Chrome, iconițe, HTTPS, ecran mereu aprins, mod repaus | ✅ gata, de testat pe Mac |
| 2 | Configurator pe Mac | ⏳ |
| 3 | Pagini Spotify, Google Meet, Activity Monitor | ⏳ |
| 4 | Claude: prompturi automate, liste Pinned / Artefacte | ⏳ |
| 5 | Screaming Frog, MeetGeek | ⏳ |
| 6 | Funcțiile din secțiunea 11 (meeting, macro-uri, snippets, Focus etc.) | ⏳ |

Butoanele cu un punct gri în colț sunt pentru funcții din etapele următoare.

## Instalare pe Mac

Ai nevoie doar de Python 3, care vine cu Command Line Tools de la Apple. Dacă nu sunt instalate, macOS le oferă automat la prima comandă `python3` sau `git`.

1. Descarcă proiectul (o singură dată):
   ```bash
   git clone https://github.com/fgirtan/mac-deck.git ~/mac-deck
   ```
2. Pornește serverul:
   ```bash
   cd ~/mac-deck && python3 -m macdeck
   ```
3. În Terminal apar adresa pentru iPhone și **codul de asociere** (6 cifre).

Pentru actualizări: `cd ~/mac-deck && git pull`, apoi repornește serverul (Ctrl+C și din nou comanda de mai sus).

### Permisiuni macOS (o singură dată)

La primele apăsări, macOS cere permisiuni pentru **Terminal** (sau aplicația din care rulezi serverul). Acceptă-le:

| Permisiune | Unde | Pentru |
|---|---|---|
| **Automation → Google Chrome** | apare automat | butoanele care deschid site-uri și reutilizează tab-urile |
| **Automation → System Events** | apare automat | blocare Mac, screenshot |
| **Accessibility** | System Settings → Privacy & Security → Accessibility → adaugă Terminal | blocare Mac, screenshot (și etapele următoare) |
| **Conexiuni de rețea** | fereastra „Allow incoming connections” | ca iPhone-ul să ajungă la Mac |

## Instalare pe iPhone

1. iPhone-ul trebuie să fie pe **același Wi-Fi** cu Mac-ul.
2. În Safari deschide adresa `http://<nume-mac>.local:8765/setup`, afișată în Terminal. Pagina te ghidează pas cu pas:
   - descarci și instalezi certificatul Mac-ului (necesar pentru HTTPS, ca ecranul să rămână aprins);
   - îl activezi din **Settings → General → About → Certificate Trust Settings**;
   - deschizi deck-ul la `https://<nume-mac>.local:8766` și introduci codul de asociere;
   - **Share → Add to Home Screen**.
3. Recomandat: **Auto-Lock → Never** și **Portrait Orientation Lock** oprit.

## Configurare

Până la configuratorul din etapa 2, butoanele se editează în `~/.macdeck/config.json`. Modificările ajung pe iPhone automat, în aproximativ o secundă, fără repornire.

Tipuri de acțiuni disponibile acum:

```jsonc
{"type": "app", "app": "Slack"}                                 // deschide o aplicație
{"type": "chrome", "url": "https://...", "match": "text"}       // URL în Chrome; sare la tab-ul existent
{"type": "chrome_profile", "email": "fgirtan@gmail.com"}        // fereastră Chrome cu profilul respectiv
{"type": "lock"} / {"type": "display_sleep"} / {"type": "screenshot"} / {"type": "caffeinate"}
```

Orice buton poate avea și `"long": {...}`, o acțiune la apăsare lungă. Exemplu: pe Gmail, apăsarea lungă deschide un email nou.

## Fișiere

```
macdeck/
  server.py     server HTTP/HTTPS, asociere, evenimente în timp real
  actions.py    acțiunile butoanelor
  system.py     volum, luminozitate (DisplayServices), comenzi
  icons.py      logo-uri din aplicațiile de pe Mac și favicon-uri
  certs.py      certificatul HTTPS local
  config.py     configurația implicită
  web/          aplicația pentru iPhone
~/.macdeck/     config.json, certificate, iconițe, telefoane asociate
```

Pentru testare pe alt sistem decât macOS: `MACDECK_SIM=1 python3 -m macdeck` (acțiunile sunt doar afișate).
