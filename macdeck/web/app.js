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
    return '<img src="/icons/' + encodeURIComponent(b.id) + '.png" alt="" data-letter="' + (b.label || '?').charAt(0) + '">';
  }

  function render() {
    var cols = cfg.ui.columns || 5, rows = cfg.ui.rows || 3, per = cols * rows;
    var sets = $('sets');
    sets.innerHTML = '';
    keyEls = {};
    cfg.sets.forEach(function (s) {
      var el = document.createElement('div');
      el.className = 'set';
      el.style.gridTemplateColumns = 'repeat(' + cols + ', 1fr)';
      el.style.gridTemplateRows = 'repeat(' + rows + ', 1fr)';
      for (var i = 0; i < per; i++) {
        var b = s.buttons[i];
        var k = document.createElement('button');
        k.className = 'key' + (b ? '' : ' empty');
        if (b) {
          var soon = b.action && (b.action.type === 'soon' || b.action.type === 'claude');
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
    $('dots').innerHTML = cfg.sets.map(function () { return '<i></i>'; }).join('');
    ui.set = Math.min(ui.set || 0, cfg.sets.length - 1);
    requestAnimationFrame(function () { sets.scrollLeft = ui.set * sets.clientWidth; updateDots(); });
    if (ui.page && !pageEls[ui.page]) {
      var pb = findButtonByPage(ui.page);
      if (pb) openPage(pb, true);
    }
  }

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function findButtonByPage(p) {
    for (var i = 0; i < cfg.sets.length; i++)
      for (var j = 0; j < cfg.sets[i].buttons.length; j++)
        if (cfg.sets[i].buttons[j].page === p) return cfg.sets[i].buttons[j];
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
  function openPage(b, instant) {
    var id = b.page, p = pageEls[id];
    if (!p) {
      var meta = (cfg.pages && cfg.pages[id]) || { title: b.label };
      p = document.createElement('section');
      p.className = 'page';
      p.innerHTML = '<header><button class="backb">' + glyph('back') + 'Înapoi</button>' +
        '<div class="ic">' + iconHTML(b).replace('<img ', '<img style="width:28px;height:28px" ') + '</div><h2>' + esc(meta.title) + '</h2></header>' +
        '<div class="body">' + glyph('wrench', 'g') +
        '<div>Controalele pentru <b>' + esc(meta.title) + '</b> vin în etapa ' + esc(meta.phase || '?') + '.</div>' +
        '<small>Aplicația a fost deschisă pe Mac.</small></div>';
      p.querySelector('.body .g').style.cssText = 'width:36px;height:36px;color:#1e7a37';
      var himg = p.querySelector('header img');
      if (himg) himg.onerror = function () { himg.remove(); };
      bindPress(p.querySelector('.backb'), function () { feedback(); closePage(id); }, null);
      edgeSwipe(p, function () { closePage(id); });
      $('pages').appendChild(p);
      pageEls[id] = p;
    }
    if (instant) p.style.transition = 'none';
    requestAnimationFrame(function () { p.classList.add('open'); if (instant) requestAnimationFrame(function () { p.style.transition = ''; }); });
    ui.page = id; store.set('macdeck.ui', ui);
  }
  function closePage(id) {
    var p = pageEls[id];
    if (p) p.classList.remove('open');   // elementul rămâne: la revenire, starea e aceeași
    ui.page = null; store.set('macdeck.ui', ui);
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
    ['volume', 'muted', 'brightness', 'toggles'].forEach(function (k) {
      if (k in s && !dragging[k]) state[k] = s[k];
    });
    paintSliders();
    var t = state.toggles || {};
    if (cfg) cfg.sets.forEach(function (set) {
      set.buttons.forEach(function (b) {
        if (b.state && keyEls[b.id]) keyEls[b.id].classList.toggle('on', !!t[b.state]);
      });
    });
    $('sleep-info').textContent = state.volume == null ? '' : 'Volum ' + state.volume + '%';
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
    if (!e.target.closest('#sets')) e.preventDefault();
  }, { passive: false });
  document.addEventListener('gesturestart', function (e) { e.preventDefault(); });

  $('rotate').querySelector('div').innerHTML = glyph('rotate');
  boot();
})();
