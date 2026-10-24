"""Habillage visuel YaRisk : palette, typographie, composants HTML (bandeau, cartes, signaux) et thème Altair.

Palette (identique au logo et à la présentation) :
  forêt #0E2A21 · vert BNP #00915A · vert profond #00573F · menthe #4FD69C · fond #F4F7F5 · ambre #E8A33D · rouge #C0392B
Les polices Sora / IBM Plex Sans sont chargées depuis Google Fonts si le réseau le permet ; sinon repli sur les polices système.
"""
import html

import altair as alt
import streamlit as st

FOREST, GREEN, DEEP, MINT, CANVAS, AMBER, RED, INK, MUTED = "#0E2A21", "#00915A", "#00573F", "#4FD69C", "#F4F7F5", "#E8A33D", "#C0392B", "#0E2A21", "#5B6B63"

LOGO = ('<svg viewBox="0 0 100 100" width="{s}" height="{s}" aria-label="YaRisk"><rect width="100" height="100" rx="24" fill="#00915A"/>'
        '<path d="M30 22 L50 48 L70 22 M50 48 L50 68" fill="none" stroke="#fff" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="40" cy="83" r="6.5" fill="#4FD69C"/><circle cx="60" cy="83" r="6.5" fill="#4FD69C"/></svg>')

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root{--forest:#0E2A21;--green:#00915A;--deep:#00573F;--mint:#4FD69C;--canvas:#F4F7F5;--line:#DCE6E0;--muted:#5B6B63;--amber:#E8A33D;--red:#C0392B;
      --card:#FFFFFF;--shadow:0 1px 2px rgba(14,42,33,.06),0 6px 18px rgba(14,42,33,.06);--r:14px;
      --font:'IBM Plex Sans',-apple-system,'Segoe UI',Roboto,Arial,sans-serif;--title:'Sora','IBM Plex Sans','Segoe UI',Arial,sans-serif}
