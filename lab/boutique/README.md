# NetStock Lab — boutique de démonstration

> **Laboratoire uniquement.** La version vulnérable contient des failles **exprès**. Le site écoute sur `127.0.0.1:8082`
> et ne doit jamais être exposé sur un réseau ni déployé sur un vrai serveur. Toutes les données sont fictives.

NetStock Lab est une petite boutique de matériel réseau (PHP, MariaDB) que j'ai écrite pour servir de cible à RIPOSTE
et aux tests manuels. Elle existe en deux versions :

| Version | Où la trouver |
|---|---|
| Vulnérable, avec 8 failles volontaires | branche `v3-s3-boutique` |
| Corrigée | branche `main` (ce dossier) |

## Les 8 failles et leur correction

| Faille | Page | Ce qu'elle permet | Correction |
|---|---|---|---|
| Injection SQL | `connexion.php` | Se connecter sans mot de passe | Requête préparée avec paramètre lié |
| Commande d'un autre client visible (IDOR) | `commande.php?id=` | Lire l'adresse et la commande d'un autre client | La requête filtre aussi sur le client connecté |
| Texte recherché réaffiché tel quel (XSS réfléchi) | `index.php?q=` | Exécuter un script dans la page | Texte échappé avec `htmlspecialchars` |
| Prix envoyé par le navigateur | `panier.php` | Payer un produit le prix qu'on veut | Prix relu dans la base, valeur du navigateur ignorée |
| Quantité négative acceptée | `panier.php` | Faire baisser le total du panier | Quantité minimale de 1 |
| Code promo réutilisable | `panier.php` | Cumuler les remises | Un seul usage par panier |
| Erreur SQL affichée | `connexion.php` | Révéler la requête et la structure de la base | Message générique |
| Mots de passe en MD5 sans sel | base `clients` | Retrouver les mots de passe en cas de fuite | Hachage bcrypt (`password_hash`, `password_verify`) |

En plus, la version corrigée ajoute un jeton anti-CSRF dans chaque formulaire, des en-têtes de sécurité et un cookie
de session `HttpOnly` et `SameSite`.

Les fraudes du panier (prix, quantité, code promo) et l'accès aux commandes d'un autre client ne se voient pas avec
des outils automatiques : elles se trouvent par des tests manuels.

## Comptes de test (fictifs)

| E-mail | Mot de passe |
|---|---|
| alice@netstock.lab | mDXDM9kKYTUjCUi |
| bob@netstock.lab | bob2027 |

## Installation dans la VM

En root, depuis ce dossier : `sh installer-dans-la-vm.sh`. Le script copie le site dans `/var/www/netstock-lab`,
crée une base `netstock_lab` avec un compte dédié (mot de passe aléatoire, jamais affiché), remplit les données
fictives et ajoute un site Apache sur `127.0.0.1:8082`. Le relancer remet tout à zéro.

Facultatif : `sh telecharger-photos.sh` ajoute les photos libres des produits (Pexels, Unsplash).

Désinstallation (root) : `a2dissite netstock-lab && systemctl reload apache2`, puis
`mysql -e "DROP DATABASE netstock_lab; DROP USER 'netstock_lab'@'localhost';"` et `rm -r /var/www/netstock-lab`.

## Tests automatiques

`scanner/tests/test_boutique.py` lance la boutique avec le serveur intégré de PHP et une base SQLite jetable. Chaque
test rejoue une attaque de la version vulnérable et vérifie qu'elle **échoue** sur la version corrigée.
