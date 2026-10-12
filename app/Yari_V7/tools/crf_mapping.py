"""Ya-Risk — correspondance des rubriques CRF (BNP Paribas Credit Rating Framework) avec la liasse fiscale
algérienne (Série G : Actif, Passif, TCR), telle que reprise dans les feuilles Saisie actif / Saisie passif /
Saisie TCR du modèle ANALYSTE V20.

Syntaxe des expressions (montants de la liasse, en KDZD, convertis en Million DZD par le générateur) :
    A:<rubrique>:brut|amort|net   Actif (Brut, Amortissements & provisions, Net)
    P:<rubrique>                  Passif
    T:<rubrique>                  TCR, solde Crédit − Débit (charge < 0, produit > 0 : convention CRF)
    ...@1                         même rubrique, exercice précédent (variations du tableau de flux)
Les rubriques CRF sans correspondance dans la liasse restent des cellules de saisie analyste.
Niveaux : "OK" = correspondance directe ; "A VALIDER" = choix d'analyste à confirmer (regroupement, approximation).
"""

AB = "Bilan - Actifs"
PB = "Bilan - Passifs"
CR = "Compte de résultat"
TF = "Tableau de Flux de Trésorerie"
RA = "Ratios & Aggregates"
LE = "Leveraged Analysis & ECB"
RO = "Rolling Cash Flow & DettNet"

SHEETS = [AB, PB, CR, TF, RA, LE, RO]
YEAR_COLS = {AB: "BCD", PB: "BCD", CR: "BCD", TF: "BCD", RA: "EFG", RO: "EFG"}   # N, N-1, N-2
NO_INPUT_ROWS = {TF: {16, 78}, RA: {25, 32}, RO: {16}}

_IMMO_BRUT = ("A:immobilisations_incorporelles:brut + A:terrains:brut + A:batiments:brut + A:autres_immobilisations_corporelles:brut"
              " + A:immobilisations_en_concession:brut + A:immobilisations_en_cours:brut")
_AUTRES_ACT = "A:autres_debiteurs:net + A:autres_creances_assimiles:net"
_AUTRES_PAS = "P:impots_passif + P:autres_dettes"

