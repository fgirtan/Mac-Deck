# Mac Deck: specificații

Telefonul (iPhone 13 mini) devine un deck de control pentru Mac, asemănător cu Logitech MX Creative Keypad.

> Status: **v3, implementat** (etapele 1–6). Detalii de instalare și utilizare în [README.md](README.md).

---

## 1. Arhitectură

| Componentă | Tehnologie | Rol |
|---|---|---|
| **Server pe Mac** | Python (fără dependințe externe), pornește automat la login | Servește pagina pentru iPhone, execută acțiunile, citește starea (volum, Meet, Spotify etc.) |
| **Deck pe iPhone** | App web (PWA), adăugată pe ecranul principal | Grila de butoane, slidere, paginile pe aplicații |
| **Configurator** | Pagină web pe Mac: `http://localhost:8765/config` | Editezi butoane, pagini, iconițe, acțiuni |
| **Configurație** | `~/.macdeck/config.json` | Totul se salvează aici; iPhone-ul se actualizează pe loc |

Comunicarea se face prin rețeaua Wi-Fi locală (HTTP + Server-Sent Events pentru starea în timp real), fără internet și fără hosting. iPhone-ul se asociază o singură dată cu Mac-ul printr-un cod, ca să nu poată controla altcineva din rețea.

### Permisiuni necesare pe Mac (o singură dată)
- **Accessibility**: pentru scurtături de tastatură și clicuri în aplicații (Screaming Frog, MeetGeek).
- **Automation → Google Chrome**: pentru taburi și controlul paginilor web.
- În Chrome: **View → Developer → Allow JavaScript from Apple Events**. Permite controlul Spotify Web și Google Meet, plus citirea stării lor (piesa curentă, microfon pornit sau oprit).

---

## 2. Ecranul principal (orizontal)

Telefonul stă **orizontal** pe un suport. Pe iPhone 13 mini zona utilă e de aproximativ 724 × 355 puncte, după marginile pentru notch și colțuri. Nu există panou de informații: tot spațiul e folosit pentru butoane.

```
┌──────────────────────────────────────────────────────────────────────┐
│ ┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐   ┌──────┐┌──────┐  ● │
│ │ Gmail ││Claude ││ Slack ││Spotify││Gemini │   │      ││      │    │
│ └───────┘└───────┘└───────┘└───────┘└───────┘   │ ███  ││ ███  │    │
│ ┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐   │ ███  ││ ███  │    │
│ │Raport ││Planif.││ David ││Finder ││Chrome │   │ ███  ││ ███  │    │
│ └───────┘└───────┘└───────┘└───────┘└───────┘   │ ███  ││ ███  │    │
│ ┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐   │ ███  ││ ███  │    │
│ │SEOGets││  DWF  ││SFrog  ││MeetGk ││Notion │   │  🔊  ││  ☀   │    │
│ └───────┘└───────┘└───────┘└───────┘└───────┘   └──────┘└──────┘    │
│                    ● ○                          volum  lumină       │
└──────────────────────────────────────────────────────────────────────┘
        grila 5×3 (~555 pt), swipe între seturi    2 slidere (~150 pt)
```

- **Grila:**
  - **5 coloane × 3 rânduri = 15 butoane pe set**, pătrate de aproximativ 100 pt, ca un keypad fizic;
  - treci de la un set la altul cu swipe stânga/dreapta; numărul de seturi e nelimitat și se adaugă din configurator;
  - mărimea grilei se poate schimba din configurator (de ex. 4×3 pentru butoane mai mari).
- **Sliderele verticale** sunt în dreapta, unde ajunge ușor degetul mare, și sunt înalte pe toată înălțimea ecranului. Rămân fixe la swipe.
  - **Volum:** tragi pentru nivel; un tap pe iconiță face mute.
  - **Luminozitate:** ecranul intern al MacBook-ului, prin framework-ul de sistem DisplayServices.
