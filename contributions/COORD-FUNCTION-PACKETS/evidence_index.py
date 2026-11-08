"""Rebuildable SQLite/FTS5 index; every key includes the original binary hash."""
import argparse,json,sqlite3
from pathlib import Path
from completion_gate import sha,atomic_json
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def build(dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise FileExistsError('Use a new index destination; do not overwrite a live index')
    db=sqlite3.connect(dest)
    db.executescript('''PRAGMA foreign_keys=ON;
    CREATE TABLE functions(binary_hash TEXT,entry TEXT,name TEXT,mode TEXT,source_path TEXT,source_sha TEXT,status TEXT,export_version TEXT,PRIMARY KEY(binary_hash,entry));
    CREATE TABLE instructions(binary_hash TEXT,entry TEXT,address TEXT,assembly TEXT,bytes TEXT,source_json_index INTEGER,PRIMARY KEY(binary_hash,address));
    CREATE TABLE relations(binary_hash TEXT,entry TEXT,site TEXT,target TEXT,kind TEXT,status TEXT);
    CREATE VIRTUAL TABLE search USING fts5(binary_hash UNINDEXED,entry UNINDEXED,source_path UNINDEXED,text);
    ''')
    for item in json.loads((HERE/'packet-index.json').read_text())['packets']:
        raw=(ROOT/item['path']).read_bytes();assert sha(raw)==item['sha256'];p=json.loads(raw);h=p['binary']['sha256'];e=p['entry']
        db.execute('INSERT INTO functions VALUES(?,?,?,?,?,?,?,?)',(h,e,p['name'],p['instruction_mode'],item['path'],sha(raw),p['name_evidence_status'],p['schema']))
        for n,i in enumerate(p['assembly']):db.execute('INSERT INTO instructions VALUES(?,?,?,?,?,?)',(h,e,i['address'],i['assembly'],i['bytes'],n))
        for c in p['direct_callees']:db.execute('INSERT INTO relations VALUES(?,?,?,?,?,?)',(h,e,c['site'],c['target'],c['kind'],'resolved_target_only'if c['resolved']else'unresolved'))
        for c in p['direct_caller_candidates']:db.execute('INSERT INTO relations VALUES(?,?,?,?,?,?)',(h,e,c['site'],e,'caller_candidate',c['status']))
        for r in p['memory_accesses']:
            if r['effective_address']:db.execute('INSERT INTO relations VALUES(?,?,?,?,?,?)',(h,e,r['site'],r['effective_address'],r['operation'],'static_memory_access_candidate'))
        text=p['name']+'\n'+'\n'.join(i['address']+' '+i['assembly']for i in p['assembly'])+'\n'+(p['decompiled_c']or'')+'\n'+'\n'.join(p['limits'])
        db.execute('INSERT INTO search VALUES(?,?,?,?)',(h,e,item['path'],text))
    db.commit()
    # A shared address MUST return two distinct hash-bound rows.
    matches=db.execute('SELECT binary_hash FROM functions WHERE entry=?',('0x80006e4c',)).fetchall();assert len(matches)==2 and len(set(matches))==2
    assert db.execute("SELECT count(*) FROM search WHERE search MATCH 'GaugeCmdTask'").fetchone()[0]==2
    counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0]for t in ('functions','instructions','relations','search')}
    db.close();atomic_json(HERE/'index-validation.json',{'schema':'ys4470.evidence-index.v1','database_sha256':sha(dest.read_bytes()),'counts':counts,'cross_version_key_test':True,'fts_test':True,
      'limits':['Index covers six packets only, not all firmware or notes. FTS is not the relations table.',
        'Caller and global matches keep candidate status; absence is not proof of no other users.',
        'Source JSON array indices are recorded instead of invented text line numbers; follow source_sha and packet path.']})
    print(json.dumps(counts))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',type=Path,required=True);ap.add_argument('--build',action='store_true');ap.add_argument('--hash');ap.add_argument('--address');ap.add_argument('--search');a=ap.parse_args()
    if a.build:build(a.db);return
    assert a.hash,'Queries require an explicit original hash'
    db=sqlite3.connect('file:'+str(a.db.resolve())+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    if a.search:rows=db.execute('SELECT entry,source_path,snippet(search,3,?,?,?,20)as excerpt FROM search WHERE binary_hash=? AND search MATCH ?',('[',']','...',a.hash,a.search))
    else:rows=db.execute('SELECT * FROM relations WHERE binary_hash=? AND (target=? OR site=?)',(a.hash,a.address,a.address))
    print(json.dumps([dict(r)for r in rows],indent=2));db.close()
if __name__=='__main__':main()