html,body,.stApp,[data-testid="stAppViewContainer"]{font-family:var(--font)}
.stApp{background:radial-gradient(1200px 500px at 85% -10%,rgba(79,214,156,.10),transparent 60%),var(--canvas)}
[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:1.4rem!important;padding-bottom:3rem!important;max-width:1500px}
h1,h2,h3,h4{font-family:var(--title)!important;color:var(--forest);letter-spacing:-.01em}
h3{font-size:1.25rem!important}
h4{font-size:1.02rem!important;font-weight:600!important;display:flex;align-items:center;gap:.5rem;margin-top:.4rem!important}
h4::before{content:"";width:4px;height:1.05em;border-radius:3px;background:linear-gradient(var(--green),var(--mint))}
/* ----- Barre latérale ----- */
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0E2A21 0%,#123829 55%,#0B231B 100%)}
[data-testid="stSidebar"] *{color:#E3EEE8}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *{color:#9DB8AB!important}
[data-testid="stSidebar"] [role="radiogroup"]{gap:4px}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:10px 12px;border-radius:10px;margin:0;width:100%;transition:background .15s}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(255,255,255,.06)}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:linear-gradient(90deg,rgba(79,214,156,.22),rgba(79,214,156,.06));box-shadow:inset 3px 0 0 var(--mint)}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:#fff;font-weight:600}
[data-testid="stSidebar"] [data-testid="stRadioOption"]{width:100%;padding:10px 12px;border-radius:10px;margin:0}
[data-testid="stSidebar"] [data-testid="stRadioOption"]>div>div:first-child:not([data-testid]){display:none}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"]{background:linear-gradient(90deg,rgba(79,214,156,.22),rgba(79,214,156,.06));box-shadow:inset 3px 0 0 var(--mint)}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p{color:#fff;font-weight:600}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"]{background:rgba(255,255,255,.08)!important;border:1px solid rgba(79,214,156,.35)!important;border-radius:10px}
[data-testid="stSidebar"] [data-testid="stSelectbox"] input{color:#fff!important;-webkit-text-fill-color:#fff}
[data-testid="stSidebar"] [data-testid="stSelectbox"] svg{fill:#9DB8AB}
[data-testid="stSidebar"] .stButton button{background:rgba(255,255,255,.06);border:1px solid rgba(79,214,156,.35);color:#E3EEE8;border-radius:10px}
[data-testid="stSidebar"] .stButton button:hover{background:rgba(79,214,156,.18);border-color:var(--mint);color:#fff}
[data-testid="stSidebar"] [data-baseweb="select"]>div{background:rgba(255,255,255,.07);border-color:rgba(79,214,156,.3)}
.yr-brand{display:flex;align-items:center;gap:12px;margin:-6px 0 18px}
.yr-brand b{font-family:var(--title);font-size:1.45rem;color:#fff;letter-spacing:-.02em}
.yr-brand b span{color:var(--mint)}
.yr-brand small{display:block;color:#9DB8AB;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase}
.yr-side-title{font-size:.7rem!important;letter-spacing:.12em;text-transform:uppercase;color:#7FA394!important;margin:18px 0 6px}
.yr-engine{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:12px;font-size:.82rem;line-height:1.3;margin:12px 0}
.yr-engine i{width:10px;height:10px;border-radius:50%;flex:none}
.yr-engine.on{background:rgba(79,214,156,.12);border:1px solid rgba(79,214,156,.35)}
.yr-engine.on i{background:var(--mint);box-shadow:0 0 0 4px rgba(79,214,156,.25);animation:yrpulse 2s infinite}
.yr-engine.off{background:rgba(232,163,61,.10);border:1px solid rgba(232,163,61,.35)}
.yr-engine.off i{background:var(--amber)}
@keyframes yrpulse{0%{box-shadow:0 0 0 0 rgba(79,214,156,.5)}70%{box-shadow:0 0 0 8px rgba(79,214,156,0)}100%{box-shadow:0 0 0 0 rgba(79,214,156,0)}}
/* ----- Bandeau ----- */
.yr-hero{position:relative;overflow:hidden;border-radius:20px;padding:22px 28px;margin-bottom:16px;color:#F4F7F5;
  background:linear-gradient(120deg,#0E2A21 0%,#00573F 55%,#00915A 100%);box-shadow:0 10px 30px rgba(0,87,63,.25)}
.yr-hero::after{content:"";position:absolute;right:-60px;top:-80px;width:320px;height:320px;border-radius:50%;
  background:radial-gradient(circle,rgba(79,214,156,.35),transparent 65%)}
.yr-hero .row{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;position:relative;z-index:1;flex-wrap:wrap}
.yr-hero .eyebrow{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--mint);font-weight:600}
.yr-hero h1{color:#fff!important;font-size:1.9rem!important;margin:.15rem 0 .2rem!important;padding:0!important;line-height:1.15}
.yr-hero p{color:#CFE3D8;margin:0;font-size:.95rem}
.yr-chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.yr-chip{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.12);
  border:1px solid rgba(255,255,255,.18);color:#fff;white-space:nowrap}
.yr-chip.mint{background:rgba(79,214,156,.2);border-color:rgba(79,214,156,.5)}
.yr-chip.amber{background:rgba(232,163,61,.22);border-color:rgba(232,163,61,.55)}
.yr-hero .side{text-align:right;font-size:.85rem;color:#CFE3D8;line-height:1.6}
.yr-hero .side b{color:#fff}
/* ----- Étapes du parcours ----- */
.st-key-yr_stepper [data-testid="stHorizontalBlock"]{gap:10px}
.st-key-yr_stepper button{border-radius:14px!important;min-height:52px;font-weight:600;border:1px solid var(--line)!important;background:#fff!important;
  color:var(--forest)!important;box-shadow:var(--shadow);transition:transform .12s}
.st-key-yr_stepper button:hover{transform:translateY(-1px);border-color:var(--green)!important}
.st-key-yr_stepper button[kind="primary"]{background:linear-gradient(120deg,#00573F,#00915A)!important;color:#fff!important;border-color:transparent!important;
  box-shadow:0 8px 20px rgba(0,145,90,.3)}
.st-key-yr_stepper button:disabled{opacity:.45;box-shadow:none}
/* ----- Onglets ----- */
[data-baseweb="tab-list"]{gap:6px;background:#fff;padding:6px;border-radius:14px;box-shadow:var(--shadow);border:1px solid var(--line);flex-wrap:wrap}
[data-baseweb="tab"]{border-radius:10px!important;padding:8px 14px!important;height:auto!important;background:transparent}
[data-baseweb="tab"] p{font-weight:500}
[data-baseweb="tab"][aria-selected="true"]{background:linear-gradient(120deg,#00573F,#00915A)!important}
[data-baseweb="tab"][aria-selected="true"] p{color:#fff!important;font-weight:600}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"]{display:none!important}
[data-testid="stTabs"] [data-baseweb="tab-panel"]{padding-top:14px}
[data-testid="stSidebar"] [role="radiogroup"]{display:flex;flex-direction:column;align-items:stretch}
[data-testid="stTabs"] [role="tablist"]{gap:2px;background:#fff;padding:6px;border-radius:14px;box-shadow:var(--shadow);border:1px solid var(--line);flex-wrap:wrap;margin-bottom:14px}
[data-testid="stTab"]{border-radius:10px!important;padding:6px 9px!important;margin:0!important;transition:background .15s}
[data-testid="stTab"] p{font-size:.85rem!important;white-space:nowrap}
[data-testid="stSidebar"] [data-testid="stRadio"],[data-testid="stSidebar"] [data-testid="stRadio"]>div{width:100%}
[data-testid="stTab"]:hover{background:#EEF5F1}
[data-testid="stTab"][aria-selected="true"]{background:linear-gradient(120deg,#00573F,#00915A)!important;box-shadow:0 4px 12px rgba(0,145,90,.25)}
[data-testid="stTab"][aria-selected="true"] p{color:#fff!important;font-weight:600}
[data-testid="stTabs"] .react-aria-SelectionIndicator{display:none!important}
/* ----- Cartes et composants natifs ----- */
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:12px 16px;box-shadow:var(--shadow)}
[data-testid="stMetricValue"]{font-family:var(--title);font-size:1.5rem!important;color:var(--forest)}
[data-testid="stMetricLabel"] p{color:var(--muted)!important;font-size:.8rem!important;text-transform:uppercase;letter-spacing:.04em}
[data-testid="stDataFrame"],[data-testid="stTable"]{border-radius:var(--r);overflow:hidden;box-shadow:var(--shadow);border:1px solid var(--line)}
[data-testid="stExpander"] details{border-radius:12px!important;border:1px solid var(--line)!important;background:#fff;box-shadow:0 1px 2px rgba(14,42,33,.05)}
[data-testid="stExpander"] summary:hover{color:var(--green)}
[data-testid="stAlert"]{border-radius:12px}
[data-testid="stForm"]{background:#fff;border:1px solid var(--line)!important;border-radius:16px;box-shadow:var(--shadow)}
[data-testid="stVegaLiteChart"]{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:10px 12px 4px;box-shadow:var(--shadow)}
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"]{
  background:linear-gradient(120deg,#00573F,#00915A)!important;border:none!important;color:#fff!important;border-radius:10px;box-shadow:0 6px 16px rgba(0,145,90,.25)}
.stButton button,.stDownloadButton button{border-radius:10px}
hr{border-color:var(--line)!important}
/* ----- Composants YaRisk ----- */
.yr-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:6px 0 16px}
.yr-kpi{position:relative;background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px 16px 12px;box-shadow:var(--shadow);overflow:hidden}
.yr-kpi::before{content:"";position:absolute;inset:0 auto 0 0;width:4px;background:var(--tone,var(--green))}
.yr-kpi .ic{position:absolute;right:12px;top:10px;font-size:1.25rem;opacity:.9}
.yr-kpi .lb{padding-right:30px;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
.yr-kpi .vl{font-family:var(--title);font-size:1.55rem;font-weight:700;color:var(--forest);margin-top:4px;line-height:1.1}
.yr-kpi .vl small{font-size:.8rem;font-weight:500;color:var(--muted);margin-left:3px}
.yr-kpi .sb{font-size:.78rem;color:var(--muted);margin-top:4px}
.yr-kpi .bar{height:6px;border-radius:6px;background:#EEF3F0;margin-top:8px;overflow:hidden}
.yr-kpi .bar i{display:block;height:100%;border-radius:6px;background:linear-gradient(90deg,var(--green),var(--mint))}
.yr-kpi.warn .bar i{background:linear-gradient(90deg,var(--amber),#F2C27A)}
.yr-kpi.bad .bar i{background:linear-gradient(90deg,var(--red),#E57364)}
.yr-ribbon{display:flex;align-items:center;gap:10px;padding:9px 14px;border-radius:12px;background:#FFF7E8;border:1px dashed #E8A33D;color:#7A4E00;font-size:.85rem;margin-bottom:12px}
.yr-client{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:18px;background:#fff;border:1px solid var(--line);border-radius:20px;padding:18px 22px;box-shadow:var(--shadow);margin-bottom:14px}
.yr-client .who{display:flex;gap:14px;align-items:center}
.yr-client .av{width:54px;height:54px;border-radius:16px;flex:none;display:grid;place-items:center;font-family:var(--title);font-weight:700;font-size:1.25rem;color:#fff;
  background:linear-gradient(135deg,#00573F,#4FD69C)}
.yr-client h2{font-size:1.35rem!important;margin:0!important;padding:0!important}
.yr-client .meta{color:var(--muted);font-size:.82rem;margin-top:2px}
.yr-client dl{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:0;font-size:.85rem}
.yr-client dt{color:var(--muted)}
.yr-client dd{margin:0;color:var(--forest);font-weight:500}
.yr-grade{display:inline-grid;place-items:center;min-width:34px;height:26px;padding:0 8px;border-radius:8px;background:var(--forest);color:var(--mint);font-family:var(--title);font-weight:700}
.yr-sig{display:flex;gap:12px;align-items:flex-start;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:10px;box-shadow:0 1px 2px rgba(14,42,33,.04)}
.yr-sig .dot{flex:none;width:32px;height:32px;border-radius:10px;display:grid;place-items:center;font-size:1rem}
.yr-sig.HIGH .dot{background:#FDECEA}.yr-sig.MEDIUM .dot{background:#FFF3E0}.yr-sig.INFO .dot{background:#E8F4EE}
.yr-sig .tg{font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.yr-sig.HIGH .tg{color:var(--red)}.yr-sig.MEDIUM .tg{color:#B26B00}.yr-sig.INFO .tg{color:var(--green)}
.yr-sig .tx{font-size:.88rem;color:var(--forest);line-height:1.4}
.yr-gauges{background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px 16px;box-shadow:var(--shadow)}
.yr-g{display:grid;grid-template-columns:150px 1fr 54px;gap:10px;align-items:center;padding:6px 0;font-size:.84rem}
.yr-g .tr{position:relative;height:10px;border-radius:10px;background:#EEF3F0;overflow:visible}
.yr-g .tr i{position:absolute;left:0;top:0;bottom:0;border-radius:10px;background:linear-gradient(90deg,var(--green),var(--mint))}
.yr-g.warn .tr i{background:linear-gradient(90deg,#D98E1E,#F2C27A)}.yr-g.bad .tr i{background:linear-gradient(90deg,var(--red),#E57364)}
.yr-g .tr b{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--forest);border-radius:2px}
.yr-g span:last-child{text-align:right;font-weight:600}
.yr-fin{background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);overflow:hidden}
.yr-fin table{width:100%;border-collapse:collapse;font-size:.86rem}
.yr-fin td{padding:7px 14px;border-bottom:1px solid #EEF3F0}
.yr-fin td:last-child{text-align:right;font-family:var(--title);font-weight:600}
.yr-fin tr:last-child td{border-bottom:none}
.yr-fin .hd{background:linear-gradient(120deg,#0E2A21,#00573F);color:#fff;font-size:.78rem;letter-spacing:.06em;text-transform:uppercase}
.yr-fin .hd td{color:#fff;font-family:var(--font);font-weight:600}
.yr-empty{background:#fff;border:1px dashed var(--line);border-radius:16px;padding:26px;text-align:center;color:var(--muted)}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)
    _altair_theme()


def e(x):
    return html.escape("" if x is None else str(x))


def brand():
    st.markdown(f'<div class="yr-brand">{LOGO.format(s=42)}<div><b><span>Ya</span>Risk</b><small>Analyse financière · Risques</small></div></div>',
                unsafe_allow_html=True)


def side_title(t):
    st.markdown(f'<div class="yr-side-title">{e(t)}</div>', unsafe_allow_html=True)


def engine(online, busy=False):
    if online:
        txt = "Moteur de lecture <b>en cours de traitement</b>" if busy else "Moteur de lecture <b>prêt</b>"
        st.markdown(f'<div class="yr-engine on"><i></i><div>{txt}<br><small>Qwen V29d · GPU Domino</small></div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="yr-engine off"><i></i><div><b>Moteur hors ligne</b><br><small>Lancez la cellule « worker » du notebook sur le GPU '
                    '(non requis pour la démo JSON).</small></div></div>', unsafe_allow_html=True)


def hero(eyebrow, title, subtitle="", chips=(), side=""):
    ch = "".join(f'<span class="yr-chip {e(c[1]) if isinstance(c, tuple) else ""}">{e(c[0] if isinstance(c, tuple) else c)}</span>' for c in chips if c)
    st.markdown(f'<div class="yr-hero"><div class="row"><div><div class="eyebrow">{e(eyebrow)}</div><h1>{e(title)}</h1>'
                f'{"<p>" + e(subtitle) + "</p>" if subtitle else ""}{"<div class=yr-chips>" + ch + "</div>" if ch else ""}</div>'
                f'<div class="side">{side}</div></div></div>', unsafe_allow_html=True)


TONES = {"green": GREEN, "mint": MINT, "amber": AMBER, "red": RED, "forest": FOREST, "blue": "#2F75B5", "grey": "#8A9A92"}


def kpis(cards):
    """cards : [{label, value, unit, sub, icon, tone, bar (0..1+), state ('', 'warn', 'bad')}]"""
    out = []
    for c in cards:
        bar = ""
        if c.get("bar") is not None:
            bar = f'<div class="bar"><i style="width:{max(0, min(100, c["bar"] * 100)):.0f}%"></i></div>'
        out.append(f'<div class="yr-kpi {e(c.get("state", ""))}" style="--tone:{TONES.get(c.get("tone", "green"), GREEN)}">'
                   f'<span class="ic">{c.get("icon", "")}</span><div class="lb">{e(c["label"])}</div>'
                   f'<div class="vl">{e(c["value"])}{"<small>" + e(c["unit"]) + "</small>" if c.get("unit") else ""}</div>'
                   f'{bar}{"<div class=sb>" + e(c["sub"]) + "</div>" if c.get("sub") else ""}</div>')
    st.markdown(f'<div class="yr-kpis">{"".join(out)}</div>', unsafe_allow_html=True)


def ribbon(text, icon="🧪"):
    st.markdown(f'<div class="yr-ribbon"><span>{icon}</span><span>{text}</span></div>', unsafe_allow_html=True)


def signals(items):
    icons = {"HIGH": "⛔", "MEDIUM": "⚠️", "INFO": "ℹ️"}
    tags = {"HIGH": "Priorité haute", "MEDIUM": "À surveiller", "INFO": "Information"}
    if not items:
        st.markdown('<div class="yr-empty">✅ Aucun signal particulier</div>', unsafe_allow_html=True)
        return
    st.markdown("".join(f'<div class="yr-sig {lv}"><div class="dot">{icons.get(lv, "•")}</div><div><div class="tg">{tags.get(lv, lv)}</div>'
                        f'<div class="tx">{e(t)}</div></div></div>' for lv, t in items), unsafe_allow_html=True)


def gauges(rows):
    """rows : [(libellé, taux 0..1+)] — barre d'utilisation avec repère de l'autorisation à 100 %."""
    out = []
    for lab, r in rows:
        st_ = "bad" if r > 1.0 else "warn" if r >= 0.85 else ""
        w = min(r, 1.15) / 1.15 * 100
        out.append(f'<div class="yr-g {st_}"><span>{e(lab)}</span><div class="tr"><i style="width:{w:.0f}%"></i>'
                   f'<b style="left:{100 / 1.15:.1f}%"></b></div><span>{r * 100:.0f} %</span></div>')
    st.markdown(f'<div class="yr-gauges">{"".join(out)}</div>', unsafe_allow_html=True)


def fin_table(title, rows):
    body = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in rows)
    st.markdown(f'<div class="yr-fin"><table><tr class="hd"><td>{e(title)}</td><td>M DZD</td></tr>{body}</table></div>', unsafe_allow_html=True)


def client_card(name, meta, left, right, grade=None):
    initials = "".join(w[0] for w in str(name or "?").replace("SARL", "").replace("SPA", "").replace("EURL", "").split()[:2]).upper() or "?"
    dl = lambda items: "<dl>" + "".join(f"<dt>{e(k)}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"
    st.markdown(f'<div class="yr-client"><div class="who"><div class="av">{e(initials)}</div><div><div class="meta" style="text-transform:uppercase;letter-spacing:.08em;font-size:.7rem">Identité du client</div><h2>{e(name)}</h2><div class="meta">{e(meta)}</div>'
                f'{"<div style=margin-top:8px>Note CRF&nbsp; <span class=yr-grade>" + e(grade) + "</span> <small style=color:#5B6B63>(simulée)</small></div>" if grade else ""}'
                f'</div></div><div>{dl(left)}</div><div>{dl(right)}</div></div>', unsafe_allow_html=True)


def _altair_theme():
    def theme():
        return {"config": {
            "font": "IBM Plex Sans, Segoe UI, Arial, sans-serif",
            "background": "transparent",
            "view": {"stroke": None},
            "axis": {"labelColor": "#5B6B63", "titleColor": "#5B6B63", "gridColor": "#EEF3F0", "domainColor": "#DCE6E0", "tickColor": "#DCE6E0",
                     "labelFontSize": 11, "titleFontSize": 11, "titleFontWeight": 500},
            "legend": {"labelColor": "#0E2A21", "titleColor": "#5B6B63", "labelFontSize": 12, "symbolType": "circle"},
            "title": {"font": "Sora, IBM Plex Sans, Arial", "fontSize": 14, "fontWeight": 600, "color": "#0E2A21", "anchor": "start", "offset": 10},
            "range": {"category": ["#00915A", "#8A9A92", "#E8A33D", "#2F75B5", "#4FD69C", "#0E2A21"]},
            "header": {"labelFont": "Sora, IBM Plex Sans, Arial", "labelFontSize": 12, "labelColor": "#0E2A21"},
        }}
    try:
        alt.theme.register("yarisk", enable=True)(theme)       # Altair ≥ 5.5
    except Exception:
        try:
            alt.themes.register("yarisk", theme); alt.themes.enable("yarisk")
        except Exception:
            pass