- **Starea conexiunii:** un punct mic în colț (verde sau roșu), care nu ocupă spațiu.
- **Paginile dedicate** folosesc aceeași împărțire: zona grilei pentru controale și informații (piesa curentă, starea înregistrării, graficele Activity Monitor), iar sliderele rămân în dreapta. Butonul **← Înapoi** stă în colțul din stânga sus.
- **Rotire:** iOS nu permite unei pagini web să blocheze orientarea, așa că pe iPhone **Portrait Orientation Lock trebuie să fie oprit** (din Control Center). Altfel telefonul rămâne blocat în vertical. Dacă telefonul e ținut vertical, deck-ul afișează un mesaj „Rotește telefonul”.

---

## 3. Butoanele principale

Legendă pentru acțiuni:
- **Chrome** = deschide adresa în Google Chrome. Dacă există deja un tab cu acea adresă, sare la el în loc să deschidă unul nou.
- **App** = deschide sau aduce în față aplicația de pe Mac.
- **→ pagină** = pe iPhone se deschide și pagina de control a aplicației (secțiunea 4).

### Setul 1: lucru zilnic (cele 15 butoane cerute inițial, ordinea se poate schimba)

| Rând | Col | Buton | Acțiune | Pagină dedicată |
|---|---|---|---|---|
| 1 | 1 | Gmail | Chrome → `https://mail.google.com` | — |
| 1 | 2 | Claude | App Claude (desktop) | → pagina Claude |
| 1 | 3 | Slack | App Slack | — |
| 1 | 4 | Spotify | Chrome → `https://open.spotify.com` | → pagina Spotify |
| 1 | 5 | Gemini | Chrome → `https://gemini.google.com` | — |
| 2 | 1 | Raport zilnic | App Claude → deschide „Raport zilnic echipă David” și trimite promptul **„pornește raportul”** | — |
| 2 | 2 | Planificare | Pe iPhone apar **2 prompturi** din care alegi (vezi 4.2.1), apoi App Claude → deschide „Planificare săptămânală workflow” și trimite promptul ales | alegere prompt |
| 2 | 3 | Dashboard David | Chrome → `https://david01.du.ro/daily/management/dashboard/florin` | — |
| 2 | 4 | Finder | App Finder | — |
| 2 | 5 | Chrome (fgirtan) | Deschide o fereastră Chrome nouă cu profilul **fgirtan@gmail.com**. Atât; celelalte butoane Chrome folosesc profilul obișnuit. | — |
| 3 | 1 | SEO Gets | Chrome → `https://seogets.com/` | — |
| 3 | 2 | DWF | Chrome → `https://app.dwf.ro/login` | — |
| 3 | 3 | Screaming Frog | App Screaming Frog SEO Spider | → pagina Screaming Frog |
| 3 | 4 | MeetGeek | App MeetGeek (desktop) | → pagina MeetGeek |
| 3 | 5 | Notion | Chrome → `https://app.notion.com/p/020088990c49423d82f7f29c5b91ff3e?v=7a2f6b94707842d1ac572d3924844823` | — |

### Setul 2: întâlniri, productivitate, SEO

