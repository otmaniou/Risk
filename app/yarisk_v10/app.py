"""Ya-Risk — POC : liasses fiscales PDF → extraction Qwen (V29d) → Bilan Actif/Passif/TCR → validation → Excel V20.

Parcours guidé, mono-utilisateur. L'extraction est réalisée par le « worker » V29d (dernière cellule du
notebook, sur GPU) qui surveille le même répertoire de données ; l'appli dépose les dossiers et suit leur statut.
"""
import copy
import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import bilan_view as bv
import modules_yr
import saisie_model as sm

st.set_page_config(page_title="Ya-Risk | Analyse financière", page_icon="📊", layout="wide")

ROOT = Path(os.environ.get("YARISK_DATA_DIR", "./data")).resolve()
DOSSIERS = ROOT / "dossiers"
DOSSIERS.mkdir(parents=True, exist_ok=True)
WORKER_FILE = ROOT / "worker.json"
WORKER_TIMEOUT_S = 25

_bilan_grid = components.declare_component("yarisk_bilan_grid", path=str(Path(__file__).resolve().parent / "bilan_grid"))

FIELDS = [
    ("identifiant_national", "Identifiant National (NIF)"),
    ("raison_sociale", "Raison sociale"),
    ("groupe_affaires", "Groupe d'affaires"),
    ("id_rmpm", "ID RMPM"),
    ("siege_racine", "Siège-Racine"),
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
STEPS = ["Dossier", "Extraction", "Bilan", "Validation", "Excel V20"]


# ---------------------------------------------------------------------------
# Outils fichiers
# ---------------------------------------------------------------------------
def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def safe_name(value, maxlen=90):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", str(value or ""))[:maxlen] or "inconnu"


def parse_ts(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def elapsed(start, end=None):
    a, b = parse_ts(start), parse_ts(end) if end else datetime.now(timezone.utc)
    if not a or not b:
        return ""
    s = int((b - a).total_seconds())
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def worker_state():
    w = read_json(WORKER_FILE, {}) or {}
    ts = parse_ts(w.get("ts"))
    online = bool(ts and (datetime.now(timezone.utc) - ts).total_seconds() < WORKER_TIMEOUT_S)
    return online, w


# ---------------------------------------------------------------------------
# Dossier
# ---------------------------------------------------------------------------
def current_dir():
    d = st.session_state.get("dossier_dir")
    return Path(d) if d and Path(d).exists() else None


def load_dossier(ddir):
    return read_json(ddir / "dossier.json", {}) if ddir else {}


def save_dossier(ddir, dossier):
    atomic_json(ddir / "dossier.json", dossier)


def sync_travail(ddir):
    """Copie de travail de chaque extraction (l'original n'est jamais modifié)."""
    (ddir / "travail").mkdir(exist_ok=True)
    for src in sorted((ddir / "extractions").glob("*.json")):
        dst = ddir / "travail" / src.name
        if not dst.exists():
            shutil.copy2(src, dst)


def travail_docs(ddir):
    out = {}
    for f in sorted((ddir / "travail").glob("*.json")) if ddir and (ddir / "travail").exists() else []:
        doc = read_json(f)
        if isinstance(doc, dict) and bv.is_v29d(doc):
            out[f.stem] = doc
    return out


def preview_images(ddir, cons):
    """Images des pages sources (rendues par le worker) : {doc_id: {page: data-URL}}.
    Si l'image manque et que PyMuPDF est disponible dans l'appli, elle est rendue à la volée (facultatif)."""
    import base64
    wanted = {}
    for table in ("ACTIF", "PASSIF", "TCR"):
        for src in (cons["sources"].get(table) or {}).values():
            wanted.setdefault(src["doc"], set()).update(src.get("pages") or [])
    out = {}
    for doc_id, pages in wanted.items():
        for n in sorted(pages):
            img = ddir / "apercu" / doc_id / f"p{int(n):03d}.jpg"
            if not img.exists():
                pdf = ddir / "pdf" / f"{doc_id}.pdf"
                if not pdf.exists():
                    continue
                try:
                    import fitz  # facultatif : présent seulement si l'environnement de l'appli l'a déjà
                    with fitz.open(str(pdf)) as d:
                        if 1 <= int(n) <= d.page_count:
                            img.parent.mkdir(parents=True, exist_ok=True)
                            d.load_page(int(n) - 1).get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(str(img.with_suffix(".png")))
                            img = img.with_suffix(".png")
                except Exception:
                    continue
            if img.exists():
                mime = "image/png" if img.suffix == ".png" else "image/jpeg"
                out.setdefault(doc_id, {})[str(n)] = f"data:{mime};base64," + base64.b64encode(img.read_bytes()).decode()
    return out


def load_corrections(ddir):
    return read_json(ddir / "corrections.json", []) or []


def load_saisie(ddir):
    """Saisies analyste des feuilles Saisie / Etatsfin (KDZD, rangées par exercice)."""
    data = read_json(ddir / "saisie.json", None) or {}
    out = sm.empty_inputs()
    out.update({k: v for k, v in data.items() if k in out})
    return out


def list_dossiers():
    rows = []
    for f in DOSSIERS.glob("*/*/dossier.json"):
        if f.parent.parent.name == "_LOTS":      # lots du traitement en masse
            continue
        d = read_json(f, {})
        if not d:
            continue
        rows.append((d.get("created_at", ""), f.parent, d))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows


def reachable_step(ddir):
    if not ddir:
        return 0
    if travail_docs(ddir):
        d = load_dossier(ddir)
        return 4 if (d.get("validation") or {}).get("statut") == "valide" else 3
    return 1 if (ddir / "statut.json").exists() else 0


def go(step):
    st.session_state.step = step


# ---------------------------------------------------------------------------
# En-tête : moteur + étapes
# ---------------------------------------------------------------------------
st.session_state.setdefault("step", 0)
ddir = current_dir()
dossier = load_dossier(ddir)
online, wstate = worker_state()

MODULES = ["📑 Analyse des liasses", "👤 Fiche client", "📦 Traitement en masse"]
with st.sidebar:
    st.markdown("### Ya-Risk")
    module = st.radio("Module", MODULES, key="module", label_visibility="collapsed")
    if online:
        busy = wstate.get("etat") == "occupe"
        st.success(("🟢 Moteur Qwen V29d : " + ("en cours de traitement" if busy else "prêt")), icon=None)
    else:
        st.warning("🔴 Moteur Qwen V29d hors ligne — lancez la cellule « worker » du notebook sur le GPU.")
    if st.button("➕ Nouveau dossier", use_container_width=True):
        st.session_state.dossier_dir = None
        go(0)
        st.rerun()
    st.markdown("**Dossiers récents**")
    recents = list_dossiers()[:25]
    if recents:
        labels = {str(p): f"{d.get('client', {}).get('raison_sociale') or '?'} — {str(d.get('created_at', ''))[:10]} — {d.get('statut', '')}"
                  for _, p, d in recents}
        pick = st.selectbox("Dossier", list(labels), format_func=labels.get, label_visibility="collapsed")
        if st.button("Ouvrir", use_container_width=True):
            st.session_state.dossier_dir = pick
            go(min(reachable_step(Path(pick)), 2) if reachable_step(Path(pick)) < 4 else 4)
            st.rerun()
    else:
        st.caption("Aucun dossier.")
    st.caption(f"Données : {ROOT}")

client = dossier.get("client", {})
if module == MODULES[1]:
    st.title("Ya-Risk | Fiche client")
    modules_yr.page_fiche(ddir, dossier)
    st.stop()
if module == MODULES[2]:
    st.title("Ya-Risk | Traitement en masse")
    modules_yr.page_masse(DOSSIERS, online)
    st.stop()
st.title("Ya-Risk | Analyse financière")
if client.get("raison_sociale"):
    st.caption(f"{client.get('raison_sociale')} · NIF {client.get('identifiant_national') or '—'} · statut : {dossier.get('statut', '')}")

max_step = reachable_step(ddir)
cols = st.columns(len(STEPS))
for i, name in enumerate(STEPS):
    with cols[i]:
        cur = st.session_state.step == i
        label = ("● " if cur else ("✓ " if i < st.session_state.step else "")) + f"{i + 1}. {name}"
        if st.button(label, key=f"step_{i}", use_container_width=True, type="primary" if cur else "secondary",
                     disabled=i > max_step and not cur):
            go(i)
            st.rerun()
st.divider()


# ---------------------------------------------------------------------------
# Étape 1 — Dossier : fiche client + liasses
# ---------------------------------------------------------------------------
def step_dossier():
    st.subheader("Fiche client et liasses fiscales")
    with st.form("client_form"):
        cols = st.columns(2)
        values = {}
        for i, (key, label) in enumerate(FIELDS):
            with cols[i % 2]:
                cur = client.get(key, "")
                if key in TRISTATE:
                    opts = ["Non renseigné", "Oui", "Non"]
                    values[key] = st.selectbox(label, opts, index=opts.index(cur) if cur in opts else 0)
                elif key == "date_derniere_revue_annuelle":
                    values[key] = st.text_input(label + " (AAAA-MM-JJ)", value=cur)
                elif key == "siege_racine":
                    values[key] = st.text_input(label + " (format 07NNN-NNNNNN)", value=cur, placeholder="07123-456789", max_chars=12)
                else:
                    values[key] = st.text_input(label + (" *" if key in ("identifiant_national", "raison_sociale") else ""), value=cur)
        values["observations"] = st.text_area("Précisions sur les particularités ou incidents", value=client.get("observations", ""))
        st.markdown("**Liasses fiscales** — une liasse PDF par exercice (jusqu'à 5 exercices sont affichés ; chaque liasse donne aussi N-1).")
        pdfs = st.file_uploader("Liasses PDF", type=["pdf"], accept_multiple_files=True)
        with st.expander("Mode démonstration sans moteur : importer des JSON V29d déjà extraits"):
            jsons = st.file_uploader("JSON V29d", type=["json"], accept_multiple_files=True)
        c1, c2 = st.columns([1, 3])
        launch = c1.form_submit_button("🚀 Lancer l'analyse", type="primary")
        update = c2.form_submit_button("Enregistrer la fiche seulement", disabled=ddir is None)

    if update and ddir:
        if values.get("siege_racine") and not re.fullmatch(r"07\d{3}-\d{6}", values["siege_racine"].strip()):
            st.error("Siège-Racine : format attendu 07NNN-NNNNNN (ex. 07123-456789).")
            return
        dossier["client"] = values
        save_dossier(ddir, dossier)
        st.success("Fiche client mise à jour.")
        return
    if not launch:
        if not online:
            st.info("Le moteur Qwen est hors ligne : vous pouvez préparer le dossier, il sera traité dès que la cellule worker sera lancée. "
                    "Pour une démonstration immédiate, utilisez l'import de JSON V29d.")
        return

    if not values["identifiant_national"].strip() or not values["raison_sociale"].strip():
        st.error("Identifiant National et Raison sociale obligatoires.")
        return
    values["siege_racine"] = values.get("siege_racine", "").strip()
    if values["siege_racine"] and not re.fullmatch(r"07\d{3}-\d{6}", values["siege_racine"]):
        st.error("Siège-Racine : format attendu 07NNN-NNNNNN (ex. 07123-456789).")
        return
    if not pdfs and not jsons:
        st.error("Importez au moins une liasse PDF (ou des JSON V29d en mode démonstration).")
        return
    docs_json = []
    for jf in jsons or []:
        try:
            d = json.loads(jf.getvalue())
            if not bv.is_v29d(d):
                raise ValueError("format V29d attendu (pages[].donnees)")
            docs_json.append((jf.name, d))
        except (ValueError, UnicodeDecodeError) as exc:
            st.error(f"{jf.name} : JSON invalide — {exc}")
            return
    seen, files = set(), []
    for f in pdfs or []:
        data = f.getvalue()
        if not data.startswith(b"%PDF-"):
            st.error(f"{f.name} : signature PDF non reconnue.")
            return
        h = hashlib.sha256(data).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        files.append((safe_name(f.name), data, h))

    run = datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + uuid.uuid4().hex[:6]
    new_dir = DOSSIERS / safe_name(values["identifiant_national"]) / run
    (new_dir / "pdf").mkdir(parents=True)
    for name, data, _ in files:
        (new_dir / "pdf" / name).write_bytes(data)
    new = {"schema_version": "yarisk-poc-v2", "execution_id": run, "created_at": now(), "client": values,
           "documents": [{"nom": n, "sha256": h} for n, _, h in files], "statut": "EN_FILE",
           "validation": {"statut": "non_valide"}}
    if docs_json:
        (new_dir / "extractions").mkdir()
        fichiers = []
        for name, d in docs_json:
            atomic_json(new_dir / "extractions" / (Path(safe_name(name)).stem + ".json"), d)
            ident = d.get("identite") or {}
            fichiers.append({"nom": name, "etat": "OK", "annee": ident.get("annee"), "entreprise": ident.get("entreprise"),
                             "nif": ident.get("nif_15"), "message": "JSON importé (démonstration)"})
        atomic_json(new_dir / "statut.json", {"etat": "TERMINE", "source": "import_json", "demande": now(), "debut": now(),
                                              "fin": now(), "progression": 1.0, "fichiers": fichiers})
        new["statut"] = "A_REVOIR"
    else:
        atomic_json(new_dir / "statut.json", {"etat": "EN_ATTENTE", "demande": now(), "progression": 0.0,
                                              "fichiers": [{"nom": n, "etat": "EN_ATTENTE"} for n, _, _ in files]})
    save_dossier(new_dir, new)
    st.session_state.dossier_dir = str(new_dir)
    go(1)
    st.rerun()


# ---------------------------------------------------------------------------
# Étape 2 — Extraction : suivi en direct du worker
# ---------------------------------------------------------------------------
ICON = {"EN_ATTENTE": "⏳", "EN_COURS": "⚙️", "OK": "✅", "ERREUR": "❌"}


@st.fragment(run_every=2)
def extraction_panel():
    d = current_dir()
    if not d:
        st.info("Aucun dossier ouvert.")
        return
    s = read_json(d / "statut.json", {}) or {}
    etat = s.get("etat", "?")
    on, w = worker_state()
    prog = float(s.get("progression") or 0.0)

    if etat == "EN_ATTENTE":
        st.progress(0.0, text="En file d'attente…")
        if not on:
            st.warning("Le moteur Qwen n'est pas lancé. Démarrez la cellule « worker » à la fin du notebook V29d (GPU) : "
                       "le dossier sera pris en charge automatiquement.")
        elif w.get("etat") == "occupe" and w.get("dossier") != str(d):
            st.info("Le moteur termine un autre dossier ; celui-ci démarrera ensuite.")
    elif etat == "EN_COURS":
        txt = f"{int(prog * 100)} % — {s.get('pdf_courant', '')} · {s.get('etape', '')}"
        if s.get("detail"):
            txt += f" · {s['detail']}"
        st.progress(min(max(prog, 0.0), 1.0), text=txt)
        st.caption(f"Temps écoulé : {elapsed(s.get('debut'))}" + ("" if on else " · ⚠️ moteur silencieux depuis plus de 25 s"))
    elif etat == "TERMINE":
        st.progress(1.0, text=f"Extraction terminée en {elapsed(s.get('debut'), s.get('fin'))}" if s.get("source") != "import_json" else "JSON importés")
    elif etat == "ERREUR":
        st.error(f"Extraction en échec : {s.get('message') or 'voir le détail des fichiers'}")

    rows = []
    for f in s.get("fichiers", []):
        rows.append({"": ICON.get(f.get("etat"), "•"), "Liasse": f.get("nom"), "Exercice": str(f.get("annee") or ""),
                     "Raison sociale lue": f.get("entreprise") or "", "NIF lu": f.get("nif") or "",
                     "Durée": f"{f.get('duree_s')} s" if f.get("duree_s") else "", "Message": f.get("message") or ""})
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if etat == "ERREUR" or (etat == "TERMINE" and not list((d / "extractions").glob("*.json"))):
        if st.button("Relancer l'extraction"):
            s.update({"etat": "EN_ATTENTE", "demande": now(), "progression": 0.0, "message": ""})
            for f in s.get("fichiers", []):
                f["etat"] = "EN_ATTENTE"
            atomic_json(d / "statut.json", s)
            st.rerun()
        return

    if etat == "TERMINE":
        sync_travail(d)
        dos = load_dossier(d)
        if dos.get("statut") in ("EN_FILE", "EXTRACTION"):
            dos["statut"] = "A_REVOIR"
            save_dossier(d, dos)
        nif = re.sub(r"\D", "", dos.get("client", {}).get("identifiant_national", ""))
        bad = [f.get("nom") for f in s.get("fichiers", []) if f.get("nif") and nif and re.sub(r"\D", "", f["nif"]) != nif]
        if bad:
            st.warning("NIF lu différent du NIF saisi pour : " + ", ".join(bad) + ". Vérifiez qu'il s'agit bien du même client.")
        cons = bv.consolidate(travail_docs(d), dos.get("annees_forcees"))
        missing = [k for k, y in cons["years_of"].items() if not y]
        if missing:
            st.warning("Exercice non détecté pour certaines liasses : indiquez-le pour continuer.")
            forced = dict(dos.get("annees_forcees") or {})
            for k in missing:
                forced[k] = st.number_input(f"Exercice de {k}", 1990, 2100, datetime.now().year - 1, key=f"y_{k}")
            if st.button("Continuer"):
                dos["annees_forcees"] = forced
                save_dossier(d, dos)
                go(2)
                st.rerun(scope="app")
            return
        key = f"auto_{d.name}"
        if not st.session_state.get(key):
            st.session_state[key] = True
            go(2)
            st.rerun(scope="app")
        if st.button("Ouvrir le bilan →", type="primary"):
            go(2)
            st.rerun(scope="app")


def step_extraction():
    st.subheader("Extraction des liasses par Qwen (V29d)")
    st.caption("Classification des pages, lecture Actif / Passif / TCR, double lecture TCR ciblée, identité et contrôles. "
               "Le bilan s'ouvre automatiquement à la fin.")
    extraction_panel()


# ---------------------------------------------------------------------------
# Étape 3 — Bilan : grille Actif / Passif / TCR / Ratios / Contrôles
# ---------------------------------------------------------------------------
def step_bilan():
    d = ddir
    docs = travail_docs(d) if d else {}
    if not docs:
        st.info("Les liasses ne sont pas encore extraites.")
        return
    cons = bv.consolidate(docs, dossier.get("annees_forcees"))
    corrections = load_corrections(d)
    wbin = load_saisie(d)
    # Données telles que lues par le moteur (avant toute correction) : base de l'indice « à l'extraction »
    orig = {}
    for k in docs:
        o = read_json(d / "extractions" / f"{k}.json")
        if isinstance(o, dict) and bv.is_v29d(o):
            orig[k] = o
    data0 = None
    if len(orig) == len(docs):
        cons0 = bv.consolidate(orig, dossier.get("annees_forcees"))
        if cons0["years"] == cons["years"]:
            data0 = cons0["data"]
    flash = st.session_state.pop("bilan_flash", None)
    if flash:
        st.success(flash)
    if (dossier.get("validation") or {}).get("statut") == "valide":
        st.info("Ce bilan est validé. Toute nouvelle correction annulera la validation (à refaire).")
    ident = [["Raison sociale", client.get("raison_sociale") or ""], ["NIF", client.get("identifiant_national") or ""],
             ["Liasses", " · ".join(f"{bv.doc_label(doc, k)} ({cons['years_of'].get(k) or '?'})" for k, doc in docs.items())]]
    version = hashlib.sha1(json.dumps([cons["data"], len(corrections), wbin["annees"], wbin["etatsfin"], wbin["crf"], wbin["textes"]],
                                      sort_keys=True, default=str).encode()).hexdigest()
    event = _bilan_grid(spec=bv.grid_spec(), years=cons["years"], data=cons["data"], alt=cons["alt"], sources=cons["sources"],
                        warnings=cons["warnings"], ident=ident, data0=data0, conf=cons["conf"], relu=cons["relu"], corr={c.get("cellule"): c for c in corrections if c.get("cellule")},
                        history=corrections, thresholds=bv.THRESHOLDS, tableLabels=bv.TABLE_LABELS, version=version,
                        pages=preview_images(d, cons), tcrP2=sorted(bv.TCR_P2_ROWS),
                        docLabels={k: bv.doc_label(doc, k) for k, doc in docs.items()},
                        wb={"inputs": {k: wbin[k] for k in ("annees", "etatsfin", "crf", "textes")}, "client": client.get("raison_sociale") or ""},
                        key="bilan_grid", default=None)
    if isinstance(event, dict) and event.get("action") == "save" and event.get("nonce") != st.session_state.get("bilan_nonce"):
        st.session_state.bilan_nonce = event.get("nonce")
        try:
            motif = str(event.get("motif") or "").strip()
            changes = event.get("changes") or []
            wb_changes = [c for c in changes if c.get("table") == "WB"]
            changes = [c for c in changes if c.get("table") != "WB"]
            if changes and not motif:
                raise ValueError("motif obligatoire")
            work = copy.deepcopy(docs)
            logs = load_corrections(d)
            touched, applied = set(), 0
            for ch in changes:
                table, rid, colkey = ch.get("table"), ch.get("row"), str(ch.get("col"))
                if table not in bv.GRID_COLS or rid not in bv.allowed_rows(table):
                    raise ValueError(f"cellule non autorisée : {table}.{rid}")
                doc_id, jcol = bv.map_grid_field(cons, table, colkey)
                value = ch.get("value")
                if value is not None:
                    value = float(value)
                    value = int(value) if value == int(value) else value
                before = bv.get_value(work[doc_id], table, rid, jcol)
                if before == value:
                    continue
                bv.set_value(work[doc_id], table, rid, jcol, value)
                touched.add(doc_id)
                applied += 1
                logs.append({"date": now(), "cellule": f"{table}.{rid}.{colkey}", "fichier": bv.doc_label(docs[doc_id], doc_id),
                             "document": doc_id, "champ": f"{table}.{rid}.{jcol}", "avant": before, "apres": value, "motif": motif})
            # Saisies analyste des feuilles Saisie / Etatsfin
            applied_wb, latest = 0, sm.latest_year(cons["years"])
            if wb_changes:
                wb_new = load_saisie(d)
                for ch in wb_changes:
                    sheet, addr, value = ch.get("sheet"), str(ch.get("addr") or ""), ch.get("value")
                    if sm.is_text_input(sheet, addr):
                        tkey = "C3" if (sheet == "Saisie" and addr == "C3") else f"{sheet}!{addr}"
                        before = wb_new["textes"].get(tkey)
                        value = (str(value).strip() or None) if value is not None else None
                        if value is None:
                            wb_new["textes"].pop(tkey, None)
                        else:
                            wb_new["textes"][tkey] = value
                        year = None
                    else:
                        year = sm.year_of_input(latest, sheet, addr) if latest else None
                        if year is None:
                            raise ValueError(f"cellule non saisissable : {sheet}!{addr}")
                        row = "".join(ch_ for ch_ in addr if ch_.isdigit())
                        if sheet in ("Saisie", "Etatsfin"):
                            grp = wb_new["annees" if sheet == "Saisie" else "etatsfin"].setdefault(str(year), {})
                        else:   # feuilles CRF : clé « feuille!ligne »
                            grp = wb_new["crf"].setdefault(str(year), {}); row = f"{sheet}!{row}"
                        before = grp.get(row)
                        if value is None:
                            grp.pop(row, None)
                        else:
                            value = round(float(value), 3)
                            grp[row] = value
                    if before == value:
                        continue
                    applied_wb += 1
                    wb_new["historique"].append({"date": now(), "feuille": sheet, "cellule": addr, "exercice": year,
                                                 "avant": before, "apres": value, "commentaire": motif})
                if applied_wb:
                    atomic_json(d / "saisie.json", wb_new)
            for doc_id in touched:
                atomic_json(d / "travail" / f"{doc_id}.json", work[doc_id])
            if applied:
                atomic_json(d / "corrections.json", logs)
                dossier["statut"] = "A_REVOIR"
            if applied or applied_wb:
                if (dossier.get("validation") or {}).get("statut") == "valide":
                    dossier["validation"] = {"statut": "obsolete", "ancienne": dossier.get("validation")}
                save_dossier(d, dossier)
            parts = []
            if applied or not applied_wb:
                parts.append(f"{applied} correction(s) enregistrée(s) dans les JSON de travail")
            if applied_wb:
                parts.append(f"{applied_wb} saisie(s) Saisie / Etatsfin enregistrée(s)")
            st.session_state.bilan_flash = " · ".join(parts) + "."
            st.rerun()
        except (ValueError, TypeError, KeyError) as exc:
            st.error(f"Enregistrement impossible : {exc}")
    c1, c2 = st.columns([3, 1])
    c2.button("Passer à la validation →", type="primary", use_container_width=True, on_click=go, args=(3,))


# ---------------------------------------------------------------------------
# Étape 4 — Validation
# ---------------------------------------------------------------------------
def step_validation():
    d = ddir
    docs = travail_docs(d) if d else {}
    if not docs:
        st.info("Aucune liasse extraite.")
        return
    cons = bv.consolidate(docs, dossier.get("annees_forcees"))
    ctrl = bv.multi_controls(cons)
    corrections = load_corrections(d)
    st.subheader("Validation du bilan")
    nb = {lv: sum(1 for a in ctrl["alerts"] if a["niveau"] == lv) for lv in ("HIGH", "MEDIUM", "LOW")}
    cross_ko = [c for c in ctrl["cross"] if c["niveau"] != "OK"]
    k = st.columns(5)
    k[0].metric("Exercices", len(cons["years"]), help=", ".join(map(str, cons["years"])))
    k[1].metric("Anomalies HIGH", nb["HIGH"])
    k[2].metric("MEDIUM / LOW", f"{nb['MEDIUM']} / {nb['LOW']}")
    k[3].metric("Contrôles croisés en écart", len(cross_ko))
    k[4].metric("Corrections", len(corrections))
    if ctrl["alerts"] or cross_ko:
        with st.expander("Anomalies restantes", expanded=nb["HIGH"] > 0):
            rows = [{"Niveau": a["niveau"], "Exercice": str(a["annee"]), "État": a["etat"], "Rubrique": a["rubrique"], "Détail": a["detail"]}
                    for a in sorted(ctrl["alerts"], key=lambda a: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[a["niveau"]])]
            rows += [{"Niveau": c["niveau"], "Exercice": str(c["annee"]), "État": "Contrôle", "Rubrique": c["controle"],
                      "Détail": f"écart {bv.fmt_dzd(c['ecart'])} DZD"} for c in cross_ko]
            st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.success("Aucune anomalie : formules, sens TCR, équilibre et cohérence inter-liasses conformes.")

    val = dossier.get("validation") or {}
    if val.get("statut") == "valide":
        st.success(f"Bilan validé par {val.get('par')} le {str(val.get('date', ''))[:16].replace('T', ' ')}.")
        st.button("Aller à l'Excel V20 →", type="primary", on_click=go, args=(4,))
        return
    if val.get("statut") == "obsolete":
        st.warning("Une validation précédente a été annulée par des corrections ultérieures.")

    with st.form("validation_form"):
        who = st.text_input("Validé par", value=st.session_state.get("valideur", ""))
        need_comment = nb["HIGH"] > 0 or bool([c for c in cross_ko if c["niveau"] == "HIGH"])
        comment = st.text_area("Commentaire de validation" + (" (obligatoire : anomalies HIGH restantes)" if need_comment else ""))
        ok = st.form_submit_button("✅ Valider le bilan et générer l'Excel V20", type="primary")
    if not ok:
        return
    if not who.strip():
        st.error("Nom du valideur obligatoire.")
        return
    if need_comment and not comment.strip():
        st.error("Des anomalies HIGH subsistent : un commentaire justifiant la validation est obligatoire.")
        return
    st.session_state.valideur = who.strip()
    vdir = d / "validation"
    if vdir.exists():
        shutil.rmtree(vdir)
    (vdir / "documents").mkdir(parents=True)
    for doc_id, doc in docs.items():
        atomic_json(vdir / "documents" / f"{doc_id}.json", doc)
    wbin = load_saisie(d)
    bundle = {"schema_version": "yarisk-poc-v2", "client": dossier.get("client"), "valide_par": who.strip(), "date": now(),
              "commentaire": comment.strip(), "exercices": cons["years"], "sources": cons["sources"],
              "anomalies_restantes": ctrl, "corrections": corrections, "documents": list(docs), "saisie_analyste": wbin}
    atomic_json(vdir / "bilan_valide.json", bundle)
    # Feuilles Saisie / Etatsfin : écritures reportées par le worker dans l'Excel (mêmes formules que l'écran)
    crf_tpl = Path(__file__).resolve().parent / "bilan_grid" / "crf_template.xlsx"
    if crf_tpl.exists():   # feuilles CRF ajoutées à l'Excel par le worker
        shutil.copy2(crf_tpl, vdir / "crf_template.xlsx")
    atomic_json(vdir / "saisie_excel.json", {"exercices": cons["years"], "modele": sm.load_model().get("source"),
                                            "model_fixes": sm.model_fixes(),
                                            "writes": sm.excel_writes(cons["years"], wbin, (dossier.get("client") or {}).get("raison_sociale"))})
    dossier["validation"] = {"statut": "valide", "par": who.strip(), "date": bundle["date"], "commentaire": comment.strip()}
    dossier["statut"] = "VALIDE"
    save_dossier(d, dossier)
    atomic_json(d / "excel_job.json", {"etat": "EN_ATTENTE", "demande": now()})
    go(4)
    st.rerun()


# ---------------------------------------------------------------------------
# Étape 5 — Excel V20
# ---------------------------------------------------------------------------
@st.fragment(run_every=2)
def excel_panel():
    d = current_dir()
    if not d:
        return
    job = read_json(d / "excel_job.json", {}) or {}
    on, _ = worker_state()
    etat = job.get("etat")
    if etat == "EN_ATTENTE":
        st.progress(0.0, text="Génération de l'Excel V20 en file d'attente…")
        if not on:
            st.warning("Le moteur V29d est hors ligne : l'Excel sera généré dès le lancement de la cellule worker.")
    elif etat == "EN_COURS":
        st.progress(0.5, text=f"Remplissage du modèle V20 et recalcul LibreOffice… ({elapsed(job.get('debut'))})")
    elif etat == "TERMINE":
        f = d / "validation" / (job.get("fichier") or "")
        st.success(f"Excel V20 généré en {elapsed(job.get('debut'), job.get('fin'))}.")
        rep = job.get("rapport") or {}
        if rep:
            st.caption(f"Exercices {rep.get('years')} · formules contrôlées {rep.get('formules')} · alertes portées dans l'Excel {rep.get('alertes')}")
        if f.exists() and f.is_file():
            st.download_button("⬇️ Télécharger l'Excel V20", f.read_bytes(), file_name=f.name, type="primary",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    elif etat == "ERREUR":
        st.error(f"Génération Excel en échec : {job.get('message')}")
        if st.button("Relancer la génération"):
            atomic_json(d / "excel_job.json", {"etat": "EN_ATTENTE", "demande": now()})
            st.rerun()
    else:
        st.info("Validez le bilan pour lancer la génération de l'Excel.")


def step_excel():
    st.subheader("Excel ANALYSTE V20")
    val = dossier.get("validation") or {}
    if val.get("statut") != "valide":
        st.info("Le bilan doit être validé avant la génération de l'Excel.")
        return
    st.caption(f"Bilan validé par {val.get('par')} le {str(val.get('date', ''))[:16].replace('T', ' ')}. "
               "L'Excel est produit par le moteur V29d à partir des JSON validés (modèle V20, formules recalculées, alertes en commentaire).")
    excel_panel()
    vb = ddir / "validation" / "bilan_valide.json"
    if vb.exists():
        st.download_button("⬇️ JSON du bilan validé", vb.read_bytes(), file_name=f"{safe_name(client.get('raison_sociale'))}_bilan_valide.json",
                           mime="application/json")


[step_dossier, step_extraction, step_bilan, step_validation, step_excel][st.session_state.step]()
st.divider()
st.caption("POC mono-utilisateur — aucune authentification ni isolation multi-utilisateur.")
