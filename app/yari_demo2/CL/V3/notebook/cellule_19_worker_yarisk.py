# CELLULE 19 — WORKER YA-RISK (POC) : traite automatiquement les dossiers déposés par l'interface web
# -----------------------------------------------------------------------------------------------
# Prérequis : avoir exécuté les cellules 1 à 17 du notebook V29d (modèle Qwen chargé, fonctions définies).
# Astuce : avant la cellule 3, définir YARISK_INPUT_DIR vers un dossier vide pour que les boucles « batch »
# des cellules 11/12/16 ne retraitent pas tout l'historique (voir CELLULE 0 dans le README).
#
# Fonctionnement :
#   - surveille <YARISK_APP_ROOT>/dossiers/*/*/statut.json  (etat = EN_ATTENTE)  -> extraction de chaque PDF
#   - surveille <YARISK_APP_ROOT>/dossiers/*/*/excel_job.json (etat = EN_ATTENTE) -> Excel V20 depuis les JSON validés
#   - écrit sa présence dans <YARISK_APP_ROOT>/worker.json toutes les 5 s (l'interface affiche « moteur prêt »)
# Arrêt : bouton « Interrupt » du notebook.
# La logique d'extraction est celle de la CELLULE 11, sans modification : seul l'appel est encapsulé
# dans une fonction pour publier la progression.

import os, json, time, uuid, shutil, traceback, re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

YARISK_APP_ROOT = Path(os.environ.get("YARISK_APP_ROOT", "/mnt/YARISK_DEMO/V2/data")).resolve()
(YARISK_APP_ROOT / "dossiers").mkdir(parents=True, exist_ok=True)
WORKER_POLL_S = 3
WORKER_HEARTBEAT_S = 5

_REQUIRED = ["pdf_manifest", "route_from_text", "route_with_qwen", "table_for_template", "render_pages", "render_page",
             "ask_batch", "ask_single", "parse_json_strictish", "decode_compact", "count_values", "chunks",
             "build_tcr_review_prompt", "decode_tcr_review", "reconcile_tcr_reads", "_row_has_value", "_row_vector",
             "_vectors_equal", "structure_signature", "extracted_page", "classification_page", "enrich_page_identities",
             "build_document", "run_document_controls", "build_client_excel", "rows_for_template", "log"]
if "fitz" not in globals() or "Image" not in globals():
    raise RuntimeError("Exécutez d'abord la cellule 2 du notebook (imports fitz / PIL)")
_missing = [n for n in _REQUIRED if not callable(globals().get(n))]
if _missing:
    raise RuntimeError("Exécutez d'abord les cellules 1 à 17 du notebook V29d — fonctions manquantes : " + ", ".join(_missing))


def _w_now():
    return datetime.now(timezone.utc).isoformat()


def _w_write(path, payload):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _w_read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


_last_beat = [0.0]
def _heartbeat(etat="pret", dossier=None, force=False):
    if force or time.time() - _last_beat[0] >= WORKER_HEARTBEAT_S or etat == "occupe":
        _w_write(YARISK_APP_ROOT / "worker.json", {"ts": _w_now(), "etat": etat, "dossier": str(dossier) if dossier else None,
                                                   "modele": MODEL_NAME, "version": SCHEMA_REGISTRY_VERSION})
        _last_beat[0] = time.time()


