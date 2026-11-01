/* Offline tests: no GitHub/Cloudflare requests, and no external packages. */
import assert from "node:assert/strict";
import test from "node:test";
import worker, {shouldDispatch, dispatchOnce, dispatchRequest} from "../cloudflare/hourly-dispatch.mjs";

const HOUR = Date.parse("2026-11-01T12:05:00Z");
const event = {scheduledTime:HOUR};
const validEnv = {DISPATCH_ENABLED:"true",GITHUB_ACTIONS_TOKEN:"fake-test-token-123456"};
const fakeFetch = async request => {
  assert.equal(request.method,"POST");
  assert.equal(request.url,
    "https://api.github.com/repos/AkatuRegumi/dnf-gold-kline/actions/workflows/collect.yml/dispatches");
  assert.equal(request.headers.get("Authorization"),"Bearer fake-test-token-123456");
  assert.deepEqual(await request.json(),{ref:"main",inputs:{region:"all"}});
  return new Response(JSON.stringify({workflow_run_id:123}),{status:200});
};
test("hourly cron is accepted within its 35-minute budget", async()=>{
  assert.equal(shouldDispatch(HOUR,HOUR+1000),true);
  assert.equal(shouldDispatch(HOUR,HOUR+34*60_000),true);
  assert.equal(shouldDispatch(HOUR,HOUR+36*60_000),false);
  assert.equal(shouldDispatch(HOUR,HOUR-2*60_000),false);
  const r=await dispatchOnce(event,validEnv,fakeFetch,HOUR+1000);
  assert.deepEqual(r,{state:"accepted",status:200});
});
test("also handles 204 old dispatch response",async()=>{
  const r=await dispatchOnce(event,validEnv,async()=>new Response(null,{status:204}),HOUR);
  assert.equal(r.state,"accepted");
});
test("disabled worker never sends an external request",async()=>{
  const fail=()=>{throw Error("must not fetch")};
  assert.equal((await dispatchOnce(event,{...validEnv,DISPATCH_ENABLED:"false"},fail,HOUR)).state,"disabled");
  assert.equal((await dispatchOnce(event,validEnv,fail,HOUR+40*60_000)).state,"skipped_stale");
});
test("unexpected response or missing secret does not claim success",async()=>{
  await assert.rejects(dispatchOnce(event,validEnv,
    async()=>new Response("denied",{status:403}),HOUR),/HTTP 403/);
  await assert.rejects(dispatchOnce(event,{...validEnv,GITHUB_ACTIONS_TOKEN:""},fakeFetch,HOUR),
    /Missing or invalid/);
});
test("request body contains no credentials and no extra region fetch",async()=>{
  const req=dispatchRequest(validEnv.GITHUB_ACTIONS_TOKEN);
  const text=await req.text();
  assert.equal(text.includes("fake-test-token"),false);
  assert.equal(text.includes("kua2"),false);
  assert.equal(text.includes('"region":"all"'),true);
});
test("there is no unauthenticated public worker endpoint",async()=>{
  const response=await worker.fetch(new Request("https://example.test/"));
  assert.equal(response.status,404);
});
