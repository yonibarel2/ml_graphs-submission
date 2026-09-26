"""Read-only audit of injected graph kind and reported graph checks."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def read(path):
    with path.open(encoding='utf-8') as f:
        yield from map(json.loads, f)

instances = {r['id']:r for r in read(ROOT/'data/processed/erdos/instances.jsonl')}
sources = defaultdict(list)
graphs = defaultdict(list)
for r in instances.values():
    sources[r['meta']['source_file']].append(r['id'])
    edges = tuple(sorted(tuple(e) if r['directed'] else tuple(sorted(e)) for e in r['edges']))
    graphs[(r['directed'],tuple(sorted(r['nodes'])),edges)].append(r['id'])
out = {'erdos':{'n':len(instances), 'source_files':len(sources), 'unique_graph_content':len(graphs),
       'shared_sources':{k:v for k,v in sources.items() if len(v)>1},
       'directed':dict(Counter(str(r['directed']) for r in instances.values()))}}
for file in (ROOT/'results/erdos/scored').glob('*.jsonl'):
    summary = {'neighbor':defaultdict(Counter), 'direction_mismatches':Counter()}
    for r in read(file):
        if r['mode']=='graph_as_code' and r['task']=='neighbor' and r['axis']=='canonical':
            inst=instances[r['instance_id']]
            expected=sorted(v for u,v in inst['edges'] if u==inst['query_args']['node'])
            s=summary['neighbor'][r['library']]
            s['n']+=1
            s['correct']+=r['correct']
            s['matches_successors']+=sorted(r['parsed_canonical'])==expected
        if r['directedness_mismatch']:
            key='/'.join(str(r[k]) for k in ('mode','library','task','correct','failure_class','construction_ok'))
            summary['direction_mismatches'][key]+=1
    out[file.stem]=summary
(ROOT/'results/review/measurement_control_followup.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
