import unittest
from completion_gate import classify,response_record,task_state,grounding_errors
class GateTests(unittest.TestCase):
    def reply(self,reason='stop',done=True,content='{}'):
        return dict(done=done,done_reason=reason,message={'content':content})
    def test_length_valid_json_is_incomplete(self):
        self.assertEqual(classify(self.reply('length'))['state'],'incomplete')
    def test_missing_or_unknown_finish_reason(self):
        for reason in (None,'max_tokens','error','tool_calls',''):
            self.assertEqual(classify(self.reply(reason))['state'],'incomplete')
    def test_not_done(self):self.assertEqual(classify(self.reply(done=False))['state'],'incomplete')
    def test_schema(self):
        for text in ('{','[]','null'):
            self.assertEqual(classify(self.reply(content=text))['state'],'invalid')
    def test_tool_injection(self):
        r=self.reply();r['message']['tool_calls']=[{'name':'shell'}]
        self.assertEqual(classify(r)['state'],'invalid')
    def test_valid_is_only_draft(self):
        g=classify(self.reply());self.assertEqual(g['state'],'draft');self.assertFalse(g['verified'])
    def test_bounded_retry(self):
        bad=response_record(self.reply('length'),1)
        self.assertEqual(task_state([bad]),'retryable')
        self.assertEqual(task_state([bad,bad]),'needs_split')
        self.assertEqual(task_state([bad,response_record(self.reply(),2)]),'draft')
    def test_exact_provided_whole_line_or_assembly(self):
        packet={'entry':'0x80003dbc'};rows=[{'address':'0x80003dd4','assembly':'b 0x80003dd0'}]
        obj={'entry':packet['entry'],'instruction_mode':'ARM','evidence_address':rows[0]['address'],'quote':'b 0x80003dd0','limitation':'unknown physical time'}
        self.assertEqual(grounding_errors(obj,packet,rows),[])
        obj['quote']='0x80003dd4 b 0x80003dd0';self.assertEqual(grounding_errors(obj,packet,rows),[])
        self.assertTrue(grounding_errors(obj,packet,[]))
        obj['quote']='b 0x80003dd4';self.assertTrue(grounding_errors(obj,packet,rows))
if __name__=='__main__':unittest.main()
