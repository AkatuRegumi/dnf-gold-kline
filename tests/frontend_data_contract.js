/* Node-only quote aggregation regression. Does not fetch network data. */
"use strict";
const assert=require("node:assert/strict");
const M=require("../docs/market-data.js");
function s(at,price,quality="usable",more={}) {
 return {observed_at:at,best_ratio:price,quality,offers_count:10,
   contributing_retail_platforms:2,...more};
}
const data=[
 s("2026-10-31T15:27:00Z",90),  // Beijing 2026-10-31 23:27
 s("2026-10-31T16:27:00Z",91),  // Beijing 2026-11-01 00:27
 s("2026-10-31T17:27:00Z",999,"partial",{offers_count:1,contributing_retail_platforms:1}),
 s("2026-11-01T01:27:00Z",89),  // Beijing Nov 1 09:27
 s("2026-11-01T10:27:00Z",93),  // Beijing Nov 1 18:27
 s("2026-11-01T16:27:00Z",95)  // Beijing Nov 2 00:27
];
assert.equal(M.beijing(data[1].observed_at).date,"2026-11-01");
assert.equal(M.beijing(data[1].observed_at).hour,"00");
assert.equal(M.bucket(data[1].observed_at,"week"),"2026-10-26");
assert.equal(M.bucket(data[1].observed_at,"month"),"2026-11");
assert.deepEqual(M.candles(data,"day").map(x=>x.date),[
  "2026-10-31","2026-11-01","2026-11-02"]);
const candle=M.candles(data,"day")[1];
assert.deepEqual([candle.o,candle.h,candle.l,candle.c,candle.n],[91,93,89,93,3]);
assert.equal(candle.midnightObserved,true);
assert.equal(M.candles(data,"day")[0].midnightObserved,false);
assert.equal(M.candles(data,"day")[0].n,1);
assert.equal(M.candles(data,"day")[2].n,1);
assert.equal(M.observations(data).length,6);
assert.equal(M.observations(data).filter(x=>!x.reliable).length,1);
assert.equal(M.latestQualified(data).best_ratio,95);
assert.deepEqual(M.ma(M.candles(data,"day"),5),[null,null,null]);
assert.equal(M.quoteDelta(data),((95-93)/93)*100);
assert.equal(M.qualified(s("2026-11-01T01:00:00Z",200,"partial")),false);
assert.equal(M.qualified(s("2026-11-01T01:00:00Z",200,"usable",
  {contributing_retail_platforms:1})),false);
assert.equal(M.qualified(s("2026-11-01T01:00:00Z",200,"usable",
  {channel_outcomes:[{coin_no:"yxb",id:17,state:"ok",accepted:4},
                     {coin_no:"yxb",id:40,state:"ok",accepted:0}],
   contributing_retail_platforms:null})),false);
assert.equal(M.qualified(s("2026-11-01T01:00:00Z",200,"usable",
  {channel_outcomes:[{coin_no:"yxb",id:17,state:"ok",accepted:4},
                     {coin_no:"yxb",id:40,state:"ok",accepted:2}],
   contributing_retail_platforms:null})),true);
assert.equal(M.qualified(s("2026-11-01T01:00:00Z",null,"usable")),false);
const single=M.candles([s("2026-11-01T10:27:00Z",93)],"day")[0];
assert.equal(single.n,1); // presenter must paint a scatter, not a forged candle
assert.equal(single.firstAt,single.lastAt);
console.log("PASS: truthful Beijing-time OHLC, quality, missing periods, MA and null values");
