import itertools
import json
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
import networkx as nx

ROOT = Path(__file__).resolve().parents[2]
summary={}
for ds in ['graphqa','erdos']:
    inst=[json.loads(l) for l in (ROOT/'data/processed'/ds/'instances.jsonl').read_text().splitlines()]
    meta=pd.DataFrame([dict(instance_id=r['id'],n=len(r['nodes']),m=len(r['edges']),directed=r['directed'],source=r['meta'].get('source_file',r['meta']['graph_id'])) for r in inst])
    rows=[json.loads(l) for f in (ROOT/'results'/ds/'scored').glob('*.jsonl') for l in f.read_text().splitlines()]
    df=pd.DataFrame(rows).merge(meta,on='instance_id')
    df['library']=df['library'].fillna('-')
    df['arm']=df['mode']+'/'+df['library']
    out={}
    canonical=df[df.axis=='canonical'].copy()
    print('\nDATASET',ds)
    print('CANONICAL SIZE WITHIN TASK Q1 VS Q4')
    contrasts=[]
    for (model,arm),group in canonical[canonical['mode']!='graph_as_code'].groupby(['model','arm']):
        for size in ['n','m']:
            deltas=[]; low=[]; high=[]
            for task,g in group.groupby('task'):
                q1,q3=g[size].quantile([.25,.75])
                if q1==q3: continue
                l=g[g[size]<=q1].correct.mean(); h=g[g[size]>=q3].correct.mean()
                deltas.append(float(h-l));low.append(float(l));high.append(float(h))
            contrasts.append(dict(model=model,arm=arm,size=size,low=float(np.mean(low)),high=float(np.mean(high)),diff=float(np.mean(deltas)),n_tasks=len(deltas)))
    print(pd.DataFrame(contrasts).to_string(index=False))
    out['canonical_size_within_task_quartiles']=contrasts
    # every pair of models, named: the first version compared "the first two columns", which
    # silently changed pair once more than two models were present
    ov=[]
    for arm,g in canonical.groupby('arm'):
        p=g.pivot(index='instance_id',columns='model',values='correct').astype(int)
        for a,b in itertools.combinations(sorted(p.columns),2):
            both=int(((p[a]==0)&(p[b]==0)).sum());either=int(((p[a]==0)|(p[b]==0)).sum())
            ov.append(dict(arm=arm,model_a=a,model_b=b,n=len(p),both_wrong=both,either_wrong=either,
                           correlation=float(p[[a,b]].corr().iloc[0,1])))
    print('OVERLAP',json.dumps(ov));out['canonical_overlap']=ov
    injected=canonical[(canonical['mode']=='graph_as_code')&(canonical.task=='neighbor')]
    if not injected.empty:
        print('INJECTED NEIGHBOR DIRECTION',injected.groupby(['model','library','directed']).agg(n=('correct','size'),correct=('correct','sum'),direction_mismatch=('directedness_mismatch','sum')).to_string())
    gt_errors=[]
    for r in inst:
        G=nx.DiGraph() if r['directed'] else nx.Graph();G.add_nodes_from(r['nodes']);G.add_edges_from(r['edges']);q=r['query_args'];t=r['task'];gt=r['ground_truth']
        if ds=='erdos':
            if t=='shortest_path':
                val=nx.shortest_path_length(G,q['u'],q['v']);gt=len(gt)-1
            elif t=='triangles':val=nx.triangles(G,q['node'])
            elif t=='degree':val=G.degree[q['node']]
            elif t=='edge_number':val=G.number_of_edges()
            elif t=='connected_component_number':val=nx.number_connected_components(G)
            elif t=='diameter':
                try:val=nx.diameter(G)
                except nx.NetworkXError:val=float('inf')
            elif t=='density':val=nx.density(G)
            elif t=='edge_existence':val=G.has_edge(q['u'],q['v'])
            elif t=='has_cycle':val=not nx.is_directed_acyclic_graph(G) if r['directed'] else not nx.is_forest(G)
            elif t=='neighbor':val=sorted(G.neighbors(q['node']))
            elif t=='common_neighbor':val=sorted(nx.common_neighbors(G,q['u'],q['v']))
            elif t=='bridges':val=sorted(sorted(e) for e in nx.bridges(G));gt=sorted(sorted(e) for e in gt)
            else:continue
            ok=abs(val-gt)<=.01 if isinstance(val,float) else val==gt
            if not ok:gt_errors.append(dict(id=r['id'],task=t,directed=r['directed'],computed=val,gt=gt))
    print('GT ERRORS',json.dumps(gt_errors));out['gt_errors']=gt_errors
    summary[ds]=out
(ROOT/'results/review/task_patterns.json').write_text(json.dumps(summary,indent=2))
