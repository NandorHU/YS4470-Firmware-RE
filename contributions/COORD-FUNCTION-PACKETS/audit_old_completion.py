"""Classify immutable old replies offline; do not resume the completed old batch."""
import argparse,json
from pathlib import Path
from completion_gate import classify,sha,atomic_json
ap=argparse.ArgumentParser();ap.add_argument('--old-job',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
rows=[]
for p in sorted(a.old_job.glob('*.json')):
    raw=p.read_bytes();d=json.loads(raw)
    if not isinstance(d,dict) or 'done_reason' not in d:continue
    reply={'done':d.get('done'),'done_reason':d.get('done_reason'),'message':{'content':d.get('content','')}}
    # Historical outputs were Markdown, so only transport completeness is comparable.
    g=classify(reply);state='incomplete' if 'incomplete_or_unknown_completion' in g['errors'] else 'unreviewed_legacy_text'
    rows.append({'file':p.name,'sha256':sha(raw),'done_reason':d.get('done_reason'),'new_state':state,'verified':False})
atomic_json(a.out,{'schema':'ys4470.legacy-completion-audit.v1','offline_only':True,'old_files_modified':False,
  'responses':len(rows),'incomplete':sum(r['new_state']=='incomplete'for r in rows),'rows':rows,
  'limits':['Transport audit only; complete old text is not verified and old jobs are never auto-requeued.']})
print(json.dumps({'responses':len(rows),'incomplete':sum(r['new_state']=='incomplete'for r in rows)}))
