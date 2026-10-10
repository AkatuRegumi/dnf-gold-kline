# DNF Gold Kline | 国服金币行情

一个非官方开源的 DNF 国服金币挂牌价格观察站。从跨二（湖南、湖北互通）开始，积累真实报价快照，展示日/周/月 K 线以及大额买金币的参考成本。

**项目状态：已于 2026-10-11 完成首次 GitHub Actions 实网采集与历史数据自动提交。** 目前部分上游渠道返回失败，行情属于**局部市场样本**，不能视作所有平台的完整报价。无数据时图表显示空白，绝不生成伪造行情。

- 数据源：[游戏达人跨二比价页面](https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2)，仅采集公开商家挂牌信息；不是实际成交价。
- 采集：GitHub Actions 每四小时低频运行一次，将成功的真实快照追加到 `docs/data/history.json`。采集失败不篡改历史。
- 展示：静态 `docs/index.html`，可托管在 GitHub Pages。K 线只采用成功来源通道至少 3 个、有效挂牌至少 10 条的快照；覆盖不足的真实快照仅作记录，不会影响行情走势。这是经验性质量门槛，并不代表数据完整性证明。
- 风险：第三方接口可能变动、拒绝云端请求或限制再发布；发生限制就停止，不绕过登录、验证码或风控。

## 启用

1. 在 Actions 手动触发 **Capture DNF gold quote**，确认运行成功且 `docs/data/history.json` 包含真实样本。
2. 在 Settings → Pages 中选择 **Deploy from a branch**，分支 `main`，目录 `/docs`。
3. 若 Actions 无法写入 `main`，检查仓库 Settings → Actions → General → Workflow permissions，允许适当的写入权限。

## 本地测试

需要 Python 3.11+，不需要额外安装 Python 依赖。

```bash
python -m unittest discover -s tests -v
python -m collector.collect
python -m http.server 8000 -d docs
```

## 开源与数据来源

源代码 MIT；上游数据不因此获得相同许可。长期公开运行前应确认网站数据使用条款及授权。采集思路借鉴 [yunko1993/astrbot_plugin_dnf_gold](https://github.com/yunko1993/astrbot_plugin_dnf_gold)（MIT），感谢原作者。本站不提供金币交易，亦不代表任何交易网站或游戏官方。

欢迎通过 Issues / Pull Requests 贡献跨区适配、价差分析、行情事件标记、数据源可靠性改进。请勿提交账号凭证、伪造历史数据或规避上游访问限制的代码。
