"""Tests applicatifs de base : ce que Nmap, Nikto et SSLScan ne testent pas.

Deux failles parmi les plus courantes (OWASP A03, injection) sont cherchées dans les paramètres du site :
  - XSS réfléchie : un marqueur inoffensif (« <rpst…> ») est-il renvoyé tel quel dans la page ?
  - injection SQL révélée par une erreur : une apostrophe provoque-t-elle un message d'erreur de la base,
    alors que la même valeur sans apostrophe, puis avec deux apostrophes (équilibrées), n'en provoque pas ?

Règles de prudence :
  - même hôte, sous l'adresse analysée, nombre de pages et de requêtes borné ;
  - valeurs envoyées inoffensives : un mot, un marqueur texte, une apostrophe ; aucune charge qui lit ou
    modifie des données ;
  - seuls les formulaires GET (recherche…) et les formulaires de connexion (avec un champ mot de passe) sont
    envoyés ; les autres formulaires POST (panier, commande, compte) peuvent modifier des données et ne le sont
    jamais ; les liens de déconnexion ou de suppression ne sont pas suivis.

Ce ne sont que des tests de base : une injection « aveugle » (sans message d'erreur), une XSS stockée ou un défaut
de contrôle d'accès ne sont pas détectés.
"""
import html
import re
import uuid
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlparse

import requests

from . import config

ERREURS_SQL = re.compile(
    r"(SQLSTATE\[|You have an error in your SQL syntax|MariaDB server version for the right syntax|"
    r"Warning: mysqli?_|PDOException|SQLite3?::|near \"[^\"]{0,40}\": syntax error|unrecognized token|"
    r"unterminated quoted string|ORA-\d{5}|pg_query\(\)|PG::SyntaxError|Unclosed quotation mark|"
    r"Microsoft OLE DB Provider|ODBC SQL Server Driver)", re.I)
# Liens jamais suivis : ils peuvent déconnecter, supprimer ou vider quelque chose.
LIENS_EVITES = re.compile(r"(deconnexion|d%C3%A9connexion|logout|logoff|signout|supprimer|delete|remove|vider|annuler)",
                          re.I)
PAGES = re.compile(r"(/|\.(php|html?|aspx?|jsp))$", re.I)
CHAMPS_TEXTE = {"text", "search", "email", "url", "tel", "textarea"}
_LIENS = re.compile(r"""href\s*=\s*["']([^"'#]+)""", re.I)
_BALISES = re.compile(r"<[^>]+>")


