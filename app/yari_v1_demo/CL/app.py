import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone, date
from pathlib import Path

import copy

import streamlit as st

import bilan_view as bv

st.set_page_config(page_title="Ya-Risk | Démo V1", page_icon="📊", layout="wide")
st.title("Ya-Risk | Analyse financière")
st.caption("Pilote mono-opérateur · moteur V29d à connecter · données financières affichées uniquement depuis un JSON importé")

ROOT = Path(os.environ.get("YARISK_DATA_DIR", "./data")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
PERSISTENT = bool(os.environ.get("YARISK_DATA_DIR"))
if not PERSISTENT:
    st.warning("Stockage local de démonstration : définissez YARISK_DATA_DIR vers un volume persistant approuvé avant d'utiliser des données réelles.")

FIELDS = [
    ("identifiant_national", "Identifiant National"),
    ("raison_sociale", "Raison sociale"),
    ("groupe_affaires", "Groupe d'affaires"),
    ("siege", "Siège"),
    ("racine_principale", "Racine principale"),
    ("secteur_activite", "Secteur d'activité"),
    ("sous_secteur_activite", "Sous-secteur d'activité"),
    ("segment", "Segment"),
    ("type_tiers", "Type tiers"),
    ("date_derniere_revue_annuelle", "Date de la dernière revue annuelle"),
    ("dernier_rating_valide", "Dernier rating validé"),
    ("societes_apparentees_engagements_bnpped", "Sociétés apparentées à engagements BNPPED"),
    ("maison_mere_cliente_bnpp_groupe", "Maison mère cliente de BNPP Groupe"),
    ("client_particularites_incidents", "Client avec particularités ou incidents"),
]
TRISTATE = {"societes_apparentees_engagements_bnpped", "maison_mere_cliente_bnpp_groupe", "client_particularites_incidents"}


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def safe_id(value):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)[:90] or "inconnu"


def dossier_path(d):
    return ROOT / "dossiers" / safe_id(d["client"]["identifiant_national"]) / d["execution_id"]


def load_corrections(dossier):
    if dossier is None:
        return []
    log_path = dossier_path(dossier) / "corrections.json"
    try:
        return json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    except ValueError:
        return []


if "dossier" not in st.session_state:
    st.session_state.dossier = None
if "edited" not in st.session_state:
    st.session_state.edited = None

client_tab, import_tab, results_tab, validation_tab, archive_tab = st.tabs([
    "1 · Fiche client", "2 · Import", "3 · Bilan", "4 · Validation", "5 · Archive"
])

with client_tab:
    st.subheader("Identification et profil client")
    st.info("L'identifiant national et la raison sociale sont obligatoires pour préparer un dossier.")
    with st.form("client_form"):
        cols = st.columns(2)
        for i, (key, label) in enumerate(FIELDS):
            with cols[i % 2]:
                if key in TRISTATE:
                    st.selectbox(label, ["Non renseigné", "Oui", "Non"], key=f"field_{key}")
                elif key == "date_derniere_revue_annuelle":
                    st.text_input(label + " (AAAA-MM-JJ)", key=f"field_{key}")
                else:
                    st.text_input(label, key=f"field_{key}")
        st.text_area("Précisions sur les particularités ou incidents", key="field_observations")
        submitted = st.form_submit_button("Enregistrer la fiche dans la session")
    if submitted:
        st.success("Fiche prête. Passez à l'onglet Import.")

with import_tab:
    st.subheader("Préparation du dossier")
    fiscal_year = st.number_input("Exercice fiscal", min_value=1990, max_value=2100, value=2025, step=1)
    pdf = st.file_uploader("Liasse fiscale PDF", type=["pdf"], key="pdf")
    json_file = st.file_uploader("JSON financier existant (optionnel, pour la démonstration)", type=["json"], key="json")
    if st.button("Créer le dossier", type="primary"):
        client = {key: st.session_state.get(f"field_{key}", "") for key, _ in FIELDS}
        client["observations"] = st.session_state.get("field_observations", "")
        if not client["identifiant_national"].strip() or not client["raison_sociale"].strip():
            st.error("Identifiant National et Raison sociale obligatoires.")
        elif pdf is None:
            st.error("Importer une liasse PDF.")
        elif not pdf.getvalue().startswith(b"%PDF-"):
            st.error("Signature PDF non reconnue.")
        else:
            financial = None
            if json_file is not None:
                try:
                    financial = json.loads(json_file.getvalue())
                    if not isinstance(financial, dict):
                        raise ValueError("Le JSON racine doit être un objet.")
                except (ValueError, UnicodeDecodeError) as exc:
                    st.error(f"JSON invalide : {exc}")
                    st.stop()
            run = uuid.uuid4().hex
            dossier = {
                "schema_version": "yarisk-demo-v1", "execution_id": run, "created_at": now(),
                "client": client, "exercice": int(fiscal_year),
                "document": {"nom_original": pdf.name, "sha256": hashlib.sha256(pdf.getvalue()).hexdigest()},
                "extraction": {"statut": "json_importe_non_verifie" if financial is not None else "moteur_non_connecte", "source": json_file.name if json_file else None},
                "validation": {"statut": "non_valide"}
            }
            path = dossier_path(dossier)
            path.mkdir(parents=True, exist_ok=False)
            (path / "source.pdf").write_bytes(pdf.getvalue())
            atomic_json(path / "dossier.json", dossier)
            if financial is not None:
                atomic_json(path / "extraction_originale.json", financial)
            st.session_state.dossier = dossier
            st.session_state.edited = financial
            st.success(f"Dossier créé : {run}")
            if financial is None:
                st.warning("Aucune extraction exécutée. Importez un JSON V29d pour afficher les données.")

