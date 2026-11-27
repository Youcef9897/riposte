<?php
require __DIR__ . '/inc/db.php';
$titre = 'Aide';
require __DIR__ . '/inc/haut.php';
?>
<h1>Aide et informations</h1>
<section class="carte texte" id="livraison">
  <h2>Livraison</h2>
  <p>Les commandes sont préparées sous 24 h et livrées en 48 h en France métropolitaine.</p>
</section>
<section class="carte texte" id="retours">
  <h2>Retours</h2>
  <p>Vous disposez de 30 jours pour retourner un article dans son emballage d'origine.</p>
</section>
<section class="carte texte" id="contact">
  <h2>Nous contacter</h2>
  <p>Par e-mail : contact@netstock.lab, du lundi au vendredi.</p>
</section>
<section class="carte texte" id="mentions">
  <h2>Mentions légales</h2>
  <p>NetStock Lab est un site de démonstration créé pour un lab de sécurité. Les produits, clients et commandes sont fictifs : aucune vente réelle.</p>
  <p>Photos des produits : Pexels et Unsplash, sous licences libres.</p>
</section>
<section class="carte texte" id="confidentialite">
  <h2>Confidentialité</h2>
  <p>Aucune donnée personnelle réelle n'est collectée. Les comptes de démonstration sont réinitialisés à chaque installation.</p>
</section>
<?php require __DIR__ . '/inc/bas.php';
