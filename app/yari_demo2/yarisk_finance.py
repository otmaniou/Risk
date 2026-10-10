"""YaRisk V4 : calculs Excel V20 déterministes, sans remplacement du JSON source.

Le registre est extrait des formules réelles des trois feuilles de saisie V20.
Les montants JSON sont exprimés en DZD. ACTIF/PASSIF Excel en KDZD,
TCR Excel en DZD. Seuils issus du notebook V29d.
"""
import ast
import copy
import json
import math
import operator
import re
from pathlib import Path

ALERT_MIN_DZD = 1_000
ALERT_MEDIUM_DZD = 10_000
ALERT_HIGH_DZD = 1_000_000
FORMULAS = json.loads(Path(__file__).with_name('v20_financial_formulas.json').read_text(encoding='utf-8'))['formulas']
COLS = {'ACTIF': {'brut': 'P', 'amort': 'Q', 'net': 'R'},
        'PASSIF': {'montant': 'H'}, 'TCR': {'debit': 'M', 'credit': 'N'}}
SCALE = {'ACTIF': 1000, 'PASSIF': 1000, 'TCR': 1}
RANGE_RE = re.compile(r'(?i)SUM\s*\(\s*(\$?[A-Z]{1,3})\$?(\d+)\s*:\s*(\$?[A-Z]{1,3})\$?(\d+)\s*\)')
REF_RE = re.compile(r'(?<![A-Za-z0-9_"\'])(\$?[A-Z]{1,3})(\$?\d+)(?![A-Za-z0-9_"\'])')
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def severity(gap):
    if gap is None or abs(gap) < ALERT_MIN_DZD:
        return None
    if abs(gap) < ALERT_MEDIUM_DZD:
        return 'LOW'
    if abs(gap) < ALERT_HIGH_DZD:
        return 'MEDIUM'
    return 'HIGH'


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _formula_ast(expression):
    # Les formules ont été figées à la construction depuis le modèle V20.
    s = expression.replace('$', '')
    s = RANGE_RE.sub(lambda m: f'SUMR("{m[1].replace("$", "")}",{m[2]},"{m[3].replace("$", "")}",{m[4]})', s)
    s = REF_RE.sub(lambda m: f'REF("{m[1].replace("$", "")}",{m[2]})', s)
    s = s.replace('^', '**').replace(';', ',')
    return ast.parse(s, mode='eval')