class _Formulaires(HTMLParser):
    """Formulaires d'une page : action, méthode et champs (nom, type, valeur par défaut)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.formulaires, self._f, self._select = [], None, None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._f = {"action": a.get("action", ""), "methode": (a.get("method") or "get").lower(), "champs": []}
        elif self._f is not None and tag in ("input", "textarea") and a.get("name"):
            genre = "textarea" if tag == "textarea" else (a.get("type") or "text").lower()
            self._f["champs"].append({"nom": a["name"], "type": genre, "valeur": a.get("value", "")})
        elif self._f is not None and tag == "select" and a.get("name"):
            self._select = {"nom": a["name"], "type": "select", "valeur": None}
            self._f["champs"].append(self._select)
        elif tag == "option" and self._select is not None and self._select["valeur"] is None:
            self._select["valeur"] = a.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form" and self._f is not None:
            self.formulaires.append(self._f)
            self._f = None
        elif tag == "select":
            self._select = None


def lire_formulaires(page: str) -> list:
    p = _Formulaires()
    try:
        p.feed(page or "")
    except Exception:          # page mal formée : on garde ce qui a été lu
        pass
    return p.formulaires


def _base(url: str) -> str:
    p = urlparse(url)
    chemin = p.path if p.path.endswith("/") else p.path.rsplit("/", 1)[0] + "/"
    return f"{p.scheme}://{p.netloc}{chemin}"


def _ligne(texte: str, debut: int, fin: int, longueur: int = 160) -> str:
    """La ligne qui contient texte[debut:fin], sans espaces superflus et bornée en longueur."""
    a = texte.rfind("\n", 0, debut) + 1
    b = texte.find("\n", fin)
    ligne = re.sub(r"\s+", " ", texte[a: b if b >= 0 else len(texte)]).strip()
    if len(ligne) > longueur:
        i = max(0, min(ligne.find(texte[debut:fin].strip()), len(ligne) - longueur))
        ligne = ligne[i: i + longueur]
    return ligne


def _extrait(corps: str, motif: str) -> str:
    """Ligne de la page où le marqueur est renvoyé."""
    i = corps.find(motif)
    return _ligne(corps, i, i + len(motif)) if i >= 0 else ""


def _erreur_sql(corps: str) -> str:
    """Première erreur SQL affichée par la page (texte sans balises) ; vide s'il n'y en a pas."""
    texte = html.unescape(_BALISES.sub("\n", corps or ""))
    m = ERREURS_SQL.search(texte)
    return _ligne(texte, m.start(), m.end()) if m else ""


class _Testeur:
    def __init__(self, cible):
        self.base = _base(cible.url)
        self.depart = cible.url
        self.session = requests.Session()
        self.requetes = 0
        self.journal = []

    def relatif(self, url: str) -> str:
        return url[len(self.base):] or "./"

    def dans_perimetre(self, url: str) -> bool:
        return url.startswith(self.base) and ".." not in url[len(self.base):]

    def envoyer(self, methode: str, url: str, donnees: dict | None = None, note: str = ""):
        """Requête bornée : renvoie la réponse, ou None si le budget est épuisé ou en cas d'erreur."""
        if self.requetes >= config.APPLICATIF_MAX_REQUETES:
            return None
        self.requetes += 1
        try:
            if methode == "post":
                r = self.session.post(url, data=donnees, timeout=config.DUREE_MAX_HTTP, allow_redirects=False,
                                      verify=False)
            else:
                r = self.session.get(url, params=donnees, timeout=config.DUREE_MAX_HTTP, allow_redirects=False,
                                     verify=False)
        except requests.RequestException:
            self.journal.append(f"--- {methode.upper()} {self.relatif(url)} {note}".rstrip())
            return None
        self.journal.append(f"{r.status_code} {methode.upper()} {self.relatif(url)} {note}".rstrip())
        return r

    # -------------------------------------------------------------- exploration

    def explorer(self) -> list:
        """Pages du site (liens de la page d'accueil, puis de ces pages) : [(url, html)]."""
        pages, a_voir, vues = [], [self.depart], set()
        while a_voir and len(pages) < config.APPLICATIF_MAX_PAGES:
            url = a_voir.pop(0).split("#")[0]
            if url in vues:
                continue
            vues.add(url)
            r = self.envoyer("get", url)
            if r is None or r.status_code != 200 or "html" not in r.headers.get("Content-Type", "html"):
                continue
            pages.append((url, r.text))
            for lien in _LIENS.findall(r.text):
                suivant = urljoin(url, lien.strip()).split("#")[0]
                sans_requete = suivant.split("?")[0]
                if (self.dans_perimetre(suivant) and not LIENS_EVITES.search(suivant)
                        and PAGES.search(sans_requete) and sans_requete not in vues):
                    a_voir.append(sans_requete)
        return pages

    def points_d_entree(self, pages) -> list:
        """Paramètres à tester : formulaires GET, formulaires de connexion et paramètres vus dans les liens."""
        points, vus = [], set()

        def ajouter(methode, page, action, champs, nom):
            cle = (methode, action.split("?")[0], nom)
            if cle in vus or not self.dans_perimetre(action) or LIENS_EVITES.search(action):
                return
            vus.add(cle)
            points.append({"methode": methode, "page": page, "action": action.split("?")[0],
                           "champs": champs, "nom": nom})

        for url, page in pages:
            for f in lire_formulaires(page):
                action = urljoin(url, f["action"] or url)
                connexion = any(c["type"] == "password" for c in f["champs"])
                if f["methode"] == "post" and not connexion:
                    continue                  # panier, commande… : peut modifier des données
                for c in f["champs"]:
                    if c["type"] in CHAMPS_TEXTE:
                        ajouter(f["methode"], url, action, f["champs"], c["nom"])
            for lien in _LIENS.findall(page):
                adresse = urljoin(url, lien.strip()).split("#")[0]
                if "?" not in adresse or not PAGES.search(adresse.split("?")[0]):
                    continue
                parametres = parse_qsl(urlparse(adresse).query, keep_blank_values=True)
                champs = [{"nom": n, "type": "text", "valeur": v} for n, v in parametres]
                for n, _ in parametres:
                    ajouter("get", url, adresse, champs, n)
        return points

    # -------------------------------------------------------------- envoi d'une valeur

    def soumettre(self, point: dict, valeur: str, note: str):
        """Envoie le formulaire (ou le lien) avec « valeur » dans le paramètre testé."""
        champs = point["champs"]
        if point["methode"] == "post":
            # Formulaire de connexion : la page est relue avant chaque envoi pour avoir un jeton anti-CSRF valable.
            r = self.envoyer("get", point["page"])
            if r is None:
                return None
            frais = [f for f in lire_formulaires(r.text) if any(c["nom"] == point["nom"] for c in f["champs"])]
            if frais:
                champs = frais[0]["champs"]
        donnees = {}
        for c in champs:
            if c["type"] in ("submit", "button", "image", "reset", "file"):
                continue
            if c["type"] in ("checkbox", "radio"):
                continue
            if c["nom"] == point["nom"]:
                donnees[c["nom"]] = valeur
            elif c["type"] == "password":
                donnees[c["nom"]] = "riposte-test"
            elif c["type"] == "email" or "mail" in c["nom"].lower():
                donnees[c["nom"]] = c["valeur"] or "riposte@exemple.test"
            else:
                donnees[c["nom"]] = c["valeur"] if c["valeur"] is not None else ""
        return self.envoyer(point["methode"], point["action"], donnees, note)


