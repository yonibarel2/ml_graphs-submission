import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/review'
summary = {}

def read(path):
    with path.open(encoding='utf-8') as f:
        for line in f:
            yield json.loads(line)

for dataset in ('graphqa', 'erdos'):
    instances = {r['id']: r for r in read(ROOT / f'data/processed/{dataset}/instances.jsonl')}
    picked = sorted(instances)[::max(1, len(instances)//150)][:150]
    summary[dataset+'_floor_sample'] = {'n':len(picked), 'tasks':dict(Counter(instances[i]['task'] for i in picked)),
        'generators':dict(Counter(instances[i]['meta'].get('generator') for i in picked)),
        'graphs':len({instances[i]['meta'].get('graph_id', i) for i in picked})}
    for file in (ROOT / f'results/{dataset}/scored').glob('*.jsonl'):
        name = dataset + '/' + file.stem
        rows = list(read(file))
        groups = defaultdict(list)
        m3 = defaultdict(list)
        invalid_empty = []
        duplicate_sets = []
        for r in rows:
            if r['answer_type'] in ('node_set', 'path') and r['parsed'] == []:
                line = r['answer_line'].strip().lower()
                if line not in ('[]','{}','none','empty','no nodes','()'):
                    invalid_empty.append({k:r[k] for k in ('record_id','mode','task','axis','answer_line','correct')})
            if r['answer_type']=='node_set' and r['parsed'] is not None and len(r['parsed']) != len(set(r['parsed'])):
                duplicate_sets.append({k:r[k] for k in ('record_id','mode','task','axis','answer_line','correct')})
            if r['mode']=='graph_as_code':
                m3[(r['task'], r['library'])].append(r)
            for axis in ('relabel','order','structure','syntax'):
                include = r['axis']==axis or (axis!='relabel' and r['axis']=='canonical')
                if include:
                    groups[(r['task'],r['instance_id'],r['mode'],r['library'],axis)].append(r)
        cells = defaultdict(Counter)
        categories = defaultdict(Counter)
        examples = []
        for key, rr in groups.items():
            task, instance, mode, lib, axis = key
            ref = [r for r in rr if r['axis']=='canonical' or (axis=='relabel' and r['params'].get('seed')=='identity')]
            if len({r['variant_id'] for r in rr})<=1 or not ref:
                continue
            all_parsed = all(r['parsed'] is not None for r in rr)
            identical = len({r['answer_key'] for r in rr})==1 and all_parsed
            all_correct = all(r['correct'] for r in rr)
            any_correct = any(r['correct'] for r in rr)
            cell = cells[(task, mode, lib, axis)]
            cell['n'] += 1
            cell['identical'] += identical
            cell['all_correct'] += all_correct
            cat = categories[(mode,lib,axis)]
            cat['n'] += 1
            cat['identical_correct'] += identical and all_correct
            cat['identical_wrong'] += identical and not all_correct
            cat['different_all_correct'] += not identical and all_correct
            cat['different_all_parsed_incorrect'] += not identical and all_parsed and not all_correct
            cat['parse_failure'] += not all_parsed
            cat['all_parse_failed'] += all(r['parsed'] is None for r in rr)
            cat['ref_correct'] += ref[0]['correct']
            cat['ref_correct_some_wrong'] += ref[0]['correct'] and not all_correct
            cat['calls_1'] += len({r['prompt_hash'] for r in rr})==1
            cat['forms_'+str(len(rr))] += 1
        nc = Counter()
        for r in rows:
            if r['failure_class']=='no_computation':
                nc[(r['mode'],r['library'],'correct' if r['correct'] else 'wrong')] += 1
        summary[name] = {
            'n':len(rows),
            'parse_failures':sum(r['parsed'] is None for r in rows),
            'categories':{'/'.join(str(x) for x in k):dict(v) for k,v in categories.items()},
            'no_computation':{'/'.join(str(x) for x in k):v for k,v in nc.items()},
            'empty_nonstandard':invalid_empty,
            'duplicate_node_sets':duplicate_sets,
            'shortest_cells':{'/'.join(str(x) for x in k):dict(v) for k,v in cells.items() if k[0]=='shortest_path'},
            'm3':{'/'.join(k):{'n':len(rr),'correct':sum(r['correct'] for r in rr),
                     'unique_prompt_hashes':len({r['prompt_hash'] for r in rr}),
                     'unique_code_failures':len({r['prompt_hash'] for r in rr if not r['correct']})} for k,rr in m3.items()},
        }
        print(name, 'rows',len(rows),'nonstandard empty',len(invalid_empty),'duplicate sets',len(duplicate_sets),
              'literal answers',sum(nc.values()),flush=True)

for file in (ROOT / 'results/hf_snapshot/ee5b49e8013c1e5eb90bc14c2f7786810af01b77/raw_replies').glob('*.tar.gz'):
    counts = Counter()
    with tarfile.open(file, 'r|gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            match = re.search(r'\.r(\d+)\.json$', member.name)
            counts['repeat_'+match.group(1) if match else 'other'] += 1
    summary['archive/'+file.name] = dict(counts)
    print(file.name,dict(counts),flush=True)

(OUT / 'measurement_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('saved',OUT / 'measurement_audit.json')
