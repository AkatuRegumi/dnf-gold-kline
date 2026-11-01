/* Quote-only market model: no network access, no invented OHLC or volume.
   Data remain individual timestamped seller-ask observations. */
(function(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.MarketData = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  const zone = "Asia/Shanghai";
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", hourCycle: "h23"
  });
  const finite = v => v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));
  const validRatio = s => s && finite(s.best_ratio) && Number(s.best_ratio) > 0;
  const sorted = samples => (Array.isArray(samples) ? samples : [])
    .filter(s => s && typeof s.observed_at === "string" &&
      Number.isFinite(Date.parse(s.observed_at)))
    .slice().sort((a,b) => Date.parse(a.observed_at)-Date.parse(b.observed_at));
  function qualified(s) {
    if (!s || !validRatio(s)) return false;
    if (!(s.quality === "usable" ||
      (s.quality == null && s.successful_channels >= 2 && s.offers_count >= 5))) return false;
    if (!finite(s.offers_count) || Number(s.offers_count) < 5) return false;
    if (finite(s.contributing_retail_platforms))
      return Number(s.contributing_retail_platforms) >= 2;
    if (Array.isArray(s.channel_outcomes) &&
      s.channel_outcomes.some(c => c.coin_no === "yxb")) {
      const contributors = new Set(s.channel_outcomes.filter(c =>
        c.coin_no === "yxb" && c.state === "ok" && Number(c.accepted) > 0
      ).map(c => String(c.id)));
      return contributors.size >= 2;
    }
    return true; // pre-breakdown snapshots retain their persisted assessment
  }
  function beijing(stamp) {
    const date = new Date(stamp);
    if (!Number.isFinite(date.getTime())) return null;
    const p = Object.fromEntries(parts.formatToParts(date)
      .filter(v => v.type !== "literal").map(v => [v.type, v.value]));
    return { date: p.year + "-" + p.month + "-" + p.day, hour: p.hour };
  }
  function bucket(stamp, timeframe) {
    const p = beijing(stamp);
    if (!p) return null;
    if (timeframe === "month") return p.date.slice(0,7);
    if (timeframe === "week") {
      const [y,m,d] = p.date.split("-").map(Number);
      const utc = new Date(Date.UTC(y,m-1,d));
      utc.setUTCDate(utc.getUTCDate() - (utc.getUTCDay()+6)%7);
      return utc.toISOString().slice(0,10);
    }
    return p.date;
  }
  function candles(samples, timeframe) {
    if (!["day","week","month"].includes(timeframe)) throw Error("Invalid timeframe");
    const buckets = new Map();
    for (const s of sorted(samples)) {
      if (!qualified(s)) continue;
      const key = bucket(s.observed_at, timeframe);
      if (!key) continue;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(s);
    }
    return Array.from(buckets, ([date, rows]) => {
      const ratios = rows.map(s => Number(s.best_ratio));
      const first = rows[0],last = rows[rows.length-1];
      const actualSlots = new Set(rows.map(s => {
        const dt = new Date(s.observed_at);
        return dt.toISOString().slice(0,13);
      }));
      return {date, o:ratios[0], h:Math.max(...ratios), l:Math.min(...ratios),
        c:ratios[ratios.length-1], n:rows.length,
        firstAt:first.observed_at, lastAt:last.observed_at,
        midnightObserved: timeframe !== "day" || beijing(first.observed_at).hour === "00",
        distinctUtcHours: actualSlots.size,
        offers: Number(last.offers_count)||0,
        platforms: Number(last.contributing_retail_platforms)||0};
    }).sort((a,b) => a.date.localeCompare(b.date));
  }
  function observations(samples) {
    return sorted(samples).filter(validRatio).map(s => ({
      time:s.observed_at, date:beijing(s.observed_at).date,
      value:Number(s.best_ratio), reliable:qualified(s),
      offers:finite(s.offers_count)?Number(s.offers_count):null,
      platforms:finite(s.contributing_retail_platforms)
        ?Number(s.contributing_retail_platforms):null,
      source:s.capture_method||"http", snapshot:s
    }));
  }
  function latestQualified(samples) {
    return sorted(samples).reverse().find(qualified) || null;
  }
  function quoteDelta(samples) {
    const arr = sorted(samples).filter(qualified);
    if (arr.length < 2) return null;
    const old = Number(arr[arr.length-2].best_ratio);
    const newest = Number(arr[arr.length-1].best_ratio);
    return old > 0 ? (newest-old)/old*100 : null;
  }
  function ma(candles, n) {
    return candles.map((_,i) => {
      if (i < n-1) return null;
      const v=candles.slice(i-n+1,i+1).map(b=>b.c);
      return v.every(Number.isFinite) ? v.reduce((a,b)=>a+b,0)/n : null;
    });
  }
  const formatTime = stamp => stamp
    ? new Date(stamp).toLocaleString("zh-CN", {
        timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit",
        hour:"2-digit",minute:"2-digit",hour12:false
      }) : "—";
  return {qualified,sorted,beijing,bucket,candles,observations,
    latestQualified,quoteDelta,ma,formatTime};
});
