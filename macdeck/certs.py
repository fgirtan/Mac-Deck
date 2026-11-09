"""Certificat HTTPS local: o autoritate proprie (CA), instalată o singură dată pe iPhone,
și un certificat de server semnat de ea pentru numele .local și IP-ul Mac-ului.
Folosește utilitarul `openssl` inclus în macOS."""
import json
import os
import subprocess

from .config import HOME

CERT_DIR = os.path.join(HOME, "certs")
CA_KEY = os.path.join(CERT_DIR, "ca.key")
CA_CRT = os.path.join(CERT_DIR, "ca.crt")
SRV_KEY = os.path.join(CERT_DIR, "server.key")
SRV_CRT = os.path.join(CERT_DIR, "server.crt")
SRV_META = os.path.join(CERT_DIR, "server.json")

CA_CNF = """[req]
distinguished_name = dn
prompt = no
[dn]
CN = Mac Deck Local CA
O = Mac Deck
[v3_ca]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
"""


def _openssl(*args):
    r = subprocess.run(["openssl"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("openssl: " + (r.stderr.strip() or "eroare"))


def ensure(hostnames, ips):
    """Creează (sau reface, dacă s-a schimbat IP-ul/numele) certificatele. Întoarce (crt, key)."""
    os.makedirs(CERT_DIR, mode=0o700, exist_ok=True)
    if not (os.path.exists(CA_KEY) and os.path.exists(CA_CRT)):
        cnf = os.path.join(CERT_DIR, "ca.cnf")
        with open(cnf, "w") as f:
            f.write(CA_CNF)
        _openssl("req", "-x509", "-new", "-nodes", "-newkey", "rsa:2048", "-sha256",
                 "-keyout", CA_KEY, "-out", CA_CRT, "-days", "3650",
                 "-config", cnf, "-extensions", "v3_ca")
        os.chmod(CA_KEY, 0o600)
        for p in (SRV_CRT, SRV_META):
            if os.path.exists(p):
                os.remove(p)

    names = sorted(set(hostnames) | {"localhost"})
    addrs = sorted(set(ips) | {"127.0.0.1"})
    wanted = {"dns": names, "ip": addrs}
    try:
        with open(SRV_META) as f:
            current = json.load(f)
    except (OSError, ValueError):
        current = None
    if current == wanted and os.path.exists(SRV_CRT) and os.path.exists(SRV_KEY):
        return SRV_CRT, SRV_KEY

    csr = os.path.join(CERT_DIR, "server.csr")
    ext = os.path.join(CERT_DIR, "server.ext")
    san = ",".join(["DNS:" + n for n in names] + ["IP:" + a for a in addrs])
    with open(ext, "w") as f:
        f.write("basicConstraints = CA:FALSE\n"
                "keyUsage = critical, digitalSignature, keyEncipherment\n"
                "extendedKeyUsage = serverAuth\n"
                "subjectAltName = %s\n" % san)
    _openssl("req", "-new", "-nodes", "-newkey", "rsa:2048", "-keyout", SRV_KEY, "-out", csr,
             "-subj", "/CN=%s/O=Mac Deck" % names[0])
    # iOS acceptă certificate de server valabile cel mult 825 de zile
    _openssl("x509", "-req", "-in", csr, "-CA", CA_CRT, "-CAkey", CA_KEY, "-CAcreateserial",
             "-out", SRV_CRT, "-days", "800", "-sha256", "-extfile", ext)
    os.chmod(SRV_KEY, 0o600)
    with open(SRV_META, "w") as f:
        json.dump(wanted, f)
    return SRV_CRT, SRV_KEY
