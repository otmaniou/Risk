"""Modules YaRisk ajoutés au parcours d'analyse des liasses :
  - Fiche client (crédits, garanties, utilisations, Centrale des risques, états financiers, questions / réponses,
    proposition de crédit, RWA) — données bancaires SIMULÉES pour la démonstration ;
  - Traitement en masse (lot de liasses → tableau Excel).
"""
import json
import os
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import bilan_view as bv
import fiche_client as fc
import masse
import ui_theme as ui

GREEN, DARK, RED, GREY, BLUE, AMBER = "#00915A", "#0E2A21", "#C00000", "#8A9A92", "#2F75B5", "#E8A33D"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(p, payload):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(p)


def _alt(chart, **kw):
    st.altair_chart(chart, theme=None, **kw)


def M(v, dec=1):
    """Montant en millions de DZD."""
    return "—" if v is None else fc.fmt(v / 1e6, dec)


def _pct(v, dec=0):
    return "—" if v is None else f"{v * 100:.{dec}f} %".replace(".", ",")


# ===========================================================================
# FICHE CLIENT
# ===========================================================================
def _docs(ddir):
    out = {}
    for f in sorted((ddir / "travail").glob("*.json")) if (ddir / "travail").exists() else []:
        d = _read(f)
        if isinstance(d, dict) and bv.is_v29d(d):
            out[f.stem] = d
    return out


def _nature(docs):
    ns = sorted({masse.nature_of(d) for d in docs.values()})
    return " / ".join(ns) if ns else "—"


def page_fiche(ddir, dossier):
    if not ddir:
        ui.hero("Fiche client", "Aucun dossier ouvert", "Ouvrez un dossier dans la barre latérale (ou créez-en un) pour afficher sa fiche.")
        return
    client = dossier.get("client") or {}
    docs = _docs(ddir)
    cons = bv.consolidate(docs, dossier.get("annees_forcees")) if docs else {"years": []}
    fin = fc.financials(cons) if docs else {}
    fdir = ddir / "fiche"
    sim_p = fdir / "donnees_simulees.json"
    data = _read(sim_p)
    if st.session_state.pop("fiche_regen", False):
        data = None
    if not data:
        data = fc.simulate(client.get("identifiant_national"), client.get("raison_sociale"), fin)
        _write(sim_p, data)
    info = dict(data["client"]); info.update({k: v for k, v in client.items() if v})
    fac, gar = data["facilites"], data["garanties"]
    rows_rwa, tot_rwa, _ = fc.rwa(fac, gar, data["impayes"], st.session_state.get("rwa_params"))
    aut = sum(f["autorisation"] for f in fac); uti = sum(f["utilisation"] for f in fac)
    cr = data["centrale_risques"][-1]
    b, a = sum(cr["bnp"].values()), sum(cr["autres"].values())
    sig = fc.signals(data, fin)
    nh = sum(1 for lv, _ in sig if lv == "HIGH")

    ui.hero("Fiche client · vue 360°", info.get("raison_sociale") or "—",
            "Crédits, utilisations, Centrale des risques, états financiers, questions, proposition et RWA sur un seul écran.",
            chips=[f"NIF {info.get('identifiant_national') or info.get('nif') or '—'}", info.get("secteur_activite"), info.get("segment") or "Corporate",
                   (f"{nh} signal(s) prioritaire(s)", "amber") if nh else ("Aucun signal prioritaire", "mint")],
            side=f"Arrêté des données<br><b>{_d(data['arrete'])}</b>")
    r1, r2 = st.columns([6, 1])
    with r1:
        ui.ribbon("<b>Données de démonstration simulées</b> — autorisations, utilisations, impayés, garanties et Centrale des risques. "
                  "Les états financiers viennent des liasses du dossier.")
    with r2:
        if st.button("🔄 Régénérer", use_container_width=True, help="Recalcule les données simulées à partir des derniers états financiers"):
            st.session_state.fiche_regen = True
            st.rerun()
    y = max(fin) if fin else None
    ui.client_card(
        info.get("raison_sociale") or "—",
        f"RC {info.get('rc', '—')} · {info.get('forme_juridique', '')} · créée en {info.get('date_creation', '—')} · {info.get('effectif', '—')} salariés",
        [("Actionnariat", ui.e(info.get("actionnariat", "—"))), ("Groupe d'affaires", ui.e(info.get("groupe_affaires") or "—")),
         ("Dirigeant", ui.e(info.get("dirigeant", "—"))), ("Dernier exercice", ui.e(f"{y} · {_nature(docs)}" if y else "aucune liasse"))],
        [("Client depuis", ui.e(info.get("relation_depuis", "—"))), ("Agence", ui.e(info.get("agence", "—"))),
         ("Chargé d'affaires", ui.e(info.get("charge_affaires", "—"))),
         ("Dernière revue", ui.e(_d(info.get("date_derniere_revue_annuelle") or info.get("derniere_revue"))))],
        grade=info.get("dernier_rating_valide") or info.get("note_crf"))
    imp = [i for i in data["impayes"] if i["statut"] != "Régularisé"]
    taux = uti / aut if aut else 0
    gv = sum((g.get("valeur") or 0) for g in gar)
    ui.kpis([
        {"label": "Autorisations", "value": M(aut), "unit": "M DZD", "icon": "💳", "sub": f"{len(fac)} lignes de crédit"},
        {"label": "Utilisations", "value": M(uti), "unit": "M DZD", "icon": "📈", "bar": taux, "state": "bad" if taux > 1 else "warn" if taux > .85 else "",
         "sub": f"{taux:.0%} des autorisations", "tone": "amber" if taux > .85 else "green"},
        {"label": "Garanties", "value": M(gv), "unit": "M DZD", "icon": "🛡️", "sub": f"couverture {gv / uti:.0%} des utilisations" if uti else ""},
        {"label": "RWA (CRR)", "value": M(tot_rwa["rwa"]), "unit": "M DZD", "icon": "⚖️", "tone": "blue",
         "sub": f"densité {_pct(tot_rwa['densite'])} · FP {M(tot_rwa['fonds_propres'])} M"},
        {"label": "Part BNP · Centrale", "value": _pct(b / (a + b) if a + b else None), "icon": "🏦", "bar": b / (a + b) if a + b else 0, "tone": "forest",
         "sub": f"{cr['nb_banques']} banques déclarantes"},
        {"label": "Impayés en cours", "value": str(len(imp)), "icon": "⛔" if imp else "✅", "tone": "red" if imp else "mint",
         "sub": f"{M(sum(i['montant'] for i in imp))} M DZD" if imp else "aucun impayé"},
    ])

    tabs = st.tabs(["🚦 Synthèse", "💳 Crédits & garanties", "📈 Utilisations", "🏦 Centrale des risques", "📊 États financiers",
                    "❓ Questions / réponses", "🧭 Proposition", "⚖️ RWA"])
    with tabs[0]:
        _tab_synthese(data, fin, docs)
    with tabs[1]:
        _tab_credits(data, rows_rwa)
    with tabs[2]:
        _tab_utilisations(data)
    with tabs[3]:
        _tab_centrale(data)
    with tabs[4]:
        _tab_etats(fin, docs)
    with tabs[5]:
        _tab_qr(fdir, fin, data)
    with tabs[6]:
        _tab_proposition(fdir, fin, data, info)
    with tabs[7]:
        _tab_rwa(data)


