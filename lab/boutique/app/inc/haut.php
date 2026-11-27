<?php $client = client_connecte(); ?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($titre ?? 'NetStock Lab') ?> — NetStock Lab</title>
<link rel="stylesheet" href="style.css?v=<?= filemtime(__DIR__ . '/../style.css') ?>">
</head>
<body>
<p class="lab"><strong>version corrigée</strong></p>
<header>
  <a class="marque" href="accueil.php">NetStock Lab</a>
  <nav>
    <a href="accueil.php">Accueil</a>
    <div class="menu">
      <a href="index.php">Catalogue ▾</a>
      <div class="sous-menu">
        <a href="index.php">Tout le matériel</a>
        <?php foreach ($db->query('SELECT nom FROM produits ORDER BY nom')->fetchAll() as $m): ?>
          <a href="index.php?q=<?= urlencode($m['nom']) ?>"><?= e($m['nom']) ?></a>
        <?php endforeach; ?>
      </div>
    </div>
    <a href="panier.php">Panier (<?= count($_SESSION['panier']) ?>)</a>
    <?php if ($client): ?>
      <a href="compte.php"><?= e($client['nom']) ?></a>
      <a href="deconnexion.php">Se déconnecter</a>
    <?php else: ?>
      <a href="connexion.php">Se connecter</a>
    <?php endif; ?>
  </nav>
</header>
<main>