with results_tab:
    dossier = st.session_state.dossier
    data = st.session_state.edited
    if dossier is None:
        st.subheader("Bilan — Actif · Passif · TCR")
        st.info("Préparez d'abord un dossier.")
    elif data is None:
        st.subheader("Bilan — Actif · Passif · TCR")
        st.warning("Aucun JSON financier chargé : extraction V29d non connectée à cette V1.")
    elif not bv.is_v29d(data):
        st.subheader("Bilan — Actif · Passif · TCR")
        st.error("Ce JSON ne suit pas le format V29d (pages[].donnees.ACTIF / PASSIF / TCR) : le bilan ne peut pas être reconstitué.")
    else:
        corrections = load_corrections(dossier)
        model = bv.build_model(data, year=dossier.get("exercice"), corrections=corrections)
        year = model["year"]
        ident_json = data.get("identite") or {}
        client = dossier["client"]

        head_l, head_r = st.columns([3, 1])
        with head_l:
            st.subheader(f"Bilan — {client.get('raison_sociale') or ident_json.get('entreprise') or ''} · exercice {year or '?'}")
        with head_r:
            unit = st.radio("Unité", ["KDZD", "DZD"], horizontal=True, key="bilan_unit")
        if year and dossier.get("exercice") and int(year) != int(dossier["exercice"]):
            st.warning(f"Exercice lu dans le JSON ({year}) différent de l'exercice saisi pour le dossier ({dossier['exercice']}). L'affichage suit le JSON.")

        def money(v):
            return "—" if v is None else f"{bv.fmt(v, unit)} {unit}"

        k = st.columns(5)
        k[0].metric(f"Total actif {year}", money(model["actif"][("total_general_actif", "net_n")].value))
        k[1].metric(f"Capitaux propres {year}", money(model["passif"][("total_capitaux_propres", "n")].value))
        k[2].metric(f"Chiffre d'affaires {year}", money(model["tcr"][("chiffre_affaires_net", "n")].value))
        k[3].metric(f"Résultat net {year}", money(model["tcr"][("resultat_net_exercice", "n")].value))
        counts = {lv: sum(1 for a in model["alerts"] if a[3].level == lv) for lv in ("HIGH", "MEDIUM", "LOW")}
        counts["HIGH"] += sum(1 for c in model["cross"] if c["level"] == "HIGH")
        k[4].metric("Alertes", sum(counts.values()) + sum(1 for c in model["cross"] if c["level"] in ("LOW", "MEDIUM")),
                    help=f"HIGH {counts['HIGH']} · MEDIUM {counts['MEDIUM']} · LOW {counts['LOW']} (contrôles recalculés sur la copie de travail)")

        fichier = (data.get("document") or {}).get("fichier_source") or dossier["document"]["nom_original"]

        def ident_rows(table):
            pages = bv.table_pages(data, table)
            src = f"{year} — {fichier}" + (f" — p.{','.join(map(str, pages))}" if pages else "")
            return [("Raison sociale", client.get("raison_sociale") or ident_json.get("entreprise")),
                    ("NIF", client.get("identifiant_national") or ident_json.get("nif_15")),
                    ("Source", src)]

        st.markdown(bv.legend_html(), unsafe_allow_html=True)
        t_actif, t_passif, t_tcr, t_ctrl = st.tabs(["Actif", "Passif", "TCR", f"Contrôles ({len(model['alerts']) + sum(1 for c in model['cross'] if c['level'] != 'OK')})"])
        with t_actif:
            st.markdown(bv.render_actif(model, ident_rows("ACTIF"), unit), unsafe_allow_html=True)
        with t_passif:
            st.markdown(bv.render_passif(model, ident_rows("PASSIF"), unit), unsafe_allow_html=True)
        with t_tcr:
            st.markdown(bv.render_tcr(model, ident_rows("TCR"), unit), unsafe_allow_html=True)
        with t_ctrl:
            st.caption("Contrôles recalculés à chaque affichage : formules du modèle V20 vs montants imprimés, sens débit/crédit du TCR, équilibre du bilan. Survolez une cellule colorée pour le détail.")
            cross_rows = [{"Contrôle": c["controle"], "Exercice": c["exercice"], "Valeur A": bv.fmt(c["a"], unit),
                           "Valeur B": bv.fmt(c["b"], unit), "Écart (DZD)": bv.fmt_dzd(c["ecart"]), "Niveau": c["level"]}
                          for c in model["cross"]]
            if cross_rows:
                st.markdown("**Contrôles croisés**")
                st.dataframe(cross_rows, use_container_width=True, hide_index=True)
            if model["alerts"]:
                order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
                rows_al = sorted(({"Niveau": c.level, "État": etat, "Rubrique": lbl, "Colonne": col, "Détail": c.note,
                                   "Page": c.page or ""} for etat, lbl, col, c in model["alerts"]),
                                 key=lambda r: order.get(r["Niveau"], 9))
                st.markdown("**Écarts par cellule**")
                st.dataframe(rows_al, use_container_width=True, hide_index=True)
            elif not cross_rows:
                st.success("Aucun contrôle calculable.")
            else:
                st.success("Aucun écart de formule détecté.")
            if corrections:
                st.markdown("**Historique des corrections**")
                st.dataframe(corrections, use_container_width=True, hide_index=True)

        st.markdown("#### Corriger une valeur")
        st.caption("La saisie se fait en DZD (unité du JSON V29d). La correction est historisée ; le JSON d'extraction original n'est jamais modifié et la validation est à refaire.")
        c1, c2, c3 = st.columns([1, 3, 2])
        with c1:
            table = st.selectbox("État", ["ACTIF", "PASSIF", "TCR"], format_func=lambda t: bv.TABLE_LABELS[t], key="corr_table")
        with c2:
            rubriques = bv.editable_rows(table)
            rid = st.selectbox("Rubrique", [r for _, r in rubriques], format_func=dict((r, l) for l, r in rubriques).get, key=f"corr_row_{table}")
        with c3:
            cols_opt = bv.column_options(table, year)
            col = st.selectbox("Colonne", [c for c, _ in cols_opt], format_func=dict(cols_opt).get, key=f"corr_col_{table}")
        current = bv.get_value(data, table, rid, col)
        c4, c5 = st.columns([2, 3])
        with c4:
            new_value = st.text_input(f"Nouvelle valeur (DZD) — actuelle : {bv.fmt_dzd(current) if current is not None else 'vide'}",
                                      key=f"edit_{table}_{rid}_{col}", placeholder="vide = effacer la valeur")
        with c5:
            justification = st.text_input("Motif de correction", key="justification")
        if st.button("Appliquer la correction"):
            if not justification.strip():
                st.error("Motif obligatoire.")
            else:
                try:
                    parsed = bv.parse_amount(new_value) if new_value.strip() else None
                    if parsed is not None and parsed == int(parsed):
                        parsed = int(parsed)
                    if parsed == current or (parsed is None and current is None):
                        st.info("Valeur identique : aucune correction enregistrée.")
                    else:
                        changed = copy.deepcopy(data)
                        bv.set_value(changed, table, rid, col, parsed)
                        path = dossier_path(dossier)
                        logs = load_corrections(dossier)
                        logs.append({"date": now(), "champ": f"{table}.{rid}.{col}", "avant": current, "apres": parsed,
                                     "motif": justification.strip()})
                        atomic_json(path / "corrections.json", logs)
                        atomic_json(path / "extraction_corrigee.json", changed)
                        st.session_state.edited = changed
                        st.session_state.dossier["validation"] = {"statut": "non_valide"}
                        atomic_json(path / "dossier.json", st.session_state.dossier)
                        st.success("Correction enregistrée ; validation à refaire.")
                        st.rerun()
                except (ValueError, TypeError) as exc:
                    st.error(f"Correction impossible : {exc}")

