import io,json,sys,unittest,uuid
from pathlib import Path
from unittest.mock import patch,MagicMock
import packet_worker as worker
from completion_gate import sha,atomic_json
class CheckpointTests(unittest.TestCase):
    def run_fixture(self,reasons):
        root=worker.ROOT;packet=next((worker.HERE/'packets').glob('*-0x80003dbc.json'));raw=packet.read_bytes();p=json.loads(raw)
        job=root/'work'/('packet-worker-test-'+uuid.uuid4().hex);job.mkdir(parents=True)
        manifest={'endpoint':'http://127.0.0.1:11435','model':'qwen2.5-coder:14b','lessons_sha256':sha((worker.HERE/'LESSONS.md').read_bytes()),
          'tasks':[{'id':'fixture','context':'full_packet','packet':packet.relative_to(root).as_posix(),'packet_sha256':sha(raw),'binary_sha256':p['binary']['sha256'],'question':'Quote the first instruction.'}]}
        atomic_json(job/'manifest.json',manifest)
        answer={'entry':p['entry'],'instruction_mode':'ARM','evidence_address':p['entry'],'quote':p['assembly'][0]['assembly'],'limitation':'Unproven physical time.'}
        replies=[{'done':True,'done_reason':r,'message':{'content':json.dumps(answer)}}for r in reasons]
        opener=MagicMock();opener.open.side_effect=[io.BytesIO(json.dumps(r).encode())for r in replies]
        with patch.object(sys,'argv',['packet_worker','--job',str(job)]),patch.object(worker.urllib.request,'build_opener',return_value=opener):worker.main()
        return job,opener
    def test_length_then_stop_and_resume(self):
        job,opener=self.run_fixture(['length','stop']);self.assertEqual(opener.open.call_count,2)
        d=json.loads((job/'fixture.json').read_text());self.assertEqual(d['state'],'draft');self.assertFalse(d['verified'])
        self.assertEqual(d['attempts'][0]['gate']['state'],'incomplete')
        with patch.object(sys,'argv',['packet_worker','--job',str(job)]),patch.object(worker.urllib.request,'build_opener',return_value=opener):worker.main()
        self.assertEqual(opener.open.call_count,2);self.assertEqual(json.loads((job/'status.json').read_text())['requests_this_run'],0)
    def test_two_cutoffs_stop_without_completion(self):
        job,opener=self.run_fixture(['length','length']);d=json.loads((job/'status.json').read_text())
        self.assertEqual(opener.open.call_count,2);self.assertEqual(d['states']['fixture'],'needs_split');self.assertEqual(d['draft_count'],0)
        self.assertEqual(d['verified_count'],0)
if __name__=='__main__':unittest.main()
