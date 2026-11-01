# Cloudflare → GitHub 每小时采集时钟

本目录是**部署模板**，不在 GitHub Actions 内自动部署 Cloudflare，**也不包含任何个人令牌**。

目标：Cloudflare Workers Cron 在 UTC 每小时 `:05` 发起一次 **GitHub `workflow_dispatch`**，由仓库既有的 Chrome DOM 采集器依次抓取九跨区。实际采样时间仍以 `observed_at` 为准。不会补造过去漏掉的小时报价。

## 部署步骤（需要仓库维护者本人在 Cloudflare 授权）

1. 在 GitHub [Fine-grained personal access tokens](https://github.com/settings/personal-access-tokens/new) 创建**只对 `AkatuRegumi/dnf-gold-kline` 一个仓库生效**的令牌，权限设置为 `Actions: Read and write`，其他权限尽量保持最低。建议设到期时间，妥善轮换。**不要发送给任何聊天、不要提交到代码或 Actions 日志**。官方 GitHub REST `workflow_dispatch` 要求细粒度令牌具备 Actions write 权限。
2. 在装有 Node.js 的本地机器检出本仓库，打开仓库根目录，执行：
   ```powershell
   npx wrangler login
   npx wrangler deploy --config cloudflare/wrangler.jsonc
   npx wrangler secret put GITHUB_ACTIONS_TOKEN --config cloudflare/wrangler.jsonc
   ```
   第二条只部署这个 Worker（不改 GitHub 定时任务）；最后一条命令会在本地要求输入令牌，并存为 Cloudflare Secret。Worker 没有公开 HTTP 采集接口。
3. **初次部署 `DISPATCH_ENABLED` 为 `"false"`，因此不发 GitHub 请求。** 在 Cloudflare Workers → `dnf-gold-hourly-clock` → Settings → Variables and Secrets 确认 GitHub Secret 已保存。在浏览器内查看 Scheduled Triggers 是否出现 `5 * * * *`。或者使用 Wrangler 本地的 `--test-scheduled` 验证计划任务入口；注意仅本地测试不会给 GitHub 发真实请求，除非开关已经启用。
4. 确认准备好后，将 **`cloudflare/wrangler.jsonc` 中的 `"DISPATCH_ENABLED": "false"` 改为 `"true"`** 并再次运行：
   ```powershell
   npx wrangler deploy --config cloudflare/wrangler.jsonc
   ```
   **不要改动/公开 `GITHUB_ACTIONS_TOKEN` 的值**。下一个 Cron 时点才会真正 dispatch。Github 最新API响应成功时为 HTTP 200，旧版本为 204；Worker 两者均接受。
5. 在仓库 [Capture DNF gold quote](https://github.com/AkatuRegumi/dnf-gold-kline/actions/workflows/collect.yml) 确认出现 `workflow_dispatch` 运行（`region=all`），并核对一次运行是九跨区；在 `docs/data/collection_status.json` 和各区 `samples` 核对真实入库时间。观察至少两个完整小时，确认触发和采集链路可靠，**再**移除旧 `collect.yml` 的三个 GitHub `schedule` cron；上线的前几轮旧 cron 作为兜底。
6. 紧急关闭：把 `DISPATCH_ENABLED` 改回 `"false"` 并重新部署；需要完全停止 Cloudflare Cron 时再把 `triggers.crons` 改为 `[]` 并部署。**仅在控制台删注释无法禁用 Cron**。如果 Cloudflare 不稳定，可保持 GitHub 旧 cron 兜底。

## 避免双重采样

GitHub Actions 工作流共享 `concurrency.group: dnf-price-history`，只允许同一仓库的一次采集作业运行。采集器在对每个跨区启动浏览器前检查该跨区是否已经保存了当前 **UTC自然小时** 的真实快照。如果有，则跳过该跨区、不再访问 YXDR、也不写第二条行情；没有保存快照的失败采样可在同小时再次尝试。UTC 小时和北京时间自然小时边界一致（北京时间比 UTC 快8小时）。

**限制**：如果某个工作流被极端延迟到下个小时才执行，行情只能按它**真实执行的时间**归档；这不是历史回填。GitHub Actions Cron / Cloudflare Cron 都不是硬实时。Cloudflare Worker 在 Cron 迟到超过35分钟时自动跳过迟到任务，避免在完全错误的时间段挤占下一次采样。

## 校验与观察指标

- 单跨区每日**预期**24次，九跨区每日**预期**216个快照。
- Cloudflare 预期24次触发/日，GitHub预期24次 `workflow_dispatch` 运行/日；漏事件/延时都可能使实际低于预期。
- 每轮最多九个页面请求，不使用额外OCR、账号、个人Cookie、代理或绕过上游限制。每跨区/小时最多1次实际成功快照。
- 可对比 GitHub `workflow_dispatch` 次数、成功作业数和九跨区小时覆盖率；**工作流 success 并不保证每个小时都采满**。
- 如果 GitHub token 过期、权限变更或 Cloudflare 被暂停，Worker会将错误HTTP状态留在自己的日志，不会记录令牌正文；继续用 GitHub 兜底，重新授权后恢复。
- 不会自动读取云端 Token；仅由持有 Cloudflare 账号权限的人设置。数据源的自动访问与重发布仍应遵守上游使用条款。

代码：`hourly-dispatch.mjs`（Worker）及 `../tests/cloudflare_dispatch.test.mjs`（完全离线回归）。`npx wrangler` 使用 Cloudflare 官方 Wrangler 工具；不需要将 Worker 编译代码导入 DNF 网站。
