"""Pornire: python3 -m macdeck   (din folderul repository-ului)

  python3 -m macdeck                    pornește serverul (în Terminal)
  python3 -m macdeck --autostart        pornire automată la login, în fundal
  python3 -m macdeck --no-autostart     oprește pornirea automată
  python3 -m macdeck --restart          repornește serverul din fundal
  python3 -m macdeck --status           arată dacă serverul rulează
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
    a = p.parse_args()
    if a.autostart or a.no_autostart or a.restart or a.status:
        from . import autostart
        cmd = "install" if a.autostart else "uninstall" if a.no_autostart else "restart" if a.restart else "status"
        sys.exit(autostart.main(cmd))
    from .server import serve
    serve(a.http_port, a.https_port)


if __name__ == "__main__":
    main()