| Rând | Col | Buton | Acțiune | Pagină dedicată |
|---|---|---|---|---|
| 1 | 1 | Google Meet | Chrome → `https://meet.google.com` | → pagina Meet |
| 1 | 2 | Calendar | Chrome → `https://calendar.google.com` | — |
| 1 | 3 | Următorul meeting (A1) | Afișează titlul și minutele rămase; tap = intră în Meet | — |
| 1 | 4 | Pornește ziua (B1) | Rulează macro-ul de dimineață | — |
| 1 | 5 | Prompt vocal (B2) | Câmp de dictare, apoi trimite textul în Claude | → pagina Prompt |
| 2 | 1 | Snippets (B3) | Lista de texte gata făcute | → pagina Snippets |
| 2 | 2 | Focus (B4) | Pornește/oprește Nu deranja, cu stare | — |
| 2 | 3 | Pomodoro (B5) | Timer 25/5, cu stare | → pagina Timer |
| 2 | 4 | Analizează pagina (C1) | Tab-ul curent din Chrome → instrumente SEO | → alegere instrument |
| 2 | 5 | Crawl site curent (C2) | Screaming Frog pe domeniul din tab-ul curent | → pagina Screaming Frog |
| 3 | 1 | Mic mute (D1) | Microfon oprit în tot sistemul, cu stare | — |
| 3 | 2 | Ieșire audio (D2) | Alegi difuzoare, AirPods sau monitor | → alegere dispozitiv |
| 3 | 3 | Safari | App Safari | — |
| 3 | 4 | Mission Control | Deschide Mission Control | — |
| 3 | 5 | Activity Monitor | App Activity Monitor (opțional) | → pagina Activity Monitor |

### Setul 3: control Mac

| Rând | Col | Buton | Acțiune | Pagină dedicată |
|---|---|---|---|---|
| 1 | 1 | Ferestre (D3) | Stânga / dreapta / tot ecranul / alt monitor | → pagina Ferestre |
| 1 | 2 | Screenshot (D4) | Captură de zonă în clipboard; apăsare lungă = înregistrare ecran | — |
| 1 | 3 | Blochează Mac (D5) | Blochează ecranul | — |
| 1 | 4 | Stinge ecranul (D5) | Pune display-ul în sleep | — |
| 1 | 5 | Ține treaz (D5) | Mac-ul nu adoarme, cu stare (util la crawl-uri lungi) | — |
| 2–3 | toate | liber (10 locuri) | — | — |

Funcțiile care nu sunt butoane se aplică peste tot: **A2** (notificări pe iconițe), **A3** (coperta Spotify pe butonul Spotify), **E1** (apăsare lungă) și **E2** (profiluri Birou/Acasă).

---

## 4. Paginile dedicate aplicațiilor

Comportament comun:
- Un tap pe iconiță deschide aplicația pe Mac și **pagina ei de control** pe iPhone.
- Butonul **← Înapoi** (sau swipe de la marginea stângă) te duce la ecranul principal, pe setul de unde ai plecat.
- **Starea se păstrează.** Când revii pe aceeași iconiță, pagina arată exact cum ai lăsat-o (căutarea scrisă, modul ales, tab-ul selectat). Pe Mac nu se redeschide nimic: dacă tab-ul sau aplicația sunt deja deschise, doar sunt aduse în față.
- Sliderele de volum și luminozitate rămân vizibile jos și pe aceste pagini.

### 4.1 Spotify (open.spotify.com în Chrome)
- **Acum se cântă:** coperta, titlul și artistul, actualizate automat.
- **Butoane:** ⏮ Anterioara · ⏯ Play/Pauză (arată starea curentă) · ⏭ Următoarea.
- **Căutare:** un câmp de text pe iPhone. Scrii acolo și rezultatele se deschid în Spotify pe Mac (`open.spotify.com/search/...`); nu se afișează pe telefon.
- Implementare: controlul tab-ului Spotify prin JavaScript din Chrome.

### 4.2 Claude
Două tab-uri pe pagină:
- **Pinned:** lista elementelor fixate (Raport zilnic echipă David, Dashboard Tehnic, Rapoarte scădere SEO Gets, Dashboard specialist cu 1-1-uri, Planificare săptămânală workflow, Rapoarte Banca Transilvania, Trenduri SEO Gets, Raport echipă Technical SEO, Portofoliu SEO & GEO pe echipe, Plan săptămânal).
- **Artefacte:** lista artefactelor.
- Un tap pe un element îl deschide.
- Fiecare element poate avea un **prompt opțional**. Când e setat, după deschidere promptul se scrie și se trimite automat (ca la butoanele Raport zilnic și Planificare).
- Listele se completează din configurator: lipești numele și link-ul fiecărui element. Claude nu are o interfață publică din care deck-ul să citească automat lista de Pinned.
- Totul se deschide în **aplicația Claude pentru Mac**:
  - mai întâi se încearcă link-ul direct (deep link);
  - dacă aplicația nu acceptă link-ul, se folosește căutarea din aplicație (⌘K → numele elementului → Enter);
  - apoi promptul se lipește în câmpul de mesaj și se trimite (Enter), prin Accessibility.
