# DNF Gold Kline | 国服金币行情

非官方、开源的 **DNF 国服九个跨区**金币挂牌报价观察站。跨区独立保存历史，计划每个跨区每小时采样一次并展示真实挂牌报价的采样日 K / 周 K / 月 K。

**采集策略（2026-10-28）：在独立 GitHub Chrome 实测中，跨二页面渲染出 67 条有效 DOM 报价（17：4、40：33、44：30）。新版沿用原日程改用浏览器渲染读取；7881 的普通/批发混合暂不纳入正式K线，避免错把批发挂单作为零售可用库存。**

- GitHub Pages：<https://akaturegumi.github.io/dnf-gold-kline/>
- 数据来源：[游戏达人比价网](https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2)，公开挂牌（并非真实成交价）。
- 跨区：跨一、跨二、跨三 A/B、跨四、跨五、跨六、跨七、跨八。完整 ID、链接在 `docs/data/regions.json` 中集中管理。
- 采集：GitHub Actions 每小时分别在 UTC :07、:27、:47 启动三个不同跨区组（九个跨区计划每天各24次）。对应北京时间每小时的 :07、:27、:47，不会同时打开九个网页。按触发的 cron 表达式固定选择三个跨区，避免 Actions 延迟启动后选择错组。**正式入口改为 Playwright Chrome 渲染游戏达人原网页，从 `#result_m .list_m .body` 的 DOM 读取金额、金币数量与提供平台；不使用 OCR、不绕过平台接口、不依赖个人 Cookie，不保证 Actions 准点执行。**一个跨区失败不会影响其他跨区，失败不会编造数据。
- 网页 DOM 中的 7881 报价可能混合普通金币与批发金币，暂时仅作为带来源计数的 `rendered_observation` 另存；正式K线和库存深度只使用已核实的普通币平台 UU898、DD373、YXB321（若有挂单）。待有可靠的普通/批发 DOM 区分类字段后，才能把 7881 纳入正式价格。此口径比网页“全部展示价”保守，不等于全平台最高价。
- 线上浏览器无写入校验：`python -m collector.browser_collect --region kua2 --dry-run`。原接口采集器 `python -m collector.collect` 作为手工诊断保留，正式工作流不会同时运行两种抓取。
- 历史数据：`docs/data/kua1.json` 至 `docs/data/kua8.json`（包括 `kua3a`/`kua3b`）。原先跨二的三条快照原样迁移到 `kua2.json`。
- 采集状态：`docs/data/collection_status.json` 单独记录每个跨区最近一次采集成功或失败与原因；失败不覆盖原有报价，即使整组失败也尝试提交状态。
- 默认的「采样观察」将每条真实快照绘制为独立采样点，低覆盖为橙色、合格为绿色；连接线仅是观测点引导线，不代表成交或完整市场。切换「合格 K 线」后，仅在当天有多个合格样本时显示蜡烛图，单次样本仅显示为点。
- 质量启发式：至少两个独立普通游戏币平台**实际贡献有效挂单**，且累计去重后的普通有效报价 ≥5 条记作 `usable`，不足时仍真实存档并标记 `partial`。正式 K 线和顶部价格卡片仅采用最近的合格快照（显示其时间）；最新 partial 只在独立的低覆盖观察区及九跨区概览中显示，绝不混入 K 线、正式价格或深度估算。不同跨区市场覆盖可能不同；**不能认为 usable 就是完整市场行情**。
- 7881 分类：同平台的 `yxb`（普通游戏币）与 `yxbpf`（批发游戏币）是两条独立请求；批发数据以 `wholesale_observation` 单独留存，不并入正式K线或大额深度，以免混用起购条件或重复库存。质量门槛按普通游戏币的独立平台数判定。
- 数据源诊断：每次采样保存各通道成功状态、有效挂单、毫秒级耗时、校验信息使用时长；失败记录有限的错误分类、原始调试信息的类型/长度及不可逆 SHA-256 短指纹（用于判断同一错误是否持续出现），**不存储调试原文、令牌、Cookie 或请求签名**。未知错误不再武断归为上游封锁；保存最近 40 次尝试摘要，不增加采集频率、不进行重试轰炸或访问限制规避。POST 使用同源 `Origin`、浏览器支持的 JSON 响应协商 `Accept`，并附加中文语言偏好；保留项目标识 User-Agent、不伪装浏览器。每轮只记录是否从上游正常获得 `u_client` Cookie 的布尔值，用来判断浏览器与纯 HTTP 客户端的会话差异；不会复制用户的 Cookie 或自行伪造客户端标识。
- 采样提频：2026-10-28 起计划从每跨区每天2次提升到每小时1次；单次只用 Chrome 正常打开每个跨区页面一次，不额外重试、不使用代理或个人Cookie。GitHub Actions 可能延误或漏调度，因此不是严格整点时间序列。若上游明确拒绝自动访问，应暂停而非绕过。采集健康仍可通过 `python -m tools.evaluate_sampling_health` 离线检查，但脚本既不会修改调度也不代表获得上游许可。
- 大额报价：页面展示公开挂单深度模型，假设可分拆下单，实际可能受限于卖家库存、手续费和数量限制。
- 没有账号密码、交易功能、实时成交量或虚构历史数据。

## 部署

GitHub Pages：在 Settings → Pages 中设为 `main` 分支下的 `/docs`。仓库启用 Actions，工作流需要 contents:write 以提交真实行情记录。仅采集脚本或跨区配置更新时自动进行一次采样，平时每小时分三组错峰运行、每次轮询三个跨区。

## 本地运行（Python 3.11+，无需外部依赖）

```bash
python -m unittest discover -s tests -v
python -m pip install playwright
python -m collector.browser_collect --region kua2 --dry-run
python -m collector.browser_collect --region kua2
python -m collector.browser_collect --region scheduled
python -m collector.browser_collect --region all
python -m http.server 8000 -d docs
```

本地目录中的 `docs/data` 也是数据仓库。若一次采集中途失败，其他成功跨区仍可独立写入，已保存记录不会被覆盖。

## 来源、许可和贡献

代码 MIT；**公开数据的使用授权与代码许可不同**，长期公开重发布前应确认上游条款。借鉴 [yunko1993/astrbot_plugin_dnf_gold](https://github.com/yunko1993/astrbot_plugin_dnf_gold)（MIT）的接口读取思路并保留致谢。网站只研究市场，既不提供游戏币交易，也不代表游戏官方或任何平台。若上游拒绝自动访问，应停止而非规避。

欢迎提交 Issues / PR：提高数据可靠性、更多独立数据源、历史行情、版本节点标注等。