# --------------------------------------------------------------------------------------------
# Extraction d'un PDF — corps de la boucle de la CELLULE 11, encapsulé avec des points de progression
# progress(etape:str, fraction:float 0..1, detail:str)
# --------------------------------------------------------------------------------------------
def extract_one_pdf(pdf_path, cid, progress):
    pdf_path = Path(pdf_path); prefix = f"[APP] "; tpdf = time.time()
    tok_in = tok_out = 0; t_render = t_route = t_extract = 0.0; retries = 0
    progress("Lecture du PDF", 0.02, "")
    t0 = time.time(); manifest = pdf_manifest(pdf_path); t_manifest = time.time() - t0
    routes = {}; unresolved = []
    for p in manifest:
        typ = route_from_text(p.get("text", ""))
        if typ: routes[p["index"]] = (typ, "TEXTE_PDF")
        else: unresolved.append(p["index"])
    progress("Classification des pages", 0.08, f"{len(manifest)} pages, {len(unresolved)} à classer par Qwen")
    dr, dq, di, do = route_with_qwen(pdf_path, manifest, routes, unresolved); t_render += dr; t_route += dq; tok_in += di; tok_out += do

    target = [i for i, (typ, src) in routes.items() if table_for_template(typ) in ACTIVE_TABLES and typ in PROMPTS_EXTRACT]
    counts = Counter(routes.get(i, ("AUTRE", "DEFAULT"))[0] for i in range(len(manifest)))
    log(prefix + pdf_path.name + " | route " + str(dict(counts)))
    progress("Rendu des pages Actif / Passif / TCR", 0.15, f"{len(target)} page(s) financières")

    normal_target = [i for i in target if not routes[i][0].startswith("TCR_")]
    tcr_target = [i for i in target if routes[i][0].startswith("TCR_")]
    rendered = []
    if normal_target:
        t0 = time.time(); rendered += render_pages(pdf_path, normal_target, PDF_EXTRACT_ZOOM, EXTRACT_MAX_SIDE, True); t_render += time.time() - t0
    if tcr_target:
        t0 = time.time(); rendered += render_pages(pdf_path, tcr_target, TCR_EXTRACT_ZOOM, TCR_EXTRACT_MAX_SIDE, True); t_render += time.time() - t0
    by_idx = {p["index"]: p for p in rendered}; extracted = {}
    total_pages = max(1, len(by_idx)); done_pages = 0
    for template in ("ACTIF", "PASSIF", "TCR_FULL", "TCR_P1", "TCR_P2"):
        plist = [by_idx[i] for i in target if i in by_idx and routes[i][0] == template]
        if not plist: continue
        prompt = PROMPTS_EXTRACT[template]
        for batch in chunks(plist, GPU_BATCH_SIZE):
            progress("Lecture Qwen " + template.replace("_", " "), 0.20 + 0.65 * done_pages / total_pages,
                     f"page(s) {', '.join(str(p['index'] + 1) for p in batch)}")
            t0 = time.time(); reps = ask_batch(prompt, [p["image"] for p in batch], SAMPLING_EXTRACT); t_extract += time.time() - t0
            for p, rep in zip(batch, reps):
                tok_in += rep["tokens_in"]; tok_out += rep["tokens_out"]
                raw = parse_json_strictish(rep["text"]); table, rows, ent, unknown = decode_compact(template, raw); nvals = count_values(rows)
                if nvals < MIN_VALUES_RETRY[template]:
                    t1 = time.time()
                    if template.startswith("TCR_"):
                        hd = render_page(pdf_path, p["index"], TCR_REVIEW_ZOOM, TCR_REVIEW_MAX_SIDE, True)
                    else:
                        hd = render_page(pdf_path, p["index"], 3.0, RETRY_MAX_SIDE, True)
                    t_render += time.time() - t1
                    rep2 = ask_single(prompt, hd["image"], SAMPLING_EXTRACT); t_extract += rep2["elapsed"]; tok_in += rep2["tokens_in"]; tok_out += rep2["tokens_out"]; retries += 1
                    raw2 = parse_json_strictish(rep2["text"]); table2, rows2, ent2, unknown2 = decode_compact(template, raw2)
                    if count_values(rows2) > nvals: p, rep, table, rows, ent, unknown = hd, rep2, table2, rows2, ent2, unknown2
                tcr_audit = None
                if template.startswith("TCR_") and TCR_CRITICAL_SECOND_READ:
                    review_rows = [r for r in TCR_CRITICAL_ROWS if r in rows_for_template(template)]
                    if review_rows:
                        progress("Double lecture TCR ciblée", 0.20 + 0.65 * done_pages / total_pages, f"page {p['index'] + 1}")
                        review_img = p if TCR_REVIEW_REUSE_FIRST_IMAGE else render_page(pdf_path, p["index"], TCR_REVIEW_ZOOM, TCR_REVIEW_MAX_SIDE, True)
                        rp, allowed = build_tcr_review_prompt(template, review_rows)
                        rep_review = ask_single(rp, review_img["image"], SAMPLING_REVIEW)
                        t_extract += rep_review["elapsed"]; tok_in += rep_review["tokens_in"]; tok_out += rep_review["tokens_out"]
                        second = decode_tcr_review(template, parse_json_strictish(rep_review["text"]), allowed)
                        informative_second = [rc for rc in review_rows if _row_has_value(_row_vector(second.get(rc, {})))]
                        second_all_null = (len(informative_second) == 0)
                        disagree = []
                        if not second_all_null:
                            for rc in review_rows:
                                fv = _row_vector(rows.get(rc, {}))
                                sv = _row_vector(second.get(rc, {})) if rc in second else (None, None, None, None)
                                if _row_has_value(sv) and not _vectors_equal(fv, sv):
                                    disagree.append(rc)
                        third = None
                        if disagree and TCR_THIRD_READ_ON_DISAGREEMENT:
                            progress("Troisième lecture TCR (désaccord)", 0.20 + 0.65 * done_pages / total_pages, f"{len(disagree)} ligne(s)")
                            t1 = time.time(); review_hd = render_page(pdf_path, p["index"], TCR_REVIEW_ZOOM, TCR_REVIEW_MAX_SIDE, True); t_render += time.time() - t1
                            rp3, allowed3 = build_tcr_review_prompt(template, disagree)
                            rep3 = ask_single(rp3, review_hd["image"], SAMPLING_REVIEW)
                            t_extract += rep3["elapsed"]; tok_in += rep3["tokens_in"]; tok_out += rep3["tokens_out"]; retries += 1
                            third = decode_tcr_review(template, parse_json_strictish(rep3["text"]), allowed3)
                        rows, tcr_audit = reconcile_tcr_reads(rows, second, third, reviewed_rows=review_rows)
                sig = structure_signature(template, rows.keys())
                if routes[p["index"]][1] == "MINI_QWEN" and not sig:
                    log(prefix + f"page {p['index'] + 1}: {template} non confirmé -> AUTRE/A_REVOIR")
                    routes[p["index"]] = ("AUTRE", "REJET_STRUCTURE_SCHEMA")
                    done_pages += 1
                    continue
                ep = extracted_page(p, template, table, rows, ent, pdf_path.name, routes[p["index"]][1], rep, sig, unknown)
                if tcr_audit is not None:
                    ep["audit_lecture_tcr_v29"] = {
                        "mode": "V29C_2E_LECTURE_CIBLEE_REUSE_IMAGE_3E_HD_SI_DESACCORD_INFORMATIF",
                        "colonnes": ["N_DEBIT", "N_CREDIT", "N1_DEBIT", "N1_CREDIT"], "grand_espace_signifie": "CELLULE_VIDE_NULL",
                        "lignes": tcr_audit,
                        "nb_ambigues": sum(1 for a in tcr_audit.values() if str(a.get("status", "")).startswith("AMBIGUOUS")),
                        "nb_lignes_revuees": len(tcr_audit),
                        "nb_corrections": sum(1 for a in tcr_audit.values() if a.get("status") == "CORRECTED_BY_2_REVIEWS")}
                extracted[p["index"]] = ep
                done_pages += 1

    progress("Identité (raison sociale, NIF, exercice)", 0.88, "")
    pages = []
    for mp in manifest:
        idx = mp["index"]
        if idx in extracted: pages.append(extracted[idx])
        else:
            typ, src = routes.get(idx, ("AUTRE", "DEFAULT")); pages.append(classification_page(mp, typ, pdf_path.name, src))
    pages.sort(key=lambda x: x["pdf_page_index"])
    ident_t, ii, io = enrich_page_identities(pdf_path, pages, manifest); tok_in += ii; tok_out += io
    total = time.time() - tpdf
    timings = {"manifest_texte": round(t_manifest, 2), "rendu_images": round(t_render, 2), "route_qwen": round(t_route, 2),
               "extraction_qwen": round(t_extract, 2), **ident_t, "retry_hd": retries, "total": round(total, 2)}
    doc = build_document(pdf_path, pages, timings, (tok_in, tok_out)); doc["document"]["client_dossier"] = cid
    progress("Contrôles déterministes", 0.95, "")
    run_document_controls(doc)
    del rendered, by_idx; gc.collect()
    return doc


