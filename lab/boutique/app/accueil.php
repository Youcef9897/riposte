<?php
require __DIR__ . '/inc/db.php';
$titre = 'Accueil';
require __DIR__ . '/inc/haut.php';
?>
<section class="hero">
  <div>
    <h1>Le matériel réseau pour monter votre lab</h1>
    <p>Câbles, switchs, cartes réseau et points d'accès : tout pour équiper un poste ou une baie.</p>
    <a class="bouton" href="index.php">Voir le catalogue</a>
  </div>
</section>
<section class="atouts">
  <div class="carte"><h2>Livraison en 48 h</h2><p>Commandes préparées sous 24 h, livrées en France métropolitaine.</p></div>
  <div class="carte"><h2>Retours sous 30 jours</h2><p>Un article ne convient pas ? Renvoyez-le dans son emballage d'origine.</p></div>
  <div class="carte"><h2>Support technique</h2><p>Une question sur un switch ou un câblage ? Écrivez-nous.</p></div>
</section>
<?php require __DIR__ . '/inc/bas.php';
