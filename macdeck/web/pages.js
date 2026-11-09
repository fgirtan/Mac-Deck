// Paginile dedicate. Fiecare funcție primește ctx și întoarce { el, update(state), poll (ms) }.
(function () {
  'use strict';

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') el.textContent = attrs[k];
      else if (k === 'html') el.innerHTML = attrs[k];
      else if (attrs[k] !== undefined && attrs[k] !== null && attrs[k] !== false) el.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  }
  function pbtn(ctx, cls, html, fn, longFn) {
    var b = h('button', { class: 'pb ' + (cls || ''), html: html });
    ctx.press(b, function () { ctx.feedback(); fn(); }, longFn || null);
    return b;
  }
  function run(ctx, body, after) {
    return ctx.call(body).then(function (r) {
      if (!r.ok) ctx.toast(r.msg || 'Eroare', true);
      else if (r.msg && r.msg !== 'OK') ctx.toast(r.msg);
      if (after) after(r);
      ctx.refresh();
      return r;
    });
  }
  function fmtTime(sec) { sec = Math.max(0, Math.round(sec)); return Math.floor(sec / 60) + ':' + ('0' + sec % 60).slice(-2); }
  function errorBox(ctx, msg) { return h('div', { class: 'perr', text: msg }); }

  // ---------------------------------------------------------------- grafice
  function chart(canvas, series, opts) {
    opts = opts || {};
    var dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, hgt = canvas.clientHeight;
    if (!w || !hgt) return;
    canvas.width = w * dpr; canvas.height = hgt * dpr;
    var c = canvas.getContext('2d'); c.scale(dpr, dpr); c.clearRect(0, 0, w, hgt);
    var max = opts.max || 1;
    if (!opts.max) series.forEach(function (s) { s.data.forEach(function (v) { if (v > max) max = v; }); });
    c.strokeStyle = '#13201a'; c.lineWidth = 1;
    for (var g = 1; g < 4; g++) { c.beginPath(); c.moveTo(0, hgt * g / 4); c.lineTo(w, hgt * g / 4); c.stroke(); }
    series.forEach(function (s) {
      var d = s.data, n = 60; if (!d.length) return;
      c.beginPath();
      d.forEach(function (v, i) {
        var x = w - (d.length - 1 - i) * (w / (n - 1)), y = hgt - (v / max) * (hgt - 2) - 1;
        if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
      });
      c.strokeStyle = s.color; c.lineWidth = 1.6; c.stroke();
      if (s.fill) {
        c.lineTo(w, hgt); c.lineTo(w - (d.length - 1) * (w / (n - 1)), hgt); c.closePath();
        var gr = c.createLinearGradient(0, 0, 0, hgt); gr.addColorStop(0, s.fill); gr.addColorStop(1, 'rgba(48,209,88,0)');
        c.fillStyle = gr; c.fill();
      }
    });
  }
  function levelColor(v, warn, crit) { return v >= crit ? '#ff453a' : v >= warn ? '#ffd60a' : '#30d158'; }
  function kb(v) { return v == null ? '–' : v >= 1024 ? (v / 1024).toFixed(1) + ' MB/s' : Math.round(v) + ' KB/s'; }

  var P = {};

  // ---------------------------------------------------------------- Spotify
  P.spotify = function (ctx) {
    var art = h('div', { class: 'sp-art' });
    var title = h('div', { class: 'sp-title', text: '–' }), artist = h('div', { class: 'sp-artist', text: '' });
    var play = pbtn(ctx, 'big', glyph('play'), function () { run(ctx, { cmd: 'playpause' }); });
    var q = h('input', { class: 'pin', type: 'search', placeholder: 'Caută în Spotify…', enterkeyhint: 'search' });
    function search() { if (q.value.trim()) { run(ctx, { cmd: 'search', q: q.value }); q.blur(); } }
    q.addEventListener('keydown', function (e) { if (e.key === 'Enter') search(); });
    var err = h('div', { class: 'perr hidden' });
    var el = h('div', { class: 'pg sp' }, [
      h('div', { class: 'sp-left' }, [art, title, artist]),
      h('div', { class: 'sp-right' }, [
        h('div', { class: 'row c' }, [
          pbtn(ctx, '', glyph('prev'), function () { run(ctx, { cmd: 'prev' }); }), play,
          pbtn(ctx, '', glyph('next'), function () { run(ctx, { cmd: 'next' }); }),
        ]),
        h('div', { class: 'row' }, [q, pbtn(ctx, 'acc', glyph('search'), search)]),
        err,
      ]),
    ]);
    return {
      el: el, poll: 1500,
      update: function (s) {
        err.classList.toggle('hidden', !s.error); err.textContent = s.error || '';
        var t = s.track;
        if (!t) { title.textContent = 'Spotify nu e deschis'; artist.textContent = 'Apasă butonul Spotify ca să-l deschizi în Chrome'; return; }
        title.textContent = t.title || '–'; artist.textContent = t.artist || '';
        art.style.backgroundImage = t.art ? 'url("' + t.art + '")' : '';
        play.innerHTML = glyph(t.playing ? 'pause' : 'play');
        play.classList.toggle('on', !!t.playing);
      },
    };
  };

  // ---------------------------------------------------------------- Google Meet
  P.meet = function (ctx) {
    var defs = [
      ['mic', 'mic', 'Microfon'], ['cam', 'camera', 'Cameră'], ['hand', 'hand', 'Ridică mâna'], ['captions', 'cc', 'Subtitrări'],
      ['chat', 'chat', 'Chat'], ['people', 'people', 'Participanți'], ['present', 'screen', 'Prezintă'], ['leave', 'phone-off', 'Ieși'],
    ];
    var btns = {};
    var status = h('div', { class: 'pnote', text: '' });
    var grid = h('div', { class: 'pgrid g4' });
    defs.forEach(function (d) {
      var b = pbtn(ctx, 'tile' + (d[0] === 'leave' ? ' danger' : ''), glyph(d[1]) + '<span>' + d[2] + '</span>', function () {
        if (d[0] === 'leave' && !confirm('Ieși din apel?')) return;
        run(ctx, { cmd: d[0] });
      });
      btns[d[0]] = b; grid.appendChild(b);
    });
    return {
      el: h('div', { class: 'pg' }, [grid, status]), poll: 1500,
      update: function (s) {
        var m = s.meet;
        status.textContent = !m ? 'Nu ești într-un apel. Pagina se deschide singură când intri într-un meeting.' : (m.title || '');
        if (!m) return;
        btns.mic.classList.toggle('off', m.mic_on === false);
        btns.mic.innerHTML = glyph(m.mic_on === false ? 'mic-off' : 'mic') + '<span>' + (m.mic_on === false ? 'Mic oprit' : 'Microfon') + '</span>';
        btns.cam.classList.toggle('off', m.cam_on === false);
        btns.cam.innerHTML = glyph('camera') + '<span>' + (m.cam_on === false ? 'Cameră oprită' : 'Cameră') + '</span>';
        btns.hand.classList.toggle('on', !!m.hand);
        btns.captions.classList.toggle('on', !!m.captions);
        btns.chat.classList.toggle('on', !!m.chat);
        btns.people.classList.toggle('on', !!m.people);
      },
    };
  };

  // ---------------------------------------------------------------- Activity Monitor
  P.activity = function (ctx) {
    function card(title) {
      var v = h('b', { text: '–' }), sub = h('small', { text: '' }), cv = h('canvas');
      var c = h('div', { class: 'am-card' }, [h('div', { class: 'am-h' }, [h('span', { text: title }), v]), cv, sub]);
      return { el: c, v: v, sub: sub, cv: cv };
    }
    var cpu = card('CPU'), mem = card('Memorie'), net = card('Rețea'), disk = card('Disc');
    var sys = h('div', { class: 'am-card am-sys' });
    var topMode = 'cpu';
    var topList = h('div', { class: 'am-top scroll' });
    var topHead = h('button', { class: 'am-h am-toggle' });
    ctx.press(topHead, function () { topMode = topMode === 'cpu' ? 'mem' : 'cpu'; ctx.feedback(); ctx.refresh(); }, null);
    var top = h('div', { class: 'am-card am-topc' }, [topHead, topList]);
    var el = h('div', { class: 'pg am' }, [cpu.el, mem.el, net.el, disk.el, sys, top]);
    return {
      el: el, poll: 1000,
      update: function (s) {
        var n = s.now || {}, hi = s.hist || {};
        cpu.v.textContent = n.cpu == null ? '–' : Math.round(n.cpu) + '%';
        cpu.v.style.color = levelColor(n.cpu || 0, 60, 85);
        cpu.sub.textContent = n.cpu_user == null ? '' : 'utilizator ' + Math.round(n.cpu_user) + '% · sistem ' + Math.round(n.cpu_sys) + '%';
        chart(cpu.cv, [{ data: hi.cpu || [], color: levelColor(n.cpu || 0, 60, 85), fill: 'rgba(48,209,88,.25)' }], { max: 100 });
        mem.v.textContent = n.mem == null ? '–' : Math.round(n.mem) + '%';
        var pc = { normal: '#30d158', 'atenție': '#ffd60a', critic: '#ff453a' }[n.pressure] || '#30d158';
        mem.v.style.color = pc;
        mem.sub.textContent = n.mem_used_gb == null ? '' : n.mem_used_gb + ' / ' + n.mem_total_gb + ' GB · presiune ' + (n.pressure || '') + (n.swap_gb ? ' · swap ' + n.swap_gb + ' GB' : '');
        chart(mem.cv, [{ data: hi.mem || [], color: pc, fill: 'rgba(48,209,88,.2)' }], { max: 100 });
        net.v.textContent = '↓ ' + kb(n.net_in);
        net.sub.textContent = '↑ ' + kb(n.net_out);
        chart(net.cv, [{ data: hi.net_in || [], color: '#30d158', fill: 'rgba(48,209,88,.18)' }, { data: hi.net_out || [], color: '#64d2ff' }]);
        disk.v.textContent = n.disk == null ? '–' : n.disk.toFixed(1) + ' MB/s';
        disk.sub.textContent = 'citire + scriere';
        chart(disk.cv, [{ data: hi.disk || [], color: '#30d158', fill: 'rgba(48,209,88,.18)' }]);
        var rows = [];
        if (n.battery != null) rows.push(['Baterie', n.battery + '%' + (n.on_ac ? ' ⚡' : '') + (n.battery_left ? ' · ' + n.battery_left : '')]);
        if (n.gpu != null) rows.push(['GPU', Math.round(n.gpu) + '%']);
        if (n.thermal) rows.push(['Termic', n.thermal === 'Nominal' ? 'normal' : n.thermal]);
        sys.innerHTML = '<div class="am-h"><span>Sistem</span></div>' + rows.map(function (r) {
          return '<div class="am-kv"><span>' + r[0] + '</span><b>' + ctx.esc(r[1]) + '</b></div>';
        }).join('') + (n.gpu_hint ? '<small class="am-hint">GPU / temperatură: vezi README (sudoers)</small>' : '');
        topHead.innerHTML = '<span>Top ' + (topMode === 'cpu' ? 'CPU' : 'memorie') + '</span><small>schimbă ⇄</small>';
        var list = (s.top || {})[topMode] || [];
        topList.innerHTML = '';
        list.forEach(function (p) {
          var r = h('button', { class: 'am-row' + (p.mine ? '' : ' sys') }, [
            h('span', { text: p.name }), h('b', { text: topMode === 'cpu' ? p.cpu.toFixed(1) + '%' : p.mem_mb + ' MB' }),
          ]);
          ctx.press(r, function () {
            if (!p.mine) return ctx.toast('Procesele de sistem nu pot fi închise', true);
            if (confirm('Închizi „' + p.name + '” (PID ' + p.pid + ')?')) run(ctx, { cmd: 'kill', pid: p.pid });
          }, null);
          topList.appendChild(r);
        });
      },
    };
  };

  // ---------------------------------------------------------------- Claude
  P.claude = function (ctx) {
    var tab = 'pinned';
    var tabs = h('div', { class: 'seg' });
    var list = h('div', { class: 'pgrid g2 scroll' });
    var last = null;
    function draw() {
      tabs.innerHTML = '';
      [['pinned', 'Pinned'], ['artifacts', 'Artefacte']].forEach(function (t) {
        tabs.appendChild(pbtn(ctx, t[0] === tab ? 'cur' : '', t[1], function () { tab = t[0]; draw(); }));
      });
      list.innerHTML = '';
      var items = (last && last[tab]) || [];
      if (!items.length) list.appendChild(h('div', { class: 'pnote', text: 'Lista e goală. Adaugă elemente din configurator → Pagini și liste → Claude.' }));
      items.forEach(function (it, i) {
        list.appendChild(pbtn(ctx, 'item', ctx.esc(it.name) + (it.prompt ? '<small>↳ ' + ctx.esc(it.prompt) + '</small>' : ''), function () {
          run(ctx, { list: tab, index: i });
        }, it.prompt ? function () { ctx.feedback(); run(ctx, { list: tab, index: i, with_prompt: false }); } : null));
      });
    }
    return {
      el: h('div', { class: 'pg' }, [tabs, list]), poll: 0,
      update: function (s) { if (JSON.stringify(s) !== JSON.stringify(last)) { last = s; draw(); } },
    };
  };

  // ---------------------------------------------------------------- Screaming Frog
  P.sfrog = function (ctx) {
    var st = null, dirty = false;
    var seg = h('div', { class: 'seg' });
    var url = h('input', { class: 'pin', type: 'url', placeholder: 'https://site.ro/', autocapitalize: 'off' });
    var lst = h('textarea', { class: 'pin', placeholder: 'Câte un URL pe rând', rows: '3' });
    var conf = h('select', { class: 'pin' });
    [url, lst, conf].forEach(function (x) { x.addEventListener('input', function () { dirty = true; }); x.addEventListener('change', save); x.addEventListener('blur', save); });
    function vals() { return { mode: st ? st.mode : 'spider', url: url.value, list: lst.value, config: conf.value }; }
    function save() { if (dirty) { dirty = false; ctx.call(Object.assign({ cmd: 'save' }, vals())); } }
    function cmd(c) { dirty = false; run(ctx, Object.assign({ cmd: c }, vals())); }
    var prog = h('div', { class: 'bar' }, [h('i')]);
    var log = h('div', { class: 'sf-log' });
    var cliBtn = pbtn(ctx, 'acc', glyph('play') + '<span>Crawl în fundal</span>', function () { cmd(st && st.cli.running ? 'cli_stop' : 'cli_start'); });
    var el = h('div', { class: 'pg sf' }, [
      h('div', { class: 'sf-l' }, [seg, url, lst, conf]),
      h('div', { class: 'sf-r' }, [
        h('div', { class: 'plabel', text: 'Fereastra Screaming Frog' }),
        h('div', { class: 'row' }, [
          pbtn(ctx, '', glyph('play') + '<span>Start</span>', function () { cmd('gui_start'); }),
          pbtn(ctx, '', glyph('pause') + '<span>Pauză</span>', function () { cmd('gui_pause'); }),
          pbtn(ctx, '', glyph('stop') + '<span>Stop</span>', function () { cmd('gui_stop'); }),
          pbtn(ctx, '', glyph('layout') + '<span>Mod</span>', function () { cmd('gui_mode'); }),
        ]),
        h('div', { class: 'plabel', text: 'Crawl în fundal (fără fereastră, export CSV)' }),
        h('div', { class: 'row' }, [cliBtn, pbtn(ctx, '', glyph('folder') + '<span>Rezultate</span>', function () { cmd('open_out'); })]),
        prog, log,
      ]),
    ]);
    return {
      el: el, poll: 1500,
      update: function (s) {
        st = s;
        seg.innerHTML = '';
        [['spider', 'Spider (un site)'], ['list', 'List (URL-uri)']].forEach(function (m) {
          seg.appendChild(pbtn(ctx, m[0] === s.mode ? 'cur' : '', m[1], function () { st.mode = m[0]; dirty = true; save(); ctx.refresh(); }));
        });
        if (document.activeElement !== url && !dirty) url.value = s.url || '';
        if (document.activeElement !== lst && !dirty) lst.value = s.list || '';
        url.classList.toggle('hidden', s.mode !== 'spider');
        lst.classList.toggle('hidden', s.mode !== 'list');
        var opts = '<option value="">Configurația implicită</option>' + (s.configs || []).map(function (c) {
          return '<option value="' + ctx.esc(c.path) + '"' + (c.path === s.config ? ' selected' : '') + '>' + ctx.esc(c.name) + '</option>';
        }).join('');
        if (conf.innerHTML !== opts && document.activeElement !== conf) conf.innerHTML = opts;
        var c = s.cli || {};
        cliBtn.innerHTML = glyph(c.running ? 'stop' : 'play') + '<span>' + (c.running ? 'Oprește crawl-ul' : 'Crawl în fundal') + '</span>';
        cliBtn.classList.toggle('on', !!c.running);
        prog.firstChild.style.width = (c.progress || 0) + '%';
        prog.classList.toggle('hidden', !c.running && c.progress == null);
        log.textContent = c.running ? (c.log || []).slice(-2).join('\n') :
          (c.exit != null ? 'Ultimul crawl s-a încheiat' + (c.exit ? ' (cod ' + c.exit + ')' : '') + '. ' : '') + (s.cli_available ? '' : 'Linia de comandă Screaming Frog nu a fost găsită.');
      },
    };
  };

  // ---------------------------------------------------------------- MeetGeek
  P.meetgeek = function (ctx) {
    var rec = pbtn(ctx, 'rec', '<i></i>', function () { run(ctx, { cmd: 'toggle' }); });
    var label = h('div', { class: 'rec-l', text: '' });
    return {
      el: h('div', { class: 'pg center' }, [rec, label]), poll: 4000,
      update: function (s) {
        rec.classList.toggle('on', !!s.recording);
        label.textContent = !s.running ? 'MeetGeek nu rulează. Apasă ca să încerci oricum.' : s.recording ? 'Înregistrează · apasă pentru Stop' : 'Apasă pentru a porni înregistrarea';
      },
    };
  };

  // ---------------------------------------------------------------- Prompt vocal
  P.voice = function (ctx) {
    var ta = h('textarea', { class: 'pin voice-ta', placeholder: 'Atinge aici, apoi 🎤 de pe tastatură ca să dictezi…' });
    var tpl = 0, chips = h('div', { class: 'chips' });
    var last = null;
    function drawChips() {
      chips.innerHTML = '';
      (last || []).forEach(function (t, i) { chips.appendChild(pbtn(ctx, i === tpl ? 'cur' : '', ctx.esc(t.label), function () { tpl = i; drawChips(); })); });
    }
    var send = pbtn(ctx, 'acc', glyph('send') + '<span>Trimite în Claude</span>', function () {
      run(ctx, { cmd: 'send', text: ta.value, template: tpl }, function (r) { if (r.ok) ta.value = ''; });
    });
    return {
      el: h('div', { class: 'pg voice' }, [ta, h('div', { class: 'row' }, [chips, send])]), poll: 0,
      update: function (s) { if (JSON.stringify(s.templates) !== JSON.stringify(last)) { last = s.templates; drawChips(); } },
    };
  };

  // ---------------------------------------------------------------- Snippets
  P.snippets = function (ctx) {
    var grid = h('div', { class: 'pgrid g3 scroll' }), last = null;
    return {
      el: h('div', { class: 'pg' }, [h('div', { class: 'pnote', text: 'Textul se lipește în aplicația din față de pe Mac.' }), grid]), poll: 0,
      update: function (s) {
        if (JSON.stringify(s.items) === JSON.stringify(last)) return;
        last = s.items; grid.innerHTML = '';
        (s.items || []).forEach(function (it, i) {
          grid.appendChild(pbtn(ctx, 'item', ctx.esc(it.label) + '<small>' + ctx.esc((it.text || '').slice(0, 70)) + '</small>', function () { run(ctx, { cmd: 'paste', index: i }); }));
        });
      },
    };
  };

  // ---------------------------------------------------------------- Pomodoro
  P.timer = function (ctx) {
    var big = h('div', { class: 'tm-big', text: '25:00' }), mode = h('div', { class: 'tm-mode' });
    var ring = h('div', { class: 'bar wide' }, [h('i')]);
    var go = pbtn(ctx, 'acc', glyph('play') + '<span>Start</span>', function () { run(ctx, { cmd: 'toggle' }); });
    return {
      el: h('div', { class: 'pg center' }, [mode, big, ring, h('div', { class: 'row c' }, [
        go, pbtn(ctx, '', glyph('reset') + '<span>Reset</span>', function () { run(ctx, { cmd: 'reset' }); }),
        pbtn(ctx, '', glyph('next') + '<span>Sari</span>', function () { run(ctx, { cmd: 'skip' }); }),
      ])]), poll: 1000,
      update: function (s) {
        var t = s.timer || {};
        big.textContent = fmtTime(t.left || 0);
        mode.textContent = (t.mode === 'break' ? '☕ Pauză' : '🎯 Lucru') + ' · runda ' + (t.round || 1);
        ring.firstChild.style.width = (t.full ? 100 * (1 - t.left / t.full) : 0) + '%';
        go.innerHTML = glyph(t.running ? 'pause' : 'play') + '<span>' + (t.running ? 'Pauză' : 'Start') + '</span>';
        big.classList.toggle('run', !!t.running);
      },
    };
  };

  // ---------------------------------------------------------------- Analizează pagina
  P.analyze = function (ctx) {
    var url = h('div', { class: 'pnote url' }), grid = h('div', { class: 'pgrid g3' }), cur = null, last = null;
    return {
      el: h('div', { class: 'pg' }, [h('div', { class: 'row' }, [url, pbtn(ctx, 'small', glyph('reset'), function () { ctx.refresh(); })]), grid]), poll: 0,
      update: function (s) {
        cur = s.url;
        url.textContent = s.url ? s.url : 'Nu găsesc un tab activ în Chrome.';
        if (JSON.stringify(s.tools) === JSON.stringify(last)) return;
        last = s.tools; grid.innerHTML = '';
        (s.tools || []).forEach(function (t, i) {
          grid.appendChild(pbtn(ctx, 'item', ctx.esc(t.label), function () { run(ctx, { cmd: 'open', index: i, url: cur }); }));
        });
      },
    };
  };

  // ---------------------------------------------------------------- Ieșire audio
  P.audio = function (ctx) {
    var grid = h('div', { class: 'pgrid g2 scroll' });
    return {
      el: h('div', { class: 'pg' }, [grid]), poll: 0,
      update: function (s) {
        grid.innerHTML = '';
        if (!s.available) { grid.appendChild(errorBox(ctx, s.hint || 'Indisponibil')); return; }
        (s.devices || []).forEach(function (d) {
          grid.appendChild(pbtn(ctx, 'item' + (d === s.current ? ' cur' : ''), glyph(/airpod|head|beats|bose|sony/i.test(d) ? 'headphones' : 'volume') + '<span>' + ctx.esc(d) + '</span>', function () { run(ctx, { cmd: 'set', name: d }); }));
        });
      },
    };
  };

  // ---------------------------------------------------------------- Ferestre
  P.windows = function (ctx) {
    var ops = [['left', 'win-left', 'Stânga'], ['right', 'win-right', 'Dreapta'], ['full', 'win-full', 'Tot ecranul'], ['center', 'win-center', 'Centru'],
      ['top', 'win-top', 'Sus'], ['bottom', 'win-bottom', 'Jos'], ['next', 'win-next', 'Alt monitor']];
    var grid = h('div', { class: 'pgrid g4' });
    ops.forEach(function (o) { grid.appendChild(pbtn(ctx, 'tile', glyph(o[1]) + '<span>' + o[2] + '</span>', function () { run(ctx, { cmd: o[0] }); })); });
    return { el: h('div', { class: 'pg' }, [grid, h('div', { class: 'pnote', text: 'Se aplică ferestrei din față de pe Mac.' })]), poll: 0, update: function () {} };
  };

  window.DeckPages = P;
})();
