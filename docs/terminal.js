/* DNF GOLD terminal: read-only presentation over persisted public quote snapshots. */
(function() {
"use strict";
const M=window.MarketData;
const $=id=>document.getElementById(id);
const current={region:"kua2",period:"day",sub:"offers",version:0};
const datasets=new Map();
let regions=[],major=null,secondary=null;
const num=(v,digits=2)=>Number.isFinite(Number(v))&&v!==null&&v!==undefined?Number(v).toFixed(digits):"—";
const escapeHtml=v=>String(v).replace(/[&<>"']/g,c=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[c]));
const nameOf=id=>regions.find(r=>r.id===id)?.name||id;
const colorOf=v=>v>0?"up":v<0?"down":"flat";
const pctText=v=>v===null?"—":(v>0?"+":"")+num(v)+"%";
const last=(samples)=>M.sorted(samples).at(-1)||null;
function dataOf(id) {
  const o=datasets.get(id);
  return o && Array.isArray(o.samples)?o.samples:[];
}
function showError(target,message) {
  $(target).textContent=message;
}
function setText(id,value) {$(id).textContent=value}
function quoteStatus(samples) {
  const valid=M.latestQualified(samples);
  if(!valid)return null;
  const delta=M.quoteDelta(samples);
  const t=Date.parse(valid.observed_at);
  return {valid,delta,ageHours:(Date.now()-t)/3600000};
}
function refreshRegions(){
  const cards=regions.map(r=>{
    const samples=dataOf(r.id);
    return {r,latest:last(samples),quote:quoteStatus(samples)};
  });
  const root=$("overview"),strip=$("ticker");
  root.replaceChildren();strip.replaceChildren();
  for(const {r,latest,quote} of cards){
    const active=r.id===current.region;
    const b=document.createElement("button");
    b.type="button";b.className="market-row";b.dataset.region=r.id;
    b.dataset.selected=String(active);
    const q=quote?.valid;
    const delta=quote?.delta??null;
    const stale=!quote || quote.ageHours>6;
    const display=q?num(q.best_ratio):"—";
    b.innerHTML='<span class="market-name">'+escapeHtml(r.name)+'</span>'+
      '<span class="market-price '+(stale?'flat':'')+'">'+display+'</span>'+
      '<span class="market-sub">'+(q?(stale?'较旧合格行情':'有效挂牌 '+q.offers_count+' 条'):'暂无合格行情')+'</span>'+
      '<span class="market-change '+(delta===null?'flat':colorOf(delta))+'">'+pctText(delta)+'</span>';
    b.onclick=()=>selectRegion(r.id);
    root.appendChild(b);
    const t=document.createElement("button");
    t.type="button";t.className="ticker-item";t.dataset.active=String(active);
    t.innerHTML='<strong>'+escapeHtml(r.name)+'</strong><span>'+
      (q?display:'—')+'</span>　<span class="'+colorOf(delta??0)+'">'+pctText(delta)+'</span>';
    t.title=latest?'最近采样：'+M.formatTime(latest.observed_at):'无采样';
    t.onclick=()=>selectRegion(r.id);
    strip.appendChild(t);
  }
}
function updateTape(samples) {
  const arr=M.sorted(samples).slice(-30).reverse(),t=$("tape");
  t.replaceChildren();
  if(!arr.length){t.textContent="目前没有报价采样";return}
  let previous=null;
  for(const s of arr) {
    const ok=M.qualified(s),v=Number(s.best_ratio);
    const row=document.createElement("div");row.className="tape-row";
    const stamp=document.createElement("div");stamp.className="tape-time";
    stamp.textContent=M.formatTime(s.observed_at);
    const val=document.createElement("div");val.className="tape-value";
    val.textContent=Number.isFinite(v)?num(v,3):"—";
    const detail=document.createElement("div");detail.className="tape-detail "+(ok?"quality-ok":"quality-partial");
    detail.textContent=(ok?"合格":"低覆盖")+" · "+(s.offers_count||0)+"条挂单";
    const src=document.createElement("div");src.className="tape-detail";
    src.style.textAlign="right";src.textContent=(s.contributing_retail_platforms??"?")+"平台";
    row.append(stamp,val,detail,src);t.appendChild(row);
    previous=v;
  }
}
function detailCard(samples,region){
  const latest=last(samples),q=quoteStatus(samples),valid=q?.valid;
  $("region-name").replaceChildren(document.createTextNode(nameOf(region)+" "));
  const tag=document.createElement("span");tag.className="tag";tag.textContent=region.toUpperCase();
  $("region-name").append(tag);
  setText("best",valid?num(valid.best_ratio,3):"—");
  const delta=$("delta");delta.textContent=q?pctText(q.delta):"—";
  delta.className=q?.delta!==null?colorOf(q.delta):"flat";
  setText("qualified-time",valid?M.formatTime(valid.observed_at):"—");
  setText("time",latest?M.formatTime(latest.observed_at):"—");
  setText("source",latest?((latest.offers_count??"?")+" 条 / "+(latest.contributing_retail_platforms??"?")+" 平台"):"—");
  setText("count",String(samples.length));
  for(const [field,id] of [["30000","d3"],["100000","d10"],["120000","d12"]]){
    const x=valid?.depth?.[field];
    setText(id,x?.ratio_wan_per_cny!=null?num(x.ratio_wan_per_cny):"库存不足");
  }
  const entry=regions.find(r=>r.id===region);
  $("market-link").href=entry?.source_url||"https://www.yxdr.com";
  const partial=$("partial-preview");
  partial.hidden=!latest||M.qualified(latest);
  if(!partial.hidden) {
    partial.textContent="最近采样覆盖不足，仅观察到 "+(latest.offers_count??"?")+" 条挂牌；"+
      "不会代替顶部的合格行情，也不会混入正式K线。";
  }
  updateTape(samples);
}
function axisCommon(){
  return {axisLine:{lineStyle:{color:"#41546a"}},axisLabel:{color:"#9db0c5",fontSize:11},
    splitLine:{show:true,lineStyle:{color:"#233144",type:"dashed"}}};
}
function tooltipBox(lines) {
  return '<div style="font:12px/1.65 system-ui;max-width:250px">'+
    lines.map((x,i)=>i===0?'<b>'+escapeHtml(x)+'</b>':'<div>'+escapeHtml(x)+'</div>').join("")+'</div>';
}
function renderTrend(samples) {
  const rows=M.observations(samples);
  const reliable=rows.filter(x=>x.reliable),partial=rows.filter(x=>!x.reliable);
  if(!rows.length){major.clear();setText("chart-summary","暂无真实采样数据");return}
  const series={
    name:"离散挂牌快照",type:"line",symbol:"circle",symbolSize:5,
    data:rows.map(x=>[Date.parse(x.time),x.value]),
    lineStyle:{color:"#d7aa6b",type:"dashed",width:1.3,opacity:.9},
    itemStyle:{color:"#d7aa6b"},
    connectNulls:false,showSymbol:rows.length<140
  };
  const option={
    animation:false,backgroundColor:"transparent",
    grid:{left:52,right:28,top:36,bottom:78},
    tooltip:{trigger:"axis",axisPointer:{type:"cross",lineStyle:{color:"#768aa1"}},
      backgroundColor:"#101c2b",borderColor:"#405671",textStyle:{color:"#edf3ff"},
      formatter(params){
        const p=params.find(x=>x.seriesName==="离散挂牌快照");
        if(!p)return "";
        const at=+p.value[0],record=rows.find(x=>Date.parse(x.time)===at);
        if(!record)return "";
        return tooltipBox([M.formatTime(record.time),
          "挂牌比例 "+num(record.value,3)+" 万金币/元",
          record.reliable?"合格报价":"低覆盖观察（非正式行情）",
          "有效挂单 "+(record.offers??"?")+" 条 · 平台 "+(record.platforms??"?")+" 家",
          "采样点连线不代表连续成交"]);
      }},
    xAxis:{type:"time",...axisCommon(),axisLabel:{color:"#9db0c5",hideOverlap:true}},
    yAxis:{type:"value",scale:true,name:"万金币/元",nameTextStyle:{color:"#9db0c5"},
      ...axisCommon()},
    dataZoom:[{type:"inside",xAxisIndex:0,filterMode:"none"},
      {type:"slider",height:20,bottom:26,borderColor:"#293748",
        fillerColor:"rgba(114,186,247,.15)",textStyle:{color:"#9db0c5"}}],
    series:[series,{
      name:"合格采样",type:"scatter",symbolSize:6,
      data:reliable.map(x=>[Date.parse(x.time),x.value]),itemStyle:{color:"#29c89a"},
      silent:true,z:5
    },{
      name:"低覆盖",type:"scatter",symbolSize:8,
      data:partial.map(x=>[Date.parse(x.time),x.value]),itemStyle:{color:"#e8ae61"},
      silent:true,z:5
    }]
  };
  major.setOption(option,true);
  setText("chart-summary","共 "+rows.length+" 个实测采样点，"+reliable.length+
    " 个合格；虚线仅连接观察值，不代表连续成交。拖动底部滑块查看历史。");
}
function renderK(samples,period){
  const bars=M.candles(samples,period);
  if(!bars.length){major.clear();setText("chart-summary","暂无合格K线数据");return}
  const categories=bars.map(b=>b.date);
  const candle=bars.map(b=>b.n<2?"-":[b.o,b.c,b.l,b.h]);
  const singles=bars.filter(b=>b.n===1).map(b=>[b.date,b.c]);
  const option={
    animation:false,backgroundColor:"transparent",
    grid:{left:57,right:26,top:42,bottom:82},
    legend:{show:true,top:10,right:15,textStyle:{color:"#9baec3",fontSize:11}},
    tooltip:{trigger:"axis",axisPointer:{type:"cross",lineStyle:{color:"#7e91aa"}},
      backgroundColor:"#101c2b",borderColor:"#405671",
      textStyle:{color:"#eef4fc"},
      formatter(params){
        const k=params[0]?.axisValue;
        const b=bars.find(b=>b.date===k);
        if(!b)return "";
        return tooltipBox([b.date+" · 采样"+(period==="day"?"日":period==="week"?"周":"月")+"K",
          "开 "+num(b.o,3)+"　高 "+num(b.h,3),
          "低 "+num(b.l,3)+"　收 "+num(b.c,3),
          "合格采样 "+b.n+" 次",
          "首笔 "+M.formatTime(b.firstAt),
          "末笔 "+M.formatTime(b.lastAt),
          ...(b.midnightObserved?[]:["未采到北京时间00点所在小时"]),
          ...(b.n===1?["单次采样，仅画点，不制造K线实体"]:[]),
          "挂牌采样OHLC，非真实成交价"]);
      }},
    xAxis:{type:"category",data:categories,...axisCommon(),
      axisLabel:{color:"#9db0c5",hideOverlap:true}},
    yAxis:{type:"value",scale:true,name:"万金币/元",nameTextStyle:{color:"#9db0c5"},
      ...axisCommon()},
    dataZoom:[{type:"inside",start:Math.max(0,100-100*32/bars.length),end:100},
      {type:"slider",height:20,bottom:25,start:Math.max(0,100-100*32/bars.length),
        end:100,borderColor:"#293748",fillerColor:"rgba(114,186,247,.16)",
        textStyle:{color:"#9db0c5"}}],
    series:[{
      name:"采样K线",type:"candlestick",data:candle,
      itemStyle:{color:"#fc687b",color0:"#29c89a",
        borderColor:"#fc687b",borderColor0:"#29c89a"},
      barMaxWidth:16
    },{
      name:"单次样本",type:"scatter",symbolSize:7,data:singles,
      itemStyle:{color:"#e8ae61"},z:6
    },...([5,10,20].map((n,i)=>({
      name:"MA"+n,type:"line",data:M.ma(bars,n),smooth:false,
      symbol:"none",connectNulls:false,lineStyle:{width:1.25,color:["#f6d18b","#9d8af2","#66b3db"][i]},
      itemStyle:{color:["#f6d18b","#9d8af2","#66b3db"][i]}
    })))]
  };
  major.setOption(option,true);
  const incomplete=period==="day"?bars.filter(b=>!b.midnightObserved).length:0;
  setText("chart-summary",bars.length+" 根周期记录；"+singles.length+
    " 个只有单次采样（仅画点）"+(incomplete?"；"+incomplete+" 天缺少00点时段合格报价":"")+
    "。拖动底部滑块查看历史。");
}
function renderSecondary(samples){
  if(!secondary)return;
  const obs=M.observations(samples).slice(-70);
  if(!obs.length){secondary.clear();return}
  const which=current.sub;
  const values=obs.map(x=>which==="offers"?x.offers:x.platforms);
  const option={animation:false,backgroundColor:"transparent",
    grid:{left:53,right:24,top:13,bottom:34},
    xAxis:{type:"category",data:obs.map(x=>M.formatTime(x.time).slice(5)),
      ...axisCommon(),axisLabel:{color:"#9db0c5",hideOverlap:true,
        interval:Math.max(0,Math.ceil(obs.length/8)-1)}},
    yAxis:{type:"value",min:0,minInterval:1,...axisCommon()},
    tooltip:{trigger:"axis",backgroundColor:"#101c2b",borderColor:"#405671",
      textStyle:{color:"#eef4fc"},
      formatter(params){const i=params[0]?.dataIndex??-1,x=obs[i];return x?tooltipBox([
        M.formatTime(x.time),
        (which==="offers"?"有效挂单":"独立普通币平台")+" "+(values[i]??"未知"),
        x.reliable?"合格":"低覆盖",
        "观察数据，不是交易量"]):""}},
    series:[{name:which==="offers"?"有效挂单":"普通币平台",type:"bar",
      barMaxWidth:15,
      data:values.map((v,i)=>v===null?"-":{
        value:v,itemStyle:{color:obs[i].reliable?"#29b69a":"#e8ae61"}
      })}]
  };
  secondary.setOption(option,true);
}
function draw(){
  const arr=dataOf(current.region);
  setText("chart-title",nameOf(current.region)+" · "+
    ({trend:"分时观察",day:"采样日K",week:"采样周K",month:"采样月K"}[current.period]));
  setText("chart-subtitle",current.period==="trend"?"真实采样时间戳 · 非连续行情":
    "北京时间00:00归日 · 合格样本聚合 · 非成交OHLC");
  if(!major){setText("chart-summary","图表引擎暂不可用。其他真实报价与采样记录仍可查看。");return}
  if(current.period==="trend")renderTrend(arr);
  else renderK(arr,current.period);
  renderSecondary(arr);
}
function selectRegion(id,writeUrl=true){
  if(!regions.some(r=>r.id===id))return;
  current.region=id;
  $("region-select").value=id;
  if(writeUrl){const url=new URL(location.href);url.searchParams.set("region",id);
    history.replaceState(null,"",url.pathname+url.search+url.hash)}
  refreshRegions();
  const data=dataOf(id);
  detailCard(data,id);
  draw();
  setText("status",data.length?
    "数据来源：游戏达人比价网\n采集：Playwright读取渲染后的真实挂牌\n"+
    "最新采样："+M.formatTime(last(data).observed_at)+"\n"+
    "最新合格："+M.formatTime(M.latestQualified(data)?.observed_at)+"\n"+
    "合格判定：至少2个独立普通金币平台及5条有效挂单。\n"+
    "7881零售/批发在网页表格中未可靠区分，暂不计入正式价格。":
    "暂无有效采样。缺失不会填造数据。");
}
async function fetchAll(){
  const seq=++current.version;
  const button=$("btn-refresh");button.disabled=true;button.textContent="更新中…";
  try {
    const manifest=await fetch("./data/regions.json",{cache:"no-store"});
    if(!manifest.ok)throw Error("跨区配置加载失败 "+manifest.status);
    const data=await manifest.json();
    if(!Array.isArray(data.regions)||data.regions.length!==9)throw Error("跨区配置错误");
    const loaded=await Promise.all(data.regions.map(async r=>{
      try{const res=await fetch("./data/"+encodeURIComponent(r.id)+".json",{cache:"no-store"});
        if(!res.ok)throw Error("HTTP "+res.status);
        const body=await res.json();
        if(body.region!==r.id||!Array.isArray(body.samples))throw Error("数据跨区不匹配");
        return [r.id,body];
      }catch(_e){return [r.id,{region:r.id,samples:[]}];}
    }));
    if(seq!==current.version)return;
    regions=data.regions;
    for(const [id,body] of loaded)datasets.set(id,body);
    const select=$("region-select");
    select.replaceChildren();
    for(const r of regions){const op=document.createElement("option");
      op.value=r.id;op.textContent=r.name;select.appendChild(op);}
    const requested=new URLSearchParams(location.search).get("region");
    const selected=regions.some(r=>r.id===current.region)?current.region:
      (regions.some(r=>r.id===requested)?requested:(data.default_region||"kua2"));
    if(requested&&regions.some(r=>r.id===requested)&&!current.loaded)current.region=requested;
    current.loaded=true;
    selectRegion(selected,false);
    setText("asof","页面更新 "+new Date().toLocaleTimeString("zh-CN",
      {timeZone:"Asia/Shanghai",hour12:false,hour:"2-digit",minute:"2-digit"}));
  }catch(err){
    setText("status","数据加载失败："+err.message+"。请检查 GitHub Pages 发布和数据文件。");
    setText("chart-summary","数据暂不可用，未制作合成行情。");
  }finally{if(seq===current.version){button.disabled=false;button.textContent="↻ 更新快照";}}
}
function init(){
  if(window.echarts){
    major=window.echarts.init($("main-chart"),"dark",{renderer:"canvas"});
    secondary=window.echarts.init($("secondary-chart"),"dark",{renderer:"canvas"});
  } else {
    $("main-chart").innerHTML='<div class="error">专业图表引擎尚未加载。报价卡片、跨区榜和采样流水仍可正常查看；请检查网络或稍后刷新。</div>';
  }
  $("region-select").addEventListener("change",e=>selectRegion(e.target.value));
  $("timeframes").addEventListener("click",e=>{
    const b=e.target.closest("button[data-kind]");if(!b)return;
    current.period=b.dataset.kind;
    $("timeframes").querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));
    draw();
  });
  $("sub-modes").addEventListener("click",e=>{
    const b=e.target.closest("button[data-ind]");if(!b)return;
    current.sub=b.dataset.ind;
    $("sub-modes").querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));
    renderSecondary(dataOf(current.region));
  });
  $("btn-refresh").addEventListener("click",fetchAll);
  window.addEventListener("resize",()=>{
    major?.resize();secondary?.resize();
  });
  fetchAll();
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);
else init();
})();
