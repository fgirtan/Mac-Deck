# Mac Deck

iPhone-ul (13 mini, orizontal) devine un deck de control pentru Mac: grilă de butoane cu logo-uri, slidere pentru volum și luminozitate, pagini dedicate pentru aplicații.

Specificațiile complete sunt în [SPEC.md](SPEC.md).

## Status

| Etapă | Conținut | Status |
|---|---|---|
| 1 | Nucleu: grilă 5×3 cu swipe, slidere, deschidere aplicații/site-uri, profil Chrome, iconițe, HTTPS, ecran mereu aprins, mod repaus | ✅ gata, de testat pe Mac |
| 2 | Configurator pe Mac (`http://localhost:8765/config`) | ✅ gata, de testat pe Mac |
| 3 | Pagini Spotify, Google Meet, Activity Monitor | ✅ gata, de testat pe Mac |
| 4 | Claude: prompturi automate, liste Pinned / Artefacte | ✅ gata, de testat pe Mac |
| 5 | Screaming Frog, MeetGeek | ✅ gata, de testat pe Mac |
| 6 | Următorul meeting, insigne, macro „Pornește ziua”, prompt vocal, snippets, Focus, Pomodoro, analiză SEO, crawl site curent, microfon, ieșire audio, ferestre, apăsare lungă, profiluri | ✅ gata, de testat pe Mac |

Totul a fost testat în modul simulat. Automatizările care depind de aplicațiile tale (Claude, MeetGeek, Screaming Frog, Spotify Web, Meet) pot avea nevoie de mici ajustări din configurator, după ce le încerci pe Mac.

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

### Permisiuni și pregătire (o singură dată)

La primele folosiri, macOS cere permisiuni pentru **Terminal** (sau aplicația din care rulezi serverul). Acceptă-le. Configuratorul → **Diagnostic** are butoane de test pentru fiecare.

| Ce | Unde | Pentru |
|---|---|---|
| **Automation → Google Chrome** | apare automat | site-uri, tab-uri, Spotify Web, Meet, analiză SEO |
| **Allow JavaScript from Apple Events** | în Chrome: **View → Developer → Allow JavaScript from Apple Events** | piesa curentă și controalele Spotify, starea și controalele din Meet |
| **Accessibility** | System Settings → Privacy & Security → Accessibility → adaugă **Terminal** | scurtături de tastatură, Claude, snippets, MeetGeek, Screaming Frog, ferestre, blocare, insigne din Dock |
| **Automation → System Events** | apare automat | la fel ca mai sus |
| **Conexiuni de rețea** | fereastra „Allow incoming connections” | ca iPhone-ul să ajungă la Mac |

Opționale, pentru funcții anume:

- **Următorul meeting:** Google Calendar → Settings → calendarul tău → *Integrate calendar* → **Secret address in iCal format**. Lipește adresa în configurator → Integrări.
- **Focus / Nu deranja:** în aplicația **Shortcuts** creează două shortcut-uri:
  - „Mac Deck Focus On”: acțiunea *Set Focus* → Do Not Disturb → **On**;
  - „Mac Deck Focus Off”: la fel, cu **Off**.
