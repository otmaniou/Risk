import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone, date
from pathlib import Path

import streamlit as st

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


def flatten(node, prefix=""):
    result = []
    if isinstance(node, dict):
        for key, val in node.items():
            result.extend(flatten(val, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for i, val in enumerate(node):
            result.extend(flatten(val, f"{prefix}[{i}]"))
    elif isinstance(node, (int, float, str)) and not isinstance(node, bool):
        result.append({"Champ": prefix, "Valeur": node})
    return result


def assign_path(obj, path, value):
    # Editing is limited to already-existing scalar leaf paths.
    parts = re.findall(r"([^\.\[\]]+)|\[(\d+)\]", path)
    keys = [int(b) if b else a for a, b in parts]
    cur = obj
    for key in keys[:-1]:
        cur = cur[key]
    old = cur[keys[-1]]
    if isinstance(old, bool) or not isinstance(old, (str, int, float)):
        raise ValueError("Champ non modifiable")
    if isinstance(old, int):
        value = int(value)
    elif isinstance(old, float):
        value = float(value)
    cur[keys[-1]] = value


if "dossier" not in st.session_state:
    st.session_state.dossier = None
if "edited" not in st.session_state:
    st.session_state.edited = None

client_tab, import_tab, results_tab, validation_tab, archive_tab = st.tabs([
    "1 · Fiche client", "2 · Import", "3 · Résultats JSON", "4 · Validation", "5 · Archive"
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
    st.subheader("Résultats financiers — contrôle avant validation")
    dossier = st.session_state.dossier
    data = st.session_state.edited
    if dossier is None:
        st.info("Préparez d'abord un dossier.")
    elif data is None:
        st.warning("Aucun JSON financier chargé : extraction V29d non connectée à cette V1.")
    else:
        st.caption("Vue générique des données du JSON existant. Les structures V29d seront spécialisées lors de l'intégration du moteur.")
        st.json(data, expanded=False)
        rows = flatten(data)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.markdown("#### Corriger une valeur")
        st.warning("Une correction est historisée et ne modifie jamais le JSON d'extraction original. Les contrôles métier V29d doivent être relancés avant validation finale.")
        if rows:
            selected = st.selectbox("Chemin JSON", [r["Champ"] for r in rows])
            current = next(r["Valeur"] for r in rows if r["Champ"] == selected)
            new_value = st.text_input("Nouvelle valeur", value=str(current), key=f"edit_{selected}")
            justification = st.text_input("Motif de correction", key="justification")
            if st.button("Appliquer la correction"):
                if not justification.strip():
                    st.error("Motif obligatoire.")
                else:
                    import copy
                    changed = copy.deepcopy(data)
                    try:
                        assign_path(changed, selected, new_value)
                        path = dossier_path(dossier)
                        log_path = path / "corrections.json"
                        logs = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
                        logs.append({"date": now(), "champ": selected, "avant": current, "apres": new_value, "motif": justification})
                        atomic_json(log_path, logs)
                        atomic_json(path / "extraction_corrigee.json", changed)
                        st.session_state.edited = changed
                        st.session_state.dossier["validation"] = {"statut": "non_valide"}
                        atomic_json(path / "dossier.json", st.session_state.dossier)
                        st.success("Correction enregistrée ; validation à refaire.")
                        st.rerun()
                    except (KeyError, IndexError, ValueError, TypeError) as exc:
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
