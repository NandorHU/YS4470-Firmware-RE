"""YS-4470 offline application patcher. Standard library only; no device access."""
from __future__ import annotations
import argparse,hashlib,json,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
DATA_SHA='9b06a2bd42cb0278488cc75b8e28c7840771d08ed8d540a83aa328b78d4b03b8'
def sha(data):return hashlib.sha256(data).hexdigest()
class PatchError(ValueError):pass
def load_patch(path=HERE/'patch-data.json'):
    raw=path.read_bytes()
    if sha(raw)!=DATA_SHA:raise PatchError('Patch-data integrity check failed; download the complete patcher folder again.')
    data=json.loads(raw)
    if data['schema']!='ys4470.public-factory-patch.v1':raise PatchError('Unsupported patch schema')
    for variant in data['variants'].values():
        end=0
        for e in variant['edits']:
            off=e['offset'];old,new=bytes.fromhex(e['old']),bytes.fromhex(e['new'])
            if off<end or not old or len(old)!=len(new)or off+len(old)>data['application_length']:
                raise PatchError('Invalid or overlapping patch range')
            end=off+len(old)
    return data
def locate(raw,data):
    if len(raw)==data['application_length']:off=0;kind='application'
    elif len(raw)==data['full_flash_length']:off=data['application_flash_offset'];kind='full-flash'
    else:raise PatchError('Unsupported size '+str(len(raw))+'. Expected a 5,943,296-byte application or a 16,777,216-byte full flash backup.')
    app=raw[off:off+data['application_length']]
    if app[4:12]!=b'eGON.EXE' or int.from_bytes(app[16:20],'little')!=len(app):
        raise PatchError('No supported eGON.EXE application at the expected offset. No bytes were changed.')
    return off,kind,app
def inspect(raw,data):
    try:off,kind,app=locate(raw,data)
    except PatchError as e:return {'supported':False,'bytes':len(raw),'file_sha256':sha(raw),'reason':str(e)}
    h=sha(app);states=[]
    for name,v in data['variants'].items():
        for original,meta in v['inputs'].items():
            if h==original and not any(s.get('state')=='factory'for s in states):states.append({'state':'factory','version':meta['version']})
            elif h==meta['output_sha256']:states.append({'state':'patched','variant':name,'source_version':meta['version']})
    return {'supported':bool(states),'bytes':len(raw),'file_sha256':sha(raw),'container':kind,
      'application_offset':off,'application_bytes':len(app),'application_sha256':h,'recognized_states':states,
      'note':'A full-flash file hash normally differs between devices. Recognition uses the embedded application hash; no full backup is uploaded.'}
def transform(raw,data,variant,reverse=False):
    off,kind,app=locate(raw,data);v=data['variants'][variant];h=sha(app);meta=None;original_hash=None
    if reverse:
        for base,item in v['inputs'].items():
            if item['output_sha256']==h:original_hash,meta=base,item;break
    elif h in v['inputs']:original_hash=h;meta=v['inputs'][h]
    if meta is None:
        raise PatchError('Unsupported application SHA-256: '+h+'. Use inspect. Already patched files must be reverted before applying another variant; no force mode is provided.')
    candidate=bytearray(app)
    for e in v['edits']:
        old,new=bytes.fromhex(e['old']),bytes.fromhex(e['new'])
        if reverse:old,new=new,old
        start=e['offset']
        if candidate[start:start+len(old)]!=old:raise PatchError('Original-byte guard failed at application offset '+hex(start))
        candidate[start:start+len(new)]=new
    expected=original_hash if reverse else meta['output_sha256']
    if sha(candidate)!=expected:raise PatchError('Output application hash failed')
    result=raw[:off]+bytes(candidate)+raw[off+len(app):]
    if len(result)!=len(raw)or result[:off]!=raw[:off]or result[off+len(app):]!=raw[off+len(app):]:
        raise PatchError('Container preservation check failed')
    report={'schema':'ys4470.public-patch-receipt.v1','action':'revert'if reverse else'apply','variant':variant,
      'source_version':meta['version'],'container':kind,'input_sha256':sha(raw),'output_sha256':sha(result),
      'input_application_sha256':h,'output_application_sha256':expected,'application_offset':off,
      'changed_ranges':len(v['edits']),'changed_bytes':v['changed_bytes'],'outside_application_preserved':True,
      'bootloader_and_logo_replaced':False,'device_access':False,'validation_scope':meta['validation'],
      'installation_note':'Offline file only. Legacy Beta3-hash installer does not accept this input. Vendor updater and physical installation of this personalized container are not verified.'}
    return result,report
def write_new(source,output,result,report):
    source=Path(source).resolve();output=Path(output).resolve();receipt=Path(str(output)+'.report.json')
    if source==output or output.exists()or receipt.exists():raise PatchError('Output or receipt already exists, or output equals input. Choose a new filename; input is never overwritten.')
    made=[]
    try:
        with output.open('xb')as f:
            made.append(output);f.write(result);f.flush();os.fsync(f.fileno())
        if sha(output.read_bytes())!=report['output_sha256']:raise PatchError('Written file verification failed')
        with receipt.open('x',encoding='utf-8')as f:
            made.append(receipt);json.dump(report,f,indent=2);f.write('\n')
    except Exception:
        for p in reversed(made):p.unlink(missing_ok=True)
        raise
def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='action',required=True)
    for action in ('inspect','apply','revert'):
        p=sub.add_parser(action);p.add_argument('input',type=Path)
        if action!='inspect':p.add_argument('--variant',choices=('continuous','timed'),default='continuous');p.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(argv)
    try:
        data=load_patch();raw=args.input.read_bytes()
        if args.action=='inspect':
            report=inspect(raw,data);print(json.dumps(report,indent=2));return 0 if report['supported']else 2
        result,report=transform(raw,data,args.variant,args.action=='revert');write_new(args.input,args.output,result,report)
        print(json.dumps(report,indent=2));print('Created:',args.output);print('Original input unchanged. No USB or firmware-write operation was performed.');return 0
    except (PatchError,OSError,ValueError)as error:print('ERROR:',error,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
