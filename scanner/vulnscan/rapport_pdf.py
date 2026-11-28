"""Rapport PDF : mise en page aérée, signets dépliables et liens entre le tableau et le détail.

Toute la présentation est ici : changer la mise en page ne touche pas au moteur d'analyse.
"""
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .texte import accord, duree, etape_resume, origine_resume

ACCENT = colors.HexColor("#1f4e79")
GRIS = colors.HexColor("#5b6878")
BORD = colors.HexColor("#dde3ea")
FOND = colors.HexColor("#f5f7fa")
TEINTES = {"Élevée": "#b42318", "Moyenne": "#c2560c", "Faible": "#a16207", "Info": "#5b6878"}
COULEURS = {g: colors.HexColor(h) for g, h in TEINTES.items()}
LARGEUR = 17 * cm                     # largeur utile d'une page A4 avec 2 cm de marge de chaque côté
LIGNES_ANNEXE = 30                    # lignes gardées par outil dans l'annexe du PDF


def _polices():
    """DejaVu (accents, flèches, symboles) si présente, sinon Helvetica."""
    d = Path("/usr/share/fonts/truetype/dejavu")
    if (d / "DejaVuSans.ttf").exists():
        pdfmetrics.registerFont(TTFont("DV", str(d / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DV-B", str(d / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("DVM", str(d / "DejaVuSansMono.ttf")))
        pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")
        return "DV", "DV-B", "DVM"
    return "Helvetica", "Helvetica-Bold", "Courier"


def _styles(normal, gras, mono):
    s = getSampleStyleSheet()
    base = s["Normal"]
    return {
        "titre": ParagraphStyle("t", parent=s["Title"], fontName=gras, fontSize=24, leading=30, textColor=ACCENT,
                                alignment=TA_CENTER),
        "sous": ParagraphStyle("s", parent=base, fontName=normal, fontSize=12, leading=17, textColor=GRIS,
                               alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", parent=base, fontName=gras, fontSize=16, leading=21, textColor=ACCENT,
                             spaceBefore=18, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base, fontName=gras, fontSize=12.5, leading=17, spaceBefore=4, spaceAfter=8),
        "p": ParagraphStyle("p", parent=base, fontName=normal, fontSize=10, leading=15, spaceAfter=8),
        "petit": ParagraphStyle("pp", parent=base, fontName=normal, fontSize=8.5, leading=12.5, textColor=GRIS,
                                spaceAfter=4),
        "etiquette": ParagraphStyle("et", parent=base, fontName=gras, fontSize=8.5, leading=11, spaceAfter=3),
        "cell": ParagraphStyle("c", parent=base, fontName=normal, fontSize=9, leading=12.5),
        "cellp": ParagraphStyle("cp", parent=base, fontName=normal, fontSize=8, leading=11, textColor=GRIS,
                                spaceBefore=2),
        "cellb": ParagraphStyle("cb", parent=base, fontName=gras, fontSize=8.8, leading=11.5, textColor=colors.white,
                                alignment=TA_CENTER),
        "pastille": ParagraphStyle("pa", parent=base, fontName=gras, fontSize=7.8, leading=10, textColor=colors.white,
                                   alignment=TA_CENTER),
        "code": ParagraphStyle("code", fontName=mono, fontSize=7.6, leading=10.4, backColor=FOND, borderColor=BORD,
                               borderWidth=0.5, borderPadding=6, spaceBefore=6, spaceAfter=10),
        "score": ParagraphStyle("sc", parent=base, fontName=gras, fontSize=34, leading=38, textColor=ACCENT,
                                alignment=TA_CENTER),
    }


def _bloc_code(texte, style, largeur=118):
    lignes = []
    for l in (texte or "").splitlines():
        lignes.extend(textwrap.wrap(l, largeur, replace_whitespace=False, drop_whitespace=False,
                                    subsequent_indent="    ") or [""])
    return Preformatted("\n".join(lignes), style)


def _tableau(donnees, largeurs, entete=True):
    t = Table(donnees, colWidths=largeurs, repeatRows=1 if entete else 0)
    st = [("LINEBELOW", (0, 0), (-1, -1), 0.4, BORD), ("BOX", (0, 0), (-1, -1), 0.4, BORD),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    if entete:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7"))]
    t.setStyle(TableStyle(st))
    return t


def _pastille(texte, couleur, S, largeur=1.8 * cm):
    """Étiquette colorée aux coins arrondis, comme les pastilles du rapport web."""
    t = Table([[Paragraph(escape(texte), S["pastille"])]], colWidths=[largeur])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), couleur), ("ROUNDEDCORNERS", [5, 5, 5, 5]),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    return t


class _Document(SimpleDocTemplate):
    """Ajoute un signet (le menu dépliable à gauche du lecteur PDF) pour chaque élément qui en porte un."""

    def afterFlowable(self, f):
        signet = getattr(f, "_signet", None)
        if signet:
            titre, cle, niveau, ferme = signet
            self.canv.bookmarkPage(cle)
            self.canv.addOutlineEntry(titre, cle, level=niveau, closed=ferme)


def _signet(flowable, titre, cle, niveau=0, ferme=False):
    flowable._signet = (titre, cle, niveau, ferme)
    return flowable


def _section(titre, cle, S, ferme=False, suite=None):
    """Titre de section avec son signet. `suite` : ce qui doit rester sur la même page que le titre."""
    titre_p = _signet(Paragraph(escape(titre), S["h1"]), titre, cle, 0, ferme)
    if suite:
        return [CondPageBreak(5 * cm), KeepTogether([titre_p] + suite)]
    return [CondPageBreak(5 * cm), titre_p]


def _carte(k, S):
    """Un constat important : liseré de couleur à gauche, texte aéré, preuves encadrées."""
    teinte = TEINTES[k["gravite"]]
    meta = (f"<b>Vérification :</b> {escape(k['verification'])}   ·   <b>Sources :</b> {escape(', '.join(k['sources']))}"
            + (f"   ·   <b>Référence :</b> {escape(k['reference'])}" if k.get("reference") else ""))
    contenu = [
        Paragraph(f'<a name="{k["code"]}"/><font color="{teinte}">{escape(k["gravite"].upper())}</font>'
                  f'<font color="#5b6878">   ·   {k["code"]}</font>', S["etiquette"]),
        Paragraph(escape(k["titre"]), S["h2"]),
        Paragraph(f"<b>Description.</b> {escape(k['description'])}", S["p"]),
        Paragraph(f"<b>Recommandation.</b> {escape(k['recommandation'])}", S["p"]),
        Paragraph("<b>Preuves</b>", S["etiquette"]),
        _bloc_code("\n".join(k["preuves"]), S["code"], largeur=86),
        Paragraph(meta, S["petit"]),
    ]
    carte = Table([["", contenu]], colWidths=[0.2 * cm, LARGEUR - 0.2 * cm])
    carte.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(teinte)), ("BOX", (0, 0), (-1, -1), 0.5, BORD),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 14), ("RIGHTPADDING", (1, 0), (1, 0), 14),
        ("TOPPADDING", (1, 0), (1, 0), 12), ("BOTTOMPADDING", (1, 0), (1, 0), 10)]))
    return _signet(carte, f"{k['code']} — {k['titre']}", f"sig-{k['code']}", 1)


