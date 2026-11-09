"""Pornire: python3 -m macdeck   (din folderul repository-ului)"""
import argparse

from .server import serve


def main():
    p = argparse.ArgumentParser(prog="macdeck", description="iPhone ca deck de control pentru Mac")
    p.add_argument("--http-port", type=int, default=8765)
    p.add_argument("--https-port", type=int, default=8766)
    a = p.parse_args()
    serve(a.http_port, a.https_port)


if __name__ == "__main__":
    main()
