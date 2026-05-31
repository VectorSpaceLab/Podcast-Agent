# Podcast-Agent CLI 使用指南

这份文档是 Podcast-Agent CLI 的统一使用文档。

## 安装

开发环境安装：

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

如果需要 PDF 或小红书图片渲染：

```bash
.venv/bin/pip install -e ".[pdf,xhs]"
.venv/bin/playwright install chromium
```

创建本地环境配置：

```bash
cp .env.example .env
```

常用环境变量：

```text
DASHSCOPE_API_KEY
YOUTUBE_COOKIES_FILE
ALIYUN_API_KEY
ALIYUN_ASR_API_BASE
ALIYUN_ASR_MODEL
OSS_ENDPOINT
OSS_BUCKET_NAME
OSS_ACCESS_KEY_ID
OSS_ACCESS_KEY_SECRET
FFMPEG_BIN
```

## 命令总览

```text
podcast-agent run              初始化一次 run，获取 source、metadata、transcript
podcast-agent transcript       单独获取 YouTube transcript
podcast-agent transcribe-audio 转录本地音频文件
podcast-agent intent           推断报告语言和长度偏好
podcast-agent evidence         从 transcript 提取证据
podcast-agent outline          生成观点大纲
podcast-agent viewpoints       生成观点详情
podcast-agent summary          生成总结
podcast-agent report           生成 reports/report.md 和 reports/report.html
podcast-agent report-pdf       基于 reports/report.html 生成 reports/report.pdf
podcast-agent xhs-report       生成 reports/xhs/ 小红书图文报告
podcast-agent full             从 URL 跑完整流程
podcast-agent full-batch       并发跑多个完整流程 case
```

查看帮助：

```bash
.venv/bin/podcast-agent --help
.venv/bin/podcast-agent full --help
.venv/bin/podcast-agent xhs-report --help
```

## 最常用：一条命令跑完整流程

```bash
.venv/bin/podcast-agent full \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "这个视频讲了什么？" \
  --output-dir output/my-report
```

最终主要输出：

```text
output/my-report/
├── input.json
├── source.json
├── elements/
│   ├── metadata.json
│   ├── transcript.vtt
│   ├── transcript.txt
│   └── transcript_info.json
├── insights/
│   ├── intent.json
│   ├── evidence.json
│   ├── outline.json
│   ├── viewpoints.json
│   └── summary.json
└── reports/
    ├── report.md
    ├── report.html
    ├── report.pdf
    └── xhs/
        ├── note.md
        ├── post_meta.json
        └── images/
```

查看 Markdown 报告：

```bash
sed -n '1,240p' output/my-report/reports/report.md
```

查看小红书发布文案：

```bash
cat output/my-report/reports/xhs/post_meta.json
```

## 分阶段运行

分阶段命令适合调试某个阶段，或复用已有 artifacts。

### 初始化基础素材

```bash
.venv/bin/podcast-agent run \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "这个视频讲了什么？" \
  --output-dir output/my-report
```

`run` 会生成基础 artifacts：

```text
input.json
source.json
elements/metadata.json
elements/transcript.vtt
elements/transcript.txt
elements/transcript_info.json
```

### 单独获取 transcript

```bash
.venv/bin/podcast-agent transcript \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --output-dir output/transcript-demo
```

该命令优先使用 YouTube 原生字幕；如果没有可用字幕，会在配置齐全时走音频转录 fallback。

### 推断报告意图

```bash
.venv/bin/podcast-agent intent \
  --question "Please summarize this briefly in English." \
  --output-dir output/my-report
```

输出：

```text
output/my-report/insights/intent.json
```

### 提取证据

已有 `input.json` 和 `elements/transcript.vtt` 时：

```bash
.venv/bin/podcast-agent evidence \
  --output-dir output/my-report
```

没有前置 artifacts 时，也可以让 evidence 命令先生成上游素材：

```bash
.venv/bin/podcast-agent evidence \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "这个视频讲了什么？" \
  --output-dir output/my-report
```

### 生成 outline、viewpoints、summary

```bash
.venv/bin/podcast-agent outline \
  --output-dir output/my-report

.venv/bin/podcast-agent viewpoints \
  --output-dir output/my-report

.venv/bin/podcast-agent summary \
  --output-dir output/my-report
```

输出：

```text
output/my-report/insights/outline.json
output/my-report/insights/viewpoints.json
output/my-report/insights/viewpoint_V*.json
output/my-report/insights/summary.json
```

## 报告生成

### Markdown 和 HTML

```bash
.venv/bin/podcast-agent report \
  --output-dir output/my-report
```

