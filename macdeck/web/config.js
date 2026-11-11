(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var h = function (tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') el.textContent = attrs[k];
      else if (k === 'html') el.innerHTML = attrs[k];
      else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== undefined && attrs[k] !== null && attrs[k] !== false) el.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  };

  var cfg = null, meta = { apps: [], chrome_profiles: [], shortcuts: [] };
  var cur = { set: 0, slot: null };
  var undoStack = [], lastSaved = null, saveTimer = null, saving = false, pending = false;

  var ACTION_TYPES = [
    ['app', 'Deschide aplicație'],
    ['chrome', 'Site în Chrome'],
    ['url', 'Site în browserul implicit'],
    ['chrome_profile', 'Fereastră Chrome cu profil'],
    ['keys', 'Scurtătură de tastatură'],
    ['claude', 'Claude + prompt'],
    ['shortcut', 'Shortcut (aplicația Shortcuts)'],
    ['applescript', 'AppleScript'],
    ['shell', 'Comandă shell'],
    ['lock', 'Blochează Mac-ul'],
    ['display_sleep', 'Stinge ecranul'],
    ['screenshot', 'Screenshot'],
    ['caffeinate', 'Ține Mac-ul treaz (comutator)'],
    ['sequence', 'Macro: mai mulți pași la rând'],
    ['page', 'Doar deschide pagina dedicată'],
    ['spotify', 'Spotify: comandă'],
    ['meet', 'Google Meet: comandă'],
    ['timer', 'Pomodoro: comandă'],
    ['next_meeting', 'Intră în următorul meeting'],
    ['crawl_current', 'Crawl site-ul din tab-ul curent'],
    ['mic_mute', 'Microfon on/off (tot sistemul)'],
    ['focus', 'Focus / Nu deranja on/off'],
    ['window', 'Mută fereastra din față'],
    ['snippet', 'Lipește un text'],
    ['profile', 'Schimbă profilul'],
    ['soon', 'Funcție dintr-o etapă viitoare'],
  ];
  var ICON_MODES = [
    ['auto', 'Automat (din aplicație / site)'],
    ['app', 'Logo-ul unei aplicații'],
    ['url', 'Favicon-ul unui site'],
    ['glyph', 'Iconiță liniară verde'],
    ['emoji', 'Emoji'],
    ['image', 'Imagine încărcată'],
  ];
  var TOGGLES = [['', 'Niciuna'], ['caffeinate', 'Ține treaz'], ['focus', 'Focus pornit'], ['mic_muted', 'Microfon oprit'],
    ['timer', 'Pomodoro rulează'], ['meet_call', 'În apel Meet']];
  var DYNAMICS = [['', 'Nu'], ['next_meeting', 'Următorul meeting (titlu + minute)'], ['timer', 'Timp rămas Pomodoro'], ['spotify', 'Coperta și piesa Spotify']];

  // ---------------------------------------------------------------- încărcare / salvare
  function load() {
    Promise.all([
      fetch('/api/config', { cache: 'no-store' }).then(function (r) { return r.json(); }),
      fetch('/api/admin/meta', { cache: 'no-store' }).then(function (r) { return r.json(); }).catch(function () { return meta; }),
    ]).then(function (res) {
      cfg = res[0].config; meta = res[1];
      normalize();
      lastSaved = JSON.stringify(cfg);
      fillDatalists();
      setState('Salvat', 'ok');
      renderAll();
    }).catch(function () { setState('Nu pot încărca configurația. Rulează serverul?', 'err'); });
  }

  function capacity() { return cfg.ui.columns * cfg.ui.rows; }
  function normalize() {
    cfg.sets.forEach(function (s) { while (s.buttons.length < capacity()) s.buttons.push(null); });
    cfg.pages = cfg.pages || {};
  }
  function cleaned() {
    var c = JSON.parse(JSON.stringify(cfg));
    c.sets.forEach(function (s) { while (s.buttons.length && s.buttons[s.buttons.length - 1] == null) s.buttons.pop(); });
    return c;
  }

  function changed(rerenderInspector) {
    renderGrid(); renderTabs();
    if (rerenderInspector) renderInspector();
    setState('Se salvează…', '');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 450);
  }

  function save() {
    if (saving) { pending = true; return; }
    var body = cleaned(), snapshot = JSON.stringify(cfg);
    saving = true;
    fetch('/api/admin/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ config: body }) })
      .then(function (r) { return r.json(); })
      .then(function (r) {
        if (r.ok) {
          if (lastSaved && lastSaved !== snapshot) { undoStack.push(lastSaved); if (undoStack.length > 50) undoStack.shift(); }
          lastSaved = snapshot;
          $('undo').disabled = !undoStack.length;
          setState('Salvat · trimis pe iPhone', 'ok');
          refreshIcons();
        } else {
          setState('Nu s-a salvat: ' + (r.errors || [r.msg]).join('; '), 'err');
        }
      })
      .catch(function () { setState('Nu pot salva. Serverul rulează?', 'err'); })
      .then(function () { saving = false; if (pending) { pending = false; save(); } });
  }

  function undo() {
    if (!undoStack.length) return;
    var prev = undoStack.pop();
    lastSaved = null; // nu împinge starea curentă înapoi în istoric
    cfg = JSON.parse(prev); normalize();
    cur.set = Math.min(cur.set, cfg.sets.length - 1);
    renderAll();
    save();
    lastSaved = prev;
    $('undo').disabled = !undoStack.length;
    toast('Modificare anulată');
  }

  function setState(t, cls) { var el = $('save-state'); el.textContent = t; el.className = cls || 'muted'; el.title = t; }

  function fillDatalists() {
    $('dl-apps').innerHTML = meta.apps.map(function (a) { return '<option value="' + esc(a) + '">'; }).join('');
    $('dl-shortcuts').innerHTML = (meta.shortcuts || []).map(function (a) { return '<option value="' + esc(a) + '">'; }).join('');
    $('dl-profiles').innerHTML = (meta.chrome_profiles || []).filter(function (p) { return p.email; })
      .map(function (p) { return '<option value="' + esc(p.email) + '">' + esc(p.name) + '</option>'; }).join('');
  }

  // ---------------------------------------------------------------- utilitare
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function slug(s) {
    return (s || 'buton').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'buton';
  }
  function allIds() {
    var ids = {};
    cfg.sets.forEach(function (s) { s.buttons.forEach(function (b) { if (b) ids[b.id] = 1; }); });
    return ids;
  }
  function uniqueId(base) {
    var ids = allIds(), id = slug(base), n = 2;
    if (!ids[id]) return id;
    while (ids[id + '-' + n]) n++;
    return id + '-' + n;
  }
  function iconVersion(b) {
    var str = JSON.stringify(b.icon || b.action || {}), x = 0;
    for (var i = 0; i < str.length; i++) x = (x * 31 + str.charCodeAt(i)) | 0;
    return (x >>> 0).toString(36);
  }
  function iconHTML(b) {
    var ic = b.icon || {};
    if (ic.type === 'glyph') return glyph(ic.name);
    if (ic.type === 'emoji') return '<span class="emoji">' + esc(ic.value) + '</span>';
    return '<img src="/icons/' + encodeURIComponent(b.id) + '.png?v=' + iconVersion(b) + '" alt="" data-letter="' + esc((b.label || '?').charAt(0)) + '">';
  }
  function fixImgs(root) {
    root.querySelectorAll('img[data-letter]').forEach(function (img) {
      img.onerror = function () { img.outerHTML = '<span class="letter">' + esc(img.dataset.letter) + '</span>'; };
    });
  }
  function refreshIcons() { renderGrid(); var hd = document.querySelector('.insp-head .ic'); if (hd && sel()) { hd.innerHTML = iconHTML(sel()); fixImgs(hd); } }
  function toast(msg, bad) {
    var t = $('toast'); t.textContent = msg; t.classList.toggle('bad', !!bad); t.classList.add('show');
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.classList.remove('show'); }, 2400);
  }
  function sel() { return cur.slot == null ? null : cfg.sets[cur.set].buttons[cur.slot]; }

  // ---------------------------------------------------------------- tab-uri și seturi
  function renderTabs() {
    var tabs = $('tabs'); tabs.innerHTML = '';
    cfg.sets.forEach(function (s, i) {
      var t = h('button', { class: 'tab' + (i === cur.set ? ' cur' : ''), text: s.name || ('Set ' + (i + 1)),
        onclick: function () { cur.set = i; cur.slot = null; renderAll(); } });
      t.addEventListener('dragover', function (e) { if (i !== cur.set) { e.preventDefault(); t.classList.add('drop'); } });
      t.addEventListener('dragleave', function () { t.classList.remove('drop'); });
      t.addEventListener('drop', function (e) { e.preventDefault(); t.classList.remove('drop'); moveToSet(+e.dataTransfer.getData('text/slot'), i); });
      tabs.appendChild(t);
    });
    tabs.appendChild(h('button', { class: 'tab add', text: '+ Set nou', onclick: function () {
      cfg.sets.push({ name: 'Set ' + (cfg.sets.length + 1), buttons: [] }); normalize();
      cur.set = cfg.sets.length - 1; cur.slot = null; changed(true); renderSetTools();
    } }));
  }

  function renderSetTools() {
    var s = cfg.sets[cur.set];
    var sp = document.querySelector('.set-profiles'); if (sp) sp.remove();
    var sa = document.querySelector('.set-apps'); if (sa) sa.remove();
    var appsIn = h('input', { type: 'text', list: 'dl-apps', placeholder: 'ex. Visual Studio Code, Figma, docs.google.com' });
    appsIn.value = (s.apps || []).join(', ');
    appsIn.addEventListener('input', function () {
      var v = appsIn.value.split(',').map(function (x) { return x.trim(); }).filter(Boolean);
      if (v.length) s.apps = v; else delete s.apps; changed(false);
    });
    $('set-tools').after(h('label', { class: 'set-apps' }, ['Afișează automat acest set când e activă aplicația (sau site-ul din Chrome), separate prin virgulă:', appsIn]));
    if ((cfg.profiles || []).length) {
      var box = h('div', { class: 'set-profiles' }, ['Vizibil în profilurile:']);
      cfg.profiles.forEach(function (p) {
        var c = h('input', { type: 'checkbox' }); c.checked = !s.profiles || !s.profiles.length || s.profiles.indexOf(p.name) !== -1;
        c.addEventListener('change', function () {
          var all = cfg.profiles.map(function (x) { return x.name; });
          var cur2 = (s.profiles && s.profiles.length) ? s.profiles.slice() : all.slice();
          if (c.checked) { if (cur2.indexOf(p.name) === -1) cur2.push(p.name); } else cur2 = cur2.filter(function (n) { return n !== p.name; });
          if (cur2.length === all.length) delete s.profiles; else s.profiles = cur2;
          changed(false);
        });
        box.appendChild(h('label', {}, [c, p.name]));
      });
      $('set-tools').after(box);
    }
    $('set-name').value = s.name || '';
    $('set-left').disabled = cur.set === 0;
    $('set-right').disabled = cur.set === cfg.sets.length - 1;
    $('set-delete').disabled = cfg.sets.length === 1;
  }
  $('set-name').addEventListener('input', function (e) { cfg.sets[cur.set].name = e.target.value; changed(false); });
  $('set-left').addEventListener('click', function () { swapSets(cur.set, cur.set - 1); });
  $('set-right').addEventListener('click', function () { swapSets(cur.set, cur.set + 1); });
  $('set-delete').addEventListener('click', function () {
    var s = cfg.sets[cur.set], n = s.buttons.filter(Boolean).length;
    if (!confirm('Ștergi setul „' + (s.name || '') + '”' + (n ? ' cu ' + n + ' butoane' : '') + '? (poți anula cu ↶)')) return;
    cfg.sets.splice(cur.set, 1); cur.set = Math.max(0, cur.set - 1); cur.slot = null; renderAll(); changed(true);
  });
  function swapSets(a, b) {
    if (b < 0 || b >= cfg.sets.length) return;
    var t = cfg.sets[a]; cfg.sets[a] = cfg.sets[b]; cfg.sets[b] = t; cur.set = b; renderSetTools(); changed(false);
  }
  function moveToSet(slot, target) {
    var src = cfg.sets[cur.set].buttons, b = src[slot];
    if (!b) return;
    var dst = cfg.sets[target].buttons, idx = dst.indexOf(null);
    if (idx === -1 || idx >= capacity()) { if (dst.length >= capacity()) return toast('Setul „' + cfg.sets[target].name + '” e plin', true); idx = dst.length; }
    dst[idx] = b; src[slot] = null; cur.slot = null;
    toast('Mutat în „' + cfg.sets[target].name + '”');
    changed(true);
  }

  // ---------------------------------------------------------------- grila
  function renderGrid() {
    var g = $('grid'), cols = cfg.ui.columns, rows = cfg.ui.rows, s = cfg.sets[cur.set];
    g.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 1fr))';
    g.innerHTML = '';
    for (var i = 0; i < cols * rows; i++) g.appendChild(tile(s.buttons[i], i));
    fixImgs(g);
    var hidden = s.buttons.slice(cols * rows).filter(Boolean).length;
    var w = document.querySelector('.hidden-warn');
    if (w) w.remove();
    if (hidden) g.after(h('p', { class: 'hidden-warn', text: hidden + ' butoane nu încap în grila actuală și nu se afișează. Mărește grila din Setări sau mută-le.' }));
  }

  function tile(b, i) {
    var t;
    if (!b) {
      t = h('div', { class: 'tile empty', text: '+', title: 'Adaugă buton', onclick: function () { addButton(i); } });
    } else {
      t = h('div', { class: 'tile' + (i === cur.slot ? ' sel' : ''), draggable: 'true', onclick: function () { cur.slot = i; renderGrid(); renderInspector(); } }, [
        h('div', { class: 'ic', html: iconHTML(b) }),
        h('div', { class: 'lb', text: b.label || '(fără nume)' }),
        b.page ? h('span', { class: 'badge', text: 'pagină ›' }) : null,
      ]);
      t.addEventListener('dragstart', function (e) { e.dataTransfer.setData('text/slot', String(i)); e.dataTransfer.effectAllowed = 'move'; t.classList.add('dragging'); });
      t.addEventListener('dragend', function () { t.classList.remove('dragging'); });
    }
    t.addEventListener('dragover', function (e) { e.preventDefault(); t.classList.add('over'); });
    t.addEventListener('dragleave', function () { t.classList.remove('over'); });
    t.addEventListener('drop', function (e) {
      e.preventDefault(); t.classList.remove('over');
      var from = +e.dataTransfer.getData('text/slot');
      if (isNaN(from) || from === i) return;
      var arr = cfg.sets[cur.set].buttons, tmp = arr[i];
      arr[i] = arr[from]; arr[from] = tmp;
      if (cur.slot === from) cur.slot = i; else if (cur.slot === i) cur.slot = from;
      changed(false);
    });
    return t;
  }

  function addButton(i) {
    var b = { id: uniqueId('buton'), label: 'Buton nou', action: { type: 'app', app: '' } };
    cfg.sets[cur.set].buttons[i] = b;
    cur.slot = i;
    changed(true);
    setTimeout(function () { var el = document.querySelector('#inspector input[data-k=label]'); if (el) { el.focus(); el.select(); } }, 30);
  }

  // ---------------------------------------------------------------- inspector
  function field(label, input, note) {
    return h('label', {}, [label, input, note ? h('p', { class: 'note', text: note }) : null]);
  }
  function textInput(obj, key, opts) {
    opts = opts || {};
    var el = h(opts.multiline ? 'textarea' : 'input', { type: opts.type || 'text', placeholder: opts.placeholder || '', list: opts.list, 'data-k': key });
    el.value = obj[key] == null ? '' : obj[key];
    el.addEventListener('input', function () {
      if (opts.type === 'number') obj[key] = el.value === '' ? undefined : +el.value;
      else if (el.value === '' && opts.optional) delete obj[key];
      else obj[key] = el.value;
      if (opts.onchange) opts.onchange();
      changed(false);
    });
    return el;
  }
  function selectInput(options, value, onchange) {
    var el = h('select', {}, options.map(function (o) { return h('option', { value: o[0], text: o[1], selected: o[0] === value }); }));
    el.addEventListener('change', function () { onchange(el.value); });
    return el;
  }
  function check(label, obj, key) {
    var c = h('input', { type: 'checkbox' }); c.checked = !!obj[key];
    c.addEventListener('change', function () { if (c.checked) obj[key] = true; else delete obj[key]; changed(false); });
    return h('label', { class: 'check' }, [c, label]);
  }

  function renderInspector() {
    var box = $('inspector'); box.innerHTML = '';
    var b = sel();
    if (!b) { box.appendChild(h('div', { class: 'empty-state', text: 'Selectează un buton din grilă sau adaugă unul pe un loc gol.' })); return; }

    var head = h('div', { class: 'insp-head' }, [h('div', { class: 'ic', html: iconHTML(b) }), h('div', {}, [h('h2', { text: b.label || '(fără nume)' }), h('small', { text: 'id: ' + b.id })])]);
    fixImgs(head);
    box.appendChild(head);

    // --- buton
    box.appendChild(h('fieldset', {}, [h('legend', { text: 'Buton' }),
      field('Nume afișat', textInput(b, 'label', { onchange: function () { head.querySelector('h2').textContent = b.label; } })),
    ]));

    // --- iconiță
    var icon = b.icon || {}, mode = icon.type || 'auto';
    var iconFs = h('fieldset', {}, [h('legend', { text: 'Iconiță' })]);
    iconFs.appendChild(field('Sursă', selectInput(ICON_MODES, mode, function (v) {
      if (v === 'auto') delete b.icon;
      else if (v === 'glyph') b.icon = { type: 'glyph', name: 'wrench' };
      else if (v === 'emoji') b.icon = { type: 'emoji', value: '⭐' };
      else if (v === 'app') b.icon = { type: 'app', app: (b.action && b.action.app) || '' };
      else if (v === 'url') b.icon = { type: 'url', url: (b.action && b.action.url) || 'https://' };
      else if (v === 'image') b.icon = { type: 'image', file: '' };
      changed(true);
    })));
    if (mode === 'app') iconFs.appendChild(field('Aplicația', textInput(b.icon, 'app', { list: 'dl-apps' })));
    if (mode === 'url') iconFs.appendChild(field('Adresa site-ului', textInput(b.icon, 'url', { type: 'url' })));
    if (mode === 'emoji') iconFs.appendChild(field('Emoji', textInput(b.icon, 'value')));
    if (mode === 'glyph') {
      var gl = h('div', { class: 'glyphs' });
      Object.keys(GLYPHS).forEach(function (name) {
        gl.appendChild(h('button', { type: 'button', class: name === icon.name ? 'cur' : '', title: name, html: glyph(name),
          onclick: function () { b.icon.name = name; changed(true); } }));
      });
      iconFs.appendChild(gl);
    }
    if (mode === 'image') {
      var file = h('input', { type: 'file', accept: 'image/*' });
      file.addEventListener('change', function () { upload(b, file.files[0]); });
      iconFs.appendChild(field('Imagine (PNG, JPG, SVG; maxim 2 MB)', file, b.icon.file ? 'Fișier curent: ' + b.icon.file : 'Pătrată, de preferat 256×256.'));
    }
    if (mode === 'auto') iconFs.appendChild(h('p', { class: 'note', text: 'Se folosește logo-ul aplicației sau favicon-ul site-ului din acțiune.' }));
    box.appendChild(iconFs);

    // --- acțiune
    box.appendChild(actionEditor('Acțiune la apăsare', b, 'action', false));

    // --- apăsare lungă
    var longFs = h('fieldset', {}, [h('legend', { text: 'Apăsare lungă' })]);
    var lc = h('input', { type: 'checkbox' }); lc.checked = !!b.long;
    lc.addEventListener('change', function () {
      if (lc.checked) b.long = { type: 'app', app: '', label: '' }; else delete b.long;
      changed(true);
    });
    longFs.appendChild(h('label', { class: 'check' }, [lc, 'Acțiune separată la apăsare lungă']));
    if (b.long) {
      longFs.appendChild(field('Mesaj afișat pe telefon', textInput(b.long, 'label', { placeholder: 'ex. Email nou', optional: true })));
      longFs.appendChild(actionEditor(null, b, 'long', true));
    }
    box.appendChild(longFs);

    // --- pagină dedicată și stare
    var pages = [['', 'Fără pagină']].concat(Object.keys(cfg.pages).map(function (k) {
      var p = cfg.pages[k]; return [k, p.title + (p.phase ? ' (controale în etapa ' + p.phase + ')' : '')];
    }));
    box.appendChild(h('fieldset', {}, [h('legend', { text: 'Pe iPhone' }),
      field('Pagină dedicată deschisă la tap', selectInput(pages, b.page || '', function (v) { if (v) b.page = v; else delete b.page; changed(true); })),
      b.page ? (function () { var c = h('input', { type: 'checkbox' }); c.checked = b.auto_page !== false;
        c.addEventListener('change', function () { if (c.checked) delete b.auto_page; else b.auto_page = false; changed(false); });
        return h('label', { class: 'check' }, [c, 'Deschide pagina automat când aplicația / site-ul e activ pe Mac']); })() : null,
      field('Starea afișată pe buton (verde când e activ)', selectInput(TOGGLES, b.state || '', function (v) { if (v) b.state = v; else delete b.state; changed(false); })),
      field('Text / imagine dinamică pe buton', selectInput(DYNAMICS, b.dynamic || '', function (v) { if (v) b.dynamic = v; else delete b.dynamic; changed(false); })),
    ]));

    // --- butoane
    box.appendChild(h('div', { class: 'foot' }, [
      h('button', { class: 'btn primary', text: '▶ Testează', onclick: function () { testAction(b.action); } }),
      h('button', { class: 'btn', text: 'Duplică', onclick: function () { duplicate(b); } }),
      h('div', { class: 'spacer' }),
      h('button', { class: 'btn danger', text: 'Șterge', onclick: function () {
        cfg.sets[cur.set].buttons[cur.slot] = null; cur.slot = null; changed(true); toast('Buton șters (↶ pentru anulare)');
      } }),
    ]));
  }

  function actionEditor(title, b, key, nested) {
    var a = b[key];
    var fs = nested ? h('div', { style: 'display:flex;flex-direction:column;gap:10px' }) : h('fieldset', {}, [h('legend', { text: title })]);
    fs.appendChild(field('Tip', selectInput(ACTION_TYPES, a.type, function (v) {
      var keep = { label: a.label };
      if (v === 'app') keep.app = a.app || '';
      if (v === 'chrome' || v === 'url') keep.url = a.url || 'https://';
      if (v === 'chrome_profile') keep.email = a.email || '';
      if (v === 'keys') keep.keys = '';
      if (v === 'claude') { keep.item = ''; keep.prompts = [{ label: 'Prompt', text: '' }]; }
      if (v === 'shortcut') keep.name = '';
      if (v === 'applescript') keep.script = 'display notification "Salut" with title "Mac Deck"';
      if (v === 'shell') keep.command = '';
      if (v === 'soon') keep.phase = 6;
      if (v === 'sequence') { keep.steps = []; keep.delay = 0.8; }
      if (v === 'spotify') keep.cmd = 'playpause';
      if (v === 'meet') keep.cmd = 'mic';
      if (v === 'timer') keep.cmd = 'toggle';
      if (v === 'window') keep.op = 'left';
      if (v === 'snippet') keep.text = '';
      if (v === 'profile') keep.name = 'auto';
      if (!keep.label) delete keep.label;
      keep.type = v;
      b[key] = keep;
      changed(true);
    })));

    switch (a.type) {
      case 'app':
        fs.appendChild(field('Aplicația', textInput(a, 'app', { list: 'dl-apps', placeholder: 'ex. Slack' }), 'Începe să scrii; lista vine din aplicațiile instalate.'));
        break;
      case 'chrome':
        fs.appendChild(field('Adresa', textInput(a, 'url', { type: 'url' })));
        fs.appendChild(field('Recunoaște tab-ul deschis după', textInput(a, 'match', { optional: true, placeholder: 'automat: adresa fără parametri' }),
          'Dacă un tab conține acest text, deck-ul sare la el în loc să deschidă unul nou.'));
        fs.appendChild(check('Deschide mereu un tab nou', a, 'new_tab'));
        break;
      case 'url':
        fs.appendChild(field('Adresa', textInput(a, 'url', { type: 'url' })));
        break;
      case 'chrome_profile':
        fs.appendChild(field('Email-ul profilului', textInput(a, 'email', { list: 'dl-profiles', type: 'email' })));
        break;
      case 'keys':
        fs.appendChild(field('Combinația de taste', keyRecorder(a), 'Click în câmp și apasă combinația, sau scrie-o (ex. cmd+shift+f, ctrl+`).'));
        fs.appendChild(field('Trimite către aplicația (opțional)', textInput(a, 'app', { list: 'dl-apps', optional: true, placeholder: 'aplicația activă' })));
        break;
      case 'claude':
        fs.appendChild(field('Elementul din Claude (numele exact)', textInput(a, 'item', { placeholder: 'ex. Planificare săptămânală workflow' })));
        fs.appendChild(promptsEditor(a));
        fs.appendChild(h('p', { class: 'note', text: 'Trimiterea automată în Claude vine în etapa 4. Cu mai multe prompturi, telefonul îți dă de ales.' }));
        break;
      case 'shortcut':
        fs.appendChild(field('Numele shortcut-ului', textInput(a, 'name', { list: 'dl-shortcuts' })));
        break;
      case 'applescript':
        fs.appendChild(field('Script', textInput(a, 'script', { multiline: true })));
        break;
      case 'shell':
        fs.appendChild(field('Comandă (bash)', textInput(a, 'command', { multiline: true, placeholder: 'ex. open ~/Downloads' })));
        break;
      case 'sequence':
        fs.appendChild(stepsEditor(a));
        break;
      case 'spotify':
        fs.appendChild(field('Comanda', selectInput([['playpause', 'Play / Pauză'], ['next', 'Piesa următoare'], ['prev', 'Piesa anterioară'], ['shuffle', 'Shuffle'], ['repeat', 'Repeat']], a.cmd, function (v) { a.cmd = v; changed(false); })));
        break;
      case 'meet':
        fs.appendChild(field('Comanda', selectInput([['mic', 'Microfon on/off'], ['cam', 'Cameră on/off'], ['hand', 'Ridică mâna'], ['captions', 'Subtitrări'], ['chat', 'Chat'], ['people', 'Participanți'], ['present', 'Prezintă'], ['leave', 'Ieși din apel']], a.cmd, function (v) { a.cmd = v; changed(false); })));
        break;
      case 'timer':
        fs.appendChild(field('Comanda', selectInput([['toggle', 'Start / Pauză'], ['reset', 'Reset'], ['skip', 'Sari la următoarea etapă']], a.cmd, function (v) { a.cmd = v; changed(false); })));
        break;
      case 'window':
        fs.appendChild(field('Poziția', selectInput([['left', 'Jumătatea stângă'], ['right', 'Jumătatea dreaptă'], ['top', 'Sus'], ['bottom', 'Jos'], ['full', 'Tot ecranul'], ['center', 'Centru'], ['next', 'Monitorul următor']], a.op, function (v) { a.op = v; changed(false); })));
        break;
      case 'snippet':
        fs.appendChild(field('Textul lipit în aplicația din față', textInput(a, 'text', { multiline: true })));
        fs.appendChild(check('Apasă Enter după lipire', a, 'enter'));
        break;
      case 'profile':
        fs.appendChild(field('Profil', selectInput([['auto', 'Automat (după program)']].concat((cfg.profiles || []).map(function (p) { return [p.name, p.name]; })), a.name, function (v) { a.name = v; changed(false); })));
        break;
      case 'next_meeting':
        fs.appendChild(h('p', { class: 'note', text: 'Necesită adresa iCal a calendarului (Integrări). Folosește și „Text dinamic: Următorul meeting”.' }));
        break;
      case 'focus':
        fs.appendChild(h('p', { class: 'note', text: 'Rulează shortcut-urile de Focus setate în Integrări.' }));
        break;
      case 'soon':
        fs.appendChild(h('p', { class: 'note', text: 'Funcția vine în etapa ' + (a.phase || '?') + ' din plan. Butonul afișează un mesaj până atunci.' }));
        break;
      default:
        fs.appendChild(h('p', { class: 'note', text: 'Nu are setări suplimentare.' }));
    }
    if (nested) fs.appendChild(h('button', { class: 'btn small', type: 'button', text: '▶ Testează apăsarea lungă', onclick: function () { testAction(b.long); } }));
    return fs;
  }

  function stepsEditor(a) {
    var wrap = h('div', { class: 'steps' });
    (a.steps || []).forEach(function (st, i) {
      var holder = {};
      Object.defineProperty(holder, 'action', { get: function () { return a.steps[i]; }, set: function (x) { a.steps[i] = x; } });
      var box = h('div', { class: 'step' }, [h('div', { class: 'li-head' }, [
        h('b', { text: 'Pasul ' + (i + 1) }), h('span', { class: 'grow' }),
        h('button', { class: 'btn small', type: 'button', text: '↑', disabled: i === 0, onclick: function () { var t = a.steps[i - 1]; a.steps[i - 1] = a.steps[i]; a.steps[i] = t; changed(true); } }),
        h('button', { class: 'btn small danger', type: 'button', text: '✕', onclick: function () { a.steps.splice(i, 1); changed(true); } }),
      ])]);
      var ed = actionEditor(null, holder, 'action', true);
      var tb = ed.querySelector('button.btn.small:last-child'); if (tb && /apăsarea lungă/.test(tb.textContent)) tb.remove();
      box.appendChild(ed);
      wrap.appendChild(box);
    });
    wrap.appendChild(h('button', { class: 'btn small', type: 'button', text: '+ Adaugă pas', onclick: function () { a.steps = a.steps || []; a.steps.push({ type: 'app', app: '' }); changed(true); } }));
    wrap.appendChild(field('Pauză între pași (secunde)', textInput(a, 'delay', { type: 'number' })));
    return field('Pași', wrap);
  }

  function promptsEditor(a) {
    var wrap = h('div', { style: 'display:flex;flex-direction:column;gap:8px' });
    (a.prompts || []).forEach(function (p, i) {
      wrap.appendChild(h('div', { class: 'prompt' }, [
        h('div', { class: 'prompt-head' }, [
          textInput(p, 'label', { placeholder: 'Titlu (ex. 📅 Săptămânal)' }),
          h('button', { class: 'btn small danger', type: 'button', text: '✕', title: 'Șterge promptul', onclick: function () { a.prompts.splice(i, 1); changed(true); } }),
        ]),
        textInput(p, 'text', { multiline: true, placeholder: 'Textul trimis în Claude' }),
      ]));
    });
    wrap.appendChild(h('button', { class: 'btn small', type: 'button', text: '+ Adaugă prompt', onclick: function () {
      a.prompts = a.prompts || []; a.prompts.push({ label: 'Prompt ' + (a.prompts.length + 1), text: '' }); changed(true);
    } }));
    return field('Prompturi', wrap);
  }

  function keyRecorder(a) {
    var el = h('input', { class: 'keyrec', placeholder: 'apasă combinația…' });
    el.value = a.keys || '';
    var names = { Meta: 'cmd', Control: 'ctrl', Alt: 'alt', Shift: 'shift' };
    var special = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Enter: 'return', Escape: 'esc',
      Backspace: 'delete', Delete: 'forwarddelete', Tab: 'tab', ' ': 'space', PageUp: 'pageup', PageDown: 'pagedown', Home: 'home', End: 'end' };
    el.addEventListener('focus', function () { el.classList.add('rec'); });
    el.addEventListener('blur', function () { el.classList.remove('rec'); });
    el.addEventListener('keydown', function (e) {
      if (names[e.key]) return; // doar modificator, așteptăm tasta
      if (e.key === 'Backspace' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey && el.value) return; // editare manuală
      if (!(e.metaKey || e.ctrlKey || e.altKey) && e.key.length === 1 && !e.shiftKey) return; // scriere manuală
      e.preventDefault();
      var parts = [];
      if (e.metaKey) parts.push('cmd'); if (e.ctrlKey) parts.push('ctrl'); if (e.altKey) parts.push('alt'); if (e.shiftKey) parts.push('shift');
      var k = special[e.key] || (/^F\d{1,2}$/.test(e.key) ? e.key.toLowerCase() : null);
      if (!k) k = (e.code && /^Key[A-Z]$/.test(e.code)) ? e.code.slice(3).toLowerCase() : (e.code && /^Digit\d$/.test(e.code) ? e.code.slice(5) : (e.code === 'Backquote' ? '`' : e.key.toLowerCase()));
      parts.push(k);
      el.value = parts.join('+'); a.keys = el.value; changed(false);
    });
    el.addEventListener('input', function () { a.keys = el.value; changed(false); });
    return el;
  }

  function upload(b, f) {
    if (!f) return;
    if (f.size > 2 * 1024 * 1024) return toast('Imaginea e prea mare (maxim 2 MB)', true);
    var r = new FileReader();
    r.onload = function () {
      fetch('/api/admin/icon', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: b.id, data: r.result }) })
        .then(function (x) { return x.json(); })
        .then(function (res) {
          if (!res.ok) return toast(res.msg || 'Încărcare eșuată', true);
          b.icon = { type: 'image', file: res.file }; changed(true); toast('Imagine încărcată');
        });
    };
    r.readAsDataURL(f);
  }

  function testAction(a) {
    fetch('/api/admin/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: a }) })
      .then(function (r) { return r.json(); })
      .then(function (r) { toast((r.ok ? '✓ ' : '') + (r.msg || (r.ok ? 'Rulat' : 'Eroare')), !r.ok); })
      .catch(function () { toast('Serverul nu răspunde', true); });
  }

  function duplicate(b) {
    var arr = cfg.sets[cur.set].buttons, idx = arr.indexOf(null);
    if (idx === -1 || idx >= capacity()) return toast('Nu mai e loc în acest set', true);
    var c = JSON.parse(JSON.stringify(b));
    c.id = uniqueId(b.label || b.id); c.label = (b.label || '') + ' (copie)';
    arr[idx] = c; cur.slot = idx; changed(true);
  }

  // ---------------------------------------------------------------- setări, export, import
  $('open-settings').addEventListener('click', function () {
    $('s-cols').value = cfg.ui.columns; $('s-rows').value = cfg.ui.rows; $('s-sleep').value = cfg.ui.sleep_minutes;
    $('s-sound').checked = cfg.ui.sound !== false; $('s-haptics').checked = cfg.ui.haptics !== false;
    $('s-auto').checked = cfg.ui.auto_switch !== false; $('s-autoclose').checked = cfg.ui.auto_close !== false;
    $('settings').showModal();
  });
  $('settings').addEventListener('close', function () {
    if ($('settings').returnValue !== 'ok') return;
    var clamp = function (v, lo, hi, d) { v = parseInt(v, 10); return isNaN(v) ? d : Math.max(lo, Math.min(hi, v)); };
    cfg.ui.columns = clamp($('s-cols').value, 2, 8, 5);
    cfg.ui.rows = clamp($('s-rows').value, 1, 6, 3);
    cfg.ui.sleep_minutes = clamp($('s-sleep').value, 1, 240, 5);
    cfg.ui.sound = $('s-sound').checked; cfg.ui.haptics = $('s-haptics').checked;
    cfg.ui.auto_switch = $('s-auto').checked; cfg.ui.auto_close = $('s-autoclose').checked;
    normalize(); cur.slot = null; changed(true);
  });
  $('export').addEventListener('click', function () {
    var blob = new Blob([JSON.stringify(cleaned(), null, 2)], { type: 'application/json' });
    var a = h('a', { href: URL.createObjectURL(blob), download: 'macdeck-config-' + new Date().toISOString().slice(0, 10) + '.json' });
    document.body.appendChild(a); a.click(); a.remove();
  });
  $('import').addEventListener('change', function (e) {
    var f = e.target.files[0]; if (!f) return;
    var r = new FileReader();
    r.onload = function () {
      try {
        var c = JSON.parse(r.result);
        if (!c.sets || !c.ui) throw new Error();
        cfg = c; normalize(); cur = { set: 0, slot: null }; renderAll(); changed(true); toast('Configurație importată (↶ pentru anulare)');
      } catch (err) { toast('Fișier invalid', true); }
      e.target.value = '';
    };
    r.readAsText(f);
  });
  $('open-phone').addEventListener('click', function () {
    $('phone-dlg').showModal();
    var box = $('phone-info');
    function post(path, body) { return fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); }); }
    function draw() {
      post('/api/admin/info').then(function (r) {
        var i = r.info || {};
        box.innerHTML = '';
        function kv(label, val) { return h('div', { class: 'kv' }, [h('span', { text: label }), h('code', { text: val || '–' })]); }
        box.appendChild(kv('1. Prima dată, pe iPhone în Safari (instalează certificatul):', i.setup));
        box.appendChild(kv('   sau prin IP, dacă adresa .local nu merge:', i.setup_ip));
        box.appendChild(kv('2. Deck-ul (apoi Share → Add to Home Screen):', i.deck));
        cfg.security = cfg.security || {};
        var nc = h('input', { type: 'checkbox' }); nc.checked = !!cfg.security.no_code;
        nc.addEventListener('change', function () {
          if (nc.checked) cfg.security.no_code = true; else delete cfg.security.no_code;
          changed(false); setTimeout(draw, 700);
        });
        box.appendChild(h('div', { class: 'auto' }, [
          h('label', { class: 'check' }, [nc, 'Fără cod de asociere în rețeaua locală']),
          h('p', { class: 'note', text: 'Orice telefon sau calculator conectat la același Wi-Fi poate folosi deck-ul fără cod. Din internet nu se poate accesa, iar configuratorul rămâne doar pe Mac. Recomandat doar pe rețeaua de acasă.' }),
        ]));
        if (!cfg.security.no_code) box.appendChild(h('div', { class: 'kv' }, [h('span', { text: '3. Cod de asociere:' }), h('div', { class: 'code', text: i.code || '' })]));
        box.appendChild(h('p', { class: 'note', text: 'Telefoane asociate: ' + (i.phones || 0) + '. După asociere, deck-ul se deschide direct de pe ecranul principal al iPhone-ului.' }));
        if (i.mac) {
          var auto = h('div', { class: 'auto' }, [
            h('b', { text: i.autostart ? '✓ Pornire automată la login: activă' : 'Pornire automată la login: oprită' }),
            h('p', { class: 'note', text: i.autostart
              ? 'Serverul pornește singur cu Mac-ul și rulează în fundal, fără Terminal.'
              : 'Activeaz-o ca serverul să pornească singur cu Mac-ul, în fundal. Apoi închide fereastra Terminal.' }),
            i.autostart ? null : h('p', { class: 'note', text: 'Pentru scurtături, Claude, snippets etc., adaugă în System Settings → Privacy & Security → Accessibility: ' + i.python }),
            h('button', { class: 'btn ' + (i.autostart ? 'danger' : 'primary'), type: 'button', text: i.autostart ? 'Oprește pornirea automată' : 'Activează pornirea automată',
              onclick: function () { post('/api/admin/autostart', { on: !i.autostart }).then(function (x) { toast(x.msg || '', !x.ok); draw(); }); } }),
          ]);
          box.appendChild(auto);
        }
      }).catch(function () { box.textContent = 'Serverul nu răspunde.'; });
    }
    draw();
  });
  $('undo').addEventListener('click', undo);
  document.addEventListener('keydown', function (e) {
    var tag = (e.target.tagName || '').toLowerCase();
    if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey && tag !== 'input' && tag !== 'textarea') { e.preventDefault(); undo(); }
  });

  // ---------------------------------------------------------------- previzualizare
  function fitPreview() {
    var ph = $('phone'), w = ph.clientWidth, scale = w / 812;
    $('frame').style.transform = 'scale(' + scale + ')';
    ph.style.height = (375 * scale + 20) + 'px';
  }
  window.addEventListener('resize', fitPreview);

  function syncPreview() {
    try { $('frame').contentWindow.postMessage({ type: 'show-set', index: cur.set }, location.origin); } catch (e) {}
  }
  $('frame').addEventListener('load', function () { setTimeout(syncPreview, 400); });

  function renderAll() { renderTabs(); renderSetTools(); renderGrid(); renderInspector(); fitPreview(); syncPreview(); }

  // ================================================================ vederi: liste, integrări, diagnostic
  var curView = 'buttons';
  document.querySelectorAll('#views .view').forEach(function (b) {
    b.addEventListener('click', function () { showView(b.dataset.view); });
  });
  function showView(v) {
    curView = v;
    document.querySelectorAll('#views .view').forEach(function (b) { b.classList.toggle('cur', b.dataset.view === v); });
    $('view-buttons').classList.toggle('hidden', v !== 'buttons');
    ['lists', 'integrations', 'diag'].forEach(function (x) { $('view-' + x).classList.toggle('hidden', v !== x); });
    if (v === 'lists') renderLists();
    if (v === 'integrations') renderIntegrations();
    if (v === 'diag') renderDiag();
    if (v === 'buttons') renderAll();
  }

  // listă generică: fields = [{key, label, type: text|multiline|number|check|csv, placeholder}]
  function listEditor(arr, fields, newItem, titleKey) {
    var wrap = h('div', { class: 'list-ed' });
    function draw() {
      wrap.innerHTML = '';
      arr.forEach(function (it, i) {
        var li = h('div', { class: 'li' }, [h('div', { class: 'li-head' }, [
          h('span', { class: 'grow', text: '#' + (i + 1) + (titleKey && it[titleKey] ? ' · ' + it[titleKey] : '') }),
          h('button', { class: 'btn small', type: 'button', text: '↑', disabled: i === 0, onclick: function () { var t = arr[i - 1]; arr[i - 1] = arr[i]; arr[i] = t; changed(false); draw(); } }),
          h('button', { class: 'btn small', type: 'button', text: '↓', disabled: i === arr.length - 1, onclick: function () { var t = arr[i + 1]; arr[i + 1] = arr[i]; arr[i] = t; changed(false); draw(); } }),
          h('button', { class: 'btn small danger', type: 'button', text: '✕', onclick: function () { arr.splice(i, 1); changed(false); draw(); } }),
        ])]);
        fields.forEach(function (f) {
          if (f.type === 'check') { li.appendChild(check(f.label, it, f.key)); return; }
          if (f.type === 'csv') {
            var inp = h('input', { type: 'text', placeholder: f.placeholder || '' });
            inp.value = (it[f.key] || []).join(', ');
            inp.addEventListener('input', function () { it[f.key] = inp.value.split(',').map(function (x) { return x.trim(); }).filter(Boolean); changed(false); });
            li.appendChild(field(f.label, inp)); return;
          }
          li.appendChild(field(f.label, textInput(it, f.key, { multiline: f.type === 'multiline', type: f.type === 'number' ? 'number' : 'text', placeholder: f.placeholder, optional: f.optional })));
        });
        wrap.appendChild(li);
      });
      wrap.appendChild(h('button', { class: 'btn small', type: 'button', text: '+ Adaugă', onclick: function () { arr.push(JSON.parse(JSON.stringify(newItem))); changed(false); draw(); } }));
    }
    draw();
    return wrap;
  }
  function card(title, desc, kids) {
    return h('div', { class: 'card' }, [h('h2', { text: title }), desc ? h('p', { text: desc }) : null].concat(kids));
  }
  function pg(id) { cfg.pages[id] = cfg.pages[id] || { title: id }; return cfg.pages[id]; }
  function arrOf(obj, key) { if (!Array.isArray(obj[key])) obj[key] = []; return obj[key]; }

  function renderLists() {
    var v = $('view-lists'); v.innerHTML = '';
    var cl = pg('claude');
    v.appendChild(card('Claude: Pinned', 'Numele exacte ale elementelor din Claude. Opțional, un prompt trimis automat după deschidere (apăsarea lungă pe telefon deschide fără prompt).',
      [listEditor(arrOf(cl, 'pinned'), [{ key: 'name', label: 'Nume' }, { key: 'prompt', label: 'Prompt (opțional)', type: 'multiline', optional: true }], { name: '' }, 'name')]));
    v.appendChild(card('Claude: Artefacte', null,
      [listEditor(arrOf(cl, 'artifacts'), [{ key: 'name', label: 'Nume' }, { key: 'prompt', label: 'Prompt (opțional)', type: 'multiline', optional: true }], { name: '' }, 'name')]));
    v.appendChild(card('Snippets', 'Texte lipite în aplicația din față de pe Mac.',
      [listEditor(arrOf(pg('snippets'), 'items'), [{ key: 'label', label: 'Titlu' }, { key: 'text', label: 'Text', type: 'multiline' }, { key: 'enter', label: 'Apasă Enter după lipire', type: 'check' }], { label: 'Snippet nou', text: '' }, 'label')]));
    v.appendChild(card('Prompt vocal: șabloane', '{text} se înlocuiește cu ce ai dictat.',
      [listEditor(arrOf(pg('voice'), 'templates'), [{ key: 'label', label: 'Nume' }, { key: 'text', label: 'Șablon', type: 'multiline' }], { label: 'Șablon nou', text: '{text}' }, 'label')]));
    v.appendChild(card('Analizează pagina: instrumente', 'Variabile: {url} (codificat), {raw} (neschimbat), {domain}.',
      [listEditor(arrOf(pg('analyze'), 'tools'), [{ key: 'label', label: 'Nume' }, { key: 'url', label: 'Adresă' }], { label: 'Instrument nou', url: 'https://' }, 'label')]));
    var sf = pg('sfrog');
    v.appendChild(card('Screaming Frog', 'Configurațiile se exportă din Screaming Frog: File → Configuration → Save As (.seospiderconfig). Prima din listă e folosită de „Crawl site curent”.', [
      listEditor(arrOf(sf, 'configs'), [{ key: 'name', label: 'Nume' }, { key: 'path', label: 'Cale fișier', placeholder: '~/Documents/SF/audit.seospiderconfig' }], { name: 'Configurație', path: '' }, 'name'),
      field('Folder rezultate', textInput(sf, 'output_folder')),
      field('Tab-uri exportate (CSV)', textInput(sf, 'export_tabs'), 'ex. Internal:All,Response Codes:Client Error (4xx)'),
    ]));
    var mg = pg('meetgeek');
    function csvField(lbl, key) {
      var inp = h('input', { type: 'text' }); inp.value = (mg[key] || []).join(', ');
      inp.addEventListener('input', function () { mg[key] = inp.value.split(',').map(function (x) { return x.trim(); }).filter(Boolean); changed(false); });
      return field(lbl, inp);
    }
    v.appendChild(card('MeetGeek', 'Butoanele de înregistrare se caută după nume. Verifică numele exacte în Diagnostic. Dacă MeetGeek are o scurtătură globală, completeaz-o și se folosește aceea.', [
      field('Numele aplicației', textInput(mg, 'app')),
      csvField('Nume buton Start (separate prin virgulă)', 'start_names'),
      csvField('Nume buton Stop', 'stop_names'),
      field('Scurtătură start/stop (opțional)', textInput(mg, 'toggle_keys', { optional: true, placeholder: 'ex. cmd+shift+r' })),
    ]));
    var np = pg('numpad');
    v.appendChild(card('Num pad', 'Implicit, tastele ajung în aplicația din față. Opțional, o aplicație anume care e adusă în față înainte de fiecare tastă (ex. Microsoft Excel).', [
      field('Trimite mereu către aplicația', textInput(np, 'send_to', { list: 'dl-apps', placeholder: 'aplicația din față', optional: true })),
    ]));
    var tm = pg('timer');
    v.appendChild(card('Pomodoro', null, [h('div', { class: 'row2' }, [
      field('Lucru (minute)', textInput(tm, 'work', { type: 'number' })), field('Pauză (minute)', textInput(tm, 'break', { type: 'number' })),
    ])]));
  }

  function renderIntegrations() {
    var v = $('view-integrations'); v.innerHTML = '';
    cfg.integrations = cfg.integrations || {};
    var c = cfg.integrations.claude = cfg.integrations.claude || {};
    c.delays = c.delays || {};
    v.appendChild(card('Claude (aplicația pentru Mac)', 'Deck-ul deschide elementele prin căutarea din aplicație și lipește promptul. Dacă e prea rapid pentru Mac-ul tău, mărește pauzele.', [
      field('Aplicația', textInput(c, 'app')),
      h('div', { class: 'row2' }, [field('Scurtătură căutare', textInput(c, 'search_keys')), field('Scurtătură chat nou', textInput(c, 'new_chat_keys'))]),
      h('div', { class: 'row2' }, [field('Pauză după activare (s)', textInput(c.delays, 'activate', { type: 'number' })), field('Pauză după căutare (s)', textInput(c.delays, 'search', { type: 'number' }))]),
      h('div', { class: 'row2' }, [field('Așteptare rezultate (s)', textInput(c.delays, 'results', { type: 'number' })), field('Așteptare deschidere (s)', textInput(c.delays, 'open', { type: 'number' }))]),
      h('button', { class: 'btn', type: 'button', text: '▶ Testează: deschide „Planificare săptămânală workflow” fără prompt', onclick: function () { testAction({ type: 'claude', item: 'Planificare săptămânală workflow' }); } }),
    ]));
    var cal = cfg.integrations.calendar = cfg.integrations.calendar || {};
    v.appendChild(card('Google Calendar: următorul meeting', 'Google Calendar → Settings → calendarul tău → Integrate calendar → „Secret address in iCal format”. Copiază adresa aici. Rămâne doar pe Mac-ul tău.', [
      field('Adresa secretă iCal', textInput(cal, 'ical_url', { placeholder: 'https://calendar.google.com/calendar/ical/.../basic.ics' })),
    ]));
    var f = cfg.integrations.focus = cfg.integrations.focus || {};
    v.appendChild(card('Focus / Nu deranja', 'macOS nu permite pornirea Focus direct din scripturi, așa că deck-ul folosește două shortcut-uri. În aplicația Shortcuts creează: „Mac Deck Focus On” (acțiunea Set Focus → Do Not Disturb → On) și „Mac Deck Focus Off” (→ Off).', [
      h('div', { class: 'row2' }, [field('Shortcut pornire', textInput(f, 'on_shortcut', { list: 'dl-shortcuts' })), field('Shortcut oprire', textInput(f, 'off_shortcut', { list: 'dl-shortcuts' }))]),
      check('Pornește Focus automat cât timp ești într-un apel Meet', f, 'during_meet'),
    ]));
    cfg.profiles = cfg.profiles || [];
    var dayNames = ['L', 'Ma', 'Mi', 'J', 'V', 'S', 'D'];
    var profWrap = h('div', { class: 'list-ed' });
    function drawProfiles() {
      profWrap.innerHTML = '';
      cfg.profiles.forEach(function (p, i) {
        p.days = p.days || [1, 2, 3, 4, 5, 6, 7];
        var days = h('div', { class: 'days' });
        dayNames.forEach(function (dn, di) {
          var cb = h('input', { type: 'checkbox' }); cb.checked = p.days.indexOf(di + 1) !== -1;
          cb.addEventListener('change', function () {
            p.days = p.days.filter(function (x) { return x !== di + 1; }); if (cb.checked) p.days.push(di + 1); p.days.sort(); changed(false);
          });
          days.appendChild(h('label', {}, [cb, dn]));
        });
        profWrap.appendChild(h('div', { class: 'li' }, [
          h('div', { class: 'li-head' }, [h('span', { class: 'grow', text: 'Profil ' + (i + 1) }),
            h('button', { class: 'btn small danger', type: 'button', text: '✕', onclick: function () { cfg.profiles.splice(i, 1); changed(false); drawProfiles(); } })]),
          field('Nume', textInput(p, 'name')), days,
          h('div', { class: 'row2' }, [field('De la', textInput(p, 'from', { placeholder: '08:00' })), field('Până la', textInput(p, 'to', { placeholder: '19:00' }))]),
        ]));
      });
      profWrap.appendChild(h('button', { class: 'btn small', type: 'button', text: '+ Profil', onclick: function () { cfg.profiles.push({ name: 'Profil nou', days: [1, 2, 3, 4, 5], from: '08:00', to: '19:00' }); changed(false); drawProfiles(); } }));
    }
    drawProfiles();
    v.appendChild(card('Profiluri (Birou / Acasă)', 'În modul automat, se alege primul profil care se potrivește cu ziua și ora; altfel ultimul. Fiecare set poate fi limitat la anumite profiluri (din tab-ul Butoane, sub numele setului).', [
      field('Profil activ', selectInput([['auto', 'Automat (după program)']].concat(cfg.profiles.map(function (p) { return [p.name, p.name]; })), cfg.ui.profile || 'auto', function (x) { cfg.ui.profile = x; changed(false); })),
      profWrap,
    ]));
  }

  function renderDiag() {
    var v = $('view-diag'); v.innerHTML = '';
    var app = h('input', { type: 'text', list: 'dl-apps', placeholder: 'ex. MeetGeek' });
    var out = h('div', { class: 'scroll' });
    v.appendChild(card('Elementele interfeței unei aplicații', 'Arată butoanele și meniurile pe care deck-ul le poate apăsa (pentru MeetGeek și Screaming Frog). Aplicația trebuie să fie deschisă; Terminal are nevoie de permisiunea Accessibility.', [
      field('Aplicația', app),
      h('button', { class: 'btn primary', type: 'button', text: 'Listează elementele', onclick: function () {
        out.innerHTML = '<p class="muted">Se citește… (poate dura până la un minut)</p>';
        fetch('/api/admin/uidump', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ app: app.value }) })
          .then(function (r) { return r.json(); }).then(function (r) {
            if (!r.ok) { out.innerHTML = '<p style="color:var(--red)">' + esc(r.msg) + '</p>'; return; }
            out.innerHTML = '<table class="dump">' + r.items.map(function (it) {
              return '<tr><td>' + esc(it.role) + '</td><td>' + esc(it.name) + '</td><td class="muted">' + esc(it.desc) + '</td></tr>';
            }).join('') + '</table>';
          });
      } }), out,
    ]));
    var tests = [
      ['Chrome: deschide Gmail', { type: 'chrome', url: 'https://mail.google.com' }],
      ['Spotify: play/pauză (verifică „Allow JavaScript from Apple Events”)', { type: 'spotify', cmd: 'playpause' }],
      ['Scurtătură: ⌘ Space (Spotlight) — verifică Accessibility', { type: 'keys', keys: 'cmd+space' }],
      ['Fereastra din față: jumătatea stângă', { type: 'window', op: 'left' }],
      ['Microfon on/off', { type: 'mic_mute' }],
    ];
    v.appendChild(card('Teste rapide de permisiuni', 'Fiecare buton rulează o acțiune pe Mac. Dacă macOS cere o permisiune, acceptă și încearcă din nou.',
      tests.map(function (t) { return h('button', { class: 'btn', type: 'button', text: '▶ ' + t[0], onclick: function () { testAction(t[1]); } }); })));
  }

  load();
})();