def _description_point(point: dict, base: str) -> str:
    chemin = point["action"][len(base):] or "./"
    return f"{point['methode'].upper()} {chemin}, paramètre « {point['nom']} »"


def tester(cible) -> dict:
    """Cherche une XSS réfléchie et une injection SQL révélée par une erreur dans les paramètres du site."""
    t = _Testeur(cible)
    res = {"xss": [], "sqli": [], "points": 0, "requetes": 0, "journal": t.journal, "ignore": ""}
    pages = t.explorer()
    points = t.points_d_entree(pages)
    res["points"] = len(points)
    if not points:
        res["ignore"] = "Aucun formulaire de recherche ou de connexion, ni paramètre d'adresse, n'a été trouvé."
    for p in points:
        if t.requetes >= config.APPLICATIF_MAX_REQUETES:
            res["ignore"] = "Le nombre maximal de requêtes a été atteint : tous les paramètres n'ont pas été testés."
            break
        lieu = _description_point(p, t.base)
        mail = "mail" in p["nom"].lower()

        # XSS réfléchie : un marqueur en forme de balise inconnue, renvoyé tel quel ou échappé ?
        marqueur = f"<rpst{uuid.uuid4().hex[:8]}>"
        r = t.soumettre(p, ("riposte@exemple.test" if mail else "riposte") + marqueur, "(marqueur XSS)")
        if r is not None and marqueur in r.text and "html" in r.headers.get("Content-Type", "html"):
            res["xss"].append({"lieu": lieu, "extrait": _extrait(r.text, marqueur)})

        # Injection SQL : valeur normale, puis avec une apostrophe, puis avec deux apostrophes (équilibrées).
        normale = "riposte@exemple.test" if mail else "riposte"
        r0 = t.soumettre(p, normale, "(valeur normale)")
        r1 = t.soumettre(p, normale + "'", "(apostrophe)")
        if r0 is None or r1 is None:
            continue
        erreur = _erreur_sql(r1.text)
        if not erreur or _erreur_sql(r0.text):
            continue
        r2 = t.soumettre(p, normale + "''", "(deux apostrophes)")
        equilibree = r2 is not None and not _erreur_sql(r2.text)
        res["sqli"].append({"lieu": lieu, "erreur": erreur, "confirme": equilibree})
    res["requetes"] = t.requetes
    return res
