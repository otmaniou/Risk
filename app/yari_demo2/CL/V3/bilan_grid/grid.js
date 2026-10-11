/* Ya-Risk — grille Bilan multi-exercices (Actif / Passif / TCR / Ratios / Contrôles)
 * Reproduit les feuilles Saisie du modèle ANALYSTE V20 : saisie dans les cellules, formules
 * recalculées en direct, anomalies >= 1 000 DZD, contrôles inter-liasses.
 * Clé de cellule : TABLE.rubrique.ANNEE:col   (col = brut|amort|net pour l'Actif, v pour le Passif, debit|credit pour le TCR)
 */
(function () {
  "use strict";
  // ---------- Protocole composant Streamlit ----------
  function send(type, extra) { window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, extra || {}), "*"); }
  var lastH = -1;
  function setHeight() {
    var h = document.getElementById("app").getBoundingClientRect().height + 14;
    if (Math.abs(h - lastH) < 2) return;
    lastH = h; send("streamlit:setFrameHeight", { height: h });
  }
  var A = null, VERSION = null, LASTSIG = null, YEARS = [];
  var S = { tab: "ACTIF", unit: "KDZD", pending: {}, undo: [], sel: null, edit: null, preview: null, motif: "", saving: false, msg: "",
            pdf: { open: false, doc: null, page: null, zoom: 100, follow: true } };
  var BLOBS = {}, BLOBSIG = null; // images des pages de liasse converties en URL blob (une seule fois)
  var M = null, M0 = null, M0VER = null, NOPEND = false, PREV = {}, NEXT = {}, HL = { dep: {}, pre: {} };

  window.addEventListener("message", function (ev) {
    var d = ev.data;
    if (!d || d.type !== "streamlit:render") return;
    var a = d.args || {}, sig = JSON.stringify(a);
    if (sig === LASTSIG) return;
    LASTSIG = sig;
    if (a.version !== VERSION) { VERSION = a.version; S.pending = {}; S.undo = []; S.saving = false; S.motif = ""; S.edit = null; S.preview = null; S.msg = ""; }
    A = a; YEARS = (a.years || []).map(Number);
    loadBlobs();
    render();
  });
  send("streamlit:componentReady", { apiVersion: 1 });
  if (window.ResizeObserver) new ResizeObserver(setHeight).observe(document.getElementById("app"));

  // ---------- Pages de liasse (aperçu PDF) ----------
  function loadBlobs() {
    var pages = A.pages || {}, sig = Object.keys(pages).map(function (d) { return d + ":" + Object.keys(pages[d]).join(","); }).join("|") + "#" + JSON.stringify(pages).length;
    if (sig === BLOBSIG) return;
    Object.keys(BLOBS).forEach(function (d) { Object.keys(BLOBS[d]).forEach(function (p) { URL.revokeObjectURL(BLOBS[d][p]); }); });
    BLOBS = {}; BLOBSIG = sig;
    Object.keys(pages).forEach(function (d) {
      BLOBS[d] = {};
      Object.keys(pages[d]).forEach(function (p) {
        var u = pages[d][p], i = u.indexOf(","), mime = u.slice(5, u.indexOf(";")), bin = atob(u.slice(i + 1)), arr = new Uint8Array(bin.length);
        for (var j = 0; j < bin.length; j++) arr[j] = bin.charCodeAt(j);
        BLOBS[d][p] = URL.createObjectURL(new Blob([arr], { type: mime }));
      });
    });
  }
  function pageFor(t, r, y) {
    var s = srcOf(t, y); if (!s || !s.pages || !s.pages.length) return null;
    var pg = s.pages[0];
    if (t === "TCR" && s.pages.length > 1 && (A.tcrP2 || []).indexOf(r) >= 0) pg = s.pages[s.pages.length - 1];
    return { doc: s.doc, page: String(pg), src: s };
  }
  function followSel() {
    if (!S.pdf.open || !S.pdf.follow || !S.sel) return;
    var q = splitK(S.sel), f = pageFor(q.t, q.r, q.y);
    if (f) { S.pdf.doc = f.doc; S.pdf.page = f.page; }
  }
  function pageTags(doc) {
    var tags = {};
    ["ACTIF", "PASSIF", "TCR"].forEach(function (t) {
      Object.keys((A.sources || {})[t] || {}).forEach(function (y) {
        var s = A.sources[t][y]; if (s.doc !== doc) return;
        (s.pages || []).forEach(function (p) { tags[p] = tags[p] || []; if (tags[p].indexOf(A.tableLabels[t]) < 0) tags[p].push(A.tableLabels[t]); });
      });
    });
    return tags;
  }
  function renderPdf() {
    var h = '<div class="pcol"><div class="ph">';
    if (!S.pdf.doc) {
      var first = Object.keys(BLOBS)[0];
      if (first) { S.pdf.doc = first; S.pdf.page = Object.keys(BLOBS[first]).sort(function (a, b) { return a - b; })[0]; }
    }
    var docs = Object.keys(BLOBS);
    if (!docs.length) return h + '<b>Liasse PDF</b><span class="sp"></span><button data-pdfclose="1">✕</button></div><div class="empty">Aucun aperçu disponible pour ce dossier. Les images des pages sont produites par le moteur V29d lors de l’extraction (dossiers importés en JSON sans PDF : pas d’aperçu).</div></div>';
    h += "<b>" + esc((A.docLabels || {})[S.pdf.doc] || S.pdf.doc) + "</b>";
    if (docs.length > 1) docs.forEach(function (d) { if (d !== S.pdf.doc) h += '<button data-pdfdoc="' + esc(d) + '" title="Autre liasse">' + esc((A.docLabels || {})[d] || d) + "</button>"; });
    h += '</div><div class="ph">';
    var tags = pageTags(S.pdf.doc);
    Object.keys(BLOBS[S.pdf.doc] || {}).sort(function (a, b) { return a - b; }).forEach(function (p) {
      h += '<button data-pdfpage="' + p + '" class="' + (p === S.pdf.page ? "on" : "") + '">p.' + p + (tags[p] ? " · " + tags[p].join("/") : "") + "</button>";
    });
    h += '<span class="sp"></span><button data-zoom="-1" title="Zoom arrière">−</button><button data-zoom="0" title="Ajuster à la largeur">' + S.pdf.zoom + ' %</button><button data-zoom="1" title="Zoom avant">+</button>';
    h += '<button data-pdffollow="1" class="' + (S.pdf.follow ? "on" : "") + '" title="La page suit la cellule sélectionnée">Suivre la sélection</button><button data-pdfclose="1" title="Fermer">✕</button></div>';
    if (S.sel) {
      var q = splitK(S.sel), s = srcOf(q.t, q.y);
      if (s) {
        var col = q.t === "ACTIF" ? (s.period === "N" ? "colonnes Brut / Amort. / Net (exercice N)" : "colonne Net de l’exercice N-1") :
          q.t === "PASSIF" ? (s.period === "N" ? "colonne N" : "colonne N-1") : (s.period === "N" ? "colonnes Débit / Crédit N" : "colonnes Débit / Crédit N-1");
        h += '<div class="hint">« ' + esc(A.spec[q.t].labels[q.r]) + " » " + q.y + " : liasse " + esc(s.fichier) + " — " + col + "</div>";
      }
    }
    var url = (BLOBS[S.pdf.doc] || {})[S.pdf.page];
    h += '<div class="pb">' + (url ? '<img src="' + url + '" style="width:' + S.pdf.zoom + '%" alt="Page ' + esc(S.pdf.page) + '">' : '<div class="empty">Page non disponible.</div>') + "</div></div>";
    return h;
  }

  // ---------- Formats ----------
  function grp(s) { return s.replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function fd(v) { return v === null || v === undefined ? "" : grp(String(Math.round(v))); }
  function fu(v) { if (v === null || v === undefined) return ""; var r = Math.round(S.unit === "KDZD" ? v / 1000 : v); return r === 0 ? "0" : grp(String(r)); }
  function editStr(v) { if (v === null || v === undefined) return ""; var x = S.unit === "KDZD" ? v / 1000 : v; return String(Number(x.toFixed(S.unit === "KDZD" ? 3 : 2))).replace(".", ","); }
  function parseIn(s) {
    s = String(s || "").replace(/[\s  ]/g, "");
    if (s === "" || s === "-") return { ok: true, v: null };
    var neg = /^\(.*\)$/.test(s); s = s.replace(/[()]/g, "");
    if (s.indexOf(",") >= 0 && s.indexOf(".") < 0) s = s.replace(",", "."); else s = s.replace(/,/g, "");
    if (!/^[-+]?\d*\.?\d+$/.test(s)) return { ok: false };
    var x = Number(s); if (neg) x = -x; if (S.unit === "KDZD") x = x * 1000;
    return { ok: true, v: Math.round(x * 100) / 100 };
  }
  function esc(s) { return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function nz(v) { return v === null || v === undefined ? null : v; }
  function splitK(k) { var p = k.split("."), yc = p[2].split(":"); return { t: p[0], r: p[1], ck: p[2], y: Number(yc[0]), c: yc[1] }; }
  var COLNAME = { brut: "Brut", amort: "Amort.", net: "Net", v: "", debit: "Débit", credit: "Crédit" };
  function colLabel(t, ck) { var yc = ck.split(":"); return (COLNAME[yc[1]] ? COLNAME[yc[1]] + " " : "") + yc[0]; }
  function srcOf(t, y) { return ((A.sources || {})[t] || {})[String(y)] || null; }
  function canEdit(t, y, c) { var s = srcOf(t, y); if (!s) return false; if (t === "ACTIF" && s.period === "N1" && c !== "net") return false; return true; }

  // ---------- Données : base (liasses + corrections enregistrées) + modifications en cours + saisie en cours ----------
  function baseVal(t, r, ck) { return nz(((A.data[t] || {})[r] || {})[ck]); }
  function rowsOf(t) {
    var base = A.data[t] || {}, out = {}, r, k;
    for (r in base) out[r] = Object.assign({}, base[r]);
    if (NOPEND) return out;
    function put(key, v) { var q = key.split("."); if (q[0] !== t) return; out[q[1]] = out[q[1]] || {}; if (v === null) delete out[q[1]][q[2]]; else out[q[1]][q[2]] = v; }
    for (k in S.pending) put(k, S.pending[k].value);
    if (S.preview) put(S.preview.k, S.preview.v);
    return out;
  }
  function curVal(k) { if (k in S.pending) return S.pending[k].value; var q = k.split("."); return baseVal(q[0], q[1], q[2]); }

  // ---------- Moteur de calcul (formules V20) ----------
  function level(g) { var a = Math.abs(g || 0), th = A.thresholds; if (a < th.min) return "OK"; if (a < th.medium) return "LOW"; if (a < th.high) return "MEDIUM"; return "HIGH"; }
  var LR = { OK: 0, LOW: 1, MEDIUM: 2, HIGH: 3 };
  function cmp(c, lab) {
    if (c.observed !== null && c.computed !== null) {
      var g = c.observed - c.computed; c.level = level(g);
      if (c.level !== "OK") c.note = "Liasse " + fd(c.observed) + " · " + lab + " " + fd(c.computed) + " · écart " + fd(g) + " DZD";
    }
  }
  function computeBalance(t) {
    var sp = A.spec[t], R = rowsOf(t), out = {};
    function obs(r, ck) { return nz((R[r] || {})[ck]); }
    function leaf(r, ck) {
      var k = r + "|" + ck; if (out[k]) return out[k].value;
      var o = obs(r, ck), c = { value: o, observed: o, computed: null, kind: "input", level: "OK", note: "" };
      var yc = ck.split(":");
      if (t === "ACTIF" && yc[1] === "net") {
        var b = obs(r, yc[0] + ":brut"), a = obs(r, yc[0] + ":amort");
        if (b !== null || a !== null) { c.kind = "formula"; c.computed = (b || 0) - (a || 0); c.value = c.computed; c.formula = "= Brut − Amortissements"; cmp(c, "Brut − Amort."); }
      }
      out[k] = c; return c.value;
    }
    function val(r, ck) {
      var f = sp.formulas[r]; if (!f) return leaf(r, ck);
      var k = r + "|" + ck; if (out[k]) return out[k].value;
      var pres = [];
      for (var i = 0; i < f.length; i++) { var v = val(f[i][0], ck); if (v !== null) pres.push(v * f[i][1]); }
      var o = r.charAt(0) === "_" ? null : obs(r, ck);
      var c = { value: null, observed: o, computed: null, kind: "formula", level: "OK", note: "" };
      c.formula = "= " + f.map(function (x, j) { return (j ? (x[1] < 0 ? " − " : " + ") : (x[1] < 0 ? "− " : "")) + (sp.labels[x[0]] || x[0]); }).join("");
      if (pres.length) { c.computed = pres.reduce(function (a, b) { return a + b; }, 0); c.value = c.computed; cmp(c, "Calculé"); }
      else { c.value = o; if (o !== null) c.note = "Composantes absentes : montant imprimé repris tel quel."; }
      out[k] = c; return c.value;
    }
    sp.layout.forEach(function (row) { YEARS.forEach(function (y) { sp.cols.forEach(function (c) { val(row[1], y + ":" + c); }); }); });
    return out;
  }
  function computeTCR() {
    var sp = A.spec.TCR, R = rowsOf("TCR"), out = {};
    function net(r, y) { var v = R[r] || {}, d = nz(v[y + ":debit"]), c = nz(v[y + ":credit"]); if (d === null && c === null) return null; return (c || 0) - (d || 0); }
    function f(r, y) {
      var k = r + "|" + y; if (out[k]) return out[k].value;
      var o = net(r, y), vals = R[r] || {}, c, fo = sp.formulas[r];
      if (fo) {
        c = { observed: o, kind: "formula", level: "OK", note: "", computed: null, value: null };
        c.formula = "= Σ (crédit − débit) : " + fo.map(function (x) { return sp.labels[x] || x; }).join(" + ");
        var parts = fo.map(function (x) { return f(x, y); }).filter(function (x) { return x !== null; });
        if (parts.length) {
          c.computed = parts.reduce(function (a, b) { return a + b; }, 0); c.value = c.computed; cmp(c, "Calculé");
          if (Math.abs(c.computed) > 1e-9) {
            var wc = y + (c.computed > 0 ? ":debit" : ":credit"), w = nz(vals[wc]);
            if (w !== null && Math.abs(w) > 1e-9) { c.level = "HIGH"; c.wrongSide = wc; c.note = (c.note ? c.note + " · " : "") + "Montant imprimé côté " + (c.computed > 0 ? "DÉBIT" : "CRÉDIT") + " alors que le solde recalculé est " + (c.computed > 0 ? "créditeur" : "débiteur"); }
          }
        } else c.value = o;
      } else {
        c = { value: o, observed: o, kind: "input", level: "OK", note: "" };
        var e = sp.side[r];
        if (e) {
          var wc2 = y + (e === "DEBIT" ? ":credit" : ":debit"), w2 = nz(vals[wc2]);
          if (w2 !== null && Math.abs(w2) > 1e-9) { c.level = "HIGH"; c.wrongSide = wc2; c.note = "Montant " + fd(w2) + " DZD au " + (e === "DEBIT" ? "CRÉDIT" : "DÉBIT") + " ; sens attendu : " + e; }
        }
      }
      out[k] = c; return c.value;
    }
    sp.layout.forEach(function (row) { YEARS.forEach(function (y) { f(row[2], y); }); });
    return out;
  }
  function V(t, r, ck) { var m = t === "ACTIF" ? M.A : M.P, x = m[r + "|" + ck]; return x ? x.value : null; }
  function T(r, y) { var x = M.T[r + "|" + y]; return x ? x.value : null; }

  // Valeur affichée d'une cellule (formule ou saisie) dans un modèle donné
  function shown(model, k, rowsT) {
    var q = splitK(k), c;
    if (q.t === "TCR") {
      c = model.T[q.r + "|" + q.y];
      if (c && c.kind === "formula") { var v = c.value; return q.c === "debit" ? (v !== null && v < 0 ? -v : null) : (v !== null && v > 0 ? v : null); }
      return nz(((rowsT || {})[q.r] || {})[q.ck]);
    }
    c = (q.t === "ACTIF" ? model.A : model.P)[q.r + "|" + q.ck];
    return c ? c.value : null;
  }
  function cellDisp(model, k) {
    if (!model) return undefined;
    var q = splitK(k), c;
    if (q.t === "TCR") { c = model.T[q.r + "|" + q.y]; if (!c || c.kind !== "formula") return undefined; return shown(model, k); }
    c = (q.t === "ACTIF" ? model.A : model.P)[q.r + "|" + q.ck];
    if (!c || c.kind !== "formula") return undefined;
    return c.value;
  }
  function differs(a, b) { return (a === null) !== (b === null) || (a !== null && Math.abs(a - b) >= 0.5); }

  function buildModel() {
    if (M0VER !== VERSION) {
      NOPEND = true;
      try { M0 = { A: computeBalance("ACTIF"), P: computeBalance("PASSIF"), T: computeTCR() }; } finally { NOPEND = false; }
      M0VER = VERSION;
    }
    M = { A: computeBalance("ACTIF"), P: computeBalance("PASSIF"), T: computeTCR() };
    var cross = [], alerts = [], altAl = {}, rowsT = rowsOf("TCR");
    YEARS.forEach(function (y) {
      var a = V("ACTIF", "total_general_actif", y + ":net"), p = V("PASSIF", "total_general_passif", y + ":v");
      if (a !== null && p !== null) cross.push({ c: "Total actif = Total passif", y: y, a: a, b: p, g: a - p, lv: level(a - p), go: "PASSIF.total_general_passif." + y + ":v" });
      var rt = T("resultat_net_exercice", y), rp = V("PASSIF", "resultat_net_passif", y + ":v");
      if (rt !== null && rp !== null) cross.push({ c: "Résultat TCR = Résultat net au passif", y: y, a: rt, b: rp, g: rt - rp, lv: level(rt - rp), go: "TCR.resultat_net_exercice." + y + ":credit" });
    });
    // Contrôle inter-liasses (colonne N-1 de la liasse suivante)
    ["ACTIF", "PASSIF", "TCR"].forEach(function (t) {
      var al = (A.alt || {})[t] || {};
      Object.keys(al).forEach(function (r) {
        Object.keys(al[r]).forEach(function (ck) {
          var k = t + "." + r + "." + ck, info = al[r][ck], mine = shown(M, k, rowsT), g = (mine || 0) - (info.v || 0), lv = level(g);
          if (lv !== "OK") altAl[k] = { level: lv, note: "Inter-liasses : " + fd(mine === null ? 0 : mine) + " ici vs " + fd(info.v) + " DZD dans " + info.src };
        });
      });
    });
    ["ACTIF", "PASSIF"].forEach(function (t) {
      var m = t === "ACTIF" ? M.A : M.P, sp = A.spec[t];
      Object.keys(m).forEach(function (k) {
        var c = m[k]; if (c.level === "OK") return; var p = k.split("|");
        alerts.push({ k: t + "." + p[0] + "." + p[1], t: t, lab: sp.labels[p[0]], cl: colLabel(t, p[1]), level: c.level, note: c.note });
      });
    });
    Object.keys(M.T).forEach(function (k) {
      var c = M.T[k]; if (c.level === "OK") return; var p = k.split("|");
      var ck = c.wrongSide || (p[1] + ((c.value || 0) < 0 ? ":debit" : ":credit"));
      alerts.push({ k: "TCR." + p[0] + "." + ck, t: "TCR", lab: A.spec.TCR.labels[p[0]], cl: colLabel("TCR", ck), level: c.level, note: c.note });
    });
    Object.keys(altAl).forEach(function (k) { var q = splitK(k); alerts.push({ k: k, t: q.t, lab: A.spec[q.t].labels[q.r], cl: colLabel(q.t, q.ck), level: altAl[k].level, note: altAl[k].note }); });
    alerts.sort(function (a, b) { return LR[b.level] - LR[a.level]; });
    M.cross = cross; M.alerts = alerts; M.altAl = altAl;
    M.nbAlerts = alerts.length + cross.filter(function (c) { return c.lv !== "OK"; }).length;
  }

  // ---------- Traçage dépendants / composantes ----------
  function parentsOf(t, rid) {
    var f = A.spec[t].formulas, out = [];
    Object.keys(f).forEach(function (k) { if (f[k].map(function (x) { return Array.isArray(x) ? x[0] : x; }).indexOf(rid) >= 0) out.push(k); });
    return out;
  }
  function traceKeys(k) {
    var res = { dep: {}, pre: {} }; if (!k) return res;
    var q = splitK(k), t = q.t, r = q.r, f = A.spec[t].formulas;
    function bfs(start, add) { var queue = [start], seen = {}; while (queue.length) { var x = queue.shift(); parentsOf(t, x).forEach(function (par) { if (!seen[par]) { seen[par] = 1; add(par); queue.push(par); } }); } }
    if (t === "TCR") {
      bfs(r, function (par) { res.dep["TCR." + par + "." + q.y + ":debit"] = 1; res.dep["TCR." + par + "." + q.y + ":credit"] = 1; });
      if (f[r]) f[r].forEach(function (x) { res.pre["TCR." + x + "." + q.y + ":debit"] = 1; res.pre["TCR." + x + "." + q.y + ":credit"] = 1; });
    } else {
      bfs(r, function (par) { res.dep[t + "." + par + "." + q.ck] = 1; });
      if (t === "ACTIF" && (q.c === "brut" || q.c === "amort")) {
        var nk = q.y + ":net", nc = M.A[r + "|" + nk];
        if (nc && nc.kind === "formula") { res.dep["ACTIF." + r + "." + nk] = 1; bfs(r, function (par) { res.dep["ACTIF." + par + "." + nk] = 1; }); }
      }
      if (f[r]) f[r].forEach(function (x) { res.pre[t + "." + x[0] + "." + q.ck] = 1; });
      if (t === "ACTIF" && q.c === "net" && !f[r]) { res.pre["ACTIF." + r + "." + q.y + ":brut"] = 1; res.pre["ACTIF." + r + "." + q.y + ":amort"] = 1; }
    }
    delete res.dep[k]; delete res.pre[k];
    return res;
  }

  // ---------- Rendu des cellules ----------
  function corrOf(k) { return (A.corr || {})[k]; }
  function tdNum(k, c, style) {
    var q = splitK(k), cls = ["n"], editable = c.kind === "input" && q.r.charAt(0) !== "_" && canEdit(q.t, q.y, q.c);
    if (c.kind === "input" && style === "row") cls.push("inp"); else if (c.kind === "input" && style === "sub") cls.push("sub"); else cls.push(style);
    if (c.kind === "input" && !editable && c.value === null && q.r.charAt(0) !== "_") cls.push("nosrc");
    var lv = c.level || "OK", note = c.note || "", aa = M.altAl[k];
    if (aa && LR[aa.level] > LR[lv]) lv = aa.level;
    if (aa) note = note ? note + " · " + aa.note : aa.note;
    if (lv !== "OK") cls.push("al-" + lv);
    if (corrOf(k)) cls.push("corr");
    if (k in S.pending) cls.push("pend");
    if (S.sel === k) cls.push("sel");
    if (HL.dep[k]) cls.push("dep");
    if (HL.pre[k]) cls.push("pre");
    var tip = [], arrow = "", v0 = cellDisp(M0, k), v1 = cellDisp(M, k);
    if (v0 !== undefined && v1 !== undefined) {
      if (differs(v0, v1)) { cls.push("dlt"); arrow = (v1 || 0) > (v0 || 0) ? "▲" : "▼"; tip.push("Avant modifications : " + (v0 === null ? "vide" : fd(v0)) + " → maintenant : " + (v1 === null ? "vide" : fd(v1)) + " DZD (Δ " + fd((v1 || 0) - (v0 || 0)) + ")"); }
      if (k in PREV && differs(PREV[k], v1)) cls.push("flash");
      NEXT[k] = v1;
    }
    if (note) tip.push(note);
    var co = corrOf(k); if (co) tip.push("Corrigé le " + String(co.date || "").slice(0, 10) + " — " + (co.motif || ""));
    if (k in S.pending) tip.push("Modification non enregistrée");
    if (!editable && c.kind === "input" && q.r.charAt(0) !== "_") { var s0 = srcOf(q.t, q.y); tip.push(s0 ? "Non disponible : la liasse source (" + s0.fichier + ", colonne N-1) ne donne que le Net" : "Aucune liasse source pour cet exercice"); }
    return '<td class="' + cls.join(" ") + '" data-k="' + k + '" data-e="' + (editable ? 1 : 0) + '"' + (tip.length ? ' title="' + esc(tip.join(" | ")) + '"' : "") + ">" + (arrow ? '<span class="dl">' + arrow + "</span>" : "") + fu(c.value) + "</td>";
  }
  function srcLine(t, y) { var s = srcOf(t, y); if (!s) return "pas de liasse"; return (s.period === "N" ? "liasse " : "liasse ") + (s.annee_liasse || "") + (s.period === "N1" ? " · col. N-1" : "") + (s.pages && s.pages.length ? " · p." + s.pages.join(",") : ""); }
  function identRows() { return ""; }
  function identBlock() { return '<table class="yr idt">' + (A.ident || []).map(function (x) { return '<tr><td class="idl">' + esc(x[0]) + '</td><td class="idv">' + esc(x[1]) + "</td></tr>"; }).join("") + "</table>"; }

  function renderBalance(t) {
    var sp = A.spec[t], u = S.unit, nc = sp.cols.length, m = t === "ACTIF" ? M.A : M.P;
    var minw = 320 + YEARS.length * nc * 100;
    var h = identBlock() + '<div class="wrap"><table class="yr" style="min-width:' + minw + 'px">';
    if (t === "ACTIF") {
      h += '<tr><th class="h1 lab" rowspan="2" style="text-align:left;font-size:15px;min-width:300px">ACTIF</th>';
      YEARS.forEach(function (y) { h += '<th class="h2 yh" colspan="3">Exercice ' + y + "<small>" + esc(srcLine(t, y)) + "</small></th>"; });
      h += "</tr><tr>";
      YEARS.forEach(function () { h += '<th class="h1">Brut<br>(' + u + ')</th><th class="h1">Amort. &amp; prov.<br>(' + u + ')</th><th class="h1">Net<br>(' + u + ")</th>"; });
      h += "</tr>";
    } else {
      h += '<tr><th class="h1 lab" style="text-align:left;font-size:15px;min-width:300px">PASSIF</th>';
      YEARS.forEach(function (y) { h += '<th class="h1 yh">' + y + " (" + u + ")<small>" + esc(srcLine(t, y)) + "</small></th>"; });
      h += "</tr>";
    }
    sp.layout.forEach(function (row) {
      var r = row[1], st = row[2];
      h += '<tr><td class="' + st + ' lab">' + esc(row[0]) + "</td>";
      YEARS.forEach(function (y) { sp.cols.forEach(function (c) { var ck = y + ":" + c; h += tdNum(t + "." + r + "." + ck, m[r + "|" + ck] || { value: null, kind: "input", level: "OK" }, st); }); });
      h += "</tr>";
    });
    if (t === "PASSIF") {
      h += '<tr id="ctlrow"><td class="row lab" style="font-style:italic">Contrôle Actif = Passif</td>';
      YEARS.forEach(function (y) {
        var a = V("ACTIF", "total_general_actif", y + ":net"), p = V("PASSIF", "total_general_passif", y + ":v");
        if (a === null || p === null) h += '<td class="row"></td>';
        else if (Math.abs(a - p) < A.thresholds.min) h += '<td class="ok-chk">OK</td>';
        else h += '<td class="ko-chk">ERREUR<br>' + fu(a - p) + "</td>";
      });
      h += '</tr><tr><td class="src" colspan="' + (YEARS.length + 1) + '">(1) à utiliser uniquement pour la présentation d’états financiers consolidés</td></tr>';
    }
    return h + "</table></div>";
  }
  function renderTCR() {
    var sp = A.spec.TCR, u = S.unit, L = sp.layout, spans = {}, i = 0;
    while (i < L.length) { if (L[i][0] && L[i][1]) { var j = i + 1; while (j < L.length && L[j][0] === null) j++; spans[i] = j - i; i = j; } else i++; }
    var minw = 440 + YEARS.length * 2 * 100;
    var h = identBlock() + '<div class="wrap"><table class="yr" style="min-width:' + minw + 'px">';
    h += '<tr><th class="h1 lcd" colspan="2" rowspan="2" style="text-align:left;font-size:15px">Rubriques</th>';
    YEARS.forEach(function (y) { h += '<th class="h1 yh" colspan="2">' + y + "<small>" + esc(srcLine("TCR", y)) + "</small></th>"; });
    h += "</tr><tr>";
    YEARS.forEach(function () { h += '<th class="h1">DÉBIT<br>(' + u + ')</th><th class="h1">CRÉDIT<br>(' + u + ")</th>"; });
    h += "</tr>";
    var R = rowsOf("TCR");
    L.forEach(function (row, idx) {
      var c0 = row[0], d0 = row[1], r = row[2], st = row[3];
      h += "<tr>";
      if (c0 && d0) h += '<td class="row lc" rowspan="' + (spans[idx] || 1) + '">' + esc(c0) + '</td><td class="row ld">' + esc(d0) + "</td>";
      else if (c0 === null && d0) h += '<td class="row ld">' + esc(d0) + "</td>";
      else if (c0 === "" && d0) h += '<td class="row lc"></td><td class="row ld">' + esc(d0) + "</td>";
      else h += '<td class="' + st + ' lcd" colspan="2">' + esc(c0) + "</td>";
      YEARS.forEach(function (y) {
        var c = M.T[r + "|" + y] || { kind: "input", level: "OK" };
        if (c.kind === "formula") {
          var v = c.value, dv = v !== null && v < 0 ? -v : null, cv = v !== null && v > 0 ? v : null, both = dv === null && cv === null;
          h += tdNum("TCR." + r + "." + y + ":debit", { value: dv, kind: "formula", level: (dv !== null || both) ? c.level : "OK", note: c.note }, st);
          h += tdNum("TCR." + r + "." + y + ":credit", { value: cv, kind: "formula", level: (cv !== null || both) ? c.level : "OK", note: c.note }, st);
        } else {
          ["debit", "credit"].forEach(function (s) {
            var ck = y + ":" + s, v2 = nz((R[r] || {})[ck]);
            h += tdNum("TCR." + r + "." + ck, { value: v2, kind: "input", level: c.wrongSide === ck ? "HIGH" : "OK", note: c.wrongSide === ck ? c.note : "" }, st);
          });
        }
      });
      h += "</tr>";
    });
    return h + "</table></div>";
  }

  // ---------- Ratios par exercice ----------
  function dv(a, b) { return a === null || b === null || Math.abs(b) < 1e-9 ? null : a / b; }
  function sumN() { var s = 0, any = false; for (var i = 0; i < arguments.length; i++) if (arguments[i] !== null) { s += arguments[i]; any = true; } return any ? s : null; }
  function neg(x) { return x === null ? null : -x; }
  function times(x, k) { return x === null ? null : x * k; }
  function ratioDefs() {
    function a(r, y) { return V("ACTIF", r, y + ":net"); }
    function pp(r, y) { return V("PASSIF", r, y + ":v"); }
    function ca(y) { return T("chiffre_affaires_net", y); }
    function achats(y) { return neg(sumN(T("achats_marchandises_vendues", y), T("matieres_premieres", y), T("autres_approvisionnements", y), T("sous_traitance_generale", y))); }
    function marge(y) { var p = T("production_exercice", y); if (p === null) return null; return p - (achats(y) || 0) + (T("variation_stocks", y) || 0); }
    function fp(y) { return pp("total_capitaux_propres", y); }
    function ta(y) { return a("total_general_actif", y); }
    function dft(y) { if (pp("total_general_passif", y) === null) return null; return (pp("emprunts_dettes_financieres", y) || 0) + (pp("tresorerie_passif", y) || 0); }
    function dfn(y) { var d = dft(y); return d === null ? null : d - (a("tresorerie_actif", y) || 0) - (a("placements_financiers_courants", y) || 0); }
    function fpn(y) { var f = fp(y); return f === null ? null : f - (a("immobilisations_incorporelles", y) || 0) - (a("ecarts_acquisition_goodwill", y) || 0); }
    function ebe(y) { return T("excedent_brut_exploitation", y); }
    function bfr(y) {
      if (ta(y) === null || pp("total_general_passif", y) === null) return null;
      return (a("stocks_encours", y) || 0) + (a("clients", y) || 0) + (a("autres_debiteurs", y) || 0) + (a("impots_assimiles_actif", y) || 0) + (a("autres_creances_assimiles", y) || 0)
        - (pp("fournisseurs_rattaches", y) || 0) - (pp("impots_passif", y) || 0) - (pp("autres_dettes", y) || 0);
    }
    function fr(y) { var f = fp(y), anc = a("total_actif_non_courant", y); if (f === null || anc === null) return null; return f + (pp("total_passifs_non_courants", y) || 0) - anc; }
    return [
      { s: "(Exploitation)" },
      { l: "Rappel du Chiffre d'Affaires", f: ca, t: "amt" },
      { l: "Evolution du CA", f: function (y) { var r = dv(ca(y), YEARS.indexOf(y - 1) >= 0 ? ca(y - 1) : null); return r === null ? null : r - 1; }, t: "pct" },
      { l: "Marge commerciale / CA", f: function (y) { return dv(marge(y), ca(y)); }, t: "pct", h: "Production − achats & sous-traitance ± variation de stocks" },
      { l: "EBE / CA", f: function (y) { return dv(ebe(y), ca(y)); }, t: "pct" },
      { l: "Résultat économique / CA", f: function (y) { return dv(T("resultat_operationnel", y), ca(y)); }, t: "pct", h: "Approché par le résultat opérationnel du TCR" },
      { l: "Achats & Sous-traitance / CA", f: function (y) { return dv(achats(y), ca(y)); }, t: "pct" },
      { l: "Charges de personnel / CA", f: function (y) { return dv(neg(T("charges_personnel", y)), ca(y)); }, t: "pct" },
      { s: "(Rentabilité)" },
      { l: "Résultat net / CA", f: function (y) { return dv(T("resultat_net_exercice", y), ca(y)); }, t: "pct" },
      { l: "Résultat net / Fonds Propres", f: function (y) { return dv(T("resultat_net_exercice", y), fp(y)); }, t: "pct" },
      { l: "Résultat net / Total Actif", f: function (y) { return dv(T("resultat_net_exercice", y), ta(y)); }, t: "pct" },
      { l: "CA / Total Actif (en X)", f: function (y) { return dv(ca(y), ta(y)); }, t: "x" },
      { l: "Total Actif / Fonds Propres (en X)", f: function (y) { return dv(ta(y), fp(y)); }, t: "x" },
      { s: "(Dette)" },
      { l: "Dettes financières totales", f: dft, t: "amt", h: "Emprunts et dettes financières + trésorerie passif (hors crédit-bail et sociétés apparentées)" },
      { l: "Dettes financières totales nettes", f: dfn, t: "amt", h: "− trésorerie actif − placements" },
      { l: "EBE / Charges financières (en X)", f: function (y) { return dv(ebe(y), neg(T("charges_financieres", y))); }, t: "x", h: "Le modèle Excel utilise le résultat financier retraité (crédit-bail)" },
      { l: "Dettes financières totales / Fonds propres", f: function (y) { return dv(dft(y), fp(y)); }, t: "x" },
      { l: "Dettes financières totales nettes / Fonds propres", f: function (y) { return dv(dfn(y), fp(y)); }, t: "x" },
      { l: "Gross Gearing (Dettes fin. tot. / FP nets d'incorporels)", f: function (y) { return dv(dft(y), fpn(y)); }, t: "x" },
      { l: "Net Gearing (Dettes fin. nettes / FP nets d'incorporels)", f: function (y) { return dv(dfn(y), fpn(y)); }, t: "x" },
      { l: "Dettes financières totales / EBE (en années)", f: function (y) { return dv(dft(y), ebe(y)); }, t: "yrs" },
      { l: "Dettes financières totales nettes / EBE (en années)", f: function (y) { return dv(dfn(y), ebe(y)); }, t: "yrs" },
      { l: "Ratio courant (Actif courant / Passif courant)", f: function (y) { return dv(a("total_actif_courant", y), pp("total_passifs_courants", y)); }, t: "x" },
      { l: "Liquidité réduite ((Actif courant − Stocks) / Passif courant)", f: function (y) { var c = a("total_actif_courant", y); return c === null ? null : dv(c - (a("stocks_encours", y) || 0), pp("total_passifs_courants", y)); }, t: "x" },
      { s: "(Investissement)" },
      { l: "Dotation aux amortissements / Immo. d'exploitation brutes", f: function (y) { var b = sumN(V("ACTIF", "immobilisations_incorporelles", y + ":brut"), V("ACTIF", "immobilisations_corporelles", y + ":brut")); return dv(neg(T("dotations_amortissements", y)), b); }, t: "pct", h: "Brut disponible uniquement pour les exercices lus en colonne N" },
      { s: "(Besoin en fonds de roulement)" },
      { l: "Rotation des stocks (Jours de CA)", f: function (y) { return times(dv(a("stocks_encours", y), ca(y)), 360); }, t: "days" },
      { l: "Délais clients (Jours de CA)", f: function (y) { return times(dv(a("clients", y), ca(y)), 360); }, t: "days" },
      { l: "Crédit fournisseurs (Jours de CA)", f: function (y) { return times(dv(pp("fournisseurs_rattaches", y), ca(y)), 360); }, t: "days" },
      { l: "Crédit fournisseurs (Jours d'achats)", f: function (y) { return times(dv(pp("fournisseurs_rattaches", y), achats(y)), 360); }, t: "days" },
      { l: "Fonds de roulement", f: fr, t: "amt" },
      { l: "BFR d'exploitation", f: bfr, t: "amt" },
      { l: "BFR (Jours de CA)", f: function (y) { return times(dv(bfr(y), ca(y)), 360); }, t: "days" }
    ];
  }
  function fmtR(v, t) {
    if (v === null || v === undefined || !isFinite(v)) return '<span style="color:#8A9A92">n/d</span>';
    if (t === "pct") return (v * 100).toFixed(1).replace(".", ",") + " %";
    if (t === "x") return v.toFixed(2).replace(".", ",") + " x";
    if (t === "yrs") return v.toFixed(1).replace(".", ",") + " ans";
    if (t === "days") return Math.round(v) + " j";
    return fu(v) + " " + S.unit;
  }
  function renderRatios() {
    var h = '<div class="wrap"><table class="yr" style="min-width:' + (420 + YEARS.length * 130) + 'px"><tr><th class="h1 lab" style="text-align:left;font-size:15px;min-width:380px">RATIOS</th>';
    YEARS.forEach(function (y) { h += '<th class="h1">' + y + "</th>"; });
    h += "</tr>";
    ratioDefs().forEach(function (d) {
      if (d.s) { h += '<tr><td class="sec lab">' + esc(d.s) + '</td><td class="sec" colspan="' + YEARS.length + '"></td></tr>'; return; }
      h += '<tr><td class="row lab"' + (d.h ? ' title="' + esc(d.h) + '"' : "") + ">" + esc(d.l) + (d.h ? ' <span style="color:#8A9A92">ⓘ</span>' : "") + "</td>";
      YEARS.forEach(function (y) { h += '<td class="n row" style="cursor:default">' + fmtR(d.f(y), d.t) + "</td>"; });
      h += "</tr>";
    });
    h += "</table></div>";
    return h + '<div class="note">Ratios recalculés en direct depuis l’Actif, le Passif et le TCR (exercices de 12 mois, base 360 jours). Ils n’intègrent pas les retraitements analyste du classeur V20 (crédit-bail, part CT de la dette, sociétés apparentées, effets escomptés) : les ratios de dette du fichier Excel peuvent différer.</div>';
  }

  // ---------- Contrôles ----------
  function renderCtrl() {
    var h = "<h4>Contrôles croisés</h4>";
    if (!M.cross.length) h += '<div class="note">Aucun contrôle croisé calculable.</div>';
    else {
      h += '<table class="lst"><tr><th>Contrôle</th><th>Exercice</th><th style="text-align:right">Valeur A</th><th style="text-align:right">Valeur B</th><th style="text-align:right">Écart (DZD)</th><th>Niveau</th></tr>';
      M.cross.forEach(function (c, i) { h += '<tr class="click" data-go="c' + i + '"><td>' + esc(c.c) + "</td><td>" + c.y + '</td><td style="text-align:right">' + fu(c.a) + '</td><td style="text-align:right">' + fu(c.b) + '</td><td style="text-align:right">' + fd(c.g) + '</td><td><span class="lv lv-' + c.lv + '">' + c.lv + "</span></td></tr>"; });
      h += "</table>";
    }
    h += "<h4>Écarts par cellule (" + M.alerts.length + ")</h4>";
    if (!M.alerts.length) h += '<div class="note">Aucun écart de formule, de sens TCR ni inter-liasses détecté.</div>';
    else {
      h += '<table class="lst"><tr><th>Niveau</th><th>État</th><th>Rubrique</th><th>Colonne</th><th>Détail</th></tr>';
      M.alerts.forEach(function (x, i) { h += '<tr class="click" data-go="a' + i + '"><td><span class="lv lv-' + x.level + '">' + x.level + "</span></td><td>" + esc(A.tableLabels[x.t]) + "</td><td>" + esc(x.lab) + "</td><td>" + esc(x.cl) + "</td><td>" + esc(x.note) + "</td></tr>"; });
      h += "</table>";
    }
    var hist = A.history || [];
    if (hist.length) {
      h += "<h4>Historique des corrections (" + hist.length + ')</h4><table class="lst"><tr><th>Date</th><th>Cellule</th><th>Liasse</th><th style="text-align:right">Avant (DZD)</th><th style="text-align:right">Après (DZD)</th><th>Motif</th></tr>';
      hist.slice().reverse().forEach(function (c) { h += "<tr><td>" + esc(String(c.date || "").slice(0, 16).replace("T", " ")) + "</td><td>" + esc(c.cellule || c.champ) + "</td><td>" + esc(c.fichier || "") + '</td><td style="text-align:right">' + fd(c.avant) + '</td><td style="text-align:right">' + fd(c.apres) + "</td><td>" + esc(c.motif) + "</td></tr>"; });
      h += "</table>";
    }
    return h + '<div class="note">Cliquez sur une ligne pour aller à la cellule concernée.</div>';
  }

  // ---------- Barre de formule ----------
  function renderFbar() {
    if (!S.sel) return '<div class="fbar"><div class="nm">—</div><div class="fx"><span class="muted">Sélectionnez une cellule. Cellules crème = saisie : frappe directe, double-clic ou Entrée pour modifier ; les formules se recalculent pendant la frappe. Suppr vide la cellule, Ctrl+Z annule.</span></div></div>';
    var q = splitK(S.sel), sp = A.spec[q.t], c;
    c = q.t === "TCR" ? M.T[q.r + "|" + q.y] : (q.t === "ACTIF" ? M.A : M.P)[q.r + "|" + q.ck];
    c = c || { kind: "input", level: "OK" };
    var name = A.tableLabels[q.t] + " › " + (sp.labels[q.r] || q.r) + " › " + colLabel(q.t, q.ck);
    var h = '<div class="fbar"><div class="nm" title="' + esc(name) + '">' + esc(name) + '</div><div class="fx">';
    var s0 = srcOf(q.t, q.y);
    if (c.kind === "input") {
      var cv = curVal(S.sel);
      h += "<span><i>fx</i>Valeur lue sur la liasse : <b>" + (cv === null ? "vide" : fd(cv) + " DZD") + "</b></span>";
      if (S.sel in S.pending) { var b0 = S.pending[S.sel].base; h += '<span class="muted">avant modification : ' + (b0 === null ? "vide" : fd(b0) + " DZD") + "</span>"; }
      var names = [];
      Object.keys(HL.dep).forEach(function (d) { var lb = sp.labels[d.split(".")[1]]; if (lb && names.indexOf(lb) < 0) names.push(lb); });
      if (names.length) h += '<span class="imp" title="' + esc(names.join(" → ")) + '">Alimente ' + names.length + " formule" + (names.length > 1 ? "s" : "") + " : " + esc(names.slice(0, 4).join(", ")) + (names.length > 4 ? "…" : "") + "</span>";
    } else {
      h += "<span><i>fx</i>" + esc(c.formula || "Formule") + "</span>";
      var ct = "—";
      if (c.computed !== null && c.computed !== undefined) ct = q.t === "TCR" ? fd(Math.abs(c.computed)) + " DZD au " + (c.computed >= 0 ? "crédit" : "débit") : fd(c.computed) + " DZD";
      h += "<span>Calculé : <b>" + ct + "</b></span>";
      var w0 = cellDisp(M0, S.sel), w1 = cellDisp(M, S.sel);
      if (w0 !== undefined && w1 !== undefined && differs(w0, w1)) h += '<span class="imp">avant modifications : ' + (w0 === null ? "vide" : fd(w0)) + " → " + (w1 === null ? "vide" : fd(w1)) + " DZD (Δ " + fd((w1 || 0) - (w0 || 0)) + ")</span>";
      if (q.r.charAt(0) !== "_" && canEdit(q.t, q.y, q.c)) {
        var side = q.t === "TCR" ? (q.c === "debit" ? " (débit)" : " (crédit)") : "";
        h += '<span>Imprimé liasse' + side + ' : <input id="fbIn" value="' + esc(editStr(curVal(S.sel))) + '" placeholder="vide"> ' + S.unit + ' <button id="fbOk">Appliquer</button></span>';
      }
    }
    var lv = c.level || "OK", note = c.note || "", aa = M.altAl[S.sel];
    if (aa) { if (LR[aa.level] > LR[lv]) lv = aa.level; note = note ? note + " · " + aa.note : aa.note; }
    if (lv !== "OK") h += '<span class="lv lv-' + lv + '">' + lv + "</span><span>" + esc(note) + "</span>";
    if (s0) h += '<span class="muted">Source : ' + esc(s0.fichier) + (s0.pages && s0.pages.length ? " p." + s0.pages.join(",") : "") + (s0.period === "N1" ? " (colonne N-1)" : "") + "</span>";
    var co = corrOf(S.sel); if (co) h += '<span class="muted">Corrigé le ' + esc(String(co.date || "").slice(0, 10)) + " : " + esc(co.motif) + "</span>";
    return h + "</div></div>";
  }

  // ---------- Rendu global ----------
  function kpis() {
    var y = YEARS[YEARS.length - 1];
    function k(l, v) { return "<div><small>" + esc(l) + "</small><b>" + (v === null || v === undefined ? "—" : fu(v) + " " + S.unit) + "</b></div>"; }
    if (!y) return '<div class="kpi"></div>';
    return '<div class="kpi">' + k("Total actif " + y, V("ACTIF", "total_general_actif", y + ":net")) + k("Capitaux propres " + y, V("PASSIF", "total_capitaux_propres", y + ":v")) +
      k("Chiffre d'affaires " + y, T("chiffre_affaires_net", y)) + k("EBE " + y, T("excedent_brut_exploitation", y)) + k("Résultat net " + y, T("resultat_net_exercice", y)) +
      '<div><small>Anomalies (≥ 1 000 DZD, ' + YEARS.length + ' ex.)</small><b style="color:' + (M.nbAlerts ? "#C00000" : "#00915A") + '">' + M.nbAlerts + "</b></div></div>";
  }
  function isGridTab() { return S.tab === "ACTIF" || S.tab === "PASSIF" || S.tab === "TCR"; }
  function tableHtml() { return S.tab === "ACTIF" ? renderBalance("ACTIF") : S.tab === "PASSIF" ? renderBalance("PASSIF") : S.tab === "TCR" ? renderTCR() : null; }
  function render() {
    if (!A) return;
    if (!YEARS.length) { document.getElementById("app").innerHTML = '<div class="warn">Aucun exercice exploitable dans les liasses extraites.</div>'; setTimeout(setHeight, 0); return; }
    var focusMotif = document.activeElement && document.activeElement.id === "motif";
    buildModel();
    HL = isGridTab() && S.sel && S.sel.split(".")[0] === S.tab ? traceKeys(S.sel) : { dep: {}, pre: {} };
    NEXT = {};
    var nP = Object.keys(S.pending).length, h = kpis();
    (A.warnings || []).forEach(function (w) { h += '<div class="warn">' + esc(w) + "</div>"; });
    h += '<div class="bar"><div class="tabs">';
    [["ACTIF", "Actif"], ["PASSIF", "Passif"], ["TCR", "TCR"], ["RATIOS", "Ratios"], ["CTRL", "Contrôles"]].forEach(function (x) {
      h += '<button data-tab="' + x[0] + '" class="' + (S.tab === x[0] ? "on" : "") + '">' + x[1] + (x[0] === "CTRL" && M.nbAlerts ? '<span class="cnt">' + M.nbAlerts + "</span>" : "") + "</button>";
    });
    h += '</div><div class="sp"></div>' + (isGridTab() ? '<button class="pdfbtn' + (S.pdf.open ? " on" : "") + '" data-pdftoggle="1" title="Afficher la page de la liasse à côté du tableau">📄 Liasse PDF</button>' : "") + '<div class="unit"><button data-unit="KDZD" class="' + (S.unit === "KDZD" ? "on" : "") + '">KDZD</button><button data-unit="DZD" class="' + (S.unit === "DZD" ? "on" : "") + '">DZD</button></div></div>';
    if (nP || S.msg) {
      h += '<div class="pendbar"><b>' + nP + " modification" + (nP > 1 ? "s" : "") + " non enregistrée" + (nP > 1 ? "s" : "") + "</b>";
      h += '<input id="motif" placeholder="Motif de correction (obligatoire)" value="' + esc(S.motif) + '">';
      h += '<button class="pri" id="save"' + (S.saving ? " disabled" : "") + ">" + (S.saving ? "Enregistrement…" : "Enregistrer") + '</button><button id="discard">Tout annuler</button>';
      if (S.msg) h += '<span class="err">' + esc(S.msg) + "</span>";
      h += "</div>";
    }
    if (isGridTab()) h += renderFbar();
    if (isGridTab() && S.pdf.open) { followSel(); h += '<div class="split"><div class="gcol">' + tableHtml() + "</div>" + renderPdf() + "</div>"; }
    else h += isGridTab() ? tableHtml() : S.tab === "RATIOS" ? renderRatios() : renderCtrl();
    if (isGridTab()) {
      h += '<div class="leg"><span><i style="background:#FFF8E1"></i>Saisie (valeur liasse, modifiable)</span><span><i style="background:#EAF5EF"></i>Sous-total (formule)</span><span><i style="background:#C6E5D4"></i>Section</span><span><i style="background:#00573F"></i>Total</span>' +
        '<span><i style="background:#FFF2CC;border:2px solid #C9A227"></i>Écart LOW ≥ 1 000 DZD</span><span><i style="background:#F8CBAD;border:2px solid #ED7D31"></i>MEDIUM ≥ 10 000</span><span><i style="background:#FFC7CE;border:2px solid #FF0000"></i>HIGH ≥ 1 M ou mauvais côté TCR</span>' +
        '<span><i style="background:linear-gradient(225deg,#7030A0 30%,#fff 30%)"></i>Corrigée</span><span><i style="background:linear-gradient(135deg,#ED7D31 30%,#fff 30%)"></i>Non enregistrée</span>' +
        '<span><i style="background:linear-gradient(90deg,#2F75B5 0,#2F75B5 4px,#fff 4px)"></i>Formule impactée (▲▼)</span><span><i style="outline:2px dashed #2F75B5;outline-offset:-3px"></i>Dépendants</span><span><i style="outline:2px dotted #00915A;outline-offset:-3px"></i>Composantes</span><span><i style="background:repeating-linear-gradient(135deg,#F4F6F5 0 3px,#fff 3px 6px)"></i>Non disponible dans la liasse</span></div>';
    }
    var oldWrap = document.querySelector(".wrap"), wrapKey = S.tab + (S.pdf.open ? "|split" : ""),
        keepX = oldWrap && oldWrap.getAttribute("data-at") === wrapKey ? oldWrap.scrollLeft : null;
    var oldPb = document.querySelector(".pcol .pb"), keep = oldPb && oldPb.getAttribute("data-at") === S.pdf.doc + "#" + S.pdf.page ? [oldPb.scrollTop, oldPb.scrollLeft] : null;
    document.getElementById("app").innerHTML = h;
    var newPb = document.querySelector(".pcol .pb");
    if (newPb) { newPb.setAttribute("data-at", S.pdf.doc + "#" + S.pdf.page); if (keep) { newPb.scrollTop = keep[0]; newPb.scrollLeft = keep[1]; } }
    var newWrap = document.querySelector(".wrap");
    if (newWrap) {
      newWrap.setAttribute("data-at", wrapKey);
      newWrap.scrollLeft = keepX !== null ? keepX : newWrap.scrollWidth; // par défaut : exercice le plus récent (N à droite, comme le V20)
      var selTd = S.sel ? tdOf(S.sel) : null;
      if (selTd) {
        var wr = newWrap.getBoundingClientRect(), cr = selTd.getBoundingClientRect(), lab = newWrap.querySelector("td.lab,td.lcd"), labW = lab ? lab.getBoundingClientRect().width : 0;
        if (cr.right > wr.right) newWrap.scrollLeft += cr.right - wr.right + 8;
        else if (cr.left < wr.left + labW) newWrap.scrollLeft -= (wr.left + labW) - cr.left + 8;
      }
      // Alignement sur le début d'un exercice (pas de colonne coupée sous les libellés figés)
      var lab2 = newWrap.querySelector("td.lab,td.lcd"), lw = lab2 ? lab2.getBoundingClientRect().width : 0, sl = newWrap.scrollLeft;
      var starts = Array.prototype.map.call(newWrap.querySelectorAll("th.yh"), function (th) { return th.offsetLeft - lw; }).filter(function (x) { return x >= 0; }).sort(function (x, y) { return x - y; });
      if (starts.length && sl > 1) {
        var snap = starts.filter(function (x) { return x >= sl - 1; })[0], maxSl = newWrap.scrollWidth - newWrap.clientWidth;
        if (snap === undefined) snap = maxSl;
        var ok = true;
        if (selTd) { var cr2 = selTd.getBoundingClientRect(), wr2 = newWrap.getBoundingClientRect(); ok = cr2.right - (snap - sl) <= wr2.right + 1 && cr2.left - (snap - sl) >= wr2.left + lw - 1; }
        if (ok) newWrap.scrollLeft = Math.min(snap, maxSl);
      }
    }
    PREV = NEXT;
    if (focusMotif) { var m = document.getElementById("motif"); if (m) { m.focus(); m.setSelectionRange(m.value.length, m.value.length); } }
    if (S.edit) openEditor(S.edit.k, S.edit.init);
    setTimeout(setHeight, 0);
  }

  // ---------- Édition ----------
  function tdOf(k) { return document.querySelector('td[data-k="' + (window.CSS && CSS.escape ? CSS.escape(k) : k) + '"]'); }
  function setPending(k, v) {
    var q = k.split("."), b = baseVal(q[0], q[1], q[2]);
    S.undo.push({ k: k, had: k in S.pending, prev: S.pending[k] });
    if ((v === null && b === null) || (v !== null && b !== null && Math.abs(v - b) < 0.005)) delete S.pending[k];
    else S.pending[k] = { value: v, base: b };
    S.msg = "";
  }
  function openEditor(k, init) {
    var td = tdOf(k); if (!td) { S.edit = null; return; }
    S.preview = null;
    td.classList.add("ed");
    td.innerHTML = '<input id="cellIn" autocomplete="off">';
    var inp = document.getElementById("cellIn");
    inp.value = init !== undefined && init !== null ? init : editStr(curVal(k));
    inp.focus();
    if (init === undefined || init === null) inp.select(); else inp.setSelectionRange(inp.value.length, inp.value.length);
    S.edit = { k: k };
    if (init !== undefined && init !== null) livePatch();
  }
  function commitEdit(move) {
    var inp = document.getElementById("cellIn"); if (!inp || !S.edit) return true;
    var r = parseIn(inp.value);
    if (!r.ok) { inp.classList.add("bad"); inp.title = "Montant non reconnu"; return false; }
    var k = S.edit.k; S.edit = null; S.preview = null;
    setPending(k, r.v);
    if (move) moveSel(move); else render();
    return true;
  }
  function cancelEdit() { S.edit = null; S.preview = null; render(); }
  // Recalcul pendant la frappe : toutes les cellules sont mises à jour sauf celle en cours de saisie.
  function livePatch() {
    var inp = document.getElementById("cellIn"); if (!inp || !S.edit) return;
    var r = parseIn(inp.value); inp.classList.toggle("bad", !r.ok); if (!r.ok) return;
    S.preview = { k: S.edit.k, v: r.v };
    buildModel(); NEXT = {};
    var html = tableHtml(); if (!html) return;
    var tmp = document.createElement("div"); tmp.innerHTML = html;
    tmp.querySelectorAll("td[data-k]").forEach(function (nt) {
      var k = nt.getAttribute("data-k"); if (k === S.edit.k) return;
      var ot = tdOf(k); if (!ot) return;
      if (ot.innerHTML !== nt.innerHTML) ot.innerHTML = nt.innerHTML;
      var flash = nt.classList.contains("flash");
      ot.className = nt.className.replace(/\bflash\b/, "").trim();
      if (flash) { void ot.offsetWidth; ot.classList.add("flash"); }
      if (nt.title) ot.title = nt.title; else ot.removeAttribute("title");
    });
    PREV = Object.assign(PREV, NEXT);
    var nr = tmp.querySelector("#ctlrow"), orow = document.getElementById("ctlrow"); if (nr && orow) orow.innerHTML = nr.innerHTML;
    var kp = document.querySelector(".kpi"), t2 = document.createElement("div"); t2.innerHTML = kpis(); if (kp) kp.replaceWith(t2.firstChild);
    var cb = document.querySelector('button[data-tab="CTRL"]'); if (cb) cb.innerHTML = "Contrôles" + (M.nbAlerts ? '<span class="cnt">' + M.nbAlerts + "</span>" : "");
  }
  function grid() {
    var rows = [];
    document.querySelectorAll("table.yr tr").forEach(function (tr) { var cells = Array.prototype.slice.call(tr.querySelectorAll("td[data-k]")); if (cells.length) rows.push(cells.map(function (td) { return td.getAttribute("data-k"); })); });
    return rows;
  }
  function moveSel(dir) {
    var g = grid(), ri = -1, ci = -1;
    for (var i = 0; i < g.length; i++) { var j = g[i].indexOf(S.sel); if (j >= 0) { ri = i; ci = j; break; } }
    if (ri < 0) { render(); return; }
    if (dir === "down") ri = Math.min(g.length - 1, ri + 1);
    if (dir === "up") ri = Math.max(0, ri - 1);
    if (dir === "right") { if (ci < g[ri].length - 1) ci++; else if (ri < g.length - 1) { ri++; ci = 0; } }
    if (dir === "left") { if (ci > 0) ci--; else if (ri > 0) { ri--; ci = g[ri].length - 1; } }
    ci = Math.min(ci, g[ri].length - 1);
    S.sel = g[ri][ci]; render();
    var td = tdOf(S.sel); if (td && td.scrollIntoView) td.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  function isEditable(k) { var td = tdOf(k); return td && td.getAttribute("data-e") === "1"; }

  document.addEventListener("click", function (e) {
    var t = e.target;
    var tb = t.closest("[data-tab]"); if (tb) { if (S.edit && !commitEdit()) return; S.tab = tb.getAttribute("data-tab"); render(); return; }
    var ub = t.closest("[data-unit]"); if (ub) { if (S.edit && !commitEdit()) return; S.unit = ub.getAttribute("data-unit"); render(); return; }
    if (t.id === "save") { save(); return; }
    var pb = t.closest("[data-pdftoggle],[data-pdfclose],[data-pdfpage],[data-pdfdoc],[data-zoom],[data-pdffollow]");
    if (pb) {
      if (S.edit && !commitEdit()) return;
      if (pb.hasAttribute("data-pdftoggle")) S.pdf.open = !S.pdf.open;
      if (pb.hasAttribute("data-pdfclose")) S.pdf.open = false;
      if (pb.hasAttribute("data-pdfpage")) { S.pdf.page = pb.getAttribute("data-pdfpage"); S.pdf.follow = false; }
      if (pb.hasAttribute("data-pdfdoc")) { S.pdf.doc = pb.getAttribute("data-pdfdoc"); S.pdf.page = Object.keys(BLOBS[S.pdf.doc] || {}).sort(function (a, b) { return a - b; })[0]; S.pdf.follow = false; }
      if (pb.hasAttribute("data-pdffollow")) S.pdf.follow = !S.pdf.follow;
      if (pb.hasAttribute("data-zoom")) { var z = +pb.getAttribute("data-zoom"); S.pdf.zoom = z === 0 ? 100 : Math.max(50, Math.min(300, S.pdf.zoom + z * 25)); }
      render(); return;
    }
    if (t.id === "discard") { S.pending = {}; S.undo = []; S.msg = ""; S.motif = ""; render(); return; }
    if (t.id === "fbOk") { var r = parseIn(document.getElementById("fbIn").value); if (!r.ok) { document.getElementById("fbIn").style.borderColor = "#C00000"; return; } setPending(S.sel, r.v); render(); return; }
    var go = t.closest("[data-go]");
    if (go) {
      var id = go.getAttribute("data-go"), key = id.charAt(0) === "a" ? M.alerts[+id.slice(1)].k : M.cross[+id.slice(1)].go;
      S.tab = key.split(".")[0]; S.sel = key; render();
      var td0 = tdOf(S.sel); if (td0 && td0.scrollIntoView) td0.scrollIntoView({ block: "center", inline: "center" });
      return;
    }
    var td = t.closest("td[data-k]");
    if (td && !td.classList.contains("ed")) { if (S.edit && !commitEdit()) return; S.sel = td.getAttribute("data-k"); render(); }
  });
  document.addEventListener("dblclick", function (e) { var td = e.target.closest("td[data-k]"); if (td && td.getAttribute("data-e") === "1") { S.sel = td.getAttribute("data-k"); render(); openEditor(S.sel); } });
  document.addEventListener("input", function (e) { if (e.target.id === "motif") S.motif = e.target.value; if (e.target.id === "cellIn") livePatch(); });
  document.addEventListener("keydown", function (e) {
    if (e.target.id === "motif") { if (e.key === "Enter") save(); return; }
    if (e.target.id === "fbIn") { if (e.key === "Enter") document.getElementById("fbOk").click(); return; }
    if (S.edit) {
      if (e.key === "Enter") { e.preventDefault(); commitEdit(e.shiftKey ? "up" : "down"); }
      else if (e.key === "Tab") { e.preventDefault(); commitEdit(e.shiftKey ? "left" : "right"); }
      else if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { var u = S.undo.pop(); if (u) { if (u.had) S.pending[u.k] = u.prev; else delete S.pending[u.k]; S.sel = u.k; render(); } e.preventDefault(); return; }
    if (!S.sel) return;
    var map = { ArrowDown: "down", ArrowUp: "up", ArrowLeft: "left", ArrowRight: "right" };
    if (map[e.key]) { e.preventDefault(); moveSel(map[e.key]); return; }
    if (e.key === "Tab") { e.preventDefault(); moveSel(e.shiftKey ? "left" : "right"); return; }
    if (!isEditable(S.sel)) return;
    if (e.key === "Enter" || e.key === "F2") { e.preventDefault(); openEditor(S.sel); return; }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); setPending(S.sel, null); render(); return; }
    if (/^[0-9\-,.(]$/.test(e.key) && !e.ctrlKey && !e.metaKey) { e.preventDefault(); openEditor(S.sel, e.key); }
  });

  function save() {
    var keys = Object.keys(S.pending); if (!keys.length) return;
    var m = (document.getElementById("motif") || {}).value || S.motif;
    if (!m || !m.trim()) { S.msg = "Motif obligatoire."; render(); var mi = document.getElementById("motif"); if (mi) mi.focus(); return; }
    S.motif = m; S.saving = true; S.msg = ""; render();
    send("streamlit:setComponentValue", { dataType: "json", value: { action: "save", nonce: Date.now() + "-" + Math.random().toString(36).slice(2), motif: m.trim(),
      changes: keys.map(function (k) { var q = k.split("."); return { table: q[0], row: q[1], col: q[2], value: S.pending[k].value }; }) } });
  }
})();