输出：

```text
output/my-report/reports/report.md
output/my-report/reports/report.html
```

### PDF

PDF 基于已有 HTML：

```bash
.venv/bin/podcast-agent report-pdf \
  --output-dir output/my-report
```

输出：

```text
output/my-report/reports/report.pdf
```

### 小红书图文报告

```bash
.venv/bin/podcast-agent xhs-report \
  --output-dir output/my-report
```

只生成 `note.md` 和 `post_meta.json`，不渲染 PNG：

```bash
.venv/bin/podcast-agent xhs-report \
  --output-dir output/my-report \
  --skip-render
```

指定写作角度：

```bash
.venv/bin/podcast-agent xhs-report \
  --output-dir output/my-report \
  --angle "面向关注 AI 创业和商业落地的读者"
```

输出：

```text
output/my-report/reports/xhs/
├── note.md
├── post_meta.json
├── cover.png
└── images/
    ├── intro.png
    └── page_1.png
```

## 本地音频转录

```bash
.venv/bin/podcast-agent transcribe-audio \
  --audio-path /path/to/audio.wav \
  --output-dir output/audio-demo \
  --language zh
```

输出：

```text
output/audio-demo/elements/transcript.vtt
output/audio-demo/elements/transcript.txt
```

## 批量并发执行

从 JSON case 文件并发跑完整流程：

```bash
.venv/bin/podcast-agent full-batch \
  --cases examples/full-report-cases.json \
  --max-jobs 3
```

只预览选中的 case，不执行：

```bash
.venv/bin/podcast-agent full-batch \
  --cases examples/full-report-cases.json \
  --tag new \
  --dry-run
```

指定 case：

```bash
.venv/bin/podcast-agent full-batch \
  --cases examples/full-report-cases.json \
  --case V9eI-t3TApE \
  --max-jobs 1
```

输出目录：

```text
output/batch-<run-id>/
├── <case-id>-<run-id>/
└── logs/
    ├── <case-id>.log
    └── summary.json
```

也可以使用脚本：

```bash
./scripts/run-full-batch.sh
MAX_JOBS=5 ./scripts/run-full-batch.sh
./scripts/run-full-batch.sh --tag new --dry-run
```

## Case 文件格式

`full-batch` 默认读取：

```text
examples/full-report-cases.json
```

格式：

```json
{
  "version": 1,
  "default_question": "这个视频讲了什么？",
  "cases": [
    {
      "id": "V9eI-t3TApE",
      "url": "https://www.youtube.com/watch?v=V9eI-t3TApE",
      "question": "这个视频讲了什么？",
      "tags": ["new", "full", "xhs", "pdf"]
    }
  ]
}
```

`question` 可省略；省略时使用 `default_question`。

## 常见工作流

### 只重新生成报告样式

如果 insights 已经生成，只调整报告样式：

```bash
.venv/bin/podcast-agent report \
  --output-dir output/my-report

.venv/bin/podcast-agent report-pdf \
  --output-dir output/my-report
```

### 只重新生成小红书稿

```bash
.venv/bin/podcast-agent xhs-report \
  --output-dir output/my-report \
  --angle "面向产品经理和创业者"
```

### 从 evidence 之后重新跑

```bash
.venv/bin/podcast-agent outline --output-dir output/my-report
.venv/bin/podcast-agent viewpoints --output-dir output/my-report
.venv/bin/podcast-agent summary --output-dir output/my-report
.venv/bin/podcast-agent report --output-dir output/my-report
.venv/bin/podcast-agent report-pdf --output-dir output/my-report
.venv/bin/podcast-agent xhs-report --output-dir output/my-report
```

## 常见问题

### `report-pdf` 报 `reports/report.html is required`

先生成 HTML：

```bash
.venv/bin/podcast-agent report \
  --output-dir output/my-report
```

### Playwright Chromium 未安装

```bash
.venv/bin/playwright install chromium
```

### YouTube 字幕或 metadata 获取失败

如果视频需要登录态，可以设置 cookies 文件：

```bash
YOUTUBE_COOKIES_FILE=/absolute/path/to/cookies.txt
```

### 音频转录缺少环境变量

音频转录需要 Aliyun 和 OSS 配置。检查 `.env` 中是否设置：

```text
ALIYUN_API_KEY
OSS_ENDPOINT
OSS_BUCKET_NAME
OSS_ACCESS_KEY_ID
OSS_ACCESS_KEY_SECRET
```

### 只想验证命令是否可用

```bash
.venv/bin/podcast-agent --help
.venv/bin/podcast-agent full-batch --dry-run
```
