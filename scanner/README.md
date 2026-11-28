# RIPOSTE — guide technique de la plateforme

Ce dossier contient la plateforme RIPOSTE : une application web qui analyse un site **autorisé** avec Nmap, Nikto, SSLScan et, en option, OWASP ZAP, **vérifie** chaque constat par des requêtes directes, teste les injections les plus courantes, puis produit un rapport en français (page web et PDF) avec un score sur 100.

La présentation du projet et les études se trouvent dans le [README principal](../README.md).

> **Cadre légal.** Analyser un système sans l'autorisation de son propriétaire est interdit (articles 323-1 et suivants du Code pénal). La plateforme refuse toute cible absente de sa liste blanche et demande de confirmer l'autorisation avant chaque analyse.

## Installation (Ubuntu 22.04)

```bash
sudo apt update
sudo apt install -y nmap nikto sslscan python3-flask python3-requests python3-reportlab fonts-dejavu-core
```

En option :
- résumé rédigé par un modèle de langage local : installer [Ollama](https://ollama.com/), puis `ollama pull mistral` ;
- analyse passive avec ZAP : `sudo snap install zaproxy --classic`.

## Lancement

```bash
cd scanner
python3 app.py              # ou IA_ACTIVE=0 python3 app.py sans Ollama
```

Puis ouvrir **http://127.0.0.1:5000**. Les rapports sont enregistrés dans `scanner/scans/`, un dossier par analyse.

## Ce que contrôle la plateforme

| Contrôle | Ce qu'il apporte |
|---|---|
| Nmap et le script `vulners` | Ports ouverts, services, versions et CVE publiées pour ces versions, avec leur score CVSS. Un constat de CVE reste « À vérifier », car il repose sur le seul numéro de version. |
| Nikto | Configuration du serveur web : en-têtes, méthodes, fichiers connus. |
| SSLScan et contrôle du certificat | Protocoles et chiffrements, certificat (expiré, mauvais nom, auto-signé), HSTS, redirection HTTP vers HTTPS. |
| Vérification directe (`verification.py`) | Chaque alerte est rejouée par une requête HTTP de lecture, puis classée Confirmé, À vérifier, Non confirmé ou Faux positif probable. |
| Chemins sensibles (`chemins.py`) | Dossiers listés (« Index of »), code source et copies de sauvegarde téléchargeables, fichiers de secrets (`.env`, `.git`, `.sql`), zones d'administration. Requêtes GET uniquement, sous l'adresse analysée, 80 au maximum. |
| Écoute locale (`ecoute.py`) | Quand la cible est la machine elle-même, l'adresse d'écoute réelle de chaque service est lue avec `ss`. Un service limité à 127.0.0.1 est signalé pour information et ne retire aucun point. |
| Tests applicatifs (`applicatif.py`) | XSS réfléchie et injection SQL révélée par une erreur (détails ci-dessous). |
| OWASP ZAP, en option (`zap.py`) | Exploration des pages et analyse passive des réponses (détails ci-dessous). |

### Tests applicatifs

| Test | Valeur envoyée | Constat si… |
|---|---|---|
| XSS réfléchie | un marqueur en forme de balise inconnue (`<rpst…>`) | le marqueur revient tel quel dans la page (gravité moyenne) |
| Injection SQL révélée par une erreur | la même valeur, puis avec une apostrophe, puis avec deux | l'apostrophe seule provoque une erreur de la base (SQLSTATE, MySQL, SQLite, PostgreSQL…) ; « Confirmé » si deux apostrophes n'en provoquent plus (gravité élevée) |

Règles de prudence : 12 pages et 80 requêtes au maximum, même hôte, sous l'adresse analysée ; seuls les formulaires de recherche et de connexion sont envoyés, jamais le panier ou une commande ; les liens de déconnexion ou de suppression ne sont pas suivis ; le jeton anti-CSRF d'un formulaire de connexion est relu avant chaque envoi.

Limites : une injection « aveugle » (sans message d'erreur), une XSS stockée ou un défaut de contrôle d'accès ne sont pas détectés.

### Sites en HTTPS

- **Adresse HTTP qui redirige vers HTTPS** : l'analyse suit la redirection si elle reste sur la même machine et porte alors sur le site HTTPS. Le rapport indique l'adresse réellement analysée. Une redirection vers une autre machine n'est jamais suivie.
- **HTTPS disponible sans redirection** : le chiffrement et le certificat sont contrôlés quand même, et le constat « HTTP ne redirige pas vers HTTPS » est émis.
- **Certificat auto-signé** : gravité Moyenne sur un site public, Faible sur une adresse locale ou privée de laboratoire, avec le rappel qu'il faut un certificat reconnu en production.

### ZAP en mode passif

ZAP est désactivé par défaut. Avec `ZAP_ACTIF=1`, la plateforme le lance en même temps que les autres outils : il parcourt les pages du site (liens et formulaires GET) et lit les réponses. Il ne lance **aucune attaque** et n'envoie **aucun formulaire POST** ; il n'écoute que sur 127.0.0.1.

- Ses alertes sont traduites en fiches françaises (`regles_zap.py`).
- Si ZAP signale un problème déjà trouvé par la plateforme, il ajoute sa preuve au constat existant, sans le compter deux fois.
- Il apporte ce que seul un parcours de toutes les pages révèle : formulaire sans jeton anti-CSRF, cookie posé par une autre page, message d'erreur affiché, bibliothèque JavaScript vulnérable.
- Une alerte peu sûre pour ZAP est classée « À vérifier » un cran en dessous ; ses alertes de simple information sont écartées.

Une analyse avec ZAP contient plus de constats : la page de comparaison le signale si une seule des deux analyses l'a utilisé.

## Comparaison avant / après

Sur la page d'accueil, « Comparer deux analyses » met côte à côte deux analyses déjà enregistrées, sans relancer d'outil. Chaque constat qui compte dans le score reçoit un statut :

| Statut | Signification |
|---|---|
| Corrigé | présent avant, absent après |
| Atténué | toujours présent, mais retire moins de points |
| Plus vérifiable | n'apparaît plus parce que l'information a été masquée (par exemple la version d'un logiciel), sans preuve de correction |
| Nouveau | absent avant, présent après |
| Aggravé | retire plus de points qu'avant |
| Toujours présent | inchangé |

La page indique l'écart de score et les points regagnés ou perdus par constat ; leur somme redonne l'écart. Elle s'exporte en PDF.

## Réglages

Ils se changent au lancement, sans modifier le code. Exemple : `IA_ACTIVE=0 python3 app.py`.

| Variable | Rôle | Valeur par défaut |
|---|---|---|
| `CIBLES_AUTORISEES` | Liste blanche (noms, IP ou réseaux) | `localhost,127.0.0.1,192.168.56.0/24` |
| `PORT_ECOUTE` | Port de la plateforme | `5000` |
| `IA_ACTIVE` | `0` pour désactiver le résumé par le modèle local | `1` |
| `IA_MODELE` | Modèle Ollama | `mistral` |
| `IA_DUREE_MAX` | Délai maximal du modèle, en secondes | `120` |
| `DUREE_MAX_NIKTO` | Durée maximale de Nikto, en secondes | `240` |
| `NMAP_PORTS` | Ports vérifiés par Nmap | `21,22,23,25,80,443,631,3306,3389,5432,8080,8443` |
| `CVE_ACTIVE` | `0` pour ne pas chercher les CVE (aucun envoi à vulners.com) | `1` |
| `CHEMINS_ACTIFS` | `0` pour désactiver le contrôle des chemins sensibles | `1` |
| `CHEMINS_SUPPLEMENTAIRES` | Chemins propres au site à contrôler en plus (`dossier/` ou `fichier`) | vide |
| `CHEMINS_MAX_REQUETES` | Nombre maximal de requêtes du contrôle des chemins | `80` |
| `TESTS_APPLICATIFS` | `0` pour désactiver les tests de XSS et d'injection SQL | `1` |
| `APPLICATIF_MAX_PAGES` / `APPLICATIF_MAX_REQUETES` | Pages explorées et requêtes maximales des tests applicatifs | `12` / `80` |
| `ZAP_ACTIF` | `1` pour ajouter l'analyse passive de ZAP | `0` |
| `ZAP_DUREE_EXPLORATION` | Durée maximale de l'exploration des pages par ZAP, en minutes | `1` |
| `DUREE_MAX_ZAP` | Durée maximale de ZAP, en secondes | `300` |

## Organisation du code

```
scanner/
├── app.py                 interface web (Flask)
├── vulnscan/
│   ├── config.py          réglages
│   ├── cible.py           validation de la cible et liste blanche
│   ├── outils.py          lancement de Nmap, Nikto et SSLScan en parallèle
│   ├── analyse.py         lecture des sorties (XML de Nmap, texte de Nikto et SSLScan)
│   ├── verification.py    vérification directe par requêtes HTTP de lecture
│   ├── chemins.py         contrôle des chemins sensibles
│   ├── applicatif.py      tests applicatifs (XSS réfléchie, injection SQL par erreur)
│   ├── ecoute.py          adresse d'écoute réelle des services locaux (ss)
│   ├── zap.py             ZAP en mode passif : plan, lancement, lecture du rapport JSON
│   ├── regles_zap.py      fiches en français des alertes de ZAP
│   ├── constats.py        constats en français : gravité, preuves, recommandations
│   ├── score.py           score sur 100 et barème
│   ├── resume.py          résumé (modèle local ou automatique)
│   ├── texte.py           rédaction : accords, durées, noms de logiciels
│   ├── comparaison.py     comparaison de deux analyses
│   ├── scan.py            déroulement complet d'une analyse
│   └── rapport_pdf.py     mise en page des rapports PDF
├── templates/             pages web
└── tests/                 tests automatiques
```

## Tests

```bash
cd scanner
python3 -m pytest -q
```

Les tests utilisent de vraies sorties d'outils enregistrées, un faux site, un vrai serveur HTTPS local et la boutique NetStock Lab lancée dans un serveur PHP jetable : ils n'analysent aucun site réel.

## Avant une mise en ligne

La plateforme est prévue pour tourner en local. Avant de l'exposer sur Internet, il faudrait au minimum une authentification des utilisateurs, une limite du nombre d'analyses, une file d'attente, un serveur web de production (par exemple Gunicorn derrière Nginx en HTTPS) et une liste blanche gérée par compte.