with validation_tab:
    st.subheader("Validation métier")
    dossier = st.session_state.dossier
    if dossier is None or st.session_state.edited is None:
        st.info("La validation exige un dossier et un JSON financier.")
    else:
        st.error("Validation financière définitive et génération Excel désactivées : les contrôles V29d ne sont pas encore intégrés à l'interface.")
        st.download_button("Télécharger le JSON de travail (NON VALIDÉ)",
                           json.dumps(st.session_state.edited, ensure_ascii=False, indent=2),
                           file_name="yarisk_travail_non_valide.json", mime="application/json")
        st.button("Valider définitivement", disabled=True)
        st.button("Générer Excel V20", disabled=True)

with archive_tab:
    st.subheader("Dossiers enregistrés")
    st.caption(f"Répertoire : {ROOT}")
    entries = []
    for f in sorted((ROOT / "dossiers").glob("*/*/dossier.json")) if (ROOT / "dossiers").exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            entries.append({"Client": d["client"].get("raison_sociale"), "Identifiant": d["client"].get("identifiant_national"),
                            "Exercice": d.get("exercice"), "Exécution": d.get("execution_id"), "Statut": d.get("validation", {}).get("statut")})
        except (ValueError, KeyError):
            continue
    st.dataframe(entries, use_container_width=True, hide_index=True)
    if not PERSISTENT:
        st.warning("Ces archives ne sont pas garanties persistantes sur Domino sans montage d'un volume ou Dataset approuvé.")

st.divider()
st.caption("Démo technique mono-utilisateur. Aucune authentification métier, isolation multi-utilisateur ni traitement IA automatique dans cette version.")
