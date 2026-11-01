/**
 * DNF GOLD hourly clock: Cloudflare Cron -> one GitHub workflow_dispatch.
 *
 * NO public API, no user browser cookies, no data scraping here.
 * The GitHub workflow remains the single recorder for all nine cross-regions.
 * GITHUB_ACTIONS_TOKEN is a Cloudflare encrypted secret; never commit it.
 */
const DISPATCH_URL =
  "https://api.github.com/repos/AkatuRegumi/dnf-gold-kline/actions/workflows/collect.yml/dispatches";

const MAX_LATENESS_MS = 35 * 60 * 1000;

export function shouldDispatch(scheduledTime, now = Date.now()) {
  return Number.isFinite(scheduledTime) &&
    Number.isFinite(now) &&
    scheduledTime <= now + 60_000 &&
    now - scheduledTime <= MAX_LATENESS_MS;
}

export function dispatchRequest(token) {
  if (typeof token !== "string" || token.trim().length < 12) {
    throw new Error("Missing or invalid GITHUB_ACTIONS_TOKEN secret");
  }
  return new Request(DISPATCH_URL, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
      "User-Agent": "dnf-gold-kline-hourly-clock",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    body: JSON.stringify({ref:"main",inputs:{region:"all"}})
  });
}

export async function dispatchOnce(event, env, doFetch = fetch, now = Date.now()) {
  if (!shouldDispatch(event?.scheduledTime, now)) {
    console.log("DNF clock: stale or unexpected scheduled event; no dispatch");
    return {state:"skipped_stale"};
  }
  if (env?.DISPATCH_ENABLED !== "true") {
    console.log("DNF clock: disabled; no dispatch");
    return {state:"disabled"};
  }
  const request = dispatchRequest(env.GITHUB_ACTIONS_TOKEN);
  const response = await doFetch(request);
  // GitHub's latest API documents 200 with a run URL; older versions used 204.
  if (response.status !== 200 && response.status !== 204) {
    // Never print response bodies: they might expose request/permission details.
    throw new Error(`GitHub workflow_dispatch failed (HTTP ${response.status})`);
  }
  console.log("DNF clock: hourly dispatch accepted by GitHub");
  return {state:"accepted",status:response.status};
}

export default {
  // Deliberately no public dispatch endpoint; the secret never leaves Workers.
  async fetch() {
    return new Response("Not Found", {status:404});
  },
  async scheduled(controller, env) {
    return dispatchOnce(controller, env);
  }
};