def _d(iso):
    if not iso:
        return "—"
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def _tab_synthese(data, fin, docs):
    sig = fc.signals(data, fin)
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.markdown("#### Signaux à regarder")
        ui.signals(sig)
    with c2:
        st.markdown("#### Utilisation des lignes")
        ui.gauges([(f["libelle"], f["utilisation"] / f["autorisation"] if f["autorisation"] else 0) for f in data["facilites"]])
        st.caption("Trait vertical = autorisation (100 %). Orange ≥ 85 %, rouge = dépassement.")
        st.markdown("#### Dernier exercice")
        if fin:
            y = max(fin); d = fin[y]
            ui.fin_table(f"Exercice {y} · {_nature(docs)}", [(lab, M(d.get(k))) for k, lab in fc.FIN_KEYS])
        else:
            st.markdown('<div class="yr-empty">Aucune liasse dans ce dossier : la fiche montre seulement les données bancaires.</div>', unsafe_allow_html=True)


def _tab_credits(data, rows_rwa):
    rw = {r["id"]: r for r in rows_rwa}
    st.markdown(f"#### Lignes de crédit — arrêté au {_d(data['arrete'])}")
    t = []
    for f in data["facilites"]:
        s = fc.usage_stats(f) if f["type"] not in ("CMT", "LEA") else {}
        t.append({"Ligne": f["libelle"], "Catégorie": fc.CAT_LABELS[f["categorie"]], "Autorisé (M)": f["autorisation"] / 1e6,
                  "Utilisé (M)": f["utilisation"] / 1e6, "Disponible (M)": max(f["autorisation"] - f["utilisation"], 0) / 1e6,
                  "Utilisation": 100 * f["utilisation"] / f["autorisation"] if f["autorisation"] else None,
                  "Moy. 90 j": 100 * s["taux_90j"] if s else float("nan"), "Jours dépass. 90 j": s.get("jours_depassement_90j", float("nan")),
                  "Taux / commission": f"{fc.fmt(f.get('taux'), 2)} %" + (" / an" if f["nature"] == "signature" else ""),
                  "Échéance": _d(f.get("echeance")), "RWA (M)": rw.get(f["id"], {}).get("rwa", 0) / 1e6})
    df = pd.DataFrame(t)
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={
        "Autorisé (M)": st.column_config.NumberColumn(format="%.1f"), "Utilisé (M)": st.column_config.NumberColumn(format="%.1f"),
        "Disponible (M)": st.column_config.NumberColumn(format="%.1f"), "RWA (M)": st.column_config.NumberColumn(format="%.1f"),
        "Utilisation": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=110),
        "Moy. 90 j": st.column_config.NumberColumn(format="%.0f %%"), "Jours dépass. 90 j": st.column_config.NumberColumn(format="%d")})
    st.markdown("#### Garanties")
    g = [{"Garantie": x["libelle"], "Détail": x["detail"], "Montant (M)": (x.get("montant") or 0) / 1e6 or None,
          "Valeur retenue (M)": (x.get("valeur") or 0) / 1e6 or None, "Expertise": _d(x.get("date_expertise")),
          "Échéance": _d(x.get("echeance")), "Lignes couvertes": ", ".join(fc.TYPES[l]["lib"] for l in x["lignes"]),
          "Réduit les RWA (CRR)": "Oui" if x["type"] in fc.CRM else "Non"} for x in data["garanties"]]
    st.dataframe(pd.DataFrame(g), hide_index=True, use_container_width=True,
                 column_config={"Montant (M)": st.column_config.NumberColumn(format="%.1f"), "Valeur retenue (M)": st.column_config.NumberColumn(format="%.1f")})
    st.caption("En approche standard européenne, seules les sûretés financières (dépôt nanti), les garanties d'établissements éligibles "
               "et l'immobilier (sous conditions) réduisent les RWA ; cautions personnelles et nantissements de fonds de commerce ou de matériel "
               "restent des garanties économiques.")
    st.markdown("#### Impayés (12 derniers mois)")
    st.dataframe(pd.DataFrame([{"Date": _d(i["date"]), "Ligne": fc.TYPES[i["ligne"]]["lib"], "Objet": i["objet"], "Montant (M)": i["montant"] / 1e6,
                                "Retard (jours)": i["jours_retard"], "Statut": i["statut"]} for i in data["impayes"]]),
                 hide_index=True, use_container_width=True, column_config={"Montant (M)": st.column_config.NumberColumn(format="%.2f")})


