# Mac Deck

iPhone-ul (13 mini, orizontal) devine un deck de control pentru Mac: grilă de butoane cu logo-uri, slidere pentru volum și luminozitate, pagini dedicate pentru aplicații.

Specificațiile complete sunt în [SPEC.md](SPEC.md).

## Status

| Etapă | Conținut | Status |
|---|---|---|
| 1 | Nucleu: grilă 5×3 cu swipe, slidere, deschidere aplicații/site-uri, profil Chrome, iconițe, HTTPS, ecran mereu aprins, mod repaus | ✅ gata, de testat pe Mac |
| 2 | Configurator pe Mac (`http://localhost:8765/config`) | ✅ gata, de testat pe Mac |
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

Mai simplu: în Finder, dă **dublu-click pe `Porneste Mac Deck.command`** din folderul `mac-deck`. Se deschide Terminal cu serverul pornit, iar după 2 secunde configuratorul se deschide în browser. Fereastra Terminal trebuie să rămână deschisă cât folosești deck-ul.

### Dacă `localhost` nu se găsește

- Serverul trebuie să **ruleze**: în Terminal trebuie să vezi caseta „Mac Deck pornit”. Dacă ai închis fereastra Terminal sau ai apăsat Ctrl+C, pornește-l din nou.
- `localhost` funcționează **doar pe Mac**. Pe iPhone folosește adresa `.local` sau IP-ul afișat în Terminal.
- Încearcă și `http://127.0.0.1:8765/config`.
- Dacă Terminal afișează `Address already in use`, portul e ocupat (de ex. de prototipul vechi `deck_test.py`). Află ce îl ocupă cu `lsof -i :8765`, apoi închide procesul cu `kill <PID>`.

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

## Configurator

Cu serverul pornit, deschide pe Mac **http://localhost:8765/config**. Pagina se deschide doar de pe Mac: telefonul și alte dispozitive din rețea nu au acces.

- **Seturi:** tab-uri sus. Le adaugi, redenumești, muți la stânga/dreapta sau le ștergi.
- **Grila:**
  - click pe un buton ca să-l editezi;
  - click pe un loc gol (`+`) ca să adaugi unul;
  - trage un buton peste altul ca să le schimbi locul, sau peste un tab ca să-l muți în alt set.
- **Editorul butonului** (panoul din dreapta):
  - **Nume** afișat pe buton.
  - **Iconiță:** automată (logo-ul aplicației sau favicon-ul site-ului), logo-ul altei aplicații, favicon-ul altui site, iconiță liniară verde, emoji sau imagine încărcată de tine.
  - **Acțiune la apăsare:** vezi tabelul de mai jos.
  - **Apăsare lungă:** o a doua acțiune, opțională, cu mesajul afișat pe telefon.
  - **Pagină dedicată** deschisă pe iPhone și **starea afișată** pe buton.
  - **▶ Testează** rulează acțiunea pe Mac, fără telefon.
- **Salvare automată:** fiecare modificare se salvează și ajunge pe iPhone în aproximativ o secundă. **↶ Anulează** (sau ⌘Z) revine la versiunea anterioară.
- **Setări:** dimensiunea grilei, minutele până la modul repaus, sunet și vibrație.
- **Export / Import:** backup pentru configurație, ca fișier JSON.
- **Previzualizare:** deck-ul exact cum apare pe iPhone; arată setul pe care îl editezi.

### Tipuri de acțiuni

| Tip | Ce face |
|---|---|
| Deschide aplicație | `open -a`: deschide sau aduce în față aplicația |
| Site în Chrome | deschide adresa; dacă un tab o conține deja, sare la el |
| Site în browserul implicit | `open URL` |
| Fereastră Chrome cu profil | Chrome cu profilul unui cont (ex. fgirtan@gmail.com) |
| Scurtătură de tastatură | ex. `cmd+shift+f`, `` ctrl+` ``, opțional către o anumită aplicație. Necesită permisiunea Accessibility. |
| Claude + prompt | unul sau mai multe prompturi la alegere. Trimiterea automată vine în etapa 4. |
| Shortcut | rulează un shortcut din aplicația Shortcuts |
| AppleScript / Comandă shell | orice script, pentru cazuri speciale |
| Blochează Mac / Stinge ecranul / Screenshot / Ține treaz | controale de sistem |

Configurația se află în `~/.macdeck/config.json` și poate fi editată și manual. Modificările din fișier se preiau automat.

## Fișiere

```
macdeck/
  server.py     server HTTP/HTTPS, asociere, evenimente în timp real
  actions.py    acțiunile butoanelor
  system.py     volum, luminozitate (DisplayServices), comenzi
  icons.py      logo-uri din aplicațiile de pe Mac și favicon-uri
  certs.py      certificatul HTTPS local
  config.py     configurația implicită
  admin.py      configuratorul: validare, aplicații instalate, iconițe încărcate
  web/          aplicația pentru iPhone (index.html, app.js) și configuratorul (config.html, config.js)
~/.macdeck/     config.json, certificate, iconițe, telefoane asociate
```

Pentru testare pe alt sistem decât macOS: `MACDECK_SIM=1 python3 -m macdeck` (acțiunile sunt doar afișate).
