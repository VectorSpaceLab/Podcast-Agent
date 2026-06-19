# Bilibili Videochat Alignment Decision

## 背景

当前 `Podcast-Agent` 的 B 站抓取链路主要依赖 `yt-dlp` 的基础能力，已经能完成元数据、字幕和音频下载，但在网络波动、Cookie 可用性、浏览器登录态接入和失败降级策略上，与 `videochat` 的实现存在明显差异。

最近一次失败日志显示：

```text
Unable to download webpage
HTTPSConnectionPool(host='www.bilibili.com', port=443): Read timed out. (read timeout=20.0)
```

这说明问题并不在业务逻辑本身，而是在 B 站网页请求层的容错能力不足。

## 决策

本项目的 B 站实现将**完全对齐 `videochat` 的能力模型**，并在此基础上保留 `Podcast-Agent` 现有的输出格式与流水线接口。

对齐目标不是“代码逐行一致”，而是做到以下几件事：

1. B 站配置项与 `videochat` 同级别。
2. B 站 `yt-dlp` 参数和 Cookie 处理策略与 `videochat` 一致。
3. B 站字幕优先级、降级逻辑和音频兜底策略与 `videochat` 一致。
4. B 站异常处理和日志语义与 `videochat` 一致或等价。

## 必须对齐的内容

### 1. 配置项

新增并贯通以下配置：

- `BILIBILI_COOKIES_FILE`
- `BILIBILI_COOKIES_FROM_BROWSER`
- `BILIBILI_USER_AGENT`

其中：

- `BILIBILI_COOKIES_FILE` 优先于浏览器 Cookie。
- `BILIBILI_COOKIES_FROM_BROWSER` 作为 Cookie 第二来源。
- `BILIBILI_USER_AGENT` 作为显式请求头。

### 2. Cookie 处理

对齐 `videochat` 的行为：

- 支持从浏览器读取 Cookie。
- 支持文件 Cookie。
- 若提供的是文件 Cookie，则按 Netscape `cookies.txt` 格式处理。
- 在输出工作目录中生成稳定的 Cookie 快照，避免源文件被覆盖或并发污染。

### 3. `yt-dlp` 请求参数

对齐 `videochat` 的 B 站请求头与请求策略：

- `Referer: https://www.bilibili.com/`
- `User-Agent` 使用配置值或默认值

同时补齐 `Podcast-Agent` 当前缺失的网络容错参数：

- `socket_timeout`
- `retries`
- `extractor_retries`

原因是当前失败模式已经明确暴露为网页读取超时，单靠默认 `yt-dlp` 参数不够。

### 4. 字幕处理

对齐 `videochat` 的字幕策略：

- 优先选择与用户语言匹配的手动字幕。
- 其次选择与用户语言匹配的自动字幕。
- 再回退到其他可用字幕。
- 过滤 B 站弹幕 XML，不把它当作可下载字幕。
- 下载字幕失败时，自动回退到音频下载和转写。

### 5. 音频兜底

对齐 `videochat` 的音频回退行为：

- 字幕列表失败，不直接终止。
- 字幕下载失败，尝试下一条字幕。
- 所有字幕尝试失败后，再走音频下载。
- 音频下载仍失败时，再暴露明确错误。

## 当前代码与目标差异

### 现状

- `src/podcast_agent/downloaders/yt_dlp.py` 只支持 `BILIBILI_COOKIES_FILE` 和 `BILIBILI_USER_AGENT`。
- `src/podcast_agent/elements/youtube_metadata.py` 的 B 站下载器构造没有完整透传调用方 cookies 参数。
- 当前 B 站 `yt-dlp` 选项没有显式设置网络超时和重试。
- 当前 B 站配置没有浏览器 Cookie 入口。

### 目标

- B 站配置、下载器、元数据获取与字幕下载，统一走同一套 B 站参数构造逻辑。
- 代码风格可以保持 `Podcast-Agent` 现有组织方式，但行为要与 `videochat` 等价。

## 非目标

以下内容不作为本次对齐目标：

- 不要求 `Podcast-Agent` 的目录结构和模块命名完全复制 `videochat`。
- 不要求日志前缀、指标名、工作流名完全一致。
- 不要求把 `videochat` 的整套工作流、评估脚本、CLI 设计全部移植过来。
- 不要求改变 `Podcast-Agent` 的报告输出格式。

## 推荐实现顺序

1. 先把 B 站配置扩展为支持 `cookies_from_browser`。
2. 再统一 B 站 `yt-dlp` 基础选项，补上 timeout / retries。
3. 修正元数据 fetcher 对 B 站 cookies 的传递路径。
4. 再对齐字幕列表、字幕下载和音频兜底的行为。
5. 最后补测试，覆盖 Cookie 优先级、参数透传、超时重试和字幕回退。

## 受影响文件

- `src/podcast_agent/config.py`
- `src/podcast_agent/elements/youtube_metadata.py`
- `src/podcast_agent/elements/youtube_transcript.py`
- `src/podcast_agent/downloaders/yt_dlp.py`
- `src/podcast_agent/sources/bilibili.py`
- `src/podcast_agent/sources/registry.py`，若需要统一构造参数
- `README.md`
- `README.zh-CN.md`
- `tests/test_downloaders_yt_dlp.py`
- `tests/test_youtube_metadata_fetch.py`
- `tests/test_youtube_transcript_fetch.py`

## 验收标准

当以下条件成立时，认为 B 站对齐完成：

1. 传入有效 `BILIBILI_COOKIES_FILE` 或 `BILIBILI_COOKIES_FROM_BROWSER` 时，B 站元数据与字幕抓取都能正常工作。
2. 网络慢、B 站响应慢时，不会在默认 20 秒超时后直接失败，而是按重试策略继续尝试。
3. 字幕优先级和音频兜底行为与 `videochat` 一致。
4. 现有 B 站相关测试覆盖新配置和新策略。

## 结论

本次修改应视为一次“B 站接入能力对齐”，不是简单修 bug。
后续实现要以 `videochat` 的行为为参照系，优先保证可用性和一致性，再做局部命名和结构适配。
