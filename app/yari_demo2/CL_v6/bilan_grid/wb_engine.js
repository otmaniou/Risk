/* Ya-Risk — moteur de formules Excel (sous-ensemble utilisé par le modèle ANALYSTE V20).
 * Évalue dans le navigateur les formules EXACTES du classeur (lues par tools/build_saisie_model.py) :
 * opérateurs + - * / ^ & % = <> < > <= >=, références et plages inter-feuilles, IF, SUM, AND, OR, TODAY
 * (+ MIN, MAX, ABS, ROUND, IFERROR par sécurité). Sémantique Excel : cellule vide = 0 ou "", texte en
 * calcul = #VALEUR!, division par zéro = #DIV/0!, propagation des erreurs.
 */
(function () {
  "use strict";
  function E(code) { return { e: code }; }
  function isErr(v) { return v !== null && typeof v === "object" && "e" in v; }
  var BLANK = null;

  // ---------- Analyse lexicale ----------
  var RE_REF = /^(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\w(])/;
  function tokenize(src) {
    var s = src.charAt(0) === "=" ? src.slice(1) : src, i = 0, out = [];
    while (i < s.length) {
      var ch = s.charAt(i), rest = s.slice(i), m;
      if (/\s/.test(ch)) { i++; continue; }
      if (ch === '"') {
        var j = i + 1, str = "";
        while (j < s.length) { if (s.charAt(j) === '"') { if (s.charAt(j + 1) === '"') { str += '"'; j += 2; continue; } break; } str += s.charAt(j); j++; }
        out.push({ t: "str", v: str }); i = j + 1; continue;
      }
      if ((m = /^#(REF!|DIV\/0!|N\/A|VALUE!|NAME\?|NUM!|NULL!)/.exec(rest))) { out.push({ t: "err", v: "#" + m[1] }); i += m[0].length; continue; }
      // référence avec feuille : 'Nom feuille'!A1  |  Nom!A1  |  [1]Nom!A1  |  Nom!#REF!
      if ((m = /^(?:'((?:[^']|'')+)'|([A-Za-z_\[\]0-9][\w.\[\]]*))!/.exec(rest))) {
        var sheet = (m[1] !== undefined ? m[1].replace(/''/g, "'") : m[2]);
        var after = rest.slice(m[0].length), r2;
        if ((r2 = RE_REF.exec(after))) { out.push({ t: "ref", sh: sheet, c: r2[2], r: +r2[4] }); i += m[0].length + r2[0].length; continue; }
        if (/^#REF!/.test(after)) { out.push({ t: "err", v: "#REF!" }); i += m[0].length + 5; continue; }
      }
      if ((m = /^(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)/.exec(rest))) { out.push({ t: "num", v: parseFloat(m[1]) }); i += m[0].length; continue; }
      if ((m = /^(TRUE|FALSE|VRAI|FAUX)(?![\w(])/i.exec(rest))) { out.push({ t: "bool", v: /^(TRUE|VRAI)$/i.test(m[1]) }); i += m[0].length; continue; }
      if ((m = RE_REF.exec(rest))) { out.push({ t: "ref", sh: null, c: m[2], r: +m[4] }); i += m[0].length; continue; }
      if ((m = /^([A-Za-z_][\w.]*)\s*\(/.exec(rest))) { out.push({ t: "fn", v: m[1].toUpperCase() }); i += m[0].length; continue; }
      if ((m = /^(<=|>=|<>)/.exec(rest))) { out.push({ t: "op", v: m[1] }); i += 2; continue; }
      if ("+-*/^&=<>%".indexOf(ch) >= 0) { out.push({ t: "op", v: ch }); i++; continue; }
      if (ch === "(" || ch === ")" || ch === "," || ch === ";" || ch === ":") { out.push({ t: ch }); i++; continue; }
      throw new Error("Caractère inattendu « " + ch + " » dans " + src);
    }
    return out;
  }

  // ---------- Analyse syntaxique ----------
  function parse(src) {
    var tk = tokenize(src), p = 0;
    function peek() { return tk[p]; }
    function isOp(v) { var x = tk[p]; return x && x.t === "op" && x.v === v; }
    function expect(t) { var x = tk[p]; if (!x || x.t !== t) throw new Error("« " + t + " » attendu dans " + src); p++; return x; }
    function cmp() {
      var a = cat();
      while (peek() && peek().t === "op" && /^(=|<>|<|>|<=|>=)$/.test(peek().v)) { var o = tk[p++].v; a = { k: "bin", o: o, a: a, b: cat() }; }
      return a;
    }
    function cat() { var a = add(); while (isOp("&")) { p++; a = { k: "bin", o: "&", a: a, b: add() }; } return a; }
    function add() { var a = mul(); while (isOp("+") || isOp("-")) { var o = tk[p++].v; a = { k: "bin", o: o, a: a, b: mul() }; } return a; }
    function mul() { var a = pow(); while (isOp("*") || isOp("/")) { var o = tk[p++].v; a = { k: "bin", o: o, a: a, b: pow() }; } return a; }
    function pow() { var a = una(); while (isOp("^")) { p++; a = { k: "bin", o: "^", a: a, b: una() }; } return a; }
    function una() { if (isOp("-")) { p++; return { k: "neg", a: una() }; } if (isOp("+")) { p++; return una(); } return post(); }
    function post() { var a = prim(); while (isOp("%")) { p++; a = { k: "pct", a: a }; } return a; }
    function prim() {
      var x = tk[p++];
      if (!x) throw new Error("Formule incomplète : " + src);
      if (x.t === "num") return { k: "lit", v: x.v };
      if (x.t === "str") return { k: "lit", v: x.v };
      if (x.t === "bool") return { k: "lit", v: x.v };
      if (x.t === "err") return { k: "lit", v: E(x.v) };
      if (x.t === "ref") {
        if (peek() && peek().t === ":") {
          p++; var y = expect("ref");
          return { k: "rng", sh: x.sh, c1: x.c, r1: x.r, c2: y.c, r2: y.r };
        }
        return { k: "ref", sh: x.sh, c: x.c, r: x.r };
      }
      if (x.t === "fn") {
        var args = [];
        if (peek() && peek().t === ")") { p++; return { k: "fn", f: x.v, args: args }; }
        while (true) {
          if (peek() && (peek().t === "," || peek().t === ";")) args.push({ k: "lit", v: BLANK, omitted: true });
          else args.push(cmp());
          var nx = tk[p++];
          if (!nx) throw new Error("« ) » attendu : " + src);
          if (nx.t === ")") break;
          if (nx.t !== "," && nx.t !== ";") throw new Error("Séparateur attendu : " + src);
          if (peek() && peek().t === ")") { args.push({ k: "lit", v: BLANK, omitted: true }); p++; break; }
        }
        return { k: "fn", f: x.v, args: args };
      }
      if (x.t === "(") { var e = cmp(); expect(")"); return e; }
      throw new Error("Élément inattendu dans " + src);
    }
    var ast = cmp();
    if (p < tk.length) throw new Error("Fin de formule inattendue : " + src);
    return ast;
  }

  // ---------- Conversions ----------
  var MS_DAY = 86400000, EPOCH = Date.UTC(1899, 11, 30);
  function serialOf(iso) { var a = iso.split("-"); return Math.round((Date.UTC(+a[0], +a[1] - 1, +a[2]) - EPOCH) / MS_DAY); }
  function isoOf(serial) { var d = new Date(EPOCH + Math.round(serial) * MS_DAY); return d; }
  function todaySerial() { var n = new Date(); return Math.round((Date.UTC(n.getFullYear(), n.getMonth(), n.getDate()) - EPOCH) / MS_DAY); }
  function toNum(v) {
    if (v === BLANK) return 0;
    if (typeof v === "number") return v;
    if (typeof v === "boolean") return v ? 1 : 0;
    if (isErr(v)) return v;
    if (typeof v === "string") {
      var s = v.replace(/[\s  ]/g, "");
      if (s === "") return E("#VALUE!");
      if (/^[-+]?\d+(,\d+)?$/.test(s)) return parseFloat(s.replace(",", "."));
      if (/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(s)) return parseFloat(s);
      return E("#VALUE!");
    }
    return E("#VALUE!");
  }
  function toBool(v) {
    if (v === BLANK) return false;
    if (typeof v === "boolean") return v;
    if (typeof v === "number") return v !== 0;
    if (isErr(v)) return v;
    if (typeof v === "string") { if (/^(TRUE|VRAI)$/i.test(v)) return true; if (/^(FALSE|FAUX)$/i.test(v)) return false; }
    return E("#VALUE!");
  }
  function toStr(v) {
    if (v === BLANK) return "";
    if (typeof v === "boolean") return v ? "VRAI" : "FAUX";
    if (typeof v === "number") return String(+v.toPrecision(15));
    return String(v);
  }
  function compare(a, b) {
    // renvoie -1 / 0 / 1 selon l'ordre Excel : nombres < textes < booléens
    if (a === BLANK) a = typeof b === "string" ? "" : typeof b === "boolean" ? false : 0;
    if (b === BLANK) b = typeof a === "string" ? "" : typeof a === "boolean" ? false : 0;
    var ra = typeof a === "number" ? 0 : typeof a === "string" ? 1 : 2, rb = typeof b === "number" ? 0 : typeof b === "string" ? 1 : 2;
    if (ra !== rb) return ra < rb ? -1 : 1;
    if (ra === 1) { a = a.toLowerCase(); b = b.toLowerCase(); }
    if (ra === 0 && Math.abs(a - b) < 1e-9 * Math.max(1, Math.abs(a), Math.abs(b))) return 0;
    return a < b ? -1 : a > b ? 1 : 0;
  }

  // ---------- Classeur ----------
  function Workbook(model) {
    this.model = model;
    this.cells = model.cells;          // { feuille: { A1: valeur | "=formule" | {d: iso} } }
    this.dyn = {};                     // valeurs injectées : { "Feuille!A1": valeur }
    this.cache = {}; this.compiled = {}; this.visiting = {};
  }
  Workbook.prototype.reset = function () { this.cache = {}; this.visiting = {}; };
  Workbook.prototype.setDyn = function (map) { this.dyn = map || {}; this.reset(); };
  Workbook.prototype.raw = function (sh, a) {
    var k = sh + "!" + a;
    if (k in this.dyn) return { dyn: true, v: this.dyn[k] };
    var c = (this.cells[sh] || {})[a];
    return { dyn: false, v: c === undefined ? BLANK : c };
  };
  Workbook.prototype.formula = function (sh, a) {
    var r = this.raw(sh, a);
    return !r.dyn && typeof r.v === "string" && r.v.charAt(0) === "=" ? r.v : null;
  };
  Workbook.prototype.get = function (sh, a) {
    var k = sh + "!" + a;
    if (k in this.cache) return this.cache[k];
    if (!(sh in this.cells)) return E("#REF!");
    var r = this.raw(sh, a), v = r.v;
    if (!r.dyn && typeof v === "string" && v.charAt(0) === "=") {
      if (this.visiting[k]) return E("#CIRC!");
      this.visiting[k] = true;
      try {
        var ast = this.compiled[k];
        if (!ast) { try { ast = parse(v); } catch (ex) { ast = { k: "lit", v: E("#NAME?") }; } this.compiled[k] = ast; }
        v = this.ev(ast, sh);
        if (v && v.range) v = E("#VALUE!");
        if (v === BLANK) v = 0;
      } finally { delete this.visiting[k]; }
    } else if (v !== null && typeof v === "object" && v.d) v = serialOf(v.d);
    this.cache[k] = v;
    return v;
  };
  function colNum(c) { var n = 0; for (var i = 0; i < c.length; i++) n = n * 26 + c.charCodeAt(i) - 64; return n; }
  function colName(n) { var s = ""; while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }
  Workbook.prototype.rangeVals = function (node, home) {
    var sh = node.sh || home, out = [];
    if (!(sh in this.cells)) return [E("#REF!")];
    var c1 = colNum(node.c1), c2 = colNum(node.c2), r1 = Math.min(node.r1, node.r2), r2 = Math.max(node.r1, node.r2);
    if (c1 > c2) { var t = c1; c1 = c2; c2 = t; }
    for (var r = r1; r <= r2; r++) for (var c = c1; c <= c2; c++) out.push(this.get(sh, colName(c) + r));
    return out;
  };
  Workbook.prototype.ev = function (n, home) {
    var self = this, a, b;
    switch (n.k) {
      case "lit": return n.v;
      case "ref": {
        var sh = n.sh || home;
        if (!(sh in this.cells)) return E("#REF!");
        var raw = this.raw(sh, n.c + n.r);
        var v = this.get(sh, n.c + n.r);
        return raw.v === BLANK ? BLANK : v;
      }
      case "rng": return { range: true, vals: this.rangeVals(n, home) };
      case "neg": a = toNum(this.ev(n.a, home)); return isErr(a) ? a : -a;
      case "pct": a = toNum(this.ev(n.a, home)); return isErr(a) ? a : a / 100;
      case "bin": {
        a = this.ev(n.a, home); b = this.ev(n.b, home);
        if (a && a.range) a = E("#VALUE!"); if (b && b.range) b = E("#VALUE!");
        if (n.o === "&") { if (isErr(a)) return a; if (isErr(b)) return b; return toStr(a) + toStr(b); }
        if (/^(=|<>|<|>|<=|>=)$/.test(n.o)) {
          if (isErr(a)) return a; if (isErr(b)) return b;
          var c = compare(a, b);
          return n.o === "=" ? c === 0 : n.o === "<>" ? c !== 0 : n.o === "<" ? c < 0 : n.o === ">" ? c > 0 : n.o === "<=" ? c <= 0 : c >= 0;
        }
        a = toNum(a); if (isErr(a)) return a; b = toNum(b); if (isErr(b)) return b;
        if (n.o === "+") return a + b;
        if (n.o === "-") return a - b;
        if (n.o === "*") return a * b;
        if (n.o === "/") return b === 0 ? E("#DIV/0!") : a / b;
        if (n.o === "^") return Math.pow(a, b);
        return E("#VALUE!");
      }
      case "fn": return this.fn(n, home);
    }
    return E("#VALUE!");
  };
  Workbook.prototype.fn = function (n, home) {
    var self = this, f = n.f, args = n.args;
    function arg(i) { var v = self.ev(args[i], home); return v && v.range ? E("#VALUE!") : v; }
    // valeurs « agrégables » : plage / référence = nombres seuls ; valeur directe = convertie
    function nums(i, logical) {
      var node = args[i], v = self.ev(node, home), out = [];
      if (v && v.range) { for (var j = 0; j < v.vals.length; j++) { var x = v.vals[j]; if (isErr(x)) return x; if (typeof x === "number" || (logical && typeof x === "boolean")) out.push(x); } return out; }
      if (node.k === "ref") { if (isErr(v)) return v; if (typeof v === "number" || (logical && typeof v === "boolean")) out.push(v); return out; }
      if (node.omitted) return out;
      var y = logical ? toBool(v) : toNum(v); if (isErr(y)) return y; out.push(y); return out;
    }
    var i, all, r;
    switch (f) {
      case "IF": {
        var c = toBool(arg(0)); if (isErr(c)) return c;
        if (c) { if (args.length < 2) return true; r = arg(1); return args[1].omitted ? 0 : r; }
        if (args.length < 3) return false; r = arg(2); return args[2].omitted ? 0 : r;
      }
      case "IFERROR": { r = arg(0); return isErr(r) ? arg(1) : r; }
      case "SUM": case "MIN": case "MAX": {
        all = [];
        for (i = 0; i < args.length; i++) { r = nums(i, false); if (isErr(r)) return r; all = all.concat(r); }
        if (f === "SUM") return all.reduce(function (s, x) { return s + x; }, 0);
        if (!all.length) return 0;
        return f === "MIN" ? Math.min.apply(null, all) : Math.max.apply(null, all);
      }
      case "AND": case "OR": {
        all = [];
        for (i = 0; i < args.length; i++) { r = nums(i, true); if (isErr(r)) return r; all = all.concat(r.map(function (x) { return typeof x === "boolean" ? x : x !== 0; })); }
        if (!all.length) return E("#VALUE!");
        return f === "AND" ? all.every(Boolean) : all.some(Boolean);
      }
      case "NOT": { r = toBool(arg(0)); return isErr(r) ? r : !r; }
      case "TODAY": return todaySerial();
      case "ABS": { r = toNum(arg(0)); return isErr(r) ? r : Math.abs(r); }
      case "ROUND": { r = toNum(arg(0)); var d = toNum(arg(1)); if (isErr(r)) return r; if (isErr(d)) return d; var p = Math.pow(10, d); return Math.round(r * p) / p; }
    }
    return E("#NAME?");
  };
  // Références directes d'une formule (pour la barre de formule et le surlignage)
  Workbook.prototype.refsOf = function (sh, a) {
    var f = this.formula(sh, a); if (!f) return [];
    var out = [];
    try {
      tokenize(f).forEach(function (t) { if (t.t === "ref") out.push({ sh: t.sh || sh, a: t.c + t.r }); });
    } catch (ex) { /* formule non analysable */ }
    return out;
  };

  // ---------- Formats de nombre Excel ----------
  function splitSections(nf) {
    var out = [], cur = "", q = false, br = false;
    for (var i = 0; i < nf.length; i++) {
      var ch = nf.charAt(i);
      if (ch === '"' && !br) q = !q;
      else if (ch === "[" && !q) br = true;
      else if (ch === "]" && !q) br = false;
      if (ch === ";" && !q && !br) { out.push(cur); cur = ""; continue; }
      if (ch === "\\" && !q) { cur += ch + nf.charAt(i + 1); i++; continue; }
      cur += ch;
    }
    out.push(cur); return out;
  }
  function grpFr(intStr) { return intStr.replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function fmtNumber(x, dec, group) {
    var s = Math.abs(x).toFixed(dec), parts = s.split(".");
    var ip = group ? grpFr(parts[0]) : parts[0];
    return ip + (dec ? "," + parts[1] : "");
  }
  function general(x) {
    if (!isFinite(x)) return "#NUM!";
    var ax = Math.abs(x), s;
    if (ax !== 0 && (ax >= 1e11 || ax < 1e-9)) s = x.toExponential(4).replace(".", ",");
    else { s = String(+x.toPrecision(10)); var neg = s.charAt(0) === "-"; if (neg) s = s.slice(1); var p = s.split("."); s = (neg ? "-" : "") + grpFr(p[0]) + (p[1] ? "," + p[1] : ""); }
    return s;
  }
  var MOIS = ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"];
  function fmtDate(serial, sec) {
    var d = isoOf(serial), Y = d.getUTCFullYear(), Mo = d.getUTCMonth() + 1, D = d.getUTCDate();
    var s = sec.replace(/\[[^\]]*\]/g, "").replace(/"([^"]*)"/g, "$1").replace(/\\(.)/g, "$1");
    return s.replace(/yyyy|yy|mmmm|mmm|mm|m|dd|d/gi, function (t) {
      t = t.toLowerCase();
      if (t === "yyyy") return String(Y); if (t === "yy") return String(Y).slice(2);
      if (t === "mmmm" || t === "mmm") return MOIS[Mo - 1]; if (t === "mm") return (Mo < 10 ? "0" : "") + Mo; if (t === "m") return String(Mo);
      if (t === "dd") return (D < 10 ? "0" : "") + D; return String(D);
    });
  }
  // Renvoie { text, color } ; color = "red" si la section porte [Red]
  function format(v, nf) {
    if (v === BLANK || v === undefined) return { text: "" };
    if (isErr(v)) return { text: v.e === "#VALUE!" ? "#VALEUR!" : v.e, err: true };
    if (typeof v === "boolean") return { text: v ? "VRAI" : "FAUX" };
    if (typeof v === "string") return { text: v };
    nf = nf || "General";
    var secs = splitSections(nf), sec = secs[0], x = v, signDone = false;
    if (secs.length >= 2 && v < 0) { sec = secs[1]; x = -v; signDone = true; }
    else if (secs.length >= 3 && v === 0) { sec = secs[2]; }
    var red = /\[Red\]|\[Rouge\]/i.test(sec);
    var body = sec.replace(/\[[^\]]*\]/g, "");
    var bare = body.replace(/"[^"]*"/g, "").replace(/\\./g, "");
    if (/^\s*General\s*$/i.test(body) || body.trim() === "") {
      if (body.trim() === "" && secs.length >= 2) return { text: "", color: red ? "red" : null };
      return { text: general(signDone ? -x : x), color: red ? "red" : null };
    }
    if (/[yd]/i.test(bare) || /m/i.test(bare.replace(/[#0.,%]/g, "")) && !/[#0]/.test(bare)) return { text: fmtDate(v, body), color: red ? "red" : null };
    var pct = bare.indexOf("%") >= 0; if (pct) x = x * 100;
    var m = /([#0,]*)(\.([0#]+))?/.exec(bare.match(/[#0][#0,.]*/) ? bare.match(/[#0][#0,.]*/)[0] : "");
    var hasNum = /[#0]/.test(bare);
    var dec = m && m[3] ? m[3].length : 0, group = m && m[1] && m[1].indexOf(",") >= 0;
    var numTxt = fmtNumber(x, dec, group);
    if (!signDone && x < 0 && Number(numTxt.replace(/[^\d]/g, "")) !== 0) numTxt = "-" + numTxt;
    // reconstitution avec les littéraux
    var out = "", placed = false, i = 0;
    while (i < body.length) {
      var ch = body.charAt(i);
      if (ch === '"') { var j = body.indexOf('"', i + 1); out += body.slice(i + 1, j < 0 ? body.length : j); i = j < 0 ? body.length : j + 1; continue; }
      if (ch === "\\") { out += body.charAt(i + 1); i += 2; continue; }
      if (/[#0,.]/.test(ch)) { if (!placed && hasNum) { out += numTxt; placed = true; } while (i < body.length && /[#0,.]/.test(body.charAt(i))) i++; continue; }
      if (ch === "_") { i += 2; out += " "; continue; }
      if (ch === "*") { i += 2; continue; }
      out += ch; i++;
    }
    return { text: out.trim(), color: red ? "red" : null };
  }

  window.YRWB = { Workbook: Workbook, parse: parse, format: format, isErr: isErr, serialOf: serialOf, colNum: colNum, colName: colName };
})();