# --------------------------------------------------------------------------------------------
# Aperçu des pages Actif / Passif / TCR pour la vue « Liasse PDF » de l'interface
# (rendu ici car PyMuPDF est déjà installé côté notebook : aucune librairie à ajouter dans l'appli)
# --------------------------------------------------------------------------------------------
PREVIEW_ZOOM = 2.0
PREVIEW_JPEG_QUALITY = 78

def render_previews(pdf_path, doc, outdir):
    want = sorted({p.get("numero_page_scannee") for p in doc.get("pages", [])
                   if set((p.get("classification") or {}).get("types") or []) & {"ACTIF", "PASSIF", "TCR"}} - {None})
    if not want: return 0
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    d = fitz.open(str(pdf_path)); n_ok = 0
    try:
        for n in want:
            if n < 1 or n > d.page_count: continue
            pix = d.load_page(n - 1).get_pixmap(matrix=fitz.Matrix(PREVIEW_ZOOM, PREVIEW_ZOOM), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.save(outdir / f"p{n:03d}.jpg", "JPEG", quality=PREVIEW_JPEG_QUALITY, optimize=True); n_ok += 1
    finally:
        d.close()
    return n_ok


# --------------------------------------------------------------------------------------------
# Traitement d'un dossier déposé par l'interface
# --------------------------------------------------------------------------------------------
def process_dossier(ddir):
    sp = ddir / "statut.json"; st_ = _w_read(sp, {}) or {}
    pdfs = sorted((ddir / "pdf").glob("*.pdf"))
    st_.update({"etat": "EN_COURS", "debut": _w_now(), "progression": 0.0, "message": "",
                "fichiers": [{"nom": p.name, "etat": "EN_ATTENTE"} for p in pdfs]})
    _w_write(sp, st_)
    dos = _w_read(ddir / "dossier.json", {}) or {}
    dos["statut"] = "EXTRACTION"; _w_write(ddir / "dossier.json", dos)
    cid = ddir.parent.name
    n = max(1, len(pdfs)); ok = 0
    for i, pdf in enumerate(pdfs):
        f = st_["fichiers"][i]; f["etat"] = "EN_COURS"; t0 = time.time()

        def progress(etape, frac, detail="", _i=i, _pdf=pdf):
            st_.update({"pdf_courant": _pdf.name, "etape": etape, "detail": detail, "progression": round((_i + frac) / n, 4)})
            _w_write(sp, st_); _heartbeat("occupe", ddir)

        try:
            doc = extract_one_pdf(pdf, cid, progress)
            _w_write(ddir / "extractions" / (pdf.stem + ".json"), doc)
            try:
                progress("Aperçu des pages pour la revue", 0.98, "")
                render_previews(pdf, doc, ddir / "apercu" / pdf.stem)
            except Exception as e:  # l'aperçu ne doit jamais faire échouer l'extraction
                log("[APP] aperçu non généré " + pdf.name + " — " + str(e))
            ident = doc.get("identite") or {}
            f.update({"etat": "OK", "annee": ident.get("annee"), "entreprise": ident.get("entreprise"), "nif": ident.get("nif_15"),
                      "duree_s": round(time.time() - t0, 1),
                      "message": f"{sum(1 for p in doc.get('pages', []) if (p.get('classification') or {}).get('extraction_active'))} page(s) financières lues"})
            ok += 1
        except Exception as e:
            f.update({"etat": "ERREUR", "message": f"{type(e).__name__}: {e}", "duree_s": round(time.time() - t0, 1)})
            log("[APP] ERREUR " + pdf.name + " — " + traceback.format_exc())
        st_["progression"] = round((i + 1) / n, 4); _w_write(sp, st_)
    st_.update({"etat": "TERMINE" if ok else "ERREUR", "fin": _w_now(), "progression": 1.0,
                "message": "" if ok else "aucune liasse extraite", "etape": "Terminé", "detail": ""})
    _w_write(sp, st_)


def process_excel(ddir):
    jp = ddir / "excel_job.json"; job = _w_read(jp, {}) or {}
    job.update({"etat": "EN_COURS", "debut": _w_now()}); _w_write(jp, job); _heartbeat("occupe", ddir)
    try:
        docs = [_w_read(f) for f in sorted((ddir / "validation" / "documents").glob("*.json"))]
        docs = [d for d in docs if isinstance(d, dict)]
        if not docs: raise ValueError("aucun JSON validé")
        dos = _w_read(ddir / "dossier.json", {}) or {}
        # Les années forcées dans l'interface (exercice non lu) sont reportées dans l'identité du document.
        forced = dos.get("annees_forcees") or {}
        for f, d in zip(sorted((ddir / "validation" / "documents").glob("*.json")), docs):
            if f.stem in forced and not (d.get("identite") or {}).get("annee"):
                d.setdefault("identite", {})["annee"] = int(forced[f.stem])
        label = re.sub(r"[^A-Za-z0-9_.-]+", "_", (dos.get("client") or {}).get("raison_sociale") or ddir.parent.name)
        out, report = build_client_excel(label, docs)
        target = ddir / "validation" / Path(out).name
        shutil.copy2(out, target)
        job.update({"etat": "TERMINE", "fin": _w_now(), "fichier": target.name,
                    "rapport": {"years": report.get("years"), "formules": report.get("formula_controls_total"),
                                "alertes": report.get("cell_alerts_expected")}})
    except Exception as e:
        job.update({"etat": "ERREUR", "fin": _w_now(), "message": f"{type(e).__name__}: {e}"})
        log("[APP] ERREUR EXCEL " + str(ddir) + " — " + traceback.format_exc())
    _w_write(jp, job)


def _pending(pattern):
    out = []
    for f in (YARISK_APP_ROOT / "dossiers").glob(pattern):
        s = _w_read(f, {}) or {}
        if s.get("etat") == "EN_ATTENTE": out.append((s.get("demande", ""), f.parent))
    return [d for _, d in sorted(out)]


print(f"✅ Worker Ya-Risk démarré — surveille {YARISK_APP_ROOT}/dossiers (Interrupt pour arrêter)")
_heartbeat("pret", force=True)
try:
    while True:
        jobs = _pending("*/*/statut.json")
        if jobs:
            print(f"{datetime.now():%H:%M:%S} → extraction {jobs[0]}")
            process_dossier(jobs[0]); _heartbeat("pret", force=True); continue
        xl = _pending("*/*/excel_job.json")
        if xl:
            print(f"{datetime.now():%H:%M:%S} → Excel V20 {xl[0]}")
            process_excel(xl[0]); _heartbeat("pret", force=True); continue
        _heartbeat("pret")
        time.sleep(WORKER_POLL_S)
except KeyboardInterrupt:
    _w_write(YARISK_APP_ROOT / "worker.json", {"ts": "1970-01-01T00:00:00+00:00", "etat": "arrete"})
    print("⏹️ Worker arrêté")
