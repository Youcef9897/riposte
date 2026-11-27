#!/bin/sh
# Télécharge les photos libres des produits (Pexels, Unsplash) listées dans app/img/photos.txt,
# les met à 400 × 260 px et les copie dans le site installé. À lancer en root, après installer-dans-la-vm.sh.
set -eu

ICI=$(cd "$(dirname "$0")" && pwd)
LISTE="$ICI/app/img/photos.txt"
DEST=/var/www/netstock-lab/img

[ "$(id -u)" -eq 0 ] || { echo "À lancer en root : su - puis sh $0"; exit 1; }
command -v convert >/dev/null || apt-get install -y imagemagick >/dev/null

mkdir -p "$DEST"
cp "$LISTE" "$DEST/photos.txt"
TMP=$(mktemp -d)
grep -v '^#' "$LISTE" | while IFS='|' read -r numero adresse page credit; do
    [ -n "$numero" ] || continue
    if curl -fsSL --max-time 60 -o "$TMP/brut" "$adresse"; then
        convert "$TMP/brut" -resize '400x260^' -gravity center -extent 400x260 -quality 85 "$DEST/produit-$numero.jpg"
        echo "Produit $numero : photo installée ($credit)"
    else
        echo "Produit $numero : téléchargement impossible, la vignette texte reste affichée"
    fi
done
# Grande photo de la page d'accueil (même photo Pexels que le produit 1, en haute définition).
ACCUEIL='https://images.pexels.com/photos/4716292/pexels-photo-4716292.jpeg?auto=compress&cs=tinysrgb&w=1920'
if curl -fsSL --max-time 60 -o "$TMP/brut" "$ACCUEIL"; then
    convert "$TMP/brut" -resize '1600x600^' -gravity center -extent 1600x600 -quality 82 "$DEST/accueil.jpg"
    echo "Accueil : photo installée (Pexels, photo n° 4716292)"
else
    echo "Accueil : téléchargement impossible, un fond bleu reste affiché"
fi
rm -rf "$TMP"
chown -R root:www-data "$DEST"
chmod 644 "$DEST"/*
echo "Vérifie chaque photo dans le navigateur : aucune marque ni visage ne doit être visible."
