"""Fetch pinned PUBLIC inputs for a reproducible release build; GUI stays offline."""
from pathlib import Path
import hashlib,json,shutil,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'work/easy-installer';HERE=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def fetch(row,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raw=path.read_bytes()
    else:
        with urllib.request.urlopen(row['url'],timeout=60)as r:raw=r.read()
        if sha(raw)!=row['sha256']:raise ValueError('Download SHA-256 mismatch: '+path.name)
        path.write_bytes(raw)
    if sha(raw)!=row['sha256']:raise ValueError('Cached input SHA-256 mismatch: '+path.name)
    return raw
def main():
    lock=json.loads((HERE/'dependencies.lock.json').read_text());resources=WORK/'resources';cache=WORK/'downloads'
    for row in lock['factory']:
        dest=ROOT/'original-firmware'/row['version']/'f1c100s.bin';fetch(row,dest)
    archive=fetch(lock['fel'],cache/lock['fel']['name'])
    with zipfile.ZipFile(cache/lock['fel']['name'])as z:exe=z.read(lock['fel']['entry'])
    if sha(exe)!=lock['fel']['exe_sha256']:raise ValueError('FEL executable identity mismatch')
    tools=resources/'tools';tools.mkdir(parents=True,exist_ok=True);(tools/'sunxi-fel.exe').write_bytes(exe)
    (tools/'zadig-2.9.exe').write_bytes(fetch(lock['zadig'],cache/lock['zadig']['name']))
    for row in lock['sources']:fetch(row,cache/row['name'])
    shutil.copyfile(ROOT/'patcher/patch-data.json',resources/'patch-data.json')
    print(json.dumps({'resources_ready':True,'public_sources':len(lock['sources']),'device_access':False}))
if __name__=='__main__':main()
