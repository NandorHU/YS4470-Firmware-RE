"""Export three original transport functions from disposable PyGhidra projects."""
import argparse,json,sys
from pathlib import Path
from trace_uart_correlation import ROOT,HERE,BASE,sha,write
sys.path.insert(0,str(ROOT/'contributions/COORD-FUNCTION-PACKETS'))
from export_packets import cfg,blocks,data_refs,raw_call_candidates
SEEDS=((0x80005e84,'MeasurementDescriptorSend'),(0x80006dc8,'UARTSelectorByteOutput'),(0x800073bc,'UART2ReceiveISR'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ghidra',type=Path,required=True);a=ap.parse_args()
    import pyghidra
    pyghidra.start(install_dir=a.ghidra)
    from ghidra.program.model.address import AddressSet
    from ghidra.app.decompiler import DecompInterface
    from jpype import JArray,JByte
    import ghidra.framework.Application as Application
    versions=[]
    for item in json.loads((ROOT/'original-firmware/manifest.json').read_text())['images']:
        path=ROOT/item['path'];raw=path.read_bytes();assert sha(raw)==item['sha256']
        functions=[];callers=raw_call_candidates(raw,{e for e,_ in SEEDS})
        with pyghidra.open_program(path,project_location=ROOT/'work/uart-correlation/ghidra',
             project_name='uart_'+item['version'].replace('.','_'),program_name=path.name,analyze=False,
             language='ARM:LE:32:v5t',loader='ghidra.app.util.opinion.BinaryLoader')as flat:
            p=flat.getCurrentProgram();tx=p.startTransaction('temporary guarded transport exports')
            try:
                p.setImageBase(flat.toAddr(hex(BASE)),True);memory=p.getMemory()
                mapped=JArray(JByte)(len(raw));assert memory.getBytes(flat.toAddr(hex(BASE)),mapped)==len(raw)and bytes(mapped)==raw
                for entry,label in SEEDS:
                    instructions,edges,calls,unresolved=cfg(raw,entry);assert not unresolved
                    body=AddressSet();assembly=[]
                    for pc,ins in sorted(instructions.items()):
                        addr=flat.toAddr(hex(pc));flat.disassemble(addr)
                        gi=flat.getInstructionAt(addr);assert gi and gi.getLength()==4
                        assert bytes(gi.getBytes())==raw[pc-BASE:pc-BASE+4]
                        body.addRange(addr,addr.add(3));assembly.append(dict(address=hex(pc),bytes=ins.bytes.hex(),assembly=str(gi)))
                    f=p.getFunctionManager().getFunctionAt(flat.toAddr(hex(entry)))
                    old=None if f is None else dict(name=str(f.getName()),comment=f.getComment())
                    if f is None:f=flat.createFunction(flat.toAddr(hex(entry)),None)
                    assert f is not None;f.setBody(body)
                    dc=DecompInterface()
                    try:
                        dc.openProgram(p);r=dc.decompileFunction(f,20,flat.getMonitor());assert r.decompileCompleted()
                        c=str(r.getDecompiledFunction().getC())
                    finally:dc.dispose()
                    bb=blocks(instructions,edges);refs,accesses=data_refs(raw,instructions,bb)
                    functions.append(dict(entry=hex(entry),analyst_label=label,name_status='role label; not a vendor symbol',
                        preserved_metadata=old,complete_local_arm_cfg=True,assembly=assembly,decompiled_c=c,
                        calls=calls,edges=edges,literal_refs=refs,memory_access_candidates=accesses,
                        raw_caller_candidates=callers[hex(entry)],body_sha256=sha(b''.join(i.bytes for _,i in sorted(instructions.items())))))
            finally:p.endTransaction(tx,False)
        versions.append(dict(version=item['version'],input_sha256=sha(raw),functions=functions))
    for f,g in zip(versions[0]['functions'],versions[1]['functions']):assert f['entry']==g['entry']and f['assembly']==g['assembly']
    write(HERE/'ghidra-functions.json',dict(schema='ys4470.uart-ghidra.v1',versions=versions,
        ghidra_version=str(Application.getApplicationVersion()),pyghidra_version=pyghidra.__version__,
        exporter_sha256=sha(Path(__file__).read_bytes()),
        limits=['Fresh disposable projects; temporary changes rolled back; no analyst project or names modified.',
                'Local ARM CFGs only. Raw BL matches may be data; indirect/transitive caller completeness not established.',
                'Decompiler and block-local constant access candidates are not independent semantic proof.']))
    print('PASS six original Ghidra function exports',flush=True)
if __name__=='__main__':main()