def _evaluate(tree, ref, sumr):
    def calc(node):
        if isinstance(node, ast.Expression): return calc(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (float,int,bool,str)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](calc(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](calc(node.left),calc(node.right))
        if isinstance(node, ast.Compare) and len(node.ops)==1:
            left,right=calc(node.left),calc(node.comparators[0]); o=node.ops[0]
            if isinstance(o,ast.Gt): return left>right
            if isinstance(o,ast.Lt): return left<right
            if isinstance(o,ast.GtE): return left>=right
            if isinstance(o,ast.LtE): return left<=right
            if isinstance(o,ast.Eq): return left==right
            if isinstance(o,ast.NotEq): return left!=right
        if isinstance(node, ast.Call) and isinstance(node.func,ast.Name):
            name=node.func.id.upper()
            if name=='IF' and len(node.args)==3:
                return calc(node.args[1]) if calc(node.args[0]) else calc(node.args[2])
            if name=='REF' and len(node.args)==2:
                return ref(calc(node.args[0]),int(calc(node.args[1])))
            if name=='SUMR' and len(node.args)==4:
                return sumr(calc(node.args[0]),int(calc(node.args[1])),calc(node.args[2]),int(calc(node.args[3])))
        raise ValueError('Expression Excel non prise en charge : '+ast.dump(node)[:180])
    return calc(tree)


def calculate_year(table, raw_rows, layout):
    """Returns (display_rows, formula_issues). No mutation of raw_rows.

    A computed value appears if at least one underlying figure is known.
    If some source leaves are missing, the result is marked partial and never
    treated as an authoritative formula mismatch.
    """
    if table not in FORMULAS: raise ValueError('Table financière inconnue')
    rows_by_num={r[0]:r[1] for r in layout if r[1]}
    col_lookup={v:k for k,v in COLS[table].items()}
    fac=SCALE[table]
    formulas=FORMULAS[table]
    memo={}
    active=set()
    trees={}

    def build(col,row):
        key=(col,row)
        if key in memo:return memo[key]
        if key in active:raise ValueError('Référence circulaire V20 : '+str(key))
        active.add(key)
        row_id=rows_by_num.get(row)
        item=(raw_rows.get(row_id, {}) if row_id else {}).get(col_lookup.get(col,''))
        observed=item.get('value') if isinstance(item,dict) else None
        raw=observed/fac if _number(observed) else None
        expression=formulas.get(str(row),{}).get(col)
        # No Excel formula: use the actual source value only.
        if not expression:
            result={'value':raw, 'observed':raw, 'calculated':None,
                    'formula':False, 'partial':False, 'leaves_present':int(raw is not None),
                    'leaves_missing':int(raw is None), 'excel':None}
        else:
            present=missing=0
            def getref(c,r):
                nonlocal present, missing
                dep=build(c,r)
                present+=dep['leaves_present'];missing+=dep['leaves_missing']
                return dep['value'] if dep['value'] is not None else 0.0
            def sumr(c1,r1,c2,r2):
                if c1!=c2 or r2<r1 or r2-r1>250:raise ValueError('Plage non prise en charge')
                return sum(getref(c1,r) for r in range(r1,r2+1))
            try:
                if expression not in trees:trees[expression]=_formula_ast(expression)
                calc=_evaluate(trees[expression],getref,sumr)
                if not _number(calc):raise ValueError('Résultat non numérique')
                calc=float(calc) if present else None
            except (ValueError,ArithmeticError,RecursionError,OverflowError):
                calc=None;missing+=1
            # Source PDF is retained when computation is impossible; never write back.
            result={'value':calc if calc is not None else raw, 'observed':raw,
                    'calculated':calc, 'formula':True,
                    'partial':bool(missing), 'leaves_present':present,
                    'leaves_missing':missing, 'excel':expression}
        active.remove(key)
        memo[key]=result
        return result

    shown=copy.deepcopy(raw_rows)
    issues=[]
    for row_num,row_id,label,kind,indent in layout:
        if not row_id:continue
        for key,col in COLS[table].items():
            res=build(col,row_num)
            previous=shown.setdefault(row_id,{}).get(key)
            if res['value'] is None and previous is None:continue
            item=copy.deepcopy(previous) if previous else {'value':None,'path':None,'page':None}
            # Persist computed number only in the in-memory view, never in the JSON.
            item.update({'value':res['value']*fac if res['value'] is not None else None,
                         'observed_value':res['observed']*fac if res['observed'] is not None else None,
                         'calculated_value':res['calculated']*fac if res['calculated'] is not None else None,
                         'is_formula':res['formula'], 'formula_partial':res['partial'],
                         'excel_formula':res['excel']})
            shown[row_id][key]=item
            if res['formula'] and res['calculated'] is not None and res['observed'] is not None:
                gap=(res['calculated']-res['observed'])*fac
                level=severity(gap)
                if level and not res['partial']:
                    issues.append({'Type':'Écart formule Excel / PDF','Tableau':table,
                                   'Rubrique':row_id,'Colonne':key,'Écart DZD':round(gap,2),
                                   'Observé DZD':res['observed']*fac,
                                   'Calculé DZD':res['calculated']*fac,
                                   'Formule Excel':res['excel'],
                                   'Niveau':level,'PDF':item.get('pdf_name'),
                                   'Page':item.get('page')})
    return shown,issues


def enrich_years(merged,years,layout):
    enriched={t:{} for t in layout}
    anomalies=[]
    for table in layout:
        for year in years:
            shown,conflicts=calculate_year(table,merged.get(table,{}).get(year,{}),layout[table])
            enriched[table][year]=shown
            for item in conflicts:item['Exercice']=year
            anomalies.extend(conflicts)
    return enriched,anomalies
