"""Tests applicatifs de base (XSS réfléchie, injection SQL révélée par une erreur) et faux positif cookie de Nikto.

Deux petits sites de test : l'un renvoie la recherche sans échappement et colle l'e-mail dans une requête SQL,
l'autre fait les choses correctement. Le module ne doit jamais envoyer le formulaire du panier ni suivre
le lien de déconnexion.
"""
import html
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from vulnscan import applicatif, constats, score
from vulnscan.cible import preparer_cible

ACCUEIL = b"""<html><body>
<a href="recherche.php">Recherche</a> <a href="connexion.php">Connexion</a>
<a href="deconnexion.php">Se deconnecter</a> <a href="recherche.php?q=switch">Switch</a>
<form method="post" action="panier.php"><input type="text" name="code"><button>Appliquer</button></form>
</body></html>"""
CONNEXION = b"""<html><body><form method="post" action="connexion.php">
<input type="hidden" name="csrf" value="jeton42">
<input type="text" name="email"><input type="password" name="mot_de_passe"><button>Se connecter</button>
</form></body></html>"""
RECHERCHE = b"""<html><body><form method="get" action="recherche.php">
<input type="search" name="q"><button>Rechercher</button></form></body></html>"""


def _site(vulnerable: bool, appels: list):
    class Site(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _repondre(self, corps: bytes, code=200):
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def do_GET(self):
            u = urlparse(self.path)
            appels.append(("GET", u.path))
            if u.path in ("/", "/index.php"):
                return self._repondre(ACCUEIL)
            if u.path == "/connexion.php":
                return self._repondre(CONNEXION)
            if u.path == "/recherche.php":
                q = parse_qs(u.query).get("q", [""])[0]
                affiche = q if vulnerable else html.escape(q)
                return self._repondre(RECHERCHE + f"<p>Résultats pour : {affiche}</p>".encode())
            return self._repondre(b"introuvable", 404)

        def do_POST(self):
            u = urlparse(self.path)
            taille = int(self.headers.get("Content-Length", 0))
            donnees = parse_qs(self.rfile.read(taille).decode())
            appels.append(("POST", u.path))
            if u.path == "/connexion.php":
                email = donnees.get("email", [""])[0]
                if vulnerable and email.count("'") % 2:
                    message = "Erreur SQL : SQLSTATE[42000]: Syntax error or access violation: 1064"
                else:
                    message = "Adresse e-mail ou mot de passe incorrect."
                return self._repondre(CONNEXION + f"<p>{message}</p>".encode())
            return self._repondre(b"commande enregistree")
    return Site


@pytest.fixture
def lancer_site():
    serveurs = []

    def lancer(vulnerable):
        appels = []
        serveur = ThreadingHTTPServer(("127.0.0.1", 0), _site(vulnerable, appels))
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        serveurs.append(serveur)
        cible = preparer_cible(f"http://127.0.0.1:{serveur.server_address[1]}/", liste_blanche=["127.0.0.1"])
        return cible, appels
    yield lancer
    for s in serveurs:
        s.shutdown()


def test_site_vulnerable_xss_et_injection_sql(lancer_site):
    cible, appels = lancer_site(True)
    r = applicatif.tester(cible)
    assert [e["lieu"] for e in r["xss"]] == ["GET recherche.php, paramètre « q »"]
    assert "<rpst" in r["xss"][0]["extrait"]
    assert len(r["sqli"]) == 1 and r["sqli"][0]["confirme"]
    assert r["sqli"][0]["lieu"] == "POST connexion.php, paramètre « email »"
    assert "SQLSTATE" in r["sqli"][0]["erreur"]
    # Prudence : ni le panier (POST qui modifie des données), ni la déconnexion.
    assert ("POST", "/panier.php") not in appels
    assert ("GET", "/deconnexion.php") not in appels


def test_site_corrige_aucune_alerte(lancer_site):
    cible, _ = lancer_site(False)
    r = applicatif.tester(cible)
    assert r["xss"] == [] and r["sqli"] == []
    assert r["points"] == 2                      # q (formulaire et lien : un seul point) + email


def test_constats_et_score():
    app = {"xss": [{"lieu": "GET recherche.php, paramètre « q »", "extrait": "Résultats pour : <rpst1>"}],
           "sqli": [{"lieu": "POST connexion.php, paramètre « email »", "erreur": "SQLSTATE[42000]", "confirme": True}],
           "points": 2, "requetes": 12, "journal": [], "ignore": ""}
    liste = constats.constats_applicatif(app)
    assert [(c.gravite, c.categorie, c.verification) for c in liste] == [
        ("Élevée", "Injection", constats.CONFIRME), ("Moyenne", "Injection", constats.CONFIRME)]
    assert score.calculer(liste)["score"] == 100 - 20 - 8


def test_injection_sans_confirmation_reste_a_verifier():
    app = {"xss": [], "sqli": [{"lieu": "GET a.php, paramètre « id »", "erreur": "SQLSTATE", "confirme": False}],
           "points": 1, "requetes": 4, "journal": [], "ignore": ""}
    (c,) = constats.constats_applicatif(app)
    assert c.verification == constats.NON_VERIFIABLE


def test_cookie_protege_signale_par_nikto_est_un_faux_positif():
    """Cas de la boutique corrigée : Nikto dit « sans HttpOnly », mais le cookie reçu porte HttpOnly."""
    cible = preparer_cible("http://127.0.0.1:8082/", liste_blanche=["127.0.0.1"], verifier_acces=False)
    obs = {"cookies": [{"nom": "PHPSESSID", "httponly": True, "secure": False, "samesite": True,
                        "brut": "PHPSESSID=abc; path=/; HttpOnly; SameSite=Lax"}],
           "entetes_absents": [], "protection_cadres": True}
    nikto = {"constats": ["Cookie PHPSESSID created without the httponly flag"]}
    (c,) = [x for x in constats.constats_web(cible, nikto, obs, []) if "PHPSESSID" in x.titre]
    assert c.verification == constats.FAUX_POSITIF and c.gravite == "Info"
    assert score.calculer([c])["score"] == 100


@pytest.mark.skipif(shutil.which("php") is None, reason="php absent")
def test_boutique_corrigee_sans_xss_ni_injection(tmp_path):
    """La vraie boutique de main (version corrigée) : aucun des deux tests ne doit la signaler."""
    from test_boutique import APP, _port_libre
    import requests
    import time
    site = tmp_path / "site"
    shutil.copytree(APP, site)
    (site / "config.php").write_text(f"<?php return ['dsn' => 'sqlite:{tmp_path / 'b.sqlite'}'];\n", encoding="utf-8")
    subprocess.run(["php", str(site / "inc" / "installer.php")], check=True, capture_output=True)
    port = _port_libre()
    serveur = subprocess.Popen(["php", "-S", f"127.0.0.1:{port}", "-t", str(site)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                requests.get(f"http://127.0.0.1:{port}/index.php", timeout=1)
                break
            except requests.ConnectionError:
                time.sleep(0.1)
        r = applicatif.tester(preparer_cible(f"http://127.0.0.1:{port}/index.php", liste_blanche=["127.0.0.1"]))
        assert r["points"] >= 2
        assert r["xss"] == [] and r["sqli"] == []
    finally:
        serveur.terminate()
        serveur.wait(timeout=5)
