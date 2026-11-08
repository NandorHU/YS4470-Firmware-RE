"""Completion is transport/schema validity, never semantic verification."""
import hashlib,json,os,tempfile
from pathlib import Path

def classify(reply):
    errors=[]
    if reply.get('done') is not True or reply.get('done_reason')!='stop':
        errors.append('incomplete_or_unknown_completion')
    if reply.get('message',{}).get('tool_calls'):errors.append('unexpected_tool_calls')
    content=reply.get('message',{}).get('content','')
    try:
        parsed=json.loads(content)
        if not isinstance(parsed,dict):raise ValueError('object required')
    except (ValueError,TypeError):parsed=None;errors.append('invalid_json_object')
    return {'state':'incomplete' if 'incomplete_or_unknown_completion' in errors else ('invalid' if errors else 'draft'),
            'errors':errors,'parsed':parsed,'verified':False}

def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:
            json.dump(obj,f,indent=2,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def response_record(reply,attempt):
    return {'attempt':attempt,'response':reply,'gate':classify(reply)}

def grounding_errors(obj,packet,provided):
    errors=[]
    if set(obj)!={'entry','instruction_mode','evidence_address','quote','limitation'}:errors.append('unexpected_fields')
    if any(not isinstance(v,str)for v in obj.values()):errors.append('non_string_field')
    if obj.get('entry')!=packet['entry']or obj.get('instruction_mode')!='ARM':errors.append('identity_or_mode_mismatch')
    candidates=[i for i in provided if i['address']==obj.get('evidence_address')]
    if not any(obj.get('quote')in(i['assembly'],i['address']+' '+i['assembly'])for i in candidates):
        errors.append('quote_or_address_not_in_provided_packet_view')
    return errors

def task_state(records,max_attempts=2):
    if records and records[-1]['gate']['state']=='draft':return 'draft'
    return 'needs_split' if len(records)>=max_attempts else 'retryable'

def sha(raw):return hashlib.sha256(raw).hexdigest()