- **Ieșire audio** (AirPods / difuzoare / monitor): instalează utilitarul, cu [Homebrew](https://brew.sh):
  ```bash
  brew install switchaudio-osx
  ```
- **GPU și starea termică** în Activity Monitor: permite `powermetrics` fără parolă. Comanda o rulezi o singură dată și cere parola de administrator:
  ```bash
  echo "$USER ALL=(root) NOPASSWD: /usr/bin/powermetrics" | sudo tee /etc/sudoers.d/macdeck
  ```
- **Screaming Frog, crawl în fundal:** folosește linia de comandă din aplicație (necesită licența). Configurațiile salvate (*File → Configuration → Save As*) se adaugă în configurator → Pagini și liste.

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

Celelalte tab-uri ale configuratorului:
- **Pagini și liste:**
  - listele Claude (Pinned / Artefacte, cu prompt opțional);
  - snippets și șabloanele pentru prompt vocal;
  - instrumentele SEO;
  - configurațiile Screaming Frog;
  - numele butoanelor MeetGeek;
  - duratele Pomodoro.
- **Integrări și profiluri:**
  - Claude: scurtăturile și pauzele automatizării;
  - adresa iCal a calendarului;
  - shortcut-urile de Focus;
  - profilurile Birou / Acasă.
- **Diagnostic:**
  - lista butoanelor și meniurilor unei aplicații, ca să ajustezi MeetGeek / Screaming Frog;
  - teste rapide de permisiuni.

Configurația se află în `~/.macdeck/config.json` și poate fi editată și manual. Modificările din fișier se preiau automat. La actualizarea proiectului, configurația existentă primește automat butoanele noi, iar modificările tale se păstrează.

## Ce face fiecare pagină

| Pagină | Conținut |
|---|---|
| **Spotify** | coperta și piesa curentă, ⏮ ⏯ ⏭, căutare (rezultatele se deschid pe Mac). Pe grilă, butonul arată coperta; apăsare lungă = play/pauză. |
| **Google Meet** | microfon, cameră, mână ridicată, subtitrări, chat, participanți, prezentare, ieșire, cu starea afișată. Se deschide singură când intri într-un apel. |
| **Activity Monitor** | grafice live pentru CPU, memorie, rețea, disc; baterie, GPU, starea termică; top 5 procese după CPU sau memorie. Tap pe un proces propriu = închidere (cu confirmare). |
| **Claude** | tab-urile Pinned și Artefacte. Tap = deschide elementul (și trimite promptul, dacă are unul); apăsare lungă = deschide fără prompt. |
| **Screaming Frog** | mod Spider / List, URL sau listă, configurație; Start / Pauză / Stop în fereastra aplicației; crawl în fundal cu progres și export CSV. |
| **MeetGeek** | buton mare de înregistrare cu stare. |
| **Prompt vocal** | dictezi cu 🎤 de pe tastatura iPhone și trimiți într-un chat nou în Claude, eventual cu un șablon. |
| **Snippets** | texte gata făcute, lipite în aplicația din față. |
| **Pomodoro** | 25/5 minute, cu notificare pe Mac; butonul de pe grilă arată timpul rămas. |
| **Analizează pagina** | tab-ul activ din Chrome → PageSpeed, Search Console, Rich Results, Schema, site:, Wayback. |
| **Ieșire audio** | lista dispozitivelor de ieșire; tap = comutare. |
| **Ferestre** | fereastra din față: stânga, dreapta, sus, jos, tot ecranul, centru, alt monitor. |

Pe grilă mai sunt:
- **Următorul meeting**: titlul și minutele rămase; tap = intri în Meet.
- **Pornește ziua**: macro configurabil, implicit Gmail, Calendar, Slack, Dashboard David și Raportul zilnic în Claude.
- **Focus**, **Mic mute**, **Crawl site curent**, **Ține treaz**: cu starea afișată pe buton.
- **Insigne** cu numărul de necitite: Gmail (din titlul tab-ului) și orice aplicație cu insignă în Dock (ex. Slack).
- **Profiluri** (Birou / Acasă): seturile pot fi afișate doar în anumite profiluri, comutate automat după program sau manual.

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
  features.py   paginile dedicate și funcțiile live (Spotify, Meet, Claude, Screaming Frog, MeetGeek, timer…)
  chrome.py     tab-uri și JavaScript în Chrome
  uiauto.py     clipboard, clicuri pe butoane după nume, diagnostic (Accessibility)
  monitor.py    datele pentru Activity Monitor
  ics.py        următorul meeting din Google Calendar (iCal)
  web/          aplicația pentru iPhone (index.html, app.js, pages.js) și configuratorul (config.html, config.js)
~/.macdeck/     config.json, certificate, iconițe, telefoane asociate
```

Pentru testare pe alt sistem decât macOS: `MACDECK_SIM=1 python3 -m macdeck` (acțiunile sunt doar afișate).
