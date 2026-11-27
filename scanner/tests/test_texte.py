"""Rédaction du rapport : accords au pluriel, durées, noms de logiciels, preuves lisibles."""
from vulnscan import comparaison, constats, outils, texte
from vulnscan.cible import Cible
from vulnscan.resume import resume_automatique


def test_accords():
    assert texte.accord(0, "faiblesse") == "0 faiblesse"
    assert texte.accord(1, "faiblesse") == "1 faiblesse"
    assert texte.accord(5, "faiblesse") == "5 faiblesses"
    assert texte.accord(2, "nouveau", "nouveaux") == "2 nouveaux"
    assert texte.accord(4, "info", "info") == "4 info"
    assert texte.accord_ou_aucun(0, "nouveau", "nouveaux") == "aucun nouveau"


def test_durees_a_la_francaise():
    assert texte.duree(12.8) == "12,8 s"
    assert texte.duree(13) == "13,0 s"
    assert texte.duree(0.0) == "< 0,1 s"
    assert texte.duree(None) == "—"


def test_noms_de_logiciels():
    assert texte.nom_logiciel("MySQL 5.5.5-10.6.23-MariaDB-0ubuntu0.22.04.1") == "MariaDB 10.6.23"
    assert texte.nom_logiciel("Apache httpd 2.4.52 ((Ubuntu))") == "Apache httpd 2.4.52 ((Ubuntu))"
    assert outils.version_nmap("Nmap version 7.80 ( https://nmap.org )") == "Nmap 7.80"


def test_origine_du_resume():
    assert texte.origine_resume("automatique") == "Résumé généré automatiquement à partir des constats."
    assert texte.origine_resume("IA locale (qwen2.5:3b)") == "Résumé rédigé par l'IA locale (qwen2.5:3b) à partir des constats."


def test_ancien_et_nouveau_titre_de_cve_restent_comparables():
    """Une analyse enregistrée avant ce changement (« connue(s) », « MySQL 5.5.5-… ») reste comparable."""
    ancien = {"code": "C05", "titre": "1 CVE connue(s) pour MySQL 5.5.5-10.6.23-MariaDB-0ubuntu0.22.04.1 (port 3306)",
              "gravite": "Moyenne", "verification": "À vérifier"}
    nouveau = dict(ancien, titre="2 CVE connues pour MariaDB 10.6.23 (port 3306)")
    assert comparaison.cle(ancien) == comparaison.cle(nouveau)


def test_bilan_et_pastilles_accordes():
    def res(i, score, liste):
        return {"id": i, "date": "d", "cible": {"url": "http://x/"}, "ports": [],
                "score": {"score": score, "niveau": "n", "comptes": {}}, "constats": liste}
    c = lambda code, titre, g: {"code": code, "titre": titre, "gravite": g, "verification": "Confirmé"}
    avant = res("20260101-000000-x-0001", 58, [c("C01", "Injection SQL", "Élevée"), c("C02", "Cookie", "Moyenne"),
                                             c("C03", "XSS", "Moyenne"), c("C04", "Certificat", "Faible"),
                                             c("C05", "HTTP", "Faible")])
    apres = res("20260101-000001-x-0001", 94, [c("C01", "Certificat", "Faible"), c("C02", "HTTP", "Faible")])
    r = comparaison.comparer(avant, apres)
    assert r["bilan"] == "Le score passe de 58 à 94/100 (+36 points) : 3 constats corrigés, aucun nouveau, 2 toujours présents."
    assert r["etiquettes"]["Corrigé"] == "3 corrigés" and r["etiquettes"]["Toujours présent"] == "2 toujours présents"


def test_preuve_injection_sql_lisible():
    app = {"sqli": [{"lieu": "POST connexion.php, paramètre « email »", "confirme": True,
                     "erreur": "SQLSTATE[42000]: Syntax error or access violation: 1064 You have an error in your SQL "
                               "syntax; check the manual that corresponds to your MariaDB server version"}], "xss": []}
    preuves = constats.constats_applicatif(app)[0].preuves
    assert preuves[0] == "POST connexion.php, paramètre « email »"
    assert preuves[1].endswith("SQLSTATE[42000]: Syntax error or access violation: 1064 You have an error in your SQL syntax")
    assert "avec deux apostrophes (valeur'') : aucune erreur" in preuves[2]


def test_resume_avec_deux_points_de_configuration():
    cible = Cible(url="http://127.0.0.1:8082/", schema="http", hote="127.0.0.1", port=8082, adresses=["127.0.0.1"])
    liste = [constats.Constat(titre="Certificat auto-signé", gravite="Faible", categorie="Chiffrement",
                              description="", recommandation="", verification="Confirmé"),
             constats.Constat(titre="HTTP ne redirige pas vers HTTPS", gravite="Faible", categorie="Chiffrement",
                              description="", recommandation="", verification="Confirmé")]
    score = {"score": 94, "niveau": "Bon", "comptes": {"Élevée": 0, "Moyenne": 0, "Faible": 2, "Info": 0}}
    texte_resume = resume_automatique(cible, liste, score)
    assert "a relevé 2 faiblesses à corriger (2 de gravité faible)" in texte_resume
    assert texte_resume.endswith("Ces points relèvent surtout de la configuration du serveur.")
    assert "(s)" not in texte_resume
