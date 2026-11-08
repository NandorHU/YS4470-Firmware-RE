// Regrade saved provider outputs: no network or model request is made here.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../..');
process.env.PROMPTFOO_CONFIG_DIR=path.join(root,'work/local-llm-tools/promptfoo-config');
process.env.PROMPTFOO_DISABLE_TELEMETRY='true';
process.env.PROMPTFOO_DISABLE_UPDATE='true';
const {assertions}=await import(pathToFileURL(path.join(root,'work/local-llm-tools/node/node_modules/promptfoo/dist/src/index.js')));
const input=fs.readFileSync(path.join(root,'work/local-llm-tools/promptfoo-results.json'));
const saved=JSON.parse(input).results.results;
const config=JSON.parse(fs.readFileSync(path.join(here,'promptfooconfig.json'),'utf8'));
const out=path.join(here,'promptfoo-results.json');
if(fs.existsSync(out))throw Error('Completed regrade exists; do not repeat it');
const results=[];
for(const r of saved){
  const test=config.tests.find(t=>t.description===r.testCase.description);
  const g=await assertions.runAssertions({test,providerResponse:r.response});
  results.push({prompt_index:r.promptIdx,case:test.description,output:r.response.output,
    finish_reason:r.response.finishReason,latency_ms:r.latencyMs,passed:g.pass,
    assertions:g.componentResults.map(c=>({type:c.assertion.type,passed:c.pass,reason:c.reason}))});
}
const test=config.tests[0];
const wrong=await assertions.runAssertions({test,providerResponse:{output:'{"relation":"equal","branch_when_equal":false}',finishReason:'stop'}});
const cutoff=await assertions.runAssertions({test,providerResponse:{output:JSON.stringify({relation:test.vars.expected_relation,branch_when_equal:test.vars.expected_equal}),finishReason:'length'}});
if(wrong.pass||cutoff.pass)throw Error('Grader accepted a negative control');
const report={schema:'ys4470.local-tools.promptfoo.v1',model:'qwen2.5-coder:14b',
  original_response_sha256:crypto.createHash('sha256').update(input).digest('hex'),
  regraded_without_model_calls:true,initial_grader_error:'Single-line JS statements were treated as an expression; corrected with newline.',
  scores:[0,1].map(i=>({prompt_index:i,passed:results.filter(r=>r.prompt_index===i&&r.passed).length,total:6})),
  negative_controls:{wrong_relation_rejected:!wrong.pass,token_cutoff_rejected:!cutoff.pass},results,
  limits:['Synthetic calibration only; not a general firmware accuracy or productivity benchmark.']};
fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({scores:report.scores,negative_controls:report.negative_controls}));
