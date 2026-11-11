"""Pornire: python3 -m macdeck   (din folderul repository-ului)

  python3 -m macdeck                    pornește serverul (în Terminal)
  python3 -m macdeck --autostart        pornire automată la login, în fundal
  python3 -m macdeck --no-autostart     oprește pornirea automată
  python3 -m macdeck --restart          repornește serverul din fundal
  python3 -m macdeck --status           arată dacă serverul rulează
  python3 -m macdeck --no-code          fără cod de asociere în rețeaua locală
  python3 -m macdeck --require-code     cere din nou codul de asociere
  python3 -m macdeck --install-app      creează aplicația „Mac Deck” în ~/Applications
"""
import argparse
import sys


def main():
    p = argparse.ArgumentParser(prog="macdeck", description="iPhone ca deck de control pentru Mac")
    p.add_argument("--http-port", type=int, default=8765)
    p.add_argument("--https-port", type=int, default=8766)
    p.add_argument("--autostart", action="store_true", help="pornire automată la login (în fundal)")
    p.add_argument("--no-autostart", action="store_true", help="oprește pornirea automată")
    p.add_argument("--restart", action="store_true", help="repornește serverul din fundal")
    p.add_argument("--status", action="store_true", help="starea serverului din fundal")
    p.add_argument("--no-code", action="store_true", help="fără cod de asociere în rețeaua locală")
    p.add_argument("--require-code", action="store_true", help="cere din nou codul de asociere")
    p.add_argument("--install-app", action="store_true", help="creează aplicația Mac Deck în ~/Applications")
    a = p.parse_args()
    if a.install_app:
        from . import macapp
        path = macapp.make_app()
        print("\n  ✓ Aplicația a fost creată: %s" % path)
        print("    O găsești în Launchpad și cu ⌘ Space → „Mac Deck”. Poți s-o tragi în Dock.\n")
        return
    if a.no_code or a.require_code:
        from .config import Config
        c = Config()
        data = c.get()
        sec = data.setdefault("security", {})
        if a.no_code:
            sec["no_code"] = True
        else:
            sec.pop("no_code", None)
        c.save(data)  # serverul pornit preia modificarea singur, în ~1 secundă
        print("\n  ✓ " + ("Codul de asociere nu mai e necesar în rețeaua locală." if a.no_code
                         else "Codul de asociere e din nou necesar.") + "\n")
        return
    if a.autostart or a.no_autostart or a.restart or a.status:
        from . import autostart
        cmd = "install" if a.autostart else "uninstall" if a.no_autostart else "restart" if a.restart else "status"
        sys.exit(autostart.main(cmd))
    from .server import serve
    serve(a.http_port, a.https_port)


if __name__ == "__main__":
    main()