def _ligne_compacte(k, S):
    """Un constat secondaire (Faible, Info) : une ligne de tableau, recommandation et première preuve en dessous."""
    detail = [Paragraph(escape(k["titre"]), S["cell"]),
              Paragraph(f"<b>À faire :</b> {escape(k['recommandation'])}", S["cellp"])]
    if k["preuves"]:
        preuve = k["preuves"][0]
        detail.append(Paragraph(f"<b>Preuve :</b> {escape(preuve if len(preuve) <= 110 else preuve[:108] + ' …')}",
                                S["cellp"]))
    return [Paragraph(f'<a name="{k["code"]}"/>{k["code"]}', S["cell"]),
            _pastille(k["gravite"], COULEURS[k["gravite"]], S), detail, Paragraph(escape(k["verification"]), S["cell"])]


def generer_pdf(r: dict, chemin: Path):
    normal, gras, mono = _polices()
    S = _styles(normal, gras, mono)
    P = lambda txt, st="p": Paragraph(escape(str(txt)), S[st])

    def premiere(canvas, doc):
        canvas.showOutline()                     # ouvre le panneau des signets à l'ouverture du fichier
        pied(canvas, doc)

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont(normal, 8)
        canvas.setFillColor(GRIS)
        if doc.page > 1:
            canvas.drawString(2 * cm, A4[1] - 1.2 * cm, "RIPOSTE — Rapport d'analyse de sécurité")
            canvas.setStrokeColor(BORD)
            canvas.line(2 * cm, A4[1] - 1.35 * cm, 19 * cm, A4[1] - 1.35 * cm)
        canvas.drawString(2 * cm, 1.2 * cm, f"{r['cible']['url']} — {r['date']}")
        canvas.drawRightString(19 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.restoreState()

    importants = [k for k in r["constats"] if k["gravite"] in ("Élevée", "Moyenne")]
    autres = [k for k in r["constats"] if k["gravite"] not in ("Élevée", "Moyenne")]
    sc = r["score"]
    h = []

    # Page de garde
    carte_score = Table([[Paragraph(f"{sc['score']}<font size=14>/100</font>", S["score"])],
                         [Paragraph(escape(sc["niveau"]), ParagraphStyle("n", parent=S["h2"], alignment=TA_CENTER))],
                         [Paragraph(escape(sc["commentaire"]), ParagraphStyle("c", parent=S["petit"], alignment=TA_CENTER))]],
                        colWidths=[7 * cm])
    carte_score.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORD), ("BACKGROUND", (0, 0), (-1, -1), FOND),
                                     ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    garde = [[P("Cible", "cell"), P(r["cible"]["url"], "cell")],
             *([[P("Adresse analysée", "cell"), P(f"{r['cible']['url_analysee']} (redirection vers HTTPS)", "cell")]]
               if r["cible"].get("url_analysee") not in (None, r["cible"]["url"]) else []),
             [P("Adresse" if len(r["cible"]["adresses"]) < 2 else "Adresses", "cell"),
              P(", ".join(r["cible"]["adresses"]), "cell")],
             [P("Date", "cell"), P(r["date"], "cell")],
             [P("Cadre", "cell"), P("Analyse réalisée sur une cible autorisée, dans un cadre pédagogique.", "cell")]]
    h += [Spacer(1, 4 * cm), _signet(Paragraph("Rapport d'analyse de sécurité", S["titre"]), "Page de garde", "garde"),
          Spacer(1, 0.3 * cm), P("Site web et services réseau", "sous"), Spacer(1, 1.6 * cm),
          carte_score, Spacer(1, 1.6 * cm), _tableau(garde, [3.5 * cm, 11 * cm], entete=False), PageBreak()]

    # 1. Synthèse
    c = sc["comptes"]
    h += _section("1. Synthèse", "synthese", S)
    h += [P(r["resume"]), P(origine_resume(r["resume_origine"]), "petit"), Spacer(1, 0.3 * cm)]
    comptes = Table([[Paragraph(f"<font size=16>{c[g]}</font><br/>{g}", S["cellb"]) for g in COULEURS]],
                    colWidths=[LARGEUR / 4] * 4)
    comptes.setStyle(TableStyle([("BACKGROUND", (i, 0), (i, 0), COULEURS[g]) for i, g in enumerate(COULEURS)]
                                + [("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                                   ("LINEAFTER", (0, 0), (2, 0), 2, colors.white)]))
    h += [comptes, Spacer(1, 0.2 * cm),
          P("Ces nombres ne comptent que les constats retenus dans le score (ni faux positifs, ni non confirmés).",
            "petit")]

    # 2. Liste des constats (références cliquables)
    lignes = [[P("Réf.", "cell"), P("Gravité", "cell"), P("Constat", "cell"), P("Vérification", "cell")]]
    for k in r["constats"]:
        lignes.append([Paragraph(f'<a href="#{k["code"]}" color="#1f4e79"><u>{k["code"]}</u></a>', S["cell"]),
                       _pastille(k["gravite"], COULEURS[k["gravite"]], S), P(k["titre"], "cell"),
                       P(k["verification"], "cell")])
    t = _tableau(lignes, [1.2 * cm, 2.2 * cm, 10.8 * cm, 2.8 * cm])
    t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    # Titre et tableau restent d'un seul bloc : ni titre seul en bas de page, ni ligne isolée sur la page suivante.
    h += _section("2. Constats", "constats", S,
                  suite=[t, Spacer(1, 0.15 * cm), P("Cliquer sur une référence mène à son détail.", "petit")])

    # 3. Détail des constats importants
    if importants:
        h += _section("3. Constats à corriger en priorité", "priorite", S, ferme=True,
                      suite=[_carte(importants[0], S), Spacer(1, 0.45 * cm)])
        for k in importants[1:]:
            h += [_carte(k, S), Spacer(1, 0.45 * cm)]

    # 4. Autres constats, en version courte
    if autres:
        h += _section("4. Autres constats", "autres", S)
        lc = [[P("Réf.", "cell"), P("Gravité", "cell"), P("Constat et action", "cell"), P("Vérification", "cell")]]
        lc += [_ligne_compacte(k, S) for k in autres]
        h.append(_tableau(lc, [1.2 * cm, 2.2 * cm, 10.8 * cm, 2.8 * cm]))

    # 5. Ports et services
    h += _section("5. Ports et services détectés", "ports", S)
    if r["ports"]:
        lp = [[P("Port", "cell"), P("État", "cell"), P("Service", "cell"), P("Version", "cell")]]
        lp += [[P(f"{p['numero']}/{p['protocole']}", "cell"), P(p["etat"], "cell"), P(p["service"], "cell"),
                P(p["version"], "cell")] for p in r["ports"]]
        h.append(_tableau(lp, [2.4 * cm, 2.4 * cm, 3 * cm, 9.2 * cm]))
    else:
        h.append(P("Aucun résultat Nmap."))

    # 6. Méthodologie
    h += _section("6. Méthodologie", "methodo", S)
    h += [P("Nmap, Nikto et SSLScan sont lancés en parallèle, chacun avec une durée maximale. Un contrôle des chemins "
            "sensibles (listage de dossiers, copies de sauvegarde, code source) est fait par des requêtes GET en nombre "
            "limité, sous l'adresse analysée."
            + (" Des tests applicatifs de base cherchent une XSS réfléchie (un marqueur texte renvoyé tel quel) et une "
               "injection SQL révélée par une erreur (une apostrophe), dans les formulaires de recherche et de connexion "
               "uniquement : les formulaires qui peuvent modifier des données ne sont jamais envoyés."
               if r.get("applicatif") else "")
            + " Quand la cible est la machine elle-même, l'adresse d'écoute de chaque service est lue avec la commande ss."
            + (" ZAP explore les pages en mode passif : il lit les réponses, sans lancer d'attaque."
               if r.get("zap") else "")),
          P("Chaque constat est ensuite vérifié par des requêtes HTTP de lecture : il est « Confirmé » s'il est "
            "reproduit, « Non confirmé » s'il ne l'est pas, « Faux positif probable » si la vérification le contredit, "
            "et « À vérifier » s'il demande un contrôle manuel.")]
    lm = [[P("Étape", "cell"), P("Version", "cell"), P("Durée", "cell")],
          [P("Vérification directe", "cell"), P("—", "cell"), P(duree(r["durees"].get("Vérification directe")), "cell")]]
    if r.get("chemins"):
        lm.append([P(f"Chemins sensibles ({accord(r['chemins']['requetes'], 'requête GET', 'requêtes GET')})", "cell"),
                   P("—", "cell"), P(duree(r["durees"].get("Chemins sensibles")), "cell")])
    if r.get("applicatif"):
        lm.append([P(f"Tests applicatifs : XSS, injection SQL ({accord(r['applicatif']['points'], 'paramètre')}, "
                     f"{accord(r['applicatif']['requetes'], 'requête')})", "cell"), P("—", "cell"),
                   P(duree(r["durees"].get("Tests applicatifs")), "cell")])
    for nom in ("Nmap", "Nikto", "SSLScan"):
        lm.append([P(nom, "cell"), P(r["versions"].get(nom, ""), "cell"),
                   P(duree(r["durees"][nom]) if nom in r["durees"] else "non lancé", "cell")])
    if r.get("zap"):
        lm.append([P(f"ZAP, analyse passive ({accord(r['zap']['alertes'], 'alerte retenue', 'alertes retenues')})", "cell"),
                   P(r["versions"].get("ZAP", ""), "cell"), P(duree(r["durees"].get("ZAP")), "cell")])
    lm.append([P(etape_resume(r["resume_origine"]), "cell"), P("—", "cell"), P(duree(r["durees"].get("Résumé")), "cell")])
    lm.append([Paragraph("<b>Total</b>", S["cell"]), P("", "cell"), P(duree(r["durees"].get("Total")), "cell")])
    h += [KeepTogether(_tableau(lm, [8.5 * cm, 5.5 * cm, 3 * cm])), Spacer(1, 0.4 * cm),
          Paragraph("<b>Barème.</b> " + escape(sc["bareme"]), S["petit"])]
    if sc.get("perimetre"):
        h.append(Paragraph("<b>Périmètre.</b> " + escape(sc["perimetre"].removeprefix("Périmètre : ")), S["petit"]))

    # Annexe : extraits des sorties brutes (la version complète reste dans le rapport web)
    h += [PageBreak(), _signet(Paragraph("Annexe : extraits des sorties des outils", S["h1"]),
                               "Annexe : sorties des outils", "annexe")]
    h.append(P(f"Pour chaque outil : la commande lancée et les {LIGNES_ANNEXE} premières lignes de sa sortie. "
               "La sortie complète figure dans le rapport web.", "petit"))
    for nom, sortie in r["sorties"].items():
        lignes_sortie = (sortie or "").splitlines()
        extrait = "\n".join(lignes_sortie[:LIGNES_ANNEXE])
        if len(lignes_sortie) > LIGNES_ANNEXE:
            extrait += f"\n… ({accord(len(lignes_sortie) - LIGNES_ANNEXE, 'ligne de plus', 'lignes de plus')})"
        h += [CondPageBreak(4 * cm), Paragraph(escape(nom), S["h2"]), P(r["commandes"].get(nom, ""), "petit"),
              _bloc_code(extrait, S["code"], largeur=100)]

    chemin.parent.mkdir(parents=True, exist_ok=True)
    doc = _Document(str(chemin), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                    bottomMargin=2 * cm, title="Rapport d'analyse de sécurité", author="RIPOSTE")
    doc.build(h, onFirstPage=premiere, onLaterPages=pied)
    return chemin


COULEURS_STATUT = {"Corrigé": colors.HexColor("#15803d"), "Atténué": colors.HexColor("#0f5e8a"),
                   "Plus vérifiable": colors.HexColor("#8a5a00"),
                   "Nouveau": colors.HexColor("#b42318"), "Aggravé": colors.HexColor("#b42318"),
                   "Toujours présent": GRIS}


def generer_pdf_comparaison(c: dict, chemin: Path):
    """PDF d'une page ou deux : scores avant/après et sort de chaque constat (étape S8)."""
    normal, gras, mono = _polices()
    S = _styles(normal, gras, mono)
    P = lambda txt, st="p": Paragraph(escape(str(txt)), S[st])

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setFont(normal, 8)
        canvas.setFillColor(GRIS)
        canvas.drawString(2 * cm, 1.2 * cm, f"Comparaison avant / après — {c['apres']['url']}")
        canvas.drawRightString(19 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.restoreState()

    h = [Paragraph("Comparaison avant / après", S["titre"]), Spacer(1, 0.2 * cm), P(c["apres"]["url"], "sous"),
         Spacer(1, 0.6 * cm)]
    if not c["meme_cible"]:
        h += [P(f"Attention : les deux analyses ne portent pas sur la même adresse ({c['avant']['url']}).", "petit")]
    centre = ParagraphStyle("ce", parent=S["petit"], alignment=TA_CENTER)
    niveau = ParagraphStyle("ni", parent=S["h2"], alignment=TA_CENTER)
    if not c.get("memes_outils", True):
        h += [P("Attention : une seule des deux analyses a utilisé ZAP ; l'écart de score n'est pas directement comparable.", "petit")]
    signe = f"{c['ecart']:+d}"
    couleur_ecart = "#15803d" if c["ecart"] > 0 else "#b42318" if c["ecart"] < 0 else "#5b6878"
    duel = Table([[Paragraph(escape(f"Avant — {c['avant']['date']}"), centre), "",
                   Paragraph(escape(f"Après — {c['apres']['date']}"), centre)],
                  [Paragraph(f"{c['avant']['score']}<font size=14>/100</font>", S["score"]),
                   Paragraph(f"<font color='{couleur_ecart}'>{signe}</font>", S["score"]),
                   Paragraph(f"{c['apres']['score']}<font size=14>/100</font>", S["score"])],
                  [Paragraph(escape(c["avant"]["niveau"]), niveau), "", Paragraph(escape(c["apres"]["niveau"]), niveau)]],
                 colWidths=[6 * cm, 4.5 * cm, 6 * cm])
    duel.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("BOX", (0, 0), (-1, -1), 0.6, BORD),
                              ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f6fa"))]))
    h += [duel, Spacer(1, 0.4 * cm), P(c["bilan"]), Spacer(1, 0.3 * cm),
          Paragraph("Constats qui comptent dans le score", S["h1"])]

    if c["lignes"]:
        lignes = [[P("Statut", "cell"), P("Constat", "cell"), P("Avant", "cell"), P("Après", "cell"), P("Points", "cell")]]
        for i, l in enumerate(c["lignes"], 1):
            av = f"{l['avant']['gravite']}" + ("" if l["points_avant"] else f" ({l['avant']['verification']})") if l["avant"] else "—"
            ap = f"{l['apres']['gravite']}" + ("" if l["points_apres"] else f" ({l['apres']['verification']})") if l["apres"] else "absent"
            lignes.append([_pastille(l["statut"], COULEURS_STATUT[l["statut"]], S, largeur=2.7 * cm), P(l["titre"], "cell"),
                           P(av, "cell"), P(ap, "cell"), P(f"{l['gain']:+d}" if l["gain"] else "0", "cell")])
        t = _tableau(lignes, [3.1 * cm, 7.6 * cm, 2.4 * cm, 2.4 * cm, 1.5 * cm])
        h.append(t)
    else:
        h.append(P("Aucun constat ne retire de points dans ces deux analyses."))
    if c.get("note_version"):
        h += [Spacer(1, 0.2 * cm), P(c["note_version"], "petit")]
    h += [Spacer(1, 0.3 * cm),
          P("« Points » : points regagnés (+) ou perdus (−) sur le score pour ce constat. Barème : Élevée −20, Moyenne −8, "
            "Faible −3, Info 0 ; les constats non confirmés et les faux positifs probables ne sont pas comptés. "
            f"Analyses comparées : {c['avant']['id']} et {c['apres']['id']}.", "petit")]

    chemin.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="Comparaison avant / après", author="Scanner de vulnérabilités")
    doc.build(h, onFirstPage=pied, onLaterPages=pied)
    return chemin
