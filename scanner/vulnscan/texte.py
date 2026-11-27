"""Petites aides de rédaction : accords au pluriel, durées et nom des logiciels, pour un rapport lisible."""
import re


def accord(n, singulier: str, pluriel: str = None) -> str:
    """« 1 faiblesse », « 2 faiblesses ». En français, 0 et 1 restent au singulier."""
    n = int(n or 0)
    mot = singulier if n < 2 else (pluriel if pluriel is not None else singulier + "s")
    return f"{n} {mot}"


def accord_ou_aucun(n, singulier: str, pluriel: str = None, aucun: str = None) -> str:
    """Comme accord(), mais « aucun … » quand le nombre vaut 0."""
    if not n:
        return aucun or f"aucun {singulier}"
    return accord(n, singulier, pluriel)


def duree(secondes) -> str:
    """« 12,8 s » ; « < 0,1 s » pour une étape quasi instantanée ; « — » si la durée est inconnue."""
    if secondes is None or secondes == "" or secondes == "—":
        return "—"
    try:
        s = float(secondes)
    except Exception:          # valeur absente du rapport (Undefined de Jinja) ou texte
        return str(secondes) or "—"
    if s < 0.1:
        return "< 0,1 s"
    return f"{s:.1f}".replace(".", ",") + " s"


def _minuscule(texte: str) -> str:
    """Première lettre en minuscule, sauf devant un sigle (« IA », « HTTP »)."""
    if len(texte) > 1 and texte[1].isupper():
        return texte
    return texte[:1].lower() + texte[1:]


def origine_resume(origine: str) -> str:
    """Phrase placée sous le résumé : qui l'a écrit."""
    if not origine or origine == "automatique":
        return "Résumé généré automatiquement à partir des constats."
    return f"Résumé rédigé par l'{_minuscule(origine)} à partir des constats."


def etape_resume(origine: str) -> str:
    """Libellé de l'étape « résumé » dans le tableau de méthodologie."""
    if not origine or origine == "automatique":
        return "Résumé (généré automatiquement)"
    return f"Résumé (rédigé par l'{_minuscule(origine)})"


_MARIADB = re.compile(r"^MySQL\s+5\.5\.5-(\d+(?:\.\d+)+)-MariaDB\b.*$", re.IGNORECASE)
_SUFFIXE_PAQUET = re.compile(r"-\d*(?:ubuntu|deb|debian)[\w.+~-]*$", re.IGNORECASE)


def nom_logiciel(version: str) -> str:
    """Nom lisible d'un logiciel détecté par Nmap.

    MariaDB se présente comme « MySQL 5.5.5-10.6.23-MariaDB-0ubuntu0.22.04.1 » (préfixe de compatibilité) :
    on garde « MariaDB 10.6.23 ». Le suffixe du paquet Debian/Ubuntu est retiré des autres versions.
    """
    v = (version or "").strip()
    m = _MARIADB.match(v)
    if m:
        return f"MariaDB {m.group(1)}"
    return _SUFFIXE_PAQUET.sub("", v)
