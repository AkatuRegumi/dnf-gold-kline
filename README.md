# DNF Gold Kline | 国服金币行情

非官方、开源的 **DNF 国服九个跨区**金币挂牌报价观察站。跨区独立保存历史，每天低频采样并展示真实报价日 K / 周 K / 月 K。

**运行状态（2026-10-18）：九个跨区均有真实采样记录；7881 等通道持续返回拒绝或无数据，部分跨区的最新快照长期为 partial。采集任务运行成功不等于合格行情更新，请查看各跨区采样时间和质量。**

- GitHub Pages：<https://akaturegumi.github.io/dnf-gold-kline/>
- 数据来源：[游戏达人比价网](https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2)，公开挂牌（并非真实成交价）。
- 跨区：跨一、跨二、跨三 A/B、跨四、跨五、跨六、跨七、跨八。完整 ID、链接在 `docs/data/regions.json` 中集中管理。
- 采集：GitHub Actions 每四小时触发一次，按触发的 cron 表达式固定选择三个跨区（九个跨区计划每天各两次），避免 Actions 实际启动延迟导致选错组；平台可能跳过定时任务，因此不保证每次都采到。一个跨区失败不会影响其他跨区，失败不会编造数据。
- 历史数据：`docs/data/kua1.json` 至 `docs/data/kua8.json`（包括 `kua3a`/`kua3b`）。原先跨二的三条快照原样迁移到 `kua2.json`。
- 采集状态：`docs/data/collection_status.json` 单独记录每个跨区最近一次采集成功或失败与原因；失败不覆盖原有报价，即使整组失败也尝试提交状态。
- 默认的「采样观察」将每条真实快照绘制为独立采样点，低覆盖为橙色、合格为绿色；连接线仅是观测点引导线，不代表成交或完整市场。切换「合格 K 线」后，仅在当天有多个合格样本时显示蜡烛图，单次样本仅显示为点。
- 质量启发式：至少两个独立普通游戏币平台**实际贡献有效挂单**，且累计去重后的普通有效报价 ≥5 条记作 `usable`，不足时仍真实存档并标记 `partial`。正式 K 线和顶部价格卡片仅采用最近的合格快照（显示其时间）；最新 partial 只在独立的低覆盖观察区及九跨区概览中显示，绝不混入 K 线、正式价格或深度估算。不同跨区市场覆盖可能不同；**不能认为 usable 就是完整市场行情**。
- 7881 分类：同平台的 `yxb`（普通游戏币）与 `yxbpf`（批发游戏币）是两条独立请求；批发数据以 `wholesale_observation` 单独留存，不并入正式K线或大额深度，以免混用起购条件或重复库存。质量门槛按普通游戏币的独立平台数判定。
- 数据源诊断：每次采样保存各通道成功状态、有效挂单、毫秒级耗时、校验信息使用时长；失败记录有限的错误分类、原始调试信息的类型/长度及不可逆 SHA-256 短指纹（用于判断同一错误是否持续出现），**不存储调试原文、令牌、Cookie 或请求签名**。未知错误不再武断归为上游封锁；保存最近 40 次尝试摘要，不增加采集频率、不进行重试轰炸或访问限制规避。POST 请求补齐浏览器同源 XHR 通常携带的 `Origin`，保留项目标识 User-Agent。
- 提频评估：`python -m tools.evaluate_sampling_health` 完全离线统计每跨区最近 12 次采样的质量率、通道成功率、跨天覆盖及新鲜度。判为 candidate 仍不代表获得上游提频许可，也不会自动修改定时工作流；当前频率保持不变。
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
