# Bilibili Videochat Alignment Execution Plan

## 目标

将 `Podcast-Agent` 的 B 站接入能力对齐到 `videochat` 的行为模型，同时保留当前项目的流水线结构、报告输出和命名习惯。

本计划对应的决策文档是：

- [Bilibili Videochat Alignment Decision](./bilibili-videochat-alignment-decision.md)

## 总体策略

按“先配置、再下载器、再业务链路、最后测试与文档”的顺序推进。每一阶段结束后都要有可验证的行为变化，避免一次性大改导致问题难以定位。

## 阶段 1. 配置层对齐

### 目标

补齐 B 站配置入口，并让配置在整个调用链中可透传。

### 任务

1. 在 `src/podcast_agent/config.py` 中新增 `BILIBILI_COOKIES_FROM_BROWSER`。
2. 检查 `.env.example`、`README.md`、`README.zh-CN.md` 中的 B 站配置说明，补上新的配置项。
3. 确认 `load_dotenv()` 读取后的配置能稳定覆盖默认值。
4. 保持 YouTube 和 Bilibili 的配置风格一致，避免单独分叉出新的配置体系。

### 验收

- `.env` 可配置 `BILIBILI_COOKIES_FILE`、`BILIBILI_COOKIES_FROM_BROWSER`、`BILIBILI_USER_AGENT`。
- 当前代码中能够读取到这些值，而不是只依赖环境变量里的单一字段。

## 阶段 2. yt-dlp 基础选项对齐

### 目标

把 B 站的 `yt-dlp` 请求行为改成更接近 `videochat`，并补上超时和重试能力。

### 任务

1. 在 `src/podcast_agent/downloaders/yt_dlp.py` 中统一 B 站基础请求头。
2. 增加 `cookies_from_browser` 支持，并把它加入 B 站选项构造函数。
3. 增加网络容错参数：
   - `socket_timeout`
   - `retries`
   - `extractor_retries`
4. 确认 metadata、subtitle、audio 三类下载路径都复用同一套 B 站基础选项。
5. 保持现有测试中对 `Referer`、`User-Agent`、`cookiefile` 的断言，同时补充对新字段的断言。

### 验收

- B 站下载器构造出的 options 中包含 B 站专用 headers。
- 网络慢时不再只靠默认 20 秒超时硬扛。
- 新增重试参数后，失败会经历重试而不是立刻退出。

## 阶段 3. 元数据获取路径对齐

### 目标

让 B 站 metadata fetcher 的参数来源和 `videochat` 一致，避免出现“传了配置却没真正生效”的情况。

### 任务

1. 检查 `src/podcast_agent/elements/youtube_metadata.py` 中 B 站 downloader 的构造逻辑。
2. 确保 `cookies_file`、`user_agent`、后续新增的 `cookies_from_browser` 能完整从配置传入。
3. 修正 B 站分支中任何硬编码环境变量覆盖调用方参数的情况。
4. 若有必要，统一 `source` 分支和 `elements` 分支的 downloader 构造方式，减少重复。

### 验收

- 传入的配置值会被实际使用。
- B 站 metadata 获取不再依赖“隐式读环境变量”。

## 阶段 4. 字幕与音频回退对齐

### 目标

把 B 站字幕优先级、失败重试和音频兜底行为对齐到 `videochat`。

### 任务

1. 检查 `src/podcast_agent/elements/youtube_transcript.py` 中 B 站字幕获取逻辑。
2. 确保手动字幕优先于自动字幕。
3. 过滤掉 B 站弹幕 XML，不把它当成可用字幕轨。
4. 保留多字幕尝试机制，不要因为单条字幕失败就直接退出。
5. 确认字幕失败后会回退到音频下载，再进入转写。
6. 检查失败日志，保证能看出是“字幕列表失败”“字幕下载失败”还是“音频兜底失败”。

### 验收

- 至少一条可用字幕存在时，优先下载字幕而不是音频。
- 所有字幕失败时，系统会自动进入音频兜底。
- 弹幕轨不再误判为字幕。

## 阶段 5. Cookie 文件稳定化

### 目标

让 B 站 cookie 的处理方式更接近 `videochat` 的稳定快照思路。

### 任务

1. 评估是否需要在 `Podcast-Agent` 中加入 Netscape `cookies.txt` 校验。
2. 评估是否需要在输出目录里生成临时 cookie 快照，避免并发或路径污染。
3. 明确 `BILIBILI_COOKIES_FILE` 和 `BILIBILI_COOKIES_FROM_BROWSER` 的优先级。
4. 如果需要，补上对 malformed cookie 文件的显式报错。

### 验收

- cookie 读取失败时会给出明确错误，而不是模糊的 `yt-dlp` 异常。
- 并发或重复运行时，cookie 行为保持稳定。

## 阶段 6. 测试补齐

### 目标

用测试锁定新行为，防止以后回退。

### 任务

1. 更新 `tests/test_downloaders_yt_dlp.py`：
   - 新增 `cookies_from_browser` 断言。
   - 新增超时和重试参数断言。
2. 更新 `tests/test_youtube_metadata_fetch.py`：
   - 验证 B 站 downloader 的配置透传。
3. 更新 `tests/test_youtube_transcript_fetch.py`：
   - 验证字幕排序、过滤、兜底逻辑。
4. 如有 cookie 校验逻辑，补对应失败测试。
5. 跑一轮 B 站相关测试回归，确认改动没有影响 YouTube 路径。

### 验收

- 新行为有测试覆盖。
- 原有 B 站测试仍然通过。
- YouTube 路径没有被 B 站改动误伤。

## 阶段 7. 文档收口

### 目标

把对齐结果写回到用户可见文档里，避免后续使用者只看到旧说明。

### 任务

1. 更新 `README.md` 中 B 站配置段落。
2. 更新 `README.zh-CN.md` 中 B 站配置段落。
3. 如有必要，在快速开始或故障排查里补一条关于超时和 cookies 的说明。
4. 确保文档里的配置名与代码完全一致。

### 验收

- README 里的配置说明可直接照着使用。
- 文档不会遗漏 `BILIBILI_COOKIES_FROM_BROWSER`。

## 建议实施顺序

1. 配置层对齐。
2. yt-dlp 基础选项对齐。
3. 元数据获取路径对齐。
4. 字幕与音频回退对齐。
5. Cookie 稳定化。
6. 测试补齐。
7. 文档收口。

## 关键风险

- 只改 `yt-dlp` 选项而不修正配置透传，会出现“看起来支持了，实际没生效”的假象。
- 只补超时不补重试，仍可能在 B 站高峰期不稳定。
- 只做字幕优先级而不保留音频兜底，会降低整体成功率。
- 只改实现不补测试，后续很容易被回归。

## 完成标准

当以下条件全部满足时，执行计划可视为完成：

1. B 站支持 file cookie 和 browser cookie 两种入口。
2. B 站 `yt-dlp` 请求具备显式 timeout 和 retry 策略。
3. 字幕和音频回退行为与 `videochat` 等价。
4. B 站相关测试覆盖新增行为。
5. README 和中文 README 同步更新。

