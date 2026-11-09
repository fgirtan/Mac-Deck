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
  var TOGGLES = [['', 'Niciuna'], ['caffeinate', 'Ține treaz']];

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
      field('Pagină dedicată deschisă la tap', selectInput(pages, b.page || '', function (v) { if (v) b.page = v; else delete b.page; changed(false); })),
      field('Starea afișată pe buton (verde când e activ)', selectInput(TOGGLES, b.state || '', function (v) { if (v) b.state = v; else delete b.state; changed(false); })),
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
      case 'soon':
        fs.appendChild(h('p', { class: 'note', text: 'Funcția vine în etapa ' + (a.phase || '?') + ' din plan. Butonul afișează un mesaj până atunci.' }));
        break;
      default:
        fs.appendChild(h('p', { class: 'note', text: 'Nu are setări suplimentare.' }));
    }
    if (nested) fs.appendChild(h('button', { class: 'btn small', type: 'button', text: '▶ Testează apăsarea lungă', onclick: function () { testAction(b.long); } }));
    return fs;
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
    $('settings').showModal();
  });
  $('settings').addEventListener('close', function () {
    if ($('settings').returnValue !== 'ok') return;
    var clamp = function (v, lo, hi, d) { v = parseInt(v, 10); return isNaN(v) ? d : Math.max(lo, Math.min(hi, v)); };
    cfg.ui.columns = clamp($('s-cols').value, 2, 8, 5);
    cfg.ui.rows = clamp($('s-rows').value, 1, 6, 3);
    cfg.ui.sleep_minutes = clamp($('s-sleep').value, 1, 240, 5);
    cfg.ui.sound = $('s-sound').checked; cfg.ui.haptics = $('s-haptics').checked;
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

  load();
})();
