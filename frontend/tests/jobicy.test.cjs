const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const fixture = [
 {id:1,jobTitle:'Software Engineer',companyName:'A',jobGeo:'Anywhere',jobExcerpt:'<b>Build products</b>',url:'https://jobicy.com/jobs/1'},
 {id:2,jobTitle:'Software Engineer',companyName:'B',jobGeo:'USA',url:'https://jobicy.com/jobs/2'},
 {id:3,jobTitle:'Software Engineer',companyName:'C',jobGeo:'EMEA',url:'https://jobicy.com/jobs/3'},
 {id:4,jobTitle:'Software Engineer',companyName:'D',jobGeo:'',url:'https://jobicy.com/jobs/4'},
];
function load(fail=false) {
 const module={exports:{}}; const calls=[];
 const code=ts.transpileModule(fs.readFileSync('app/api/jobicy/route.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 vm.runInNewContext(code,{module,exports:module.exports,require:()=>({NextResponse:{json:(body,options)=>({body,status:options?.status||200})}}),fetch:async(url,options)=>{calls.push({url,options});return {ok:!fail,json:async()=>({jobs:fixture})}},AbortSignal,URL,URLSearchParams});
 return {get:module.exports.GET,calls};
}
const request=query=>({nextUrl:new URL('https://example.com/api/jobicy?'+query)});
test('Ghana receives worldwide and EMEA roles, not US-only or unknown eligibility',async()=>{const {get,calls}=load();const result=await get(request('q=software&country=gh'));assert.deepEqual(Array.from(result.body.jobs,j=>j.id),['jobicy:1','jobicy:3']);assert.equal(result.body.jobs[0].description,'Build products');assert.equal(calls[0].options.next.revalidate,3600);});
test('feed failure returns a partial-source error instead of fabricated jobs',async()=>{const {get}=load(true);const r=await get(request('q=software&country=gh'));assert.equal(r.status,503);assert.equal(r.body.jobs.length,0);});
test('page two does not repeat page one',async()=>{const {get}=load();assert.equal((await get(request('q=software&country=gh&page=2'))).body.jobs.length,0);});
test('unsupported country makes no upstream request',async()=>{const {get,calls}=load();assert.equal((await get(request('q=software&country=zz'))).body.jobs.length,0);assert.equal(calls.length,0);});
