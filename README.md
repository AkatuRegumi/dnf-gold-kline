# DNF Gold Kline | 国服金币行情

非官方、开源的 **DNF 国服九个跨区**金币挂牌报价观察站。跨区独立保存历史，每天低频采样并展示真实报价日 K / 周 K / 月 K。

**运行状态（2026-10-11）：九个跨区均已有真实采样记录，但部分通道间歇不返回数据，最新快照不一定合格；各跨区以网站及 JSON 的时间戳、quality 为准。**

- GitHub Pages：<https://akaturegumi.github.io/dnf-gold-kline/>
- 数据来源：[游戏达人比价网](https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2)，公开挂牌（并非真实成交价）。
- 跨区：跨一、跨二、跨三 A/B、跨四、跨五、跨六、跨七、跨八。完整 ID、链接在 `docs/data/regions.json` 中集中管理。
- 采集：GitHub Actions 每四小时触发一次，按触发的 cron 表达式固定选择三个跨区（九个跨区计划每天各两次），避免 Actions 实际启动延迟导致选错组；平台可能跳过定时任务，因此不保证每次都采到。一个跨区失败不会影响其他跨区，失败不会编造数据。
- 历史数据：`docs/data/kua1.json` 至 `docs/data/kua8.json`（包括 `kua3a`/`kua3b`）。原先跨二的三条快照原样迁移到 `kua2.json`。
- 采集状态：`docs/data/collection_status.json` 单独记录每个跨区最近一次采集成功或失败与原因；失败不覆盖原有报价，即使整组失败也尝试提交状态。
- K 线只在当天有多个合格样本时展示最高、最低和实体；单次样本仅显示为点，不制造蜡烛图。
- 质量启发式：成功通道 ≥2 且有效报价 ≥5 条记作 `usable`，不足时仍真实存档并标记 `partial`。正式 K 线和顶部价格卡片仅采用最近的合格快照（显示其时间）；最新 partial 只在独立的低覆盖观察区及九跨区概览中显示，绝不混入 K 线、正式价格或深度估算。不同跨区市场覆盖可能不同；**不能认为 usable 就是完整市场行情**。
- 数据源诊断：上游个别报价通道间歇性不可用时，仅记录公开响应的状态与返回结构类型，不记录令牌或原始请求，以便确认问题原因；不会重试轰炸上游或绕过拒绝。
- 大额报价：页面展示公开挂单深度模型，假设可分拆下单，实际可能受限于卖家库存、手续费和数量限制。
- 没有账号密码、交易功能、实时成交量或虚构历史数据。

## 部署

GitHub Pages：在 Settings → Pages 中设为 `main` 分支下的 `/docs`。仓库启用 Actions，工作流需要 contents:write 以提交真实行情记录。仅采集脚本或跨区配置更新时自动进行一次采样，平时每四小时运行一次、每次轮询三个跨区。

## 本地运行（Python 3.11+，无需外部依赖）

```bash
python -m unittest discover -s tests -v
python -m collector.collect --region kua2
python -m collector.collect --region scheduled
python -m collector.collect --region all
python -m http.server 8000 -d docs
```

本地目录中的 `docs/data` 也是数据仓库。若一次采集中途失败，其他成功跨区仍可独立写入，已保存记录不会被覆盖。

## 来源、许可和贡献

代码 MIT；**公开数据的使用授权与代码许可不同**，长期公开重发布前应确认上游条款。借鉴 [yunko1993/astrbot_plugin_dnf_gold](https://github.com/yunko1993/astrbot_plugin_dnf_gold)（MIT）的接口读取思路并保留致谢。网站只研究市场，既不提供游戏币交易，也不代表游戏官方或任何平台。若上游拒绝自动访问，应停止而非规避。

欢迎提交 Issues / PR：提高数据可靠性、更多独立数据源、历史行情、版本节点标注等。
