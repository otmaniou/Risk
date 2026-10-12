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
  function curVal(k) { if (k in S.pending) return S.pending[k].value; if (isWB(k)) return wbBase(k); var q = k.split("."); return baseVal(q[0], q[1], q[2]); }

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
    wbBuild();
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
    // Actif : colonne Net en blanc comme dans le modèle V20 (formule Brut − Amort.), même si la valeur vient de la liasse
    var netCol = q.t === "ACTIF" && q.c === "net" && style === "row";
    if (c.kind === "input" && style === "row" && !netCol) cls.push("inp"); else if (c.kind === "input" && style === "sub") cls.push("sub"); else cls.push(style);
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
    var wc = wbChecks();
    if (wc.length) {
      h += "<h4>Contrôles du classeur (Saisie / Etatsfin)</h4><table class=\"lst\"><tr><th>Contrôle</th><th>Exercice</th><th>Résultat</th><th style=\"text-align:right\">Écart (KDZD)</th></tr>";
      wc.forEach(function (c, i) { h += '<tr class="click" data-go="w' + i + '"><td>' + esc(c.c) + "</td><td>" + c.y + '</td><td style="color:#C00000;font-weight:700">' + esc(c.v) + '</td><td style="text-align:right">' + (c.g === null ? "" : esc(YRWB.format(c.g, "#,##0.0").text)) + "</td></tr>"; });
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
    if (!S.sel) return renderFbarEmpty();
    return renderFbarSel();
  }
  function renderFbarEmpty() { return '<div class="fbar"><div class="nm">—</div><div class="fx"><span class="muted">Sélectionnez une cellule. Cellules crème = saisie : frappe directe, double-clic ou Entrée pour modifier ; les formules se recalculent pendant la frappe. Suppr vide la cellule, Ctrl+Z annule.</span></div></div>'; }
  function renderFbarSel() {
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

  // ---------- Feuilles Saisie / Etatsfin (formules exactes du modèle, moteur wb_engine.js) ----------
  // Clé : WB|Feuille|Adresse   (ex. WB|Saisie|H48). Montants en KDZD, comme dans le classeur.
  var WBM = window.YR_MODEL || null, WB = null, WB0 = null, WBVER = null, SIN = {}, EIN = {}, LIN = {}, RID = {};
  if (WBM) {
    WBM.saisieInputs.forEach(function (a) { SIN[a] = 1; }); SIN.C3 = 1;
    WBM.etatsInputs.forEach(function (a) { EIN[a] = 1; });
    Object.keys(WBM.liasseInputs).forEach(function (sh) { LIN[sh] = {}; WBM.liasseInputs[sh].forEach(function (a) { LIN[sh][a] = 1; }); });
    [["ACTIF", "ACTIF_ROWS"], ["PASSIF", "PASSIF_ROWS"], ["TCR", "TCR_ROWS"]].forEach(function (x) { RID[x[0]] = {}; Object.keys(WBM.cfg[x[1]]).forEach(function (r) { RID[x[0]][WBM.cfg[x[1]][r]] = r; }); });
  }
  var WBTAB = { SAISIE: "Saisie", ETATS: "Etatsfin" };
  function isWB(k) { return !!k && k.indexOf("WB|") === 0; }
  function isWBTab() { return S.tab === "SAISIE" || S.tab === "ETATS"; }
  function wbParts(k) { var p = k.split("|"); return { sh: p[1], a: p[2], c: p[2].replace(/\d+/g, ""), r: +p[2].replace(/\D+/g, "") }; }
  function tabOfKey(k) { if (!k) return null; if (isWB(k)) return wbParts(k).sh === "Saisie" ? "SAISIE" : "ETATS"; return k.split(".")[0]; }
  function latestY() { return YEARS.length ? Math.max.apply(null, YEARS) : null; }
  function wbRanks() { var L = latestY(), K = Math.min(4, L - Math.min.apply(null, YEARS)), out = []; for (var k = K; k >= 0; k--) out.push(k); return out; }
  function yearOfCol(sh, col) {
    var L = latestY();
    if (sh === "Saisie") { var i = WBM.saisieYearCols.indexOf(col); return i < 0 ? null : L - i; }
    for (var j = 0; j < WBM.etatsYearCols.length; j++) if (WBM.etatsYearCols[j][0] === col || WBM.etatsYearCols[j][1] === col) return L - j;
    return null;
  }
  function wbIsInput(sh, a) { return sh === "Saisie" ? !!SIN[a] : sh === "Etatsfin" ? !!EIN[a] : false; }
  function wbInputs() { return ((A.wb || {}).inputs) || {}; }
  function wbBase(k) {
    var q = wbParts(k), inp = wbInputs();
    if (q.sh === "Saisie" && q.a === "C3") { var t = (inp.textes || {}).C3; return t === undefined || t === "" ? null : t; }
    var y = yearOfCol(q.sh, q.c); if (y === null) return null;
    var g = q.sh === "Saisie" ? inp.annees : inp.etatsfin, v = ((g || {})[String(y)] || {})[String(q.r)];
    return v === undefined ? null : v;
  }
  function wbDyn(noPend) {
    var d = {}, L = latestY(), cfg = WBM.cfg, ranks = WBM.ranks;
    if (L === null) return d;
    var keep = NOPEND; NOPEND = !!noPend;
    try {
      [["ACTIF", "Saisie actif"], ["PASSIF", "Saisie passif"], ["TCR", "Saisie TCR"]].forEach(function (x) {
        var R = rowsOf(x[0]), rows = cfg[x[0] + "_ROWS"], ok = LIN[x[1]];
        Object.keys(R).forEach(function (rid) {
          if (!(rid in rows)) return;
          Object.keys(R[rid]).forEach(function (ck) {
            var v = R[rid][ck]; if (v === null || v === undefined) return;
            var yc = ck.split(":"), k = L - Number(yc[0]); if (k < 0 || k > 4) return;
            var rk = ranks[k], col = x[0] === "ACTIF" ? cfg.ACTIF_GROUPES[rk][["brut", "amort", "net"].indexOf(yc[1])] : x[0] === "PASSIF" ? cfg.PASSIF_COLS[rk] : cfg.TCR_PAIRES[rk][["debit", "credit"].indexOf(yc[1])];
            var a = col + rows[rid]; if (ok[a]) d[x[1] + "!" + a] = v / 1000;
          });
        });
      });
    } finally { NOPEND = keep; }
    d["Saisie!C2"] = (A.wb || {}).client || "";
    WBM.saisieYearCols.forEach(function (c, k) { d["Saisie!" + c + "3"] = YRWB.serialOf((L - k) + "-12-31"); });
    var inp = wbInputs();
    if ((inp.textes || {}).C3) d["Saisie!C3"] = inp.textes.C3;
    [["Saisie", inp.annees, WBM.saisieYearCols.map(function (c) { return c; })], ["Etatsfin", inp.etatsfin, WBM.etatsYearCols.map(function (c) { return c[1]; })]].forEach(function (x) {
      Object.keys(x[1] || {}).forEach(function (y) {
        var col = x[2][L - Number(y)]; if (!col) return;
        Object.keys(x[1][y]).forEach(function (r) { var a = col + r; if (wbIsInput(x[0], a) && x[1][y][r] !== null) d[x[0] + "!" + a] = x[1][y][r]; });
      });
    });
    if (!noPend) {
      Object.keys(S.pending).forEach(function (k) { if (isWB(k)) { var q = wbParts(k); d[q.sh + "!" + q.a] = S.pending[k].value; } });
      if (S.preview && isWB(S.preview.k)) { var q = wbParts(S.preview.k); d[q.sh + "!" + q.a] = S.preview.v; }
    }
    return d;
  }
  function wbBuild() {
    if (!WBM || !window.YRWB || !YEARS.length) return;
    if (!WB) { WB = new YRWB.Workbook(WBM); WB0 = new YRWB.Workbook(WBM); WB0.compiled = WB.compiled; }
    if (WBVER !== VERSION) { WB0.setDyn(wbDyn(true)); WBVER = VERSION; }
    WB.setDyn(wbDyn(false));
  }
  function wbVal(sh, a) { return WB.get(sh, a); }
  function wbStyle(sh, a) { var i = (WBM.display[sh].styles || {})[a]; return i === undefined ? null : WBM.styles[i]; }
  var BORD = { thin: "1px solid #8FA79A", hair: "1px solid #B7C7BE", medium: "2px solid #4E6358", thick: "3px solid #2E3D35", double: "3px double #4E6358", dotted: "1px dotted #8FA79A", dashed: "1px dashed #8FA79A" };
  function cssOf(st, numeric) {
    if (!st) return numeric ? "text-align:right" : "";
    var s = [];
    s.push("background:" + (st.bg || "#fff"));
    if (st.fg && st.fg.toUpperCase() !== "#000000") s.push("color:" + st.fg);
    if (st.b) s.push("font-weight:700");
    if (st.i) s.push("font-style:italic");
    if (st.sz && Math.abs(st.sz - 10) > 0.1) s.push("font-size:" + Math.round(st.sz * 1.3) + "px");
    var h = st.h === "centerContinuous" ? "center" : st.h;
    s.push("text-align:" + (h && h !== "general" ? h : numeric ? "right" : "left"));
    if (BORD[st.bt]) s.push("border-top:" + BORD[st.bt]);
    if (BORD[st.bb]) s.push("border-bottom:" + BORD[st.bb]);
    return s.join(";");
  }
  function wbText(sh, a) { var v = wbVal(sh, a); return v === null || YRWB.isErr(v) ? "" : String(typeof v === "number" ? YRWB.format(v, (wbStyle(sh, a) || {}).nf).text : v); }
  function rowLabel(sh, r, col) {
    if (sh === "Saisie") { var t = (wbText("Saisie", "C" + r) || wbText("Saisie", "B" + r)).trim(); return t || ("ligne " + r); }
    var side = col && "JKLMN".indexOf(col) >= 0 ? "I" : "A";
    return (wbText("Etatsfin", side + r) || wbText("Etatsfin", (side === "I" ? "A" : "I") + r)).trim() || ("ligne " + r);
  }
  function describeRef(sh, a) {
    var c = a.replace(/\d+/g, ""), r = +a.replace(/\D+/g, ""), cfg = WBM.cfg, L = latestY(), i, k;
    if (sh === "Saisie actif" || sh === "Saisie passif" || sh === "Saisie TCR") {
      var t = sh === "Saisie actif" ? "ACTIF" : sh === "Saisie passif" ? "PASSIF" : "TCR", rid = RID[t][r];
      for (k = 0; k < WBM.ranks.length; k++) {
        var rk = WBM.ranks[k], cols = t === "ACTIF" ? cfg.ACTIF_GROUPES[rk] : t === "PASSIF" ? [cfg.PASSIF_COLS[rk]] : cfg.TCR_PAIRES[rk];
        i = cols.indexOf(c);
        if (i >= 0) {
          var ck = t === "ACTIF" ? ["brut", "amort", "net"][i] : t === "PASSIF" ? "v" : ["debit", "credit"][i];
          var lab = rid && A.spec[t] ? A.spec[t].labels[rid] : "ligne " + r;
          return { txt: A.tableLabels[t] + " › " + (lab || rid) + " › " + colLabel(t, (L - k) + ":" + ck), go: rid ? t + "." + rid + "." + (L - k) + ":" + ck : null };
        }
      }
      return { txt: sh + "!" + a };
    }
    if (sh === "Saisie" || sh === "Etatsfin") {
      var y = yearOfCol(sh, c);
      return { txt: sh + " › " + rowLabel(sh, r, c) + (y ? " › " + y : ""), go: "WB|" + sh + "|" + a };
    }
    return { txt: sh + "!" + a };
  }
  function wbFlag(v0, v1) { return typeof v0 === "number" && typeof v1 === "number" ? Math.abs(v0 - v1) >= 0.0005 : String(v0) !== String(v1); }
  function wbTd(sh, a, extraCls) {
    var k = "WB|" + sh + "|" + a, st = wbStyle(sh, a), v = wbVal(sh, a), input = wbIsInput(sh, a), f = WB.formula(sh, a);
    var fm = YRWB.format(v, st ? st.nf : null), cls = ["n", "wb"], tip = [];
    if (extraCls) cls.push(extraCls);
    if (input) cls.push("winp");
    if (fm.err) cls.push("werr");
    if (k in S.pending) { cls.push("pend"); tip.push("Saisie non enregistrée"); }
    if (S.sel === k) cls.push("sel");
    if (HL.pre[k]) cls.push("pre");
    var arrow = "";
    if (f) {
      var v0 = WB0.get(sh, a);
      if (wbFlag(v0, v)) {
        cls.push("dlt");
        if (typeof v0 === "number" && typeof v === "number") { arrow = v > v0 ? "▲" : "▼"; tip.push("Avant modifications : " + YRWB.format(v0, st ? st.nf : null).text + " → maintenant : " + fm.text); }
      }
      if (k in PREV && wbFlag(PREV[k], v)) cls.push("flash");
      NEXT[k] = v;
    }
    if (input) tip.push("Saisie analyste (KDZD) : double-clic ou frappe directe");
    var style = cssOf(st, typeof v === "number" || input);
    if (fm.color === "red" || fm.err) style += ";color:#C00000"; else if (input) style += ";color:#1F4E9A;font-weight:600";
    return '<td class="' + cls.join(" ") + '" data-k="' + esc(k) + '" data-e="' + (input ? 1 : 0) + '" style="' + style + '"' + (tip.length ? ' title="' + esc(tip.join(" | ")) + '"' : "") + ">" + (arrow ? '<span class="dl">' + arrow + "</span>" : "") + esc(fm.text) + "</td>";
  }
  function wbLab(sh, a, cls, span) {
    var st = wbStyle(sh, a), t = wbText(sh, a), v = wbVal(sh, a);
    if (YRWB.isErr(v)) t = YRWB.format(v).text;
    return '<td class="' + (cls || "") + '"' + (span ? ' colspan="' + span + '"' : "") + ' style="' + cssOf(st, false) + (YRWB.isErr(v) ? ";color:#C00000" : "") + '" title="' + esc(t) + '">' + esc(t) + "</td>";
  }
  function emptyRow(sh, r, cols) {
    for (var i = 0; i < cols.length; i++) { var v = (WBM.cells[sh] || {})[cols[i] + r]; if (v !== undefined && v !== null && v !== "") return false; if (WB.raw(sh, cols[i] + r).dyn) return false; }
    return true;
  }
  function wbBanner(sh) {
    var h = '<div class="note wbnote">';
    if (sh === "Saisie") h += "Feuille <b>Saisie</b> du modèle ANALYSTE V20, en <b>KDZD</b>. Les colonnes d’exercice reprennent les onglets Actif / Passif / TCR par les formules du modèle ; les cellules <span class=\"winpk\">bleues</span> sont les saisies analyste (annexes, hors bilan, crédit-bail, cessions…). Tout se recalcule pendant la frappe, Etatsfin compris.";
    else h += "Feuille <b>Etatsfin</b> du modèle ANALYSTE V20 (KDZD), calculée en direct depuis la feuille Saisie : bilan fonctionnel, compte de résultat analytique, tableau de flux et ratios. Seul l’échéancier de la dette MLT (2 ans, 2/5 ans, &gt; 5 ans) est à saisir.";
    var n1 = YEARS.filter(function (y) { var s = srcOf("ACTIF", y); return s && s.period === "N1"; });
    if (n1.length) h += '<br><span class="wbwarn">Actif ' + n1.join(", ") + " : seul le Net est connu (colonne N-1 de la liasse suivante). Comme dans l’Excel V20, Brut et Amortissements restent vides : les immobilisations, stocks et créances de cet exercice sont à 0 dans Saisie.</span>";
    return h + "</div>";
  }
  function renderSaisie() {
    if (!WB) return '<div class="warn">Modèle Saisie indisponible (bilan_grid/model_saisie.js manquant).</div>';
    var sh = "Saisie", ks = wbRanks(), ycols = ks.map(function (k) { return WBM.saisieYearCols[k]; }), L = latestY(), d = WBM.display.Saisie, hid = {};
    (d.hiddenRows || []).forEach(function (r) { hid[r] = 1; });
    var h = wbBanner(sh) + '<div class="wrap"><table class="yr wbt" style="min-width:' + (560 + ycols.length * 118) + 'px">';
    h += '<tr><th class="h1 wcode">Réf.</th><th class="h1 wlab" colspan="2" style="text-align:left;font-size:15px">SAISIE (KDZD)</th>';
    ks.forEach(function (k) { h += '<th class="h1 yh wy">' + (L - k) + "<small>" + esc(srcLine("PASSIF", L - k)) + "</small></th>"; });
    h += '<th class="h1 wnote"></th></tr>';
    for (var r = 1; r <= d.lastRow; r++) {
      if (hid[r]) continue;
      if (emptyRow(sh, r, ["A", "B", "C", "J"].concat(ycols))) { h += '<tr class="sp"><td colspan="' + (4 + ycols.length) + '"></td></tr>'; continue; }
      h += "<tr>" + wbLab(sh, "A" + r, "wcode");
      var b = wbText(sh, "B" + r), c = wbText(sh, "C" + r);
      if (r === 3) h += wbLab(sh, "B" + r, "wb1") + wbTd(sh, "C3", "wtxt");
      else if (r === 2) h += wbLab(sh, "B" + r, "wb1") + wbLab(sh, "C" + r, "wb2");
      else if (b && !c) h += wbLab(sh, "B" + r, "wlab", 2);
      else h += wbLab(sh, "B" + r, "wb1") + wbLab(sh, "C" + r, "wb2");
      ycols.forEach(function (col) { h += wbTd(sh, col + r); });
      var note = (WBM.cells.Saisie || {})["J" + r];
      h += '<td class="wnote">' + (typeof note === "string" && note.charAt(0) !== "=" ? '<span title="' + esc(note) + '">ⓘ</span>' : "") + "</td></tr>";
    }
    return h + "</table></div>";
  }
  function renderEtats() {
    if (!WB) return '<div class="warn">Modèle Etatsfin indisponible.</div>';
    var sh = "Etatsfin", ks = wbRanks(), d = WBM.display.Etatsfin, hid = {}, L = latestY();
    (d.hiddenRows || []).forEach(function (r) { hid[r] = 1; });
    var ac = ks.map(function (k) { return WBM.etatsYearCols[k][0]; }), pc = ks.map(function (k) { return WBM.etatsYearCols[k][1]; });
    var h = wbBanner(sh) + '<div class="wrap"><table class="yr wbt" style="min-width:' + (600 + ks.length * 2 * 104) + 'px">';
    h += '<tr><th class="h1 elab" style="text-align:left;font-size:15px">ETATS FINANCIERS (KDZD)</th>';
    ks.forEach(function (k) { h += '<th class="h1 yh wy">' + (L - k) + "</th>"; });
    h += '<th class="h1 elab2" style="text-align:left"></th>';
    ks.forEach(function (k) { h += '<th class="h1 wy">' + (L - k) + "</th>"; });
    h += "</tr>";
    for (var r = 1; r <= d.lastRow; r++) {
      if (hid[r]) continue;
      if (emptyRow(sh, r, ["A", "I"].concat(ac, pc))) { h += '<tr class="sp"><td colspan="' + (2 + ac.length * 2) + '"></td></tr>'; continue; }
      h += "<tr>" + wbLab(sh, "A" + r, "elab");
      if (r <= 3) h += wbLab(sh, "D" + r, "ehead", ac.length); // unité, société, groupe (colonne D du modèle)
      else ac.forEach(function (col) { h += wbTd(sh, col + r); });
      h += wbLab(sh, "I" + r, "elab2");
      pc.forEach(function (col) { h += wbTd(sh, col + r); });
      h += "</tr>";
    }
    return h + "</table></div>";
  }
  function wbChecks() {
    // Contrôles portés par le classeur : Actif = Passif, Résultat net, total actif Saisie / Etatsfin
    if (!WB) return [];
    var out = [], L = latestY();
    wbRanks().forEach(function (k) {
      var y = L - k, sc = WBM.saisieYearCols[k], ec = WBM.etatsYearCols[k][0];
      [["Saisie", sc + "118", "Saisie : Actif = Passif", sc + "119"], ["Saisie", sc + "184", "Saisie : Résultat net (CR) = Résultat au passif", sc + "185"],
       ["Saisie", sc + "212", "Saisie : Total actif net = Etatsfin", null], ["Etatsfin", ec + "32", "Etatsfin : Actif = Passif", WBM.etatsYearCols[k][1] + "32"]].forEach(function (x) {
        var v = wbVal(x[0], x[1]); if (v === null || v === "" || v === "OK" || v === 0) return;
        var g = x[3] ? wbVal(x[0], x[3]) : null;
        out.push({ c: x[2], y: y, v: YRWB.isErr(v) ? v.e : String(v), g: typeof g === "number" ? g : null, k: "WB|" + x[0] + "|" + (x[3] && typeof g === "number" ? x[3] : x[1]) });
      });
    });
    return out;
  }
  function parseKD(s) {
    s = String(s || "").replace(/[\s  ]/g, "");
    if (s === "" || s === "-") return { ok: true, v: null };
    var neg = /^\(.*\)$/.test(s); s = s.replace(/[()]/g, "");
    if (s.indexOf(",") >= 0 && s.indexOf(".") < 0) s = s.replace(",", "."); else s = s.replace(/,/g, "");
    if (!/^[-+]?\d*\.?\d+$/.test(s)) return { ok: false };
    var x = Number(s); if (neg) x = -x;
    return { ok: true, v: Math.round(x * 1000) / 1000 };
  }
  function isTextKey(k) { return isWB(k) && wbParts(k).a === "C3"; }
  function editParse(k, s) { if (isTextKey(k)) { s = String(s || "").trim(); return { ok: true, v: s === "" ? null : s }; } return isWB(k) ? parseKD(s) : parseIn(s); }
  function editInit(k) { var v = curVal(k); if (isTextKey(k)) return v === null ? "" : String(v); if (isWB(k)) return v === null ? "" : String(v).replace(".", ","); return editStr(v); }
  function renderWbFbar() {
    var k = S.sel, q = wbParts(k), v = wbVal(q.sh, q.a), st = wbStyle(q.sh, q.a), f = WB.formula(q.sh, q.a), y = yearOfCol(q.sh, q.c);
    var name = q.sh + " › " + (q.a === "C3" ? "Groupe" : rowLabel(q.sh, q.r, q.c)) + (y ? " › " + y : "") + "  (" + q.a + ")";
    var h = '<div class="fbar wbf"><div class="nm" title="' + esc(name) + '">' + esc(name) + '</div><div class="fx">';
    if (wbIsInput(q.sh, q.a)) {
      var cv = curVal(k);
      h += "<span><i>fx</i>Saisie analyste" + (isTextKey(k) ? "" : " (KDZD)") + " : <b>" + (cv === null ? "vide" : esc(isTextKey(k) ? cv : YRWB.format(cv, st ? st.nf : null).text)) + "</b></span>";
      if (k in S.pending) { var b0 = S.pending[k].base; h += '<span class="muted">enregistré : ' + (b0 === null ? "vide" : esc(String(b0))) + "</span>"; }
      h += '<span class="muted">Double-clic, Entrée ou frappe directe pour saisir ; Suppr pour vider.</span>';
    } else if (f) {
      h += '<span class="fxf"><i>fx</i>' + esc(f) + "</span><span>= <b>" + esc(YRWB.format(v, st ? st.nf : null).text || "vide") + "</b></span>";
      var v0 = WB0.get(q.sh, q.a);
      if (wbFlag(v0, v) && typeof v0 === "number" && typeof v === "number") h += '<span class="imp">avant modifications : ' + esc(YRWB.format(v0, st ? st.nf : null).text) + "</span>";
      var refs = WB.refsOf(q.sh, q.a), seen = {}, items = [];
      refs.forEach(function (rf) {
        var key = rf.sh + "!" + rf.a; if (seen[key]) return; seen[key] = 1;
        var dsc = describeRef(rf.sh, rf.a), rv = WB.get(rf.sh, rf.a), rs = wbStyle(rf.sh, rf.a);
        items.push('<span class="ref"' + (dsc.go ? ' data-goref="' + esc(dsc.go) + '"' : "") + ' title="' + esc(key) + '">' + esc(dsc.txt) + " = <b>" + esc(YRWB.format(rv, rs ? rs.nf : "#,##0.0").text || "vide") + "</b></span>");
      });
      if (items.length) h += '<span class="refs">' + items.slice(0, 12).join("") + (items.length > 12 ? "<span>… +" + (items.length - 12) + "</span>" : "") + "</span>";
    } else h += '<span class="muted">Cellule vide du modèle.</span>';
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
  function tableHtml() { return S.tab === "ACTIF" ? renderBalance("ACTIF") : S.tab === "PASSIF" ? renderBalance("PASSIF") : S.tab === "TCR" ? renderTCR() : S.tab === "SAISIE" ? renderSaisie() : S.tab === "ETATS" ? renderEtats() : null; }
  function render() {
    if (!A) return;
    if (!YEARS.length) { document.getElementById("app").innerHTML = '<div class="warn">Aucun exercice exploitable dans les liasses extraites.</div>'; setTimeout(setHeight, 0); return; }
    var focusMotif = document.activeElement && document.activeElement.id === "motif";
    buildModel();
    HL = isGridTab() && S.sel && tabOfKey(S.sel) === S.tab ? traceKeys(S.sel) : { dep: {}, pre: {} };
    if (isWBTab() && S.sel && tabOfKey(S.sel) === S.tab && WB) { var wq = wbParts(S.sel); WB.refsOf(wq.sh, wq.a).forEach(function (rf) { if (rf.sh === wq.sh) HL.pre["WB|" + rf.sh + "|" + rf.a] = 1; }); }
    NEXT = {};
    var nP = Object.keys(S.pending).length, h = kpis();
    (A.warnings || []).forEach(function (w) { h += '<div class="warn">' + esc(w) + "</div>"; });
    h += '<div class="bar"><div class="tabs">';
    [["ACTIF", "Actif"], ["PASSIF", "Passif"], ["TCR", "TCR"], ["SAISIE", "Saisie"], ["ETATS", "Etatsfin"], ["RATIOS", "Ratios"], ["CTRL", "Contrôles"]].forEach(function (x) {
      h += '<button data-tab="' + x[0] + '" class="' + (S.tab === x[0] ? "on" : "") + '">' + x[1] + (x[0] === "CTRL" && M.nbAlerts ? '<span class="cnt">' + M.nbAlerts + "</span>" : "") + "</button>";
    });
    h += '</div><div class="sp"></div>' + (isGridTab() ? '<button class="pdfbtn' + (S.pdf.open ? " on" : "") + '" data-pdftoggle="1" title="Afficher la page de la liasse à côté du tableau">📄 Liasse PDF</button>' : "") + (isWBTab() ? '<span class="muted wunit">Unité : KDZD (000 DZD)</span></div>' : '<div class="unit"><button data-unit="KDZD" class="' + (S.unit === "KDZD" ? "on" : "") + '">KDZD</button><button data-unit="DZD" class="' + (S.unit === "DZD" ? "on" : "") + '">DZD</button></div></div>');
    if (nP || S.msg) {
      h += '<div class="pendbar"><b>' + nP + " modification" + (nP > 1 ? "s" : "") + " non enregistrée" + (nP > 1 ? "s" : "") + "</b>";
      h += '<input id="motif" placeholder="' + (onlyWB() ? "Commentaire (facultatif pour les saisies Saisie / Etatsfin)" : "Motif de correction (obligatoire)") + '" value="' + esc(S.motif) + '">';
      h += '<button class="pri" id="save"' + (S.saving ? " disabled" : "") + ">" + (S.saving ? "Enregistrement…" : "Enregistrer") + '</button><button id="discard">Tout annuler</button>';
      if (S.msg) h += '<span class="err">' + esc(S.msg) + "</span>";
      h += "</div>";
    }
    if (isGridTab()) h += (S.sel && tabOfKey(S.sel) !== S.tab) ? renderFbarEmpty() : renderFbar();
    if (isWBTab()) h += (S.sel && tabOfKey(S.sel) === S.tab) ? renderWbFbar() : '<div class="fbar wbf"><div class="nm">—</div><div class="fx"><span class="muted">Sélectionnez une cellule pour voir sa formule du modèle et ses composantes (cliquables). Cellules bleues = saisie analyste.</span></div></div>';
    if (isGridTab() && S.pdf.open) { followSel(); h += '<div class="split"><div class="gcol">' + tableHtml() + "</div>" + renderPdf() + "</div>"; }
    else h += (isGridTab() || isWBTab()) ? tableHtml() : S.tab === "RATIOS" ? renderRatios() : renderCtrl();
    if (isGridTab()) {
      h += '<div class="leg"><span><i style="background:#FFF8E1"></i>Saisie (valeur liasse, modifiable)</span><span><i style="background:#EAF5EF"></i>Sous-total (formule)</span><span><i style="background:#C6E5D4"></i>Section</span><span><i style="background:#00573F"></i>Total</span>' +
        '<span><i style="background:#FFF2CC;border:2px solid #C9A227"></i>Écart LOW ≥ 1 000 DZD</span><span><i style="background:#F8CBAD;border:2px solid #ED7D31"></i>MEDIUM ≥ 10 000</span><span><i style="background:#FFC7CE;border:2px solid #FF0000"></i>HIGH ≥ 1 M ou mauvais côté TCR</span>' +
        '<span><i style="background:linear-gradient(225deg,#7030A0 30%,#fff 30%)"></i>Corrigée</span><span><i style="background:linear-gradient(135deg,#ED7D31 30%,#fff 30%)"></i>Non enregistrée</span>' +
        '<span><i style="background:linear-gradient(90deg,#2F75B5 0,#2F75B5 4px,#fff 4px)"></i>Formule impactée (▲▼)</span><span><i style="outline:2px dashed #2F75B5;outline-offset:-3px"></i>Dépendants</span><span><i style="outline:2px dotted #00915A;outline-offset:-3px"></i>Composantes</span><span><i style="background:repeating-linear-gradient(135deg,#F4F6F5 0 3px,#fff 3px 6px)"></i>Non disponible dans la liasse</span></div>';
    }
    if (isWBTab()) {
      h += '<div class="leg"><span><i style="background:#fff;border-color:#1F4E9A"></i><b style="color:#1F4E9A">Saisie analyste</b></span><span><i style="background:#EAF5EF"></i>Sous-total (formule du modèle)</span><span><i style="background:#00915A"></i>En-tête</span>' +
        '<span><i style="background:linear-gradient(90deg,#2F75B5 0,#2F75B5 4px,#fff 4px)"></i>Formule impactée par vos modifications (▲▼)</span><span><i style="outline:2px dotted #00915A;outline-offset:-3px"></i>Composantes de la cellule</span><span><b style="color:#C00000">Négatif ! / Erreur!</b> contrôle du modèle</span></div>';
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
      newWrap.scrollLeft = keepX !== null ? keepX : S.tab === "ETATS" ? 0 : newWrap.scrollWidth; // par défaut : exercice le plus récent (N à droite, comme le V20)
      var selTd = S.sel ? tdOf(S.sel) : null;
      if (selTd) {
        var wr = newWrap.getBoundingClientRect(), cr = selTd.getBoundingClientRect(), labW = stickyW(newWrap);
        if (cr.right > wr.right) newWrap.scrollLeft += cr.right - wr.right + 8;
        else if (cr.left < wr.left + labW) newWrap.scrollLeft -= (wr.left + labW) - cr.left + 8;
      }
      // Alignement sur le début d'un exercice (pas de colonne coupée sous les libellés figés)
      var lw = stickyW(newWrap), sl = newWrap.scrollLeft;
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

  function stickyW(wrap) {
    var row = wrap.querySelector("tr:nth-child(2)") || wrap.querySelector("tr"), mx = 0, left = wrap.getBoundingClientRect().left;
    if (!row) return 0;
    Array.prototype.forEach.call(row.querySelectorAll("td.lab,td.lcd,td.lc,td.ld,td.wcode,td.wb1,td.wb2,td.wlab,td.elab"), function (td) { mx = Math.max(mx, td.getBoundingClientRect().right - left); });
    return mx;
  }
  // ---------- Édition ----------
  function tdOf(k) { return document.querySelector('td[data-k="' + (window.CSS && CSS.escape ? CSS.escape(k) : k) + '"]'); }
  function setPending(k, v) {
    var q = k.split("."), b = isWB(k) ? wbBase(k) : baseVal(q[0], q[1], q[2]);
    S.undo.push({ k: k, had: k in S.pending, prev: S.pending[k] });
    if ((v === null && b === null) || (v !== null && b !== null && (typeof v === "string" ? v === b : Math.abs(v - b) < (isWB(k) ? 0.0005 : 0.005)))) delete S.pending[k];
    else S.pending[k] = { value: v, base: b };
    S.msg = "";
  }
  function openEditor(k, init) {
    var td = tdOf(k); if (!td) { S.edit = null; return; }
    S.preview = null;
    td.classList.add("ed");
    td.innerHTML = '<input id="cellIn" autocomplete="off">';
    var inp = document.getElementById("cellIn");
    inp.value = init !== undefined && init !== null ? init : editInit(k);
    if (isTextKey(k)) inp.style.textAlign = "left";
    inp.focus();
    if (init === undefined || init === null) inp.select(); else inp.setSelectionRange(inp.value.length, inp.value.length);
    S.edit = { k: k };
    if (init !== undefined && init !== null) livePatch();
  }
  function commitEdit(move) {
    var inp = document.getElementById("cellIn"); if (!inp || !S.edit) return true;
    var r = editParse(S.edit.k, inp.value);
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
    var r = editParse(S.edit.k, inp.value); inp.classList.toggle("bad", !r.ok); if (!r.ok) return;
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
    var gr = t.closest("[data-goref]");
    if (gr) {
      if (S.edit && !commitEdit()) return;
      var gk = gr.getAttribute("data-goref"); S.tab = tabOfKey(gk); S.sel = gk; render();
      var tg = tdOf(gk); if (tg && tg.scrollIntoView) tg.scrollIntoView({ block: "center", inline: "center" });
      return;
    }
    var go = t.closest("[data-go]");
    if (go) {
      var id = go.getAttribute("data-go"), key = id.charAt(0) === "a" ? M.alerts[+id.slice(1)].k : id.charAt(0) === "w" ? wbChecks()[+id.slice(1)].k : M.cross[+id.slice(1)].go;
      S.tab = tabOfKey(key); S.sel = key; render();
      var td0 = tdOf(S.sel); if (td0 && td0.scrollIntoView) td0.scrollIntoView({ block: "center", inline: "center" });
      return;
    }
    var td = t.closest("td[data-k]");
    if (td && !td.classList.contains("ed")) {
      if (S.edit && !commitEdit()) return;
      var ck = td.getAttribute("data-k");
      // double-clic : le 1er clic redessine la grille, le navigateur ne voit donc pas de dblclick -> détection par le délai
      var tnow = Date.now(), dbl = LASTCLICK.k === ck && tnow - LASTCLICK.t < 500;
      LASTCLICK = { k: ck, t: tnow };
      if (dbl && ck === S.sel && td.getAttribute("data-e") === "1") { openEditor(ck); return; }
      S.sel = ck; render();
    }
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
    if ((/^[0-9\-,.(]$/.test(e.key) || (isTextKey(S.sel) && e.key.length === 1)) && !e.ctrlKey && !e.metaKey) { e.preventDefault(); openEditor(S.sel, e.key); }
  });

  var LASTCLICK = { k: null, t: 0 };
  function onlyWB() { var ks = Object.keys(S.pending); return ks.length > 0 && ks.every(isWB); }
  function save() {
    var keys = Object.keys(S.pending); if (!keys.length) return;
    var m = (document.getElementById("motif") || {}).value || S.motif || "";
    if (!m.trim() && !onlyWB()) { S.msg = "Motif obligatoire pour corriger une valeur de liasse."; render(); var mi = document.getElementById("motif"); if (mi) mi.focus(); return; }
    S.motif = m; S.saving = true; S.msg = ""; render();
    send("streamlit:setComponentValue", { dataType: "json", value: { action: "save", nonce: Date.now() + "-" + Math.random().toString(36).slice(2), motif: m.trim(),
      changes: keys.map(function (k) {
        if (isWB(k)) { var w = wbParts(k); return { table: "WB", sheet: w.sh, addr: w.a, year: yearOfCol(w.sh, w.c), row: w.r, value: S.pending[k].value }; }
        var q = k.split("."); return { table: q[0], row: q[1], col: q[2], value: S.pending[k].value }; }) } });
  }
})();