- Elementele se deschid **după nume**, prin căutarea din aplicație (⌘K). Aplicația pentru Mac nu oferă link-uri către conversații, așa că în configurator ajunge doar numele exact al fiecărui element.

#### 4.2.1 Butonul „Planificare” cu alegere de prompt
Un tap pe buton afișează pe iPhone două opțiuni mari:

| Opțiune | Prompt trimis în „Planificare săptămânală workflow” |
|---|---|
| 📅 **Săptămânal** | „Fă-mi planificarea săptămânală, citește Gmail, Slack, CRM, MeetGeek și fă-mi planificarea în Notion. Dă-mi și aici informația.” |
| ☀️ **Zilnic** | „Fă-mi planificarea zilnică și adaugă în Notion task-urile.” |

- După alegere, Claude se deschide pe Mac la elementul respectiv și promptul se trimite automat.
- **Anulează** (sau tap în afara opțiunilor) închide alegerea fără să facă nimic.
- Orice buton Claude poate avea în configurator unul sau mai multe prompturi: unul se trimite direct, mai multe deschid alegerea.

### 4.3 Screaming Frog SEO Spider
- **Mod de crawl:** `Spider` (pornește de la un URL) sau `List` (o listă de URL-uri).
  - Spider: câmp pentru URL.
  - List: lipești lista de URL-uri sau alegi un fișier salvat.
- **Configurații:** alegi una dintre configurațiile tale salvate (fișiere `.seospiderconfig`, exportate din Screaming Frog). Le gestionezi din configuratorul de pe Mac.
- **Butoane:** ▶ Start · ⏸ Pauză / Reia · ⏹ Stop. Starea e vizibilă (rulează sau în pauză).
- Implementare: Start, Pauză și Stop în fereastra deschisă, prin automatizarea interfeței (Accessibility).
- **Crawl în fundal** prin linia de comandă a Screaming Frog (există licență plătită). Rulează fără fereastră, cu progresul afișat pe deck, și exportă automat rezultatele în CSV, într-un folder ales de tine. Nu permite pauză.

### 4.4 MeetGeek
- Buton mare **⏺ Start / ⏹ Stop recording**, cu stare (roșu când înregistrează).
- Înregistrarea se pornește din **aplicația desktop MeetGeek**, prin automatizarea interfeței (Accessibility): clic pe butonul de record din fereastră sau din meniul din bara de sus.
- La implementare rulăm pe Mac un mic utilitar care listează elementele interfeței MeetGeek, ca să identificăm exact butonul de start/stop și indicatorul de stare.

### 4.5 Google Meet (meet.google.com în Chrome)
| Buton | Scurtătură Meet | Stare afișată |
|---|---|---|
| 🎤 Microfon on/off | ⌘D | da, roșu când e oprit |
| 📷 Cameră on/off | ⌘E | da |
| ✋ Ridică mâna | ⌃⌘H | da |
| 💬 Chat | ⌃⌘C | — |
| 👥 Participanți | ⌃⌘P | — |
| 🖥 Partajare ecran | — (clic prin pagină) | — |
| 📕 Subtitrări | C | da |
| ☎ Ieși din apel | clic pe butonul de închidere | — |

- Comenzile ajung direct la tab-ul Meet, chiar dacă nu e în față.
- Când intri într-un apel Meet, iPhone-ul trece **automat** pe pagina Meet. Când ieși din apel, revine unde erai.

