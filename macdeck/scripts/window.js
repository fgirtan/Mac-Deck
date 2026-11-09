// JXA: mută/redimensionează fereastra din față. argv[0] = left|right|top|bottom|full|center|next
ObjC.import('AppKit');
function run(argv) {
  var op = argv[0];
  var se = Application('System Events');
  var proc = se.processes.whose({ frontmost: true })[0];
  var win = proc.windows[0];
  if (!win) return 'no-window';
  var screens = $.NSScreen.screens, n = screens.count;
  var mainH = screens.objectAtIndex(0).frame.size.height;
  var pos = win.position(), size = win.size();
  // ecranul pe care se află centrul ferestrei (coordonate AppKit: originea jos-stânga)
  var cx = pos[0] + size[0] / 2, cy = mainH - (pos[1] + size[1] / 2), idx = 0;
  for (var i = 0; i < n; i++) {
    var f = screens.objectAtIndex(i).frame;
    if (cx >= f.origin.x && cx < f.origin.x + f.size.width && cy >= f.origin.y && cy < f.origin.y + f.size.height) { idx = i; break; }
  }
  if (op === 'next') idx = (idx + 1) % n;
  var v = screens.objectAtIndex(idx).visibleFrame;
  var x = v.origin.x, y = mainH - (v.origin.y + v.size.height), w = v.size.width, h = v.size.height;
  var r;
  switch (op) {
    case 'left': r = [x, y, w / 2, h]; break;
    case 'right': r = [x + w / 2, y, w / 2, h]; break;
    case 'top': r = [x, y, w, h / 2]; break;
    case 'bottom': r = [x, y + h / 2, w, h / 2]; break;
    case 'full': r = [x, y, w, h]; break;
    case 'center': r = [x + w * 0.15, y + h * 0.1, w * 0.7, h * 0.8]; break;
    case 'next': r = [x + (w - Math.min(size[0], w)) / 2, y + (h - Math.min(size[1], h)) / 2, Math.min(size[0], w), Math.min(size[1], h)]; break;
    default: return 'unknown';
  }
  win.position = [Math.round(r[0]), Math.round(r[1])];
  win.size = [Math.round(r[2]), Math.round(r[3])];
  return 'ok';
}
