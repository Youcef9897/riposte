"""Résumé exécutif en français : rédigé par l'IA locale (Ollama), sinon généré automatiquement.

L'IA ne reçoit que la liste des constats déjà calculés (quelques lignes) et
n'écrit qu'un paragraphe court : c'est ce qui rend cette étape rapide.
"""
import requests

from . import config
from .constats import FAUX_POSITIF, NON_CONFIRME
from .texte import accord


def _retenus(constats):
    return [c for c in constats if c.verification not in (FAUX_POSITIF, NON_CONFIRME) and c.gravite != "Info"]


def _dans_la_phrase(titre: str) -> str:
    """Met la première lettre en minuscule pour l'insérer dans une phrase, sauf devant un sigle (HTTP, XSS…)."""
    if len(titre) > 1 and titre[1].isupper():
        return titre
    return titre[:1].lower() + titre[1:]


def resume_automatique(cible, constats, score) -> str:
    retenus = _retenus(constats)
    c = score["comptes"]
    if not retenus:
        return (f"L'analyse de {cible.url} n'a relevé aucune faiblesse confirmée parmi les points contrôlés. "
                f"Le score de sécurité est de {score['score']}/100 (niveau « {score['niveau']} »).")
    priorites = " ; ".join(_dans_la_phrase(x.titre) for x in retenus[:3])
    noms = {"Élevée": "de gravité élevée", "Moyenne": "de gravité moyenne", "Faible": "de gravité faible"}
    detail = ", ".join(f"{c[g]} {noms[g]}" for g in ("Élevée", "Moyenne", "Faible") if c[g])
    if any(x.categorie == "Injection" for x in retenus):
        fin = "Les failles d'injection se corrigent dans le code du site ; les autres points, dans la configuration du serveur."
    elif len(retenus) == 1:
        fin = "Ce point relève surtout de la configuration du serveur."
    else:
        fin = "Ces points relèvent surtout de la configuration du serveur."
    return (
        f"L'analyse de {cible.url} a relevé {accord(len(retenus), 'faiblesse')} à corriger ({detail}). "
        f"Le score de sécurité est de {score['score']}/100, soit un niveau « {score['niveau']} ». "
        + ("La correction prioritaire porte sur : " if len(retenus) == 1 else "Les corrections prioritaires portent sur : ")
        + f"{priorites}. {fin}"
    )


def resume_ia(cible, constats, score) -> tuple:
    """Renvoie (texte, origine). Origine : « IA locale (modèle) » ou « automatique »."""
    automatique = resume_automatique(cible, constats, score)
    if not config.IA_ACTIVE:
        return automatique, "automatique"
    faits = "\n".join(f"- [{c.gravite}] {c.titre}" for c in _retenus(constats)[:10]) or "- Aucune faiblesse confirmée"
    consigne = f"""Tu es consultant en cybersécurité. Rédige en français le résumé exécutif d'un rapport d'audit,
destiné à un responsable non technique.

Contraintes :
- 4 à 6 phrases, un seul paragraphe, sans titre, sans liste, sans Markdown.
- Utilise uniquement les faits ci-dessous ; n'invente rien.
- Termine par la priorité de correction.

Cible : {cible.url}
Score : {score['score']}/100 (niveau {score['niveau']})
Constats :
{faits}
"""
    try:
        rep = requests.post(config.IA_URL, timeout=config.IA_DUREE_MAX, json={
            "model": config.IA_MODELE, "prompt": consigne, "stream": False, "keep_alive": "15m",
            "options": {"num_predict": config.IA_LONGUEUR_MAX, "num_ctx": 2048, "temperature": 0.2},
        })
        texte = (rep.json().get("response") or "").strip()
        texte = texte.replace("#", "").replace("*", "").strip()
        if len(texte) < 80:
            return automatique, "automatique"
        return texte, f"IA locale ({config.IA_MODELE})"
    except (requests.RequestException, ValueError):
        return automatique, "automatique"