def _facility_chart(f, start):
    n = len(f["serie"])
    dates = pd.date_range(start, periods=n, freq="D")
    df = pd.DataFrame({"Date": dates, "Utilisation": [v / 1e6 for v in f["serie"]], "Autorisation": f["autorisation"] / 1e6})
    df["Dépassement"] = df["Utilisation"].where(df["Utilisation"] > df["Autorisation"] * 1.0001)
    base = alt.Chart(df).encode(x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %y")))
    area = base.mark_area(color=GREEN, opacity=0.35, line={"color": GREEN}).encode(
        y=alt.Y("Utilisation:Q", title="M DZD"), tooltip=[alt.Tooltip("Date:T", format="%d/%m/%Y"), alt.Tooltip("Utilisation:Q", format=",.1f"),
                                                          alt.Tooltip("Autorisation:Q", format=",.1f")])
    lim = base.mark_line(color=DARK, strokeDash=[6, 3], strokeWidth=2).encode(y="Autorisation:Q")
    pts = base.mark_circle(color=RED, size=28).encode(y="Dépassement:Q")
    title = f["libelle"] if f["type"] not in ("CMT", "LEA") else f"{f['libelle']} — capital restant dû"
    return (area + lim + pts).properties(height=210, title=title)


def _tab_utilisations(data):
    st.caption("Utilisation quotidienne (aire verte) et autorisation (trait pointillé) sur 12 mois ; points rouges = dépassements.")
    fac = data["facilites"]
    cols = st.columns(2)
    for i, f in enumerate(fac):
        with cols[i % 2]:
            _alt(_facility_chart(f, data["debut_serie"]), use_container_width=True)
            s = fc.usage_stats(f) if f["type"] not in ("CMT", "LEA") else {}
            if s:
                st.caption(f"Moyenne {_pct(s['taux_moyen'])} · 90 jours {_pct(s['taux_90j'])} · pointe {_pct(s['taux_max'])} · "
                           f"{s['jours_depassement']} jour(s) de dépassement sur 12 mois (max {s['max_consecutifs']} consécutifs)")
            else:
                st.caption(f"Montant initial {M(f['autorisation'])} M · restant dû {M(f['utilisation'])} M · échéance {_d(f.get('echeance'))} · "
                           f"amortissement {f.get('periodicite', '')}")


def _tab_centrale(data):
    cr = data["centrale_risques"]
    st.caption("Déclarations mensuelles à la Centrale des risques de la Banque d'Algérie (simulées) : BNP Paribas El Djazaïr comparé aux autres banques.")
    rows = []
    for m in cr:
        rows.append({"Mois": m["mois"], "Banque": "BNP Paribas El Djazaïr", "Encours (M)": sum(m["bnp"].values()) / 1e6})
        rows.append({"Mois": m["mois"], "Banque": "Autres banques", "Encours (M)": sum(m["autres"].values()) / 1e6})
    df = pd.DataFrame(rows)
    color = alt.Scale(domain=["BNP Paribas El Djazaïr", "Autres banques"], range=[GREEN, GREY])
    bars = alt.Chart(df).mark_bar().encode(x=alt.X("Mois:O", title=None), y=alt.Y("Encours (M):Q", stack="zero", title="M DZD"),
                                           color=alt.Color("Banque:N", scale=color, legend=alt.Legend(orient="top", title=None)),
                                           tooltip=["Mois", "Banque", alt.Tooltip("Encours (M):Q", format=",.1f")])
    share = pd.DataFrame([{"Mois": m["mois"], "Part BNP": sum(m["bnp"].values()) / max(1.0, sum(m["bnp"].values()) + sum(m["autres"].values()))} for m in cr])
    line = alt.Chart(share).mark_line(color=DARK, point=True).encode(x="Mois:O", y=alt.Y("Part BNP:Q", axis=alt.Axis(format="%"), title="Part BNP"),
                                                                     tooltip=["Mois", alt.Tooltip("Part BNP:Q", format=".0%")])
    _alt(alt.layer(bars, line).resolve_scale(y="independent").properties(height=320), use_container_width=True)
    st.markdown("#### Par type de crédit")
    rows = []
    for m in cr:
        for kcat, lab in fc.CAT_LABELS.items():
            rows.append({"Mois": m["mois"], "Type": lab, "BNP": m["bnp"][kcat] / 1e6, "Autres banques": m["autres"][kcat] / 1e6})
    d2 = pd.DataFrame(rows).melt(["Mois", "Type"], var_name="Banque", value_name="Encours (M)")
    ch = alt.Chart(d2).mark_line(point=False).encode(
        x=alt.X("Mois:O", title=None, axis=alt.Axis(labelAngle=-45, labelOverlap=True)), y=alt.Y("Encours (M):Q", title="M DZD"),
        color=alt.Color("Banque:N", scale=alt.Scale(domain=["BNP", "Autres banques"], range=[GREEN, GREY]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["Mois", "Type", "Banque", alt.Tooltip("Encours (M):Q", format=",.1f")]
    ).properties(height=170, width=330).facet(facet=alt.Facet("Type:N", title=None), columns=2)
    _alt(ch, use_container_width=False)
    last, first = cr[-1], cr[-13] if len(cr) >= 13 else cr[0]
    t = [{"Type": lab, "BNP (M)": last["bnp"][kcat] / 1e6, "Autres banques (M)": last["autres"][kcat] / 1e6,
          "Part BNP": 100 * last["bnp"][kcat] / (last["bnp"][kcat] + last["autres"][kcat]) if last["bnp"][kcat] + last["autres"][kcat] else float("nan"),
          "Autres banques, variation 12 mois": 100 * (last["autres"][kcat] / first["autres"][kcat] - 1) if first["autres"][kcat] else float("nan")}
         for kcat, lab in fc.CAT_LABELS.items()]
    st.dataframe(pd.DataFrame(t), hide_index=True, use_container_width=True, column_config={
        "BNP (M)": st.column_config.NumberColumn(format="%.1f"), "Autres banques (M)": st.column_config.NumberColumn(format="%.1f"),
        "Part BNP": st.column_config.NumberColumn(format="%.1f %%"), "Autres banques, variation 12 mois": st.column_config.NumberColumn(format="%.1f %%")})


def _tab_etats(fin, docs):
    if not fin:
        st.info("Aucune liasse extraite pour ce client.")
        return
    ys = sorted(fin)
    st.caption(f"Montants en millions de DZD, issus des liasses du dossier (après corrections de l'analyste) · nature : {_nature(docs)}")
    rows = [[lab] + [M(fin[y].get(k)) for y in ys] for k, lab in fc.FIN_KEYS]
    rows += [["Capacité d'autofinancement (RN + dotations)"] + [M(fin[y].get("caf")) for y in ys]]
    st.dataframe(pd.DataFrame(rows, columns=["Agrégat"] + [str(y) for y in ys]), hide_index=True, use_container_width=True)
    st.markdown("#### Ratios")
    rr = []
    for k, lab, kind in fc.RATIOS:
        vals = []
        for y in ys:
            v = fin[y].get(k)
            vals.append("—" if v is None else _pct(v, 1) if kind == "pct" else f"{v:.2f}".replace(".", ",") if kind == "x" else f"{v:.0f} j")
        rr.append([lab] + vals)
    st.dataframe(pd.DataFrame(rr, columns=["Ratio"] + [str(y) for y in ys]), hide_index=True, use_container_width=True)
    df = pd.DataFrame([{"Exercice": str(y), "Agrégat": lab, "M DZD": (fin[y].get(k) or 0) / 1e6}
                       for y in ys for k, lab in (("ca", "Chiffre d'affaires"), ("ebe", "EBE"), ("rn", "Résultat net"))])
    _alt(alt.Chart(df).mark_bar().encode(
        x=alt.X("Exercice:N", title=None), xOffset="Agrégat:N", y=alt.Y("M DZD:Q"),
        color=alt.Color("Agrégat:N", scale=alt.Scale(range=[DARK, GREEN, AMBER]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["Exercice", "Agrégat", alt.Tooltip("M DZD:Q", format=",.1f")]).properties(height=260), use_container_width=True)


def _tab_qr(fdir, fin, data):
    st.caption("Questions des Risques au commercial, générées à partir des états financiers et du fonctionnement des comptes. "
               "Le commercial répond (après échange avec le client) ; les réponses sont conservées dans le dossier.")
    p = fdir / "questions.json"
    store = _read(p, {}) or {}
    saved = {q["id"]: q for q in store.get("questions", [])}
    v = "".join(ch for ch in str(store.get("maj") or "0") if ch.isdigit())[-8:]   # clés de widgets renouvelées à chaque enregistrement
    auto = fc.questions(fin, data)
    qs = [dict(q, **{k: saved[q["id"]][k] for k in ("reponse", "statut", "repondu_par", "date_reponse") if q["id"] in saved and k in saved[q["id"]]})
          for q in auto] + [q for q in saved.values() if q.get("source") == "manuelle"]
    nb = len(qs); rep = sum(1 for q in qs if q.get("statut") in ("Répondue", "Clôturée"))
    st.progress(rep / nb if nb else 0, text=f"{rep} / {nb} question(s) répondue(s)")
    with st.form("qr_form"):
        for q in qs:
            badge = {"Haute": "🔴", "Moyenne": "🟠", "Basse": "⚪"}.get(q["priorite"], "")
            with st.expander(f"{badge} [{q['theme']}] {q['question']}", expanded=False):
                st.caption(f"Pourquoi : {q['pourquoi']} · priorité {q['priorite']}")
                st.text_area("Réponse du commercial", value=q.get("reponse", ""), key=f"rep_{q['id']}_{v}", height=90)
                c1, c2 = st.columns(2)
                c1.selectbox("Statut", ["Ouverte", "Répondue", "Clôturée"], index=["Ouverte", "Répondue", "Clôturée"].index(q.get("statut", "Ouverte")),
                             key=f"st_{q['id']}_{v}")
                c2.text_input("Répondu par", value=q.get("repondu_par", ""), key=f"by_{q['id']}_{v}")
        if st.form_submit_button("💾 Enregistrer les réponses", type="primary"):
            out = []
            for q in qs:
                q = dict(q)
                r, s_, by = st.session_state.get(f"rep_{q['id']}_{v}", ""), st.session_state.get(f"st_{q['id']}_{v}", "Ouverte"), st.session_state.get(f"by_{q['id']}_{v}", "")
                if (r or "") != (q.get("reponse") or "") or s_ != q.get("statut", "Ouverte"):
                    q["date_reponse"] = _now()
                q.update({"reponse": r, "statut": s_ if not (r and s_ == "Ouverte") else "Répondue", "repondu_par": by})
                out.append(q)
            _write(p, {"questions": out, "maj": _now()})
            st.success("Réponses enregistrées.")
            st.rerun()
    with st.expander("➕ Ajouter une question"):
        with st.form("qr_add", clear_on_submit=True):
            th = st.selectbox("Thème", ["Activité", "Rentabilité", "Structure", "Endettement", "Cycle d'exploitation", "Trésorerie", "Garanties",
                                        "Autres banques", "Gouvernance", "Conformité", "Autre"])
            tx = st.text_area("Question")
            pr = st.selectbox("Priorité", ["Haute", "Moyenne", "Basse"], index=1)
            if st.form_submit_button("Ajouter") and tx.strip():
                import hashlib
                q = {"id": "m" + hashlib.md5((tx + _now()).encode()).hexdigest()[:7], "theme": th, "question": tx.strip(),
                     "pourquoi": "Question ajoutée par l'analyste", "priorite": pr, "source": "manuelle", "statut": "Ouverte"}
                store.setdefault("questions", list(saved.values())).append(q)
                _write(p, store); st.rerun()
    txt = "\n\n".join(f"[{q['priorite']}] {q['theme']} — {q['question']}\nPourquoi : {q['pourquoi']}\nRéponse : {q.get('reponse') or '…'}" for q in qs)
    st.download_button("⬇️ Exporter le questionnaire (texte)", txt.encode("utf-8"), file_name="questions_risques.txt")


def _tab_proposition(fdir, fin, data, info):
    st.caption("Aide à la décision : propositions calculées à partir du dernier exercice et des lignes actuelles. Règles indicatives et paramétrables ; "
               "la proposition reste celle de l'analyste et du comité.")
    if not fin:
        st.info("Il faut au moins une liasse extraite pour calculer une proposition.")
        return
    c1, c2, c3 = st.columns(3)
    nouveau = c1.toggle("Nouveau client (aucune ligne actuelle)", value=False)
    besoin = c2.number_input("Demande de financement moyen terme / leasing (M DZD)", min_value=0.0, value=0.0, step=10.0)
    part_lea = c3.slider("Part en leasing", 0, 100, 30, 5) / 100
    with st.expander("Paramètres des règles"):
        a, b, c = st.columns(3)
        P = {"besoin_mt": besoin * 1e6, "part_leasing": part_lea,
             "jours_ca_fc": a.number_input("Facilité de caisse : jours de CA", 0, 60, 15),
             "quotite_stocks": a.slider("Avances sur marchandises : % des stocks", 0, 100, 50, 5) / 100,
             "quotite_escompte": b.slider("Escompte : % des créances clients", 0, 100, 60, 5) / 100,
             "part_import": b.slider("Part des achats importés", 0, 100, 35, 5) / 100,
             "mois_import": b.number_input("Mois d'achats importés couverts par LC", 1, 12, 3),
             "pct_ca_cautions": c.slider("Cautions : % du CA", 0, 30, 5, 1) / 100,
             "dfin_ebe_max": c.number_input("Dettes financières / EBE maximum", 0.5, 8.0, 3.5, 0.5),
             "gearing_max": c.number_input("Gearing maximum", 0.2, 4.0, 1.2, 0.1)}
    lines, ind = fc.proposal(fin, data, P, nouveau_client=nouveau)
    ui.kpis([
        {"label": f"Chiffre d'affaires {ind['exercice']}", "value": M(ind["ca"]), "unit": "M DZD", "icon": "💰", "tone": "forest"},
        {"label": "EBE", "value": M(ind["ebe"]), "unit": "M DZD", "icon": "⚙️", "sub": f"marge {ind['ebe'] / ind['ca']:.1%}" if ind["ca"] else ""},
        {"label": "BFR d'exploitation", "value": M(ind["bfr"]), "unit": "M DZD", "icon": "🔄", "tone": "blue"},
        {"label": "Fonds de roulement", "value": M(ind["fr"]), "unit": "M DZD", "icon": "🏛️",
         "sub": "couvre le BFR" if ind["fr"] >= ind["bfr"] else f"besoin non couvert {M(ind['bfr'] - ind['fr'])} M"},
        {"label": "Capacité moyen terme", "value": M(ind["capacite_mt"]), "unit": "M DZD", "icon": "🚀", "tone": "mint", "sub": "endettement résiduel possible"},
    ])
    if ind["malus"]:
        st.error("Points de vigilance appliqués (abattement de 30 % sur les lignes de trésorerie) : " + ", ".join(ind["malus"]))
    df = pd.DataFrame([{"Ligne": l["libelle"], "Actuel (M)": l["actuel"] / 1e6, "Proposé (M)": l["propose"] / 1e6,
                        "Variation": 100 * l["variation"] if l["variation"] is not None else float("nan"), "Décision": l["decision"], "Justification": l["justification"],
                        "Garanties proposées": l["garantie"]} for l in lines])
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={
        "Actuel (M)": st.column_config.NumberColumn(format="%.1f"), "Proposé (M)": st.column_config.NumberColumn(format="%.1f"),
        "Variation": st.column_config.NumberColumn(format="%.1f %%"), "Justification": st.column_config.TextColumn(width="large"),
        "Garanties proposées": st.column_config.TextColumn(width="large")})
    # RWA avant / après
    taux = P.get("taux_utilisation_proj", fc.PROP_DEFAULTS["taux_utilisation_proj"])
    limits = {l["id"]: l["propose"] for l in lines}
    usages = {}
    for l in lines:
        t = fc.TYPES[l["id"]]
        usages[l["id"]] = l["propose"] if t.get("amortissable") else l["propose"] * taux
    facs = [f for f in data["facilites"] if f["id"] in limits] if not nouveau else \
        [dict(id=k_, type=k_, libelle=fc.TYPES[k_]["lib"], categorie=fc.TYPES[k_]["cat"], nature=fc.TYPES[k_]["nature"], autorisation=0.0, utilisation=0.0)
         for k_ in limits]
    _, tot_after, _ = fc.rwa(facs, data["garanties"] if not nouveau else [], data["impayes"] if not nouveau else [],
                             st.session_state.get("rwa_params"), limits=limits, usages=usages)
    _, tot_now, _ = fc.rwa(data["facilites"], data["garanties"], data["impayes"], st.session_state.get("rwa_params"))
    d_aut = sum(limits.values()) - (0 if nouveau else sum(f['autorisation'] for f in data['facilites']))
    d_rwa = tot_after['rwa'] - (0 if nouveau else tot_now['rwa'])
    st.markdown("#### Impact de la proposition")
    ui.kpis([
        {"label": "Autorisations proposées", "value": M(sum(limits.values())), "unit": "M DZD", "icon": "🧭", "tone": "forest",
         "sub": f"{'+' if d_aut >= 0 else ''}{M(d_aut)} M vs actuel"},
        {"label": "RWA actuels", "value": M(0 if nouveau else tot_now["rwa"]), "unit": "M DZD", "icon": "⚖️", "tone": "grey"},
        {"label": "RWA après proposition", "value": M(tot_after["rwa"]), "unit": "M DZD", "icon": "📐", "tone": "red" if d_rwa > 0 else "green",
         "sub": f"{'+' if d_rwa >= 0 else ''}{M(d_rwa)} M · utilisation supposée {taux:.0%}"},
        {"label": "Fonds propres consommés", "value": M(tot_after["fonds_propres"]), "unit": "M DZD", "icon": "🏦", "tone": "blue", "sub": "8 % des RWA"},
    ])
    p = fdir / "proposition.json"
    saved = _read(p, {}) or {}
    avis = st.selectbox("Avis de l'analyste", ["À compléter", "Favorable", "Favorable sous conditions", "Défavorable"],
                        index=["À compléter", "Favorable", "Favorable sous conditions", "Défavorable"].index(saved.get("avis", "À compléter")))
    com = st.text_area("Commentaire / conditions", value=saved.get("commentaire", ""), height=100)
    cA, cB = st.columns(2)
    if cA.button("💾 Enregistrer la proposition", type="primary"):
        _write(p, {"date": _now(), "avis": avis, "commentaire": com, "parametres": P, "lignes": lines, "indicateurs": ind,
                   "rwa_apres": tot_after["rwa"], "nouveau_client": nouveau})
        st.success("Proposition enregistrée dans le dossier.")
    note = [f"# Proposition de crédit — {info.get('raison_sociale') or ''}", f"Arrêté des données bancaires : {_d(data['arrete'])} (simulées)",
            f"Base : exercice {ind['exercice']} — CA {M(ind['ca'])} M DZD, EBE {M(ind['ebe'])} M, BFR {M(ind['bfr'])} M, FR {M(ind['fr'])} M", "",
            "| Ligne | Actuel (M DZD) | Proposé (M DZD) | Décision | Garanties |", "|---|---|---|---|---|"]
    note += [f"| {l['libelle']} | {M(l['actuel'])} | {M(l['propose'])} | {l['decision']} | {l['garantie']} |" for l in lines]
    note += ["", f"RWA après proposition : {M(tot_after['rwa'])} M DZD (approche standard CRR, simplifiée)", f"Avis : {avis}", "", com or ""]
    cB.download_button("⬇️ Note de proposition (Markdown)", "\n".join(note).encode("utf-8"), file_name="proposition_credit.md")


def _tab_rwa(data):
    st.caption(f"Actifs pondérés (RWA) des engagements actuels, arrêtés au {_d(data['arrete'])} — approche standard européenne (CRR / CRR3), "
               "version simplifiée pour la démonstration : à valider avec les Risques groupe.")
    with st.expander("Hypothèses de calcul", expanded=False):
        a, b, c = st.columns(3)
        prm = {"rw_corporate": a.number_input("Pondération entreprise non notée", 0.0, 2.0, 1.0, 0.05),
               "rw_defaut": a.number_input("Pondération exposition en défaut", 0.0, 2.0, 1.5, 0.05),
               "rw_banque": b.number_input("Pondération banque garante", 0.0, 1.5, 0.5, 0.05),
               "rw_immo_com": b.number_input("Pondération part garantie par immobilier", 0.0, 1.5, 0.6, 0.05),
               "ccf_engagement": c.number_input("CCF engagement non tiré", 0.0, 1.0, 0.4, 0.05),
               "ccf_revocable": c.number_input("CCF ligne révocable à tout moment", 0.0, 1.0, 0.1, 0.05),
               "facteur_pme": a.toggle("Facteur de soutien PME (0,7619)", value=False),
               "ratio_fp": b.number_input("Exigence de fonds propres", 0.0, 0.3, 0.08, 0.005)}
        st.session_state.rwa_params = prm
        st.markdown("- **EAD** = utilisé × CCF de l'engagement (100 % pour un décaissement, 50 % caution de marché, 20 % lettre de crédit import) "
                    "+ non tiré × CCF d'engagement (40 %, ou 10 % si la ligne est révocable à tout moment).\n"
                    "- **Atténuation** : dépôt nanti déduit de l'EAD ; garantie bancaire → pondération de la banque ; hypothèque → pondération immobilière "
                    "sur la part ≤ 55 % de la valeur du bien.\n"
                    "- **Défaut** : ligne avec un impayé de plus de 90 jours → pondération défaut.\n"
                    "- **RWA** = Σ part × pondération ; **fonds propres** = RWA × exigence.")
    rows, tot, _ = fc.rwa(data["facilites"], data["garanties"], data["impayes"], st.session_state.get("rwa_params"))
    prot = tot["cash"] + tot["garantie_bancaire"] + tot["immobilier"]
    ui.kpis([
        {"label": "Exposition (EAD)", "value": M(tot["ead"]), "unit": "M DZD", "icon": "🎯", "tone": "forest"},
        {"label": "Protections éligibles", "value": M(prot), "unit": "M DZD", "icon": "🛡️", "bar": prot / tot["ead"] if tot["ead"] else 0,
         "sub": f"{prot / tot['ead']:.0%} de l'EAD" if tot["ead"] else ""},
        {"label": "RWA", "value": M(tot["rwa"]), "unit": "M DZD", "icon": "⚖️", "tone": "blue"},
        {"label": "Densité RWA / EAD", "value": _pct(tot["densite"]), "icon": "📊", "bar": tot["densite"] or 0, "tone": "amber"},
        {"label": "Fonds propres consommés", "value": M(tot["fonds_propres"]), "unit": "M DZD", "icon": "🏦", "tone": "mint"},
    ])
    df = pd.DataFrame([{"Ligne": r["libelle"], "Autorisé": r["autorisation"] / 1e6, "Utilisé": r["utilisation"] / 1e6, "Non tiré": r["non_tire"] / 1e6,
                        "CCF tiré": 100 * r["ccf_tire"], "CCF non tiré": 100 * r["ccf_non_tire"], "EAD": r["ead"] / 1e6, "Dépôt nanti": r["cash"] / 1e6,
                        "Garantie bancaire": r["garantie_bancaire"] / 1e6, "Immobilier": r["immobilier"] / 1e6, "Non couvert": r["non_couvert"] / 1e6,
                        "Pondération": 100 * r["rw_contrepartie"], "RWA": r["rwa"] / 1e6, "Densité": 100 * (r["densite"] or 0),
                        "Défaut": "Oui" if r["defaut"] else ""} for r in rows])
    num = {c: st.column_config.NumberColumn(format="%.1f") for c in ("Autorisé", "Utilisé", "Non tiré", "EAD", "Dépôt nanti", "Garantie bancaire",
                                                                       "Immobilier", "Non couvert", "RWA")}
    num.update({c: st.column_config.NumberColumn(format="%.1f %%") for c in ("CCF tiré", "CCF non tiré", "Pondération", "Densité")})
    st.dataframe(df, hide_index=True, use_container_width=True, column_config=num)
    st.caption("Montants en M DZD.")
    d2 = pd.DataFrame([{"Ligne": r["libelle"], "Mesure": m, "M DZD": r[k_] / 1e6} for r in rows for m, k_ in (("EAD", "ead"), ("RWA", "rwa"))])
    _alt(alt.Chart(d2).mark_bar().encode(
        y=alt.Y("Ligne:N", sort=None, title=None), yOffset="Mesure:N", x=alt.X("M DZD:Q"),
        color=alt.Color("Mesure:N", scale=alt.Scale(domain=["EAD", "RWA"], range=[GREY, GREEN]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["Ligne", "Mesure", alt.Tooltip("M DZD:Q", format=",.1f")]).properties(height=300), use_container_width=True)


# ===========================================================================
# TRAITEMENT EN MASSE
# ===========================================================================
def page_masse(dossiers_root, worker_online):
    ui.hero("Traitement en masse", "Des dizaines de liasses, un seul tableau",
            "Le moteur lit chaque PDF, YaRisk calcule les agrégats et les contrôles, vous récupérez un Excel prêt à filtrer.",
            chips=[("Mizan · lecture IA", "mint"), "Contrôles automatiques", "Export Excel", ("Données non revues : usage statistique", "amber")])

    lots_root = Path(dossiers_root) / "_LOTS"
    lots_root.mkdir(parents=True, exist_ok=True)
    with st.expander("➕ Nouveau lot", expanded=not any(lots_root.iterdir())):
        with st.form("lot_form", clear_on_submit=True):
            nom = st.text_input("Nom du lot", placeholder="ex. Corporate — revue annuelle 2025")
            pdfs = st.file_uploader("Liasses PDF (plusieurs fichiers)", type=["pdf"], accept_multiple_files=True)
            jsons = st.file_uploader("ou JSON déjà extraits (V29d, CNRC)", type=["json"], accept_multiple_files=True)
            c1, c2 = st.columns(2)
            go_ = c1.form_submit_button("🚀 Lancer le traitement", type="primary")
            demo = c2.form_submit_button("🧪 Créer un lot de démonstration (100 liasses fictives)")
        if go_ or demo:
            run = datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + uuid.uuid4().hex[:6]
            ldir = lots_root / run
            (ldir / "pdf").mkdir(parents=True)
            (ldir / "extractions").mkdir()
            n = 0
            if demo:
                for k_, d in masse.demo_docs(100).items():
                    _write(ldir / "extractions" / f"{k_}.json", d); n += 1
                nom = nom or "Démonstration — 100 liasses fictives"
            for f in jsons or []:
                try:
                    d = json.loads(f.getvalue())
                except Exception:
                    st.error(f"{f.name} : JSON illisible"); continue
                if bv.is_v29d(d):
                    _write(ldir / "extractions" / (Path(f.name).stem + ".json"), d); n += 1
            for f in pdfs or []:
                data = f.getvalue()
                if data.startswith(b"%PDF-"):
                    (ldir / "pdf" / Path(f.name).name).write_bytes(data)
            nb_pdf = len(list((ldir / "pdf").glob("*.pdf")))
            _write(ldir / "dossier.json", {"lot": True, "nom": nom or run, "created_at": _now(), "client": {"raison_sociale": nom or run},
                                           "statut": "EN_FILE" if nb_pdf else "TERMINE"})
            if nb_pdf:
                _write(ldir / "statut.json", {"etat": "EN_ATTENTE", "demande": _now(), "progression": 0.0,
                                              "fichiers": [{"nom": p.name, "etat": "EN_ATTENTE"} for p in sorted((ldir / "pdf").glob("*.pdf"))]})
            else:
                _write(ldir / "statut.json", {"etat": "TERMINE", "source": "import_json", "progression": 1.0})
            if not nb_pdf and not n:
                shutil.rmtree(ldir, ignore_errors=True); st.error("Aucun fichier exploitable.")
            else:
                st.session_state.lot = str(ldir); st.rerun()
    lots = sorted([p for p in lots_root.iterdir() if (p / "dossier.json").exists()], reverse=True)
    if not lots:
        st.info("Aucun lot pour l'instant.")
        return
    labels = {str(p): f"{(_read(p / 'dossier.json', {}) or {}).get('nom', p.name)} — {p.name[:15]}" for p in lots}
    cur = st.session_state.get("lot") if st.session_state.get("lot") in labels else str(lots[0])
    pick = st.selectbox("Lot", list(labels), index=list(labels).index(cur), format_func=labels.get)
    st.session_state.lot = pick
    running = (_read(Path(pick) / "statut.json", {}) or {}).get("etat") in ("EN_ATTENTE", "EN_COURS")
    st.fragment(_lot_panel, run_every=3 if running else None)(Path(pick), worker_online)


def _lot_panel(ldir, worker_online):
    s = _read(ldir / "statut.json", {}) or {}
    etat = s.get("etat")
    files = s.get("fichiers") or []
    if etat in ("EN_ATTENTE", "EN_COURS"):
        done = sum(1 for f in files if f.get("etat") in ("OK", "ERREUR"))
        st.progress(float(s.get("progression") or 0), text=f"{done} / {len(files)} liasse(s) lue(s) · {s.get('pdf_courant') or ''} {s.get('etape') or ''}")
        if not worker_online:
            st.warning("Le moteur de lecture est hors ligne : le lot sera traité dès le lancement de la cellule worker sur le GPU.")
    rows = masse.summarize_dir(ldir / "extractions")
    if not rows:
        st.info("En attente des premières liasses lues…")
        return
    df = pd.DataFrame(rows)
    ok = int((df["statut"] == "OK").sum())
    n = len(df)
    ui.kpis([
        {"label": "Liasses lues", "value": str(n), "icon": "📄", "sub": f"{df['nif'].nunique() if 'nif' in df else '—'} clients distincts"},
        {"label": "Sans anomalie", "value": str(ok), "icon": "✅", "bar": ok / n if n else 0, "sub": f"{ok / n:.0%} du lot" if n else ""},
        {"label": "À revoir", "value": str(n - ok), "icon": "🔎", "tone": "amber", "state": "warn", "bar": (n - ok) / n if n else 0,
         "sub": "écart actif / passif ou formule"},
        {"label": "CA cumulé", "value": fc.fmt((df['ca'].fillna(0).sum() if 'ca' in df else 0) / 1e9, 1), "unit": "Md DZD", "icon": "💰", "tone": "forest"},
        {"label": "Fonds propres cumulés", "value": fc.fmt((df['fp'].fillna(0).sum() if 'fp' in df else 0) / 1e9, 1), "unit": "Md DZD", "icon": "🏛️", "tone": "blue"},
    ])
    show = df[[c for c, _, _ in masse.COLUMNS if c in df.columns]].copy()
    for c, _, kind in masse.COLUMNS:
        if kind == "p" and c in show:
            show[c] = show[c] * 100
        if kind == "n" and c in show:
            show[c] = show[c] / 1e6
    show = show.rename(columns={c: lab.replace("(DZD)", "(M DZD)") for c, lab, _ in masse.COLUMNS})
    filt = st.radio("Afficher", ["Toutes", "À revoir"], horizontal=True, key=f"filt_{ldir.name}")
    if filt == "À revoir":
        show = show[show["Statut"] != "OK"]
    st.caption("Montants en millions de DZD à l'écran ; l'Excel garde les montants en DZD.")
    cfg = {lab.replace("(DZD)", "(M DZD)"): st.column_config.NumberColumn(format="%.1f") for c, lab, kind in masse.COLUMNS if kind == "n"}
    cfg.update({lab: st.column_config.NumberColumn(format="%.1f %%") for c, lab, kind in masse.COLUMNS if kind == "p"})
    st.dataframe(show, hide_index=True, use_container_width=True, column_config=cfg, height=420)
    try:
        xls = masse.to_excel(rows, (_read(ldir / "dossier.json", {}) or {}).get("nom", ldir.name))
        st.download_button("⬇️ Télécharger l'Excel du lot", xls, file_name=f"YaRisk_lot_{ldir.name}.xlsx", type="primary",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_{ldir.name}")
    except ImportError:
        st.download_button("⬇️ Télécharger (CSV)", show.to_csv(index=False, sep=";").encode("utf-8-sig"), file_name=f"YaRisk_lot_{ldir.name}.csv")
    if "ca" in df and df["ca"].notna().any():
        d2 = df.dropna(subset=["ca", "fp"]).assign(**{"CA (M)": lambda x: x["ca"] / 1e6, "Autonomie": lambda x: x["r_autonomie"],
                                                      "Statut": lambda x: x["statut"]})
        _alt(alt.Chart(d2).mark_circle(size=60, opacity=0.8).encode(
            x=alt.X("CA (M):Q", scale=alt.Scale(type="log"), title="Chiffre d'affaires (M DZD, échelle log)"),
            y=alt.Y("Autonomie:Q", axis=alt.Axis(format="%"), title="Autonomie financière (FP / total bilan)"),
            color=alt.Color("Statut:N", scale=alt.Scale(domain=["OK", "À revoir"], range=[GREEN, RED]), legend=alt.Legend(orient="top", title=None)),
            tooltip=["raison_sociale", "exercice", alt.Tooltip("CA (M):Q", format=",.1f"), alt.Tooltip("Autonomie:Q", format=".0%"), "statut"]
        ).properties(height=320, title="Portefeuille du lot : taille et solidité financière"), use_container_width=True)
