"""Read saved experiment artifacts without executing generated model programs."""
import ast
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
MODELS = ['hf-qwen3-8b-nscale', 'hf-deepseek-v3.1-novita', 'hf-gemma-4-31b', 'hf-deepseek-v4-flash']

def rows(path):
    with path.open(encoding='utf8') as f:
        for line in f:
            yield json.loads(line)

def code_features(code):
    if not code:
        return dict(no_code=True)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return dict(syntax_error=True)
    imports = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports.extend((a.name, a.asname or a.name.split('.')[0]) for a in n.names)
        if isinstance(n, ast.ImportFrom):
            imports.append((n.module or '', 'from_import'))
    nx_import = any(x == 'networkx' or x.startswith('networkx.') for x, _ in imports)
    uses_nx = any(isinstance(n, ast.Name) and n.id == 'nx' and isinstance(n.ctx, ast.Load) for n in ast.walk(tree))
    return dict(imports_networkx=nx_import, uses_nx=uses_nx,
                nx_without_import=uses_nx and not nx_import)

def bump(stats, key, **vals):
    stats[key]['n'] += 1
    stats[key].update({k:int(v) for k,v in vals.items() if v})

out = {}
instances = {x['id']:x for x in rows(ROOT/'data/processed/graphqa/instances.jsonl')}
unreachable = {}
for iid,x in instances.items():
    if x['task'] != 'disconnected_nodes':
        continue
    adj = defaultdict(set)
    for u,v in x['edges']:
        adj[u].add(v); adj[v].add(u)
    seen = {x['query_args']['node']}
    todo = list(seen)
    while todo:
        u = todo.pop()
        fresh = adj[u]-seen
        seen.update(fresh); todo.extend(fresh)
    unreachable[iid] = sorted(set(x['nodes'])-seen)
out['disconnected_truths_agree'] = sum(unreachable[k] == instances[k]['ground_truth'] for k in unreachable)

for dataset in ['graphqa','erdos']:
  for model in MODELS:
    print('Processing', dataset, model, flush=True)
    base = ROOT/'results'/dataset
    scored = {r['record_id']:r for r in rows(base/'scored'/f'{model}.jsonl')}
    stats = defaultdict(Counter)
    for r in scored.values():
        arm = f"{r['mode']}/{r['library']}"
        bump(stats, 'all/'+arm, correct=r['correct'], execution=r['failure_class']=='execution',
             declared_true=r['declared_ok'] is True, declared_false=r['declared_ok'] is False,
             declared_missing=r['declared_ok'] is None,
             wrong_decl_correct=r['declared_ok'] is False and r['correct'],
             wrong_graph_correct=r['graph_match'] is False and r['correct'])
        if dataset=='graphqa' and r['task']=='disconnected_nodes':
            bump(stats, f"disconnected/{arm}/{r['axis']}", correct=r['correct'],
                 matches_unreachable=r['parsed_canonical']==unreachable[r['instance_id']])
        if dataset=='graphqa' and r['task']=='node_degree':
            bump(stats, f"degree/{arm}/{r['axis']}/{r['params'].get('structure')}/{r['params'].get('replicated')}",
                 correct=r['correct'], doubled=r['ground_truth']>0 and r['parsed_canonical']==2*r['ground_truth'])
    seen_responses = set()
    examples = {}
    for r in rows(base/'responses'/f'{model}.jsonl'):
        if r['record_id'] not in scored:
            continue
        s = scored[r['record_id']]
        arm = f"{s['mode']}/{s['library']}"
        if s['mode']=='direct':
            continue
        feats = code_features(r.get('code'))
        nxsyntax = s['params'].get('syntax')=='networkx_code'
        bump(stats, 'response_weighted/'+arm, **feats)
        bump(stats, f'response_syntax/{arm}/{nxsyntax}', **feats)
        key = (s['prompt_hash'], arm)
        if key not in seen_responses:
            bump(stats, 'response_unique/'+arm, **feats)
            seen_responses.add(key)
        if dataset=='graphqa' and s['axis']=='canonical' and s['mode']=='code' and s['library']=='native' and s['task']=='disconnected_nodes':
            if not s['correct'] and 'disconnected' not in examples:
                examples['disconnected'] = {k:r[k] for k in ['record_id','code']}
        if dataset=='graphqa' and s['axis']=='structure' and s['mode']=='code' and s['library']=='native' and s['task']=='node_degree':
            if s['ground_truth']>0 and s['parsed_canonical']==2*s['ground_truth'] and 'degree' not in examples:
                examples['degree'] = {k:r[k] for k in ['record_id','code']}
    exception_counts = defaultdict(Counter)
    for r in rows(base/'exec'/f'{model}.jsonl'):
        if r['record_id'] not in scored:
            continue
        s = scored[r['record_id']]
        arm = f"{s['mode']}/{s['library']}"
        error = r.get('exception') or r.get('stderr') or ''
        last = error.strip().splitlines()[-1] if error.strip() else ''
        nxsyntax = s['params'].get('syntax')=='networkx_code'
        bump(stats, f'exec_syntax/{arm}/{nxsyntax}',
             failure=s['failure_class']=='execution',
             nx_nameerror="NameError: name 'nx' is not defined" in error,
             nx_attrerror=bool(re.search(r"AttributeError: module 'networkx(?:\.[^']*)?' has no attribute",error)),
             any_attrerror='AttributeError:' in error,
             graph_observed=bool(r.get('graphs')))
        if s['failure_class']=='execution':
            exception_counts[arm][last] += 1
    out[f'{dataset}/{model}'] = dict(stats=dict(stats), exceptions=dict(exception_counts),examples=examples)

path = ROOT/'results/review/mechanisms_summary.json'
path.write_text(json.dumps(out, indent=2, ensure_ascii=False),encoding='utf8')
print(path)