MAPPING = {
    # ------------------------------------------------------------------ Bilan - Actifs
    (AB, 16): ("A:ecarts_acquisition_goodwill:net", "OK", "Écart d'acquisition – goodwill (net)"),
    (AB, 17): ("A:immobilisations_incorporelles:net", "OK", "Immobilisations incorporelles (net)"),
    (AB, 21): ("A:terrains:brut + A:batiments:brut + A:autres_immobilisations_corporelles:brut", "OK",
               "Terrains + bâtiments + autres immobilisations corporelles (brut)"),
    (AB, 22): ("-(A:terrains:amort + A:batiments:amort + A:autres_immobilisations_corporelles:amort)", "OK",
               "Amortissements cumulés des mêmes postes, en négatif"),
    (AB, 29): ("A:immobilisations_en_cours:net", "A VALIDER", "Immobilisations en cours (net), rattachées aux immobilisations corporelles"),
    (AB, 31): ("A:immobilisations_en_concession:net", "A VALIDER",
               "Immobilisations en concession (net) ; à reclasser en corporel si ce ne sont pas des droits de concession"),
    (AB, 34): ("A:autres_participations_creances:net", "OK", "Autres participations et créances rattachées (net)"),
    (AB, 35): ("A:titres_mis_en_equivalence:net", "OK", "Titres mis en équivalence (net)"),
    (AB, 37): ("A:autres_titres_immobilises:net + A:prets_actifs_financiers_non_courants:net", "OK",
               "Autres titres immobilisés + prêts et autres actifs financiers non courants (net)"),
    (AB, 39): ("A:impots_differes_actif:net", "OK", "Impôts différés actif"),
    (AB, 57): ("A:stocks_encours:brut", "A VALIDER", "Stocks et en-cours (brut) : la liasse ne ventile pas MP / produits finis / marchandises"),
    (AB, 58): ("-A:stocks_encours:amort", "A VALIDER", "Pertes de valeur sur stocks, en négatif"),
    (AB, 69): ("A:clients:brut", "OK", "Clients (brut)"),
    (AB, 70): ("-A:clients:amort", "OK", "Pertes de valeur sur clients, en négatif"),
    (AB, 76): ("A:impots_assimiles_actif:net", "OK", "Impôts et assimilés (actif)"),
    (AB, 79): (_AUTRES_ACT, "OK", "Autres débiteurs + autres créances et emplois assimilés (net)"),
    (AB, 82): ("A:placements_financiers_courants:net", "OK", "Placements et autres actifs financiers courants (net)"),
    (AB, 83): ("A:tresorerie_actif:net", "OK", "Trésorerie (actif)"),
    # ------------------------------------------------------------------ Bilan - Passifs
    (PB, 19): ("P:capital_emis - P:capital_non_appele", "OK", "Capital émis − capital non appelé"),
    (PB, 23): ("P:primes_reserves", "A VALIDER", "Primes et réserves (la liasse ne sépare pas primes / réserves : ventiler avec l'annexe)"),
    (PB, 24): ("P:report_a_nouveau", "OK", "Report à nouveau (distribuable)"),
    (PB, 26): ("P:resultat_net_passif", "OK", "Résultat net (passif)"),
    (PB, 34): ("P:ecart_reevaluation + P:ecart_equivalence", "A VALIDER", "Écart de réévaluation + écart d'équivalence"),
    (PB, 42): ("P:provisions_produits_avance", "A VALIDER", "Provisions et produits constatés d'avance (non courants)"),
    (PB, 44): ("P:emprunts_dettes_financieres", "OK", "Emprunts et dettes financières (non courants)"),
    (PB, 51): ("P:autres_dettes_non_courantes", "OK", "Autres dettes non courantes"),
    (PB, 54): ("P:tresorerie_passif", "OK", "Trésorerie passif (concours bancaires courants)"),
    (PB, 60): ("P:impots_differes_provisionnes", "OK", "Impôts différés et provisionnés"),
    (PB, 67): ("P:fournisseurs_rattaches", "OK", "Fournisseurs et comptes rattachés"),
    (PB, 74): ("P:autres_dettes", "OK", "Autres dettes (courantes)"),
    (PB, 76): ("P:impots_passif", "OK", "Impôts (passif)"),
    # ------------------------------------------------------------------ Compte de résultat (Crédit − Débit)
    (CR, 16): ("T:chiffre_affaires_net", "OK", "Chiffre d'affaires net des rabais, remises, ristournes"),
    (CR, 17): ("T:production_stockee_destockee", "OK", "Production stockée ou déstockée"),
    (CR, 18): ("T:production_immobilisee", "OK", "Production immobilisée"),
    (CR, 20): ("T:matieres_premieres + T:autres_approvisionnements", "OK", "Matières premières + autres approvisionnements consommés"),
    (CR, 21): ("T:achats_marchandises_vendues", "OK", "Achats de marchandises vendues"),
    (CR, 25): ("T:variation_stocks", "OK", "Variation des stocks (non ventilée MP / marchandises dans la liasse)"),
    (CR, 26): ("T:achats_etudes_prestations + T:autres_consommations + T:rabais_remises_ristournes_obtenus_achats + T:sous_traitance_generale"
               " + T:entretien_reparations + T:primes_assurances + T:publicite + T:deplacements_missions + T:autres_services"
               " + T:rabais_remises_ristournes_obtenus_services", "OK",
               "Services extérieurs et autres consommations (hors locations, personnel extérieur et honoraires)"),
    (CR, 27): ("T:subvention_exploitation + T:impots_taxes_assimiles + T:autres_produits_operationnels + T:autres_charges_operationnelles",
               "A VALIDER", "Subventions d'exploitation + impôts et taxes + autres produits / charges opérationnels"),
    (CR, 29): ("T:charges_personnel + T:personnel_exterieur + T:remuneration_intermediaires", "OK",
               "Charges de personnel + personnel extérieur + rémunérations d'intermédiaires et honoraires"),
    (CR, 31): ("T:locations", "OK", "Locations"),
    (CR, 33): ("T:dotations_amortissements", "OK", "Dotations aux amortissements"),
    (CR, 37): ("T:reprises_pertes_valeur_provisions", "A VALIDER", "Reprises sur pertes de valeur et provisions"),
    (CR, 38): ("T:provisions + T:pertes_valeur", "A VALIDER", "Dotations aux provisions + pertes de valeur"),
    (CR, 44): ("T:elements_extraordinaires_produits + T:elements_extraordinaires_charges", "A VALIDER",
               "Éléments extraordinaires (produits − charges)"),
    (CR, 47): ("T:charges_financieres", "OK", "Charges financières"),
    (CR, 50): ("T:produits_financiers", "OK", "Produits financiers"),
    (CR, 64): ("T:impots_exigibles_resultats", "OK", "Impôts exigibles sur résultats ordinaires"),
    (CR, 65): ("T:impots_differes_resultats", "OK", "Impôts différés (variations) sur résultats ordinaires"),
    # ------------------------------------------------------------------ Tableau de flux (variations de bilan)
    (TF, 18): ("T:charges_financieres", "A VALIDER", "Charges financières du TCR (intérêts versés supposés égaux aux intérêts comptabilisés)"),
    (TF, 33): ("-(A:stocks_encours:brut - A:stocks_encours:brut@1)", "OK", "− variation des stocks bruts"),
    (TF, 34): ("-(A:clients:brut - A:clients:brut@1)", "OK", "− variation des clients bruts"),
    (TF, 35): ("P:fournisseurs_rattaches - P:fournisseurs_rattaches@1", "OK", "Variation des fournisseurs"),
    (TF, 37): (f"-(({_AUTRES_ACT}) - ({_AUTRES_ACT.replace(':net', ':net@1')})) + ({_AUTRES_PAS}) - ({_AUTRES_PAS.replace('P:impots_passif', 'P:impots_passif@1').replace('P:autres_dettes', 'P:autres_dettes@1')})",
               "OK", "− variation des autres débiteurs / créances + variation des dettes d'impôts et autres dettes"),
    (TF, 38): ("-(A:impots_assimiles_actif:net - A:impots_assimiles_actif:net@1)", "A VALIDER", "− variation des créances d'impôts (actif)"),
    (TF, 41): (f"-(({_IMMO_BRUT}) - ({_IMMO_BRUT.replace(':brut', ':brut@1')}))", "A VALIDER",
               "− variation des immobilisations brutes (incorporelles, corporelles, concession, en cours) ; hors cessions"),
    (TF, 43): ("T:produits_financiers", "A VALIDER", "Produits financiers du TCR (intérêts et dividendes encaissés supposés égaux aux produits comptabilisés)"),
    (TF, 67): ("T:elements_extraordinaires_produits + T:elements_extraordinaires_charges", "A VALIDER", "Éléments extraordinaires du TCR (produits − charges)"),
    (TF, 55): ("-(P:resultat_net_passif@1 - ((P:primes_reserves + P:report_a_nouveau) - (P:primes_reserves@1 + P:report_a_nouveau@1)))",
               "A VALIDER", "Résultat N-1 non mis en réserve (dividendes versés), en négatif"),
    (TF, 58): ("(P:capital_emis - P:capital_non_appele) - (P:capital_emis@1 - P:capital_non_appele@1)", "OK", "Variation du capital"),
    (TF, 66): ("(P:emprunts_dettes_financieres + P:autres_dettes_non_courantes) - (P:emprunts_dettes_financieres@1 + P:autres_dettes_non_courantes@1)",
               "A VALIDER", "Variation nette des emprunts et autres dettes non courantes"),
    (TF, 69): ("-((A:immobilisations_financieres:net - A:impots_differes_actif:net) - (A:immobilisations_financieres:net@1 - A:impots_differes_actif:net@1))",
               "A VALIDER", "− variation des immobilisations financières nettes (hors impôts différés)"),
    (TF, 74): ("P:tresorerie_passif - P:tresorerie_passif@1", "OK", "Variation des concours bancaires courants"),
}

# Cellules du modèle CRF saisies en dur à remplacer par une formule cohérente avec la ligne (même motif que la ligne 28).
CELL_FORMULAS = {
    (RA, "E31"): "=IF(COUNT('Tableau de Flux de Trésorerie'!B39,'Tableau de Flux de Trésorerie'!B18)=0,\"\",IFERROR(ROUND(-'Tableau de Flux de Trésorerie'!B39/'Tableau de Flux de Trésorerie'!B18,1),\"\"))",
    (RA, "F31"): "=IF(COUNT('Tableau de Flux de Trésorerie'!C39,'Tableau de Flux de Trésorerie'!C18)=0,\"\",IFERROR(ROUND(-'Tableau de Flux de Trésorerie'!C39/'Tableau de Flux de Trésorerie'!C18,1),\"\"))",
    (RA, "G31"): "=IF(COUNT('Tableau de Flux de Trésorerie'!D39,'Tableau de Flux de Trésorerie'!D18)=0,\"\",IFERROR(ROUND(-'Tableau de Flux de Trésorerie'!D39/'Tableau de Flux de Trésorerie'!D18,1),\"\"))",
}
