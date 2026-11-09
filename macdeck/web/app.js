(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };

  // ---------------------------------------------------------------- stocare locală (sigură)
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };

  var token = store.get('macdeck.token', '');
  var cfg = null, state = {}, es = null;
  var ui = store.get('macdeck.ui', { set: 0, page: null });
  var keyEls = {};       // id buton -> element
  var pageEls = {};      // id pagină -> element (păstrate, ca starea să rămână)
  var dragging = {};

  // ---------------------------------------------------------------- API
  function api(path, body) {
    var opts = { headers: { 'X-Deck-Token': token } };
    if (body !== undefined) {
      opts.method = 'POST';
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    } else {
      opts.cache = 'no-store';
    }
    return fetch(path, opts).then(function (r) {
      if (r.status === 401) { showPair(); throw new Error('neasociat'); }
      return r.json();
    });
  }

  function boot() {
    api('/api/config').then(function (d) {
      cfg = d.config;
      hidePair();
      render();
      applyState(d.state);
      connect();
    }).catch(function (e) {
      if (e.message !== 'neasociat') { setConn(false); setTimeout(boot, 2000); }
    });
  }

  function reloadConfig() {
    api('/api/config').then(function (d) { cfg = d.config; render(); applyState(d.state); }).catch(function () {});
  }

  function connect() {
    if (es) es.close();
    es = new EventSource('/api/events?k=' + encodeURIComponent(token));
    es.onopen = function () { setConn(true); };
    es.onerror = function () { setConn(false); };
    es.onmessage = function (ev) {
      var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      setConn(true);
      if (m.type === 'state') applyState(m);
      else if (m.type === 'config') reloadConfig();
      else if (m.type === 'toast') toast(m.msg);
      else if (m.type === 'open-page') { var pb = cfg && findButtonByPage(m.page); if (pb && ui.page !== m.page) { if (ui.page) closePage(ui.page); openPage(pb); } }
      else if (m.type === 'close-page') { if (ui.page === m.page) closePage(m.page); }
    };
  }

  function setConn(ok) { $('dot').classList.toggle('ok', ok); }

  // ---------------------------------------------------------------- asociere
  function showPair() { $('pair').classList.remove('hidden'); setTimeout(function () { $('pair-code').focus(); }, 50); }
  function hidePair() { $('pair').classList.add('hidden'); }
  $('pair-code').addEventListener('input', function (e) {
    var v = e.target.value.replace(/\D/g, '').slice(0, 6);
    e.target.value = v;
    $('pair-err').textContent = '';
    if (v.length === 6) {
      fetch('/api/pair', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: v }) })
        .then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
        .then(function (res) {
          if (res[0] && res[1].token) {
            token = res[1].token; store.set('macdeck.token', token);
            e.target.value = ''; e.target.blur(); boot();
          } else {
            $('pair-err').textContent = 'Cod greșit. Verifică Terminal-ul de pe Mac.';
            e.target.value = '';
          }
        }).catch(function () { $('pair-err').textContent = 'Nu găsesc Mac-ul.'; });
    }
  });

  // ---------------------------------------------------------------- grila
  function iconHTML(b) {
    var ic = b.icon || {};
    if (ic.type === 'glyph') return glyph(ic.name);
    if (ic.type === 'emoji') return '<span style="font-size:30px">' + ic.value + '</span>';
    return '<img src="/icons/' + encodeURIComponent(b.id) + '.png?v=' + iconVersion(b) + '" alt="" data-letter="' + (b.label || '?').charAt(0) + '">';
  }

  function iconVersion(b) {
    var str = JSON.stringify(b.icon || b.action || {}), h = 0;
    for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36);
  }

  function render() {
    var cols = cfg.ui.columns || 5, rows = cfg.ui.rows || 3, per = cols * rows;
    var sets = $('sets');
    sets.innerHTML = '';
    keyEls = {};
    visibleSets().forEach(function (s) {
      var el = document.createElement('div');
      el.className = 'set';
      el.style.gridTemplateColumns = 'repeat(' + cols + ', 1fr)';
      el.style.gridTemplateRows = 'repeat(' + rows + ', 1fr)';
      for (var i = 0; i < per; i++) {
        var b = s.buttons[i];
        var k = document.createElement('button');
        k.className = 'key' + (b ? '' : ' empty');
        if (b) {
          var soon = b.action && b.action.type === 'soon';
          k.innerHTML = '<div class="ic">' + iconHTML(b) + '</div><div class="lb">' + esc(b.label) + '</div>' +
            (soon ? '<span class="soon"></span>' : '') + (b.page ? '<span class="has-page">›</span>' : '');
          bindPress(k, pressFn(b, false), b.long ? pressFn(b, true) : null);
          keyEls[b.id] = k;
        }
        el.appendChild(k);
      }
      sets.appendChild(el);
    });
    sets.querySelectorAll('img[data-letter]').forEach(function (img) {
      img.onerror = function () { img.outerHTML = '<span class="letter">' + esc(img.dataset.letter) + '</span>'; };
    });
    var vis = visibleSets();
    $('dots').innerHTML = vis.map(function () { return '<i></i>'; }).join('');
    ui.set = Math.min(ui.set || 0, vis.length - 1);
    renderedProfile = currentProfile();
    requestAnimationFrame(function () { sets.scrollLeft = ui.set * sets.clientWidth; updateDots(); });
    if (ui.page && !pageEls[ui.page]) {
      var pb = findButtonByPage(ui.page);
      if (pb) openPage(pb, true);
    }
  }

  var renderedProfile = null;
  function currentProfile() { return (state.live && state.live.profile) || null; }
  function visibleSets() {
    var p = currentProfile();
    var v = cfg.sets.filter(function (s) { return !s.profiles || !s.profiles.length || !p || s.profiles.indexOf(p) !== -1; });
    return v.length ? v : cfg.sets;
  }

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function findButtonByPage(p) {
    for (var i = 0; i < cfg.sets.length; i++)
      for (var j = 0; j < cfg.sets[i].buttons.length; j++)
        if (cfg.sets[i].buttons[j] && cfg.sets[i].buttons[j].page === p) return cfg.sets[i].buttons[j];
    return null;
  }

  var scrollT;
  $('sets').addEventListener('scroll', function () {
    clearTimeout(scrollT);
    scrollT = setTimeout(function () {
      var s = $('sets');
      ui.set = Math.round(s.scrollLeft / s.clientWidth);
      store.set('macdeck.ui', ui);
      updateDots();
    }, 80);
  }, { passive: true });
  function updateDots() {
    var d = $('dots').children;
    for (var i = 0; i < d.length; i++) d[i].classList.toggle('cur', i === ui.set);
  }
  window.addEventListener('resize', function () {
    var s = $('sets'); s.scrollLeft = ui.set * s.clientWidth;
  });

  // tap / apăsare lungă
  function bindPress(el, onTap, onLong) {
    var t, x0, y0, longFired, active;
    el.addEventListener('pointerdown', function (e) {
      active = true; longFired = false; x0 = e.clientX; y0 = e.clientY;
      el.classList.add('down');
      if (onLong) t = setTimeout(function () { if (active) { longFired = true; el.classList.remove('down'); onLong(); } }, 550);
    });
    el.addEventListener('pointermove', function (e) {
      if (active && (Math.abs(e.clientX - x0) > 12 || Math.abs(e.clientY - y0) > 12)) cancel();
    });
    el.addEventListener('pointerup', function () {
      if (active && !longFired) onTap();
      cancel();
    });
    el.addEventListener('pointercancel', cancel);
    el.addEventListener('pointerleave', cancel);
    el.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    function cancel() { active = false; clearTimeout(t); el.classList.remove('down'); }
  }

  function pressFn(b, long) {
    return function () {
      feedback();
      var a = long ? b.long : b.action;
      if (!long && a && a.type === 'claude' && a.prompts && a.prompts.length > 1) return openSheet(b);
      if (!long && b.page) openPage(b);
      runButton(b, long);
    };
  }

  function runButton(b, long, choice) {
    var el = keyEls[b.id];
    var body = { id: b.id, long: !!long };
    if (choice !== undefined) body.choice = choice;
    api('/api/action', body).then(function (r) {
      flash(el, r.ok ? 'ok' : (r.soon ? null : 'fail'));
      if (!r.ok) toast(r.msg || 'Eroare', !r.soon);
      else if (long && b.long && b.long.label) toast(b.long.label);
    }).catch(function (e) { flash(el, 'fail'); toast(e.message === 'neasociat' ? 'Neasociat' : 'Mac-ul nu răspunde', true); });
  }

  function flash(el, cls) {
    if (!el || !cls) return;
    el.classList.add(cls);
    setTimeout(function () { el.classList.remove(cls); }, 650);
  }

  // ---------------------------------------------------------------- alegere (sheet)
  function openSheet(b) {
    $('sheet-title').textContent = b.label;
    var box = $('sheet-opts');
    box.innerHTML = '';
    b.action.prompts.forEach(function (p, i) {
      var o = document.createElement('button');
      o.className = 'opt';
      o.innerHTML = esc(p.label) + '<small>' + esc(p.text) + '</small>';
      bindPress(o, function () { feedback(); closeSheet(); runButton(b, false, i); }, null);
      box.appendChild(o);
    });
    $('sheet').classList.remove('hidden');
  }
  function closeSheet() { $('sheet').classList.add('hidden'); }
  $('sheet-cancel').addEventListener('click', closeSheet);
  $('sheet').addEventListener('click', function (e) { if (e.target.id === 'sheet') closeSheet(); });

  // ---------------------------------------------------------------- pagini dedicate
  var pageCtl = {};   // id pagină -> { r: renderer, timer, ctx }
  function openPage(b, instant) {
    var id = b.page, p = pageEls[id];
    if (!p) {
      var meta = (cfg.pages && cfg.pages[id]) || { title: b.label };
      p = document.createElement('section');
      p.className = 'page';
      p.innerHTML = '<header><button class="backb">' + glyph('back') + 'Înapoi</button>' +
        '<div class="ic">' + iconHTML(b).replace('<img ', '<img style="width:28px;height:28px" ') + '</div><h2>' + esc(meta.title || b.label) + '</h2></header>' +
        '<div class="body"></div>';
      var himg = p.querySelector('header img');
      if (himg) himg.onerror = function () { himg.remove(); };
      bindPress(p.querySelector('.backb'), function () { feedback(); closePage(id); }, null);
      edgeSwipe(p, function () { closePage(id); });
      var ctx = {
        id: id, button: b, meta: meta, esc: esc, toast: toast, feedback: feedback, press: bindPress,
        call: function (body) { return api('/api/page/' + id, body || {}); },
        get: function () { return api('/api/page/' + id); },
        refresh: function () { refreshPage(id); },
      };
      var maker = window.DeckPages && window.DeckPages[id];
      var body = p.querySelector('.body');
      if (maker) {
        var r = maker(ctx);
        body.appendChild(r.el);
        pageCtl[id] = { r: r, ctx: ctx, timer: null };
      } else {
        body.classList.add('empty');
        body.textContent = 'Pagina „' + id + '” nu există.';
      }
      $('pages').appendChild(p);
      pageEls[id] = p;
    }
    if (instant) p.style.transition = 'none';
    requestAnimationFrame(function () { p.classList.add('open'); if (instant) requestAnimationFrame(function () { p.style.transition = ''; }); });
    ui.page = id; store.set('macdeck.ui', ui);
    startPage(id);
  }
  function refreshPage(id) {
    var c = pageCtl[id];
    if (!c) return;
    c.ctx.get().then(function (st) { try { c.r.update(st || {}); } catch (e) { console.error(e); } }).catch(function () {});
  }
  function startPage(id) {
    var c = pageCtl[id];
    if (!c) return;
    stopPage(id);
    refreshPage(id);
    if (c.r.poll) c.timer = setInterval(function () { if (!document.hidden && !sleeping) refreshPage(id); }, c.r.poll);
  }
  function stopPage(id) { var c = pageCtl[id]; if (c && c.timer) { clearInterval(c.timer); c.timer = null; } }
  function closePage(id) {
    var p = pageEls[id];
    if (p) p.classList.remove('open');   // elementul rămâne: la revenire, starea e aceeași
    stopPage(id);
    if (ui.page === id) { ui.page = null; store.set('macdeck.ui', ui); }
  }
  function edgeSwipe(el, cb) {
    var x0 = null;
    el.addEventListener('pointerdown', function (e) {
      var r = el.getBoundingClientRect();
      x0 = (e.clientX - r.left < 28) ? e.clientX : null;
    });
    el.addEventListener('pointerup', function (e) { if (x0 !== null && e.clientX - x0 > 70) cb(); x0 = null; });
  }

  // ---------------------------------------------------------------- slidere
  function makeSlider(rootId, key) {
    var root = $(rootId), tr = root.querySelector('.track');
    var fill = root.querySelector('.fill'), val = root.querySelector('.val');
    var last = 0;
    function show(v) {
      fill.style.height = (v == null ? 0 : v) + '%';
      val.textContent = v == null ? '–' : v;
    }
    function at(e) {
      var r = tr.getBoundingClientRect();
      return Math.round(Math.max(0, Math.min(100, (r.bottom - e.clientY) / r.height * 100)));
    }
    function move(e) {
      var v = at(e);
      state[key] = v; show(v);
      if (key === 'volume') { state.muted = false; root.classList.remove('muted'); }
      var now = Date.now();
      if (now - last > 60) { last = now; send(v); }
    }
    function send(v) { var b = {}; b[key] = v; api('/api/system', b).then(check).catch(function () {}); }
    tr.addEventListener('pointerdown', function (e) {
      if (root.classList.contains('na')) return toast('Luminozitatea nu e disponibilă pe ecranul curent', true);
      dragging[key] = true; tr.classList.add('drag'); tr.setPointerCapture(e.pointerId); move(e);
    });
    tr.addEventListener('pointermove', function (e) { if (dragging[key]) move(e); });
    function end() {
      if (!dragging[key]) return;
      dragging[key] = false; tr.classList.remove('drag'); send(state[key]); feedback(true);
    }
    tr.addEventListener('pointerup', end);
    tr.addEventListener('pointercancel', end);
    return show;
  }
  function check(r) { if (r && r.ok === false && r.msg) toast(r.msg, true); }
  var showVol = makeSlider('vol', 'volume');
  var showBri = makeSlider('bri', 'brightness');
  $('vol-icon').innerHTML = glyph('volume');
  $('bri-icon').innerHTML = glyph('sun');
  bindPress($('vol-icon'), function () {
    feedback(); state.muted = !state.muted; paintSliders();
    api('/api/system', { mute: true }).then(check).catch(function () {});
  }, null);

  function paintSliders() {
    if (!dragging.volume) showVol(state.volume);
    if (!dragging.brightness) showBri(state.brightness);
    $('vol').classList.toggle('muted', !!state.muted);
    $('vol').classList.toggle('na', state.volume == null);
    $('bri').classList.toggle('na', state.brightness == null);
    $('vol-icon').innerHTML = glyph(state.muted ? 'volume-off' : 'volume');
  }

  function applyState(s) {
    if (!s) return;
    ['volume', 'muted', 'brightness', 'toggles', 'live'].forEach(function (k) {
      if (k in s && !dragging[k]) state[k] = s[k];
    });
    paintSliders();
    var t = state.toggles || {}, live = state.live || {};
    if (cfg && currentProfile() !== renderedProfile) render();
    if (cfg) cfg.sets.forEach(function (set) {
      set.buttons.forEach(function (b) {
        if (!b || !keyEls[b.id]) return;
        var k = keyEls[b.id];
        if (b.state) k.classList.toggle('on', !!t[b.state]);
        if (b.dynamic) dynamicKey(b, k, live);
        badgeKey(b, k, live.badges || {});
      });
    });
    if (live.hint && live.hint !== shownHint) { shownHint = live.hint; toast(live.hint, true); }
    $('sleep-info').textContent = state.volume == null ? '' : 'Volum ' + state.volume + '%';
  }

  var shownHint = null;
  function setLabel(k, txt) { var lb = k.querySelector('.lb'); if (lb && lb.textContent !== txt) lb.textContent = txt; }
  function dynamicKey(b, k, live) {
    if (b.dynamic === 'next_meeting') {
      var m = live.next_meeting;
      if (!m) { setLabel(k, 'Niciun meeting'); k.classList.remove('on', 'soon-m'); return; }
      var mins = Math.round((m.start * 1000 - Date.now()) / 60000);
      var when = mins <= 0 ? 'acum' : mins < 60 ? 'în ' + mins + ' min' : new Date(m.start * 1000).toTimeString().slice(0, 5);
      setLabel(k, m.title + ' · ' + when);
      k.classList.toggle('on', mins <= 5);
    } else if (b.dynamic === 'timer') {
      var tm = live.timer;
      if (!tm || (!tm.running && tm.left === tm.full)) { setLabel(k, b.label); return; }
      var sec = tm.left;
      setLabel(k, (tm.mode === 'break' ? '☕ ' : '') + Math.floor(sec / 60) + ':' + ('0' + sec % 60).slice(-2));
    } else if (b.dynamic === 'spotify') {
      var sp = live.spotify, ic = k.querySelector('.ic');
      if (sp && sp.art) {
        var img = ic.querySelector('img.cover');
        if (!img) { ic.innerHTML = '<img class="cover" alt="">'; img = ic.querySelector('img'); }
        if (img.getAttribute('src') !== sp.art) img.src = sp.art;
        setLabel(k, sp.title || b.label);
        k.classList.toggle('on', !!sp.playing);
      } else if (ic.querySelector('img.cover')) {
        ic.innerHTML = iconHTML(b); setLabel(k, b.label); k.classList.remove('on');
      }
    }
  }
  function badgeCount(b, badges) {
    var a = b.action || {};
    if (b.badge === false) return 0;
    if (a.type === 'chrome' && /mail\.google\.com/.test(a.url || '')) return badges.__gmail || 0;
    var app = a.app || (b.icon && b.icon.app);
    var dock = badges.__dock || {};
    if (app && dock[app]) { var n = parseInt(dock[app], 10); return isNaN(n) ? '•' : n; }
    return 0;
  }
  function badgeKey(b, k, badges) {
    var n = badgeCount(b, badges), el = k.querySelector('.badge-n');
    if (!n) { if (el) el.remove(); return; }
    if (!el) { el = document.createElement('span'); el.className = 'badge-n'; k.appendChild(el); }
    var txt = typeof n === 'number' && n > 99 ? '99+' : String(n);
    if (el.textContent !== txt) el.textContent = txt;
  }

  // ---------------------------------------------------------------- feedback
  var audio = null;
  function feedback(quiet) {
    var u = (cfg && cfg.ui) || {};
    if (u.haptics !== false) {
      try { $('haptic').click(); } catch (e) {}           // iOS 18+: comutatorul nativ vibrează
      if (navigator.vibrate) try { navigator.vibrate(8); } catch (e) {}
    }
    if (u.sound !== false && !quiet) tick();
  }
  function tick() {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      var o = audio.createOscillator(), g = audio.createGain(), t = audio.currentTime;
      o.frequency.value = 2200; g.gain.setValueAtTime(0.05, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.03);
      o.connect(g).connect(audio.destination); o.start(t); o.stop(t + 0.035);
    } catch (e) {}
  }

  function toast(msg, bad) {
    var t = $('toast');
    t.textContent = msg; t.classList.toggle('bad', !!bad); t.classList.add('show');
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.classList.remove('show'); }, 2200);
  }

  // ---------------------------------------------------------------- ecran mereu aprins
  var wake = null;
  function keepAwake() {
    if ('wakeLock' in navigator && window.isSecureContext) {
      navigator.wakeLock.request('screen').then(function (l) {
        wake = l; $('awake').innerHTML = glyph('sun'); $('awake').querySelector('svg').style.cssText = 'width:12px;height:12px';
        l.addEventListener('release', function () { wake = null; });
      }).catch(videoFallback);
    } else {
      videoFallback();
    }
  }
  function videoFallback() {
    var v = $('nosleep');
    var p = v.play();
    if (p && p.then) p.then(function () {
      $('awake').innerHTML = glyph('sun'); $('awake').querySelector('svg').style.cssText = 'width:12px;height:12px;opacity:.6';
    }).catch(function () {});
  }
  document.addEventListener('pointerdown', function () { if (!wake) keepAwake(); }, true);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') { keepAwake(); if (!es || es.readyState === 2) boot(); }
  });

  // ---------------------------------------------------------------- mod repaus + pixel shift (protecție OLED)
  var lastTouch = Date.now(), sleeping = false;
  document.addEventListener('pointerdown', function (e) {
    lastTouch = Date.now();
    if (sleeping) { e.preventDefault(); e.stopPropagation(); wakeUp(); }
  }, true);
  $('sleep').addEventListener('click', function (e) { e.stopPropagation(); });
  function goSleep() {
    sleeping = true; $('sleep').classList.remove('hidden'); moveClock(); tickClock();
  }
  function wakeUp() {
    // ascundem după ce trece și evenimentul de click, ca primul tap să nu apese un buton
    setTimeout(function () { sleeping = false; $('sleep').classList.add('hidden'); }, 350);
  }
  function tickClock() {
    var d = new Date();
    $('sleep-clock').textContent = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }
  function moveClock() {
    var el = $('sleep-inner');
    el.style.left = (10 + Math.random() * 55) + '%';
    el.style.top = (10 + Math.random() * 50) + '%';
  }
  setInterval(function () {
    var mins = (cfg && cfg.ui && cfg.ui.sleep_minutes) || 5;
    if (!sleeping && Date.now() - lastTouch > mins * 60000) goSleep();
    if (sleeping) tickClock();
  }, 1000);
  setInterval(function () { if (sleeping) moveClock(); }, 60000);
  setInterval(function () {
    document.body.style.transform = 'translate(' + (Math.round(Math.random() * 4) - 2) + 'px,' + (Math.round(Math.random() * 4) - 2) + 'px)';
  }, 180000);

  // fără scroll / zoom accidental (în afară de swipe-ul dintre seturi)
  document.addEventListener('touchmove', function (e) {
    if (!e.target.closest('#sets, .scroll, textarea')) e.preventDefault();
  }, { passive: false });
  document.addEventListener('gesturestart', function (e) { e.preventDefault(); });

  // previzualizarea din configurator arată setul editat
  window.addEventListener('message', function (e) {
    if (e.origin !== location.origin || !e.data || e.data.type !== 'show-set') return;
    var s = $('sets');
    ui.set = e.data.index; s.scrollTo({ left: ui.set * s.clientWidth, behavior: 'smooth' }); updateDots();
  });

  $('rotate').querySelector('div').innerHTML = glyph('rotate');
  boot();
})();