### 4.6 Activity Monitor (date în timp real)
O fereastră separată cu grafice care se actualizează în fiecare secundă, cu un istoric de aproximativ 60 de secunde:

| Grafic | Ce arată |
|---|---|
| **CPU** | % total, separat User și System; opțional câte o bară pe fiecare nucleu |
| **Memorie** | memorie folosită din total, presiunea memoriei (verde, galben, roșu), swap |
| **Rețea** | viteza de download și upload (KB/s, MB/s) |
| **Disc** | citire și scriere (MB/s), spațiu liber |
| **Baterie / Energie** | % baterie, se încarcă sau nu, timp rămas (pe MacBook) |
| **Top procese** | cele 5 procese care consumă cel mai mult CPU sau memorie. Un tap comută între cele două. |

- Graficele sunt verzi pe negru, ca restul deck-ului. Se colorează în galben sau roșu la încărcare mare.
- Datele se citesc din instrumentele de sistem macOS (`top`, `vm_stat`, `netstat`, `iostat`, `pmset`), fără să fie nevoie ca Activity Monitor să fie deschis.
- **GPU și temperatură** (activ, frecvență), prin `powermetrics`. Cere drepturi de administrator, configurate o singură dată (o regulă `sudoers` limitată strict la `powermetrics`).
- Un tap pe un proces din top deschide o confirmare **„Închide procesul”**. Procesele de sistem nu pot fi închise.

---

## 5. Comportament general
- Pagina **nu** se schimbă automat după aplicația activă de pe Mac. Navigarea e manuală (tap pe iconiță, apoi Înapoi). Singura excepție e Google Meet: deck-ul trece pe pagina Meet când intri într-un apel.
- Swipe între seturile de butoane (5×3); setul curent se ține minte.
- Conexiunea se reface automat dacă Mac-ul intră în sleep sau rețeaua cade.
- Deck-ul arată starea în timp real: volum, luminozitate, microfon și cameră în Meet, play/pauză Spotify, înregistrare MeetGeek, crawl Screaming Frog.

---

## 6. Aspect
- **Temă închisă:** fundal negru (#000 sau #0b0b0f), accent **verde**.
- **Butoane:**
  - **aplicații:** logo-ul real, preluat automat din aplicația instalată pe Mac;
  - **site-uri:** favicon sau logo descărcat o singură dată și păstrat local;
  - poți înlocui oricând logo-ul cu o imagine sau un emoji ales de tine.
- Sub fiecare iconiță e un text scurt, editabil.
- **Butoanele cu stare** (activ, pornit, înregistrează) au contur sau fundal verde. Microfonul oprit și înregistrarea activă folosesc roșu, pentru că sunt convenții universale.
- Font de sistem, colțuri rotunjite, fără bară Safari (mod ecran complet).

---

## 7. Feedback la apăsare
- **Vibrație:** Safari nu permite vibrația direct. Pe iOS 18+ se poate obține o vibrație scurtă printr-un truc: un comutator nativ ascuns, apăsat la fiecare tap. Se testează pe telefonul tău.
- **Vizual:** butonul se micșorează ușor și se luminează în verde.
- **Sunet:** clic discret, cu posibilitatea de a fi oprit din setări.
- **Confirmare:** după acțiune, butonul clipește verde la succes și roșu la eroare (de ex. aplicația nu e instalată).

---

## 7b. Ecranul telefonului rămâne mereu aprins
Deck-ul împiedică blocarea ecranului cât timp e deschis. Sunt trei niveluri, folosite automat în ordinea asta:

1. **Wake Lock API.** E metoda oficială a browserului și funcționează doar pe HTTPS.
   - Serverul de pe Mac generează un certificat local (o autoritate de certificare proprie, ca la `mkcert`).
   - Pe iPhone îl instalezi o singură dată: descarci profilul de la `http://<mac>.local:8765/cert`, apoi îl activezi din Settings → General → About → Certificate Trust Settings.
   - Deck-ul se deschide apoi la `https://<mac>.local:8766`.
2. **Rezervă fără HTTPS.** Un video invizibil, mut și în buclă (tehnica NoSleep.js) ține ecranul aprins dacă Wake Lock nu e disponibil. Se activează la primul tap pe deck.
3. **Din setările iPhone-ului (recomandat oricum, ca plasă de siguranță):**
   - Settings → Display & Brightness → Auto-Lock → **Never**;
   - opțional, Guided Access, care blochează telefonul în deck: Settings → Accessibility → Guided Access, apoi triplu-clic pe butonul lateral.

Indicatorul din colț arată dacă protecția e activă (de ex. 🔒 *ecran ținut aprins*).

### Protecție pentru ecranul OLED
iPhone 13 mini are ecran OLED. Imaginile statice afișate ore întregi pot lăsa urme (burn-in). De aceea:
- după **5 minute fără atingere** (configurabil), deck-ul trece într-un **mod repaus**: ecran negru cu ceasul și câteva date (volum, CPU) mici, în nuanțe închise, care se mută ușor la fiecare minut;
- primul tap trezește deck-ul, fără să declanșeze vreun buton;
- interfața normală se deplasează imperceptibil cu 1–2 pixeli periodic (pixel shift).

Fără program de noapte: deck-ul e activ oricând îl atingi.

---

## 8. Configuratorul de pe Mac
- Deschis din browser: `http://localhost:8765/config`.
- **Seturi:**
  - adaugi, ștergi sau redenumești seturi de butoane (implicit 15, grila 5×3);
  - rearanjezi butoanele prin drag & drop.
- **Pentru fiecare buton:**
  - nume și iconiță (automată sau încărcată de tine);
  - tipul acțiunii:
    - deschide aplicație;
    - deschide URL în Chrome, cu sau fără profil anume;
    - scurtătură de tastatură;
    - Claude + prompt;
    - comandă (AppleScript sau Shell);
    - Shortcut din aplicația Shortcuts;
  - pagina dedicată (opțional).
- **Liste:** editezi lista Claude (Pinned și Artefacte), configurațiile Screaming Frog și listele de URL-uri.
- **Previzualizare:** vezi deck-ul exact cum apare pe iPhone; modificările ajung pe telefon instant.
- **Siguranță:** export/import pentru `config.json` (backup).

---

## 9. Decizii

Nu mai există întrebări deschise. Detaliile de configurare (link-ul iCal din Google Calendar, textele pentru snippets, profilurile Birou/Acasă) se completează în configurator, la instalare.

### Răspunsuri primite
| Întrebare | Răspuns |
|---|---|
| Luminozitate | ecranul MacBook-ului |
| Profil Chrome fgirtan | doar butonul dedicat, care deschide profilul și atât |
| Claude | aplicația pentru Mac |
| MeetGeek | aplicația desktop |
| Notion | browser |
| Calendar | Google Calendar |
| Safari | da, ca buton |
| Meet: trecere automată pe pagina Meet | da |
| Screaming Frog: licență plătită | da |
| Spotify: rezultatele căutării | doar pe Mac |
| Activity Monitor: GPU + temperatură, închidere procese | da, da |
| Orientare | **orizontal**, grilă 5×3, fără panou de informații |
| Claude: link-uri | nu există; căutare după nume |
| Planificare | 2 prompturi la alegere (săptămânal / zilnic) |
| Mod repaus | da, după 5 minute; fără program de noapte |
| Propuneri secțiunea 11 | **toate** aprobate |

---

## 10. Plan de implementare (propunere)

1. **Nucleu:**
   - server, asociere cu telefonul, **HTTPS local + ecran mereu aprins**;
   - grila 5×3 cu swipe, slidere volum + luminozitate;
   - butoane de deschidere (app, Chrome, Chrome cu profil), iconițe automate.
2. **Configurator** pe Mac.
3. **Pagini dedicate:** Spotify, Google Meet și Activity Monitor (au cele mai clare comenzi).
4. **Claude:** liste plus prompt automat.
5. **Screaming Frog și MeetGeek.**
6. **Funcțiile din secțiunea 11:** A1–A3, B1–B5, C1–C2, D1–D5, E1–E2.
7. **Finisaje:** vibrație, sunet, pornire automată la login.

---

## 11. Funcții suplimentare (toate aprobate)

### A. Informații dintr-o privire
| # | Propunere | Ce face |
|---|---|---|
| A1 | **Următorul meeting** | Un buton cu text dinamic (sau o bandă subțire deasupra grilei): „Daily David · în 12 min”. Un buton **Intră** deschide link-ul Meet, iar pagina Meet apare automat. Datele vin din Google Calendar, printr-un link iCal privat. |
| A2 | **Notificări pe iconițe** | Bulină cu numărul de necitite pe Gmail, Slack, Calendar etc., citită din insignele din Dock. |
| A3 | **Mini-player Spotify** | Butonul Spotify de pe grilă afișează coperta piesei curente. Apăsare lungă = play/pauză. |

### B. Productivitate
| # | Propunere | Ce face |
|---|---|---|
| B1 | **Macro-uri** („Pornește ziua”) | Un buton rulează o secvență: Gmail + Calendar + Slack + Dashboard David, apoi pornește Raportul zilnic în Claude. Configurabil. |
| B2 | **Prompt vocal către Claude** | Dictezi pe iPhone cu microfonul tastaturii, iar textul se trimite în Claude pe Mac, eventual cu un șablon („analizează: …”). |
| B3 | **Snippets** | Butoane care lipesc pe Mac texte gata făcute: prompturi folosite des, răspunsuri standard, semnături, liste de verificare SEO. |
| B4 | **Focus / Nu deranja** | Pornește sau oprește modul Focus de pe Mac, cu starea afișată. Opțional: pornit automat cât timp ești în Meet. |
| B5 | **Pomodoro / timer** | Timer pe deck, eventual legat de Focus. |

### C. SEO, pentru tab-ul curent din Chrome
| # | Propunere | Ce face |
|---|---|---|
| C1 | **Analizează pagina curentă** | Ia URL-ul din tab-ul activ și îl deschide în PageSpeed Insights, Rich Results Test, Search Console (inspectare URL), SEO Gets etc. |
| C2 | **Crawl pagina / site-ul curent** | Pornește Screaming Frog direct pe domeniul din tab-ul curent. |

### D. Control Mac
| # | Propunere | Ce face |
|---|---|---|
| D1 | **Microfon global mute** | Oprește microfonul în tot sistemul, nu doar în Meet. Starea e afișată și e util în orice aplicație de call. |
| D2 | **Ieșire audio** | Comută între difuzoare, AirPods și monitor dintr-un tap. |
| D3 | **Ferestre** | Mută fereastra activă în stânga, dreapta, pe tot ecranul sau pe celălalt monitor. |
| D4 | **Screenshot / înregistrare ecran** | Captură de zonă direct în clipboard, gata de lipit în Slack sau Claude. |
| D5 | **Blochează Mac-ul / Stinge ecranul / Nu adormi** | Butoane rapide pentru plecat de la birou, plus „ține Mac-ul treaz” în timpul crawl-urilor lungi. |

### E. Interacțiune
| # | Propunere | Ce face |
|---|---|---|
| E1 | **Apăsare lungă** = acțiune secundară | De exemplu: tap deschide Slack, apăsare lungă închide Slack. Pe Gmail, apăsare lungă = „Compune email nou”. |
| E2 | **Profiluri** | Seturi complet diferite pentru „Birou” și „Acasă”, comutate manual sau după ora din zi. |
