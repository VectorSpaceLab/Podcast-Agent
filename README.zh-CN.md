# Podcast-Agent

<p align="center">
  <strong>用于理解播客和长视频内容的工具。</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue">
  <img alt="CLI" src="https://img.shields.io/badge/Interface-CLI-green">
  <img alt="Input" src="https://img.shields.io/badge/Input-YouTube%20%7C%20Bilibili-red">
  <img alt="Output" src="https://img.shields.io/badge/Output-Markdown-black">
</p>

Podcast-Agent 可以将 YouTube 和 Bilibili 播客或长视频转换为结构化报告，帮助用户更快理解和分析内容。

[Homepage](https://vectorspacelab.github.io/Podcast-Agent/) | [概览](#概览) | [架构](#架构) | [项目结构](#项目结构) | [安装](#安装) | [快速开始](#快速开始) | [CLI-使用](#cli-使用)

## 概览

Podcast-Agent 适用于：

- 快速理解播客或长视频的核心内容。
- 生成 Markdown、PDF、小红书图片等多种格式报告。
- 保存中间产物，便于检查、调试或后续处理。

当前输入支持 YouTube 和 Bilibili 视频。

## 架构

Podcast-Agent 分为四层：

- **内容获取**  
  获取视频 metadata、字幕、音频转录和上下文信息。

- **语义提取**  
  根据用户问题提取相关证据、关键片段和上下文。

- **洞察组织**  
  生成观点结构、逻辑关系和分析框架。

- **报告生成**  
  基于 metadata、证据、观点和总结生成结构化报告。

## 项目结构

```text
src/podcast_agent/
├── sources/       Source detection and source adapters
├── elements/      Metadata, transcript fetching, and formatting
├── transcribers/  Audio transcription fallback
├── insights/      Evidence, outline, viewpoint, and summary generation
├── pipeline/      Pipeline orchestration, context, and artifact handling
├── reports/       Markdown, HTML, PDF, and Xiaohongshu report rendering
└── cli/           Command-line entry points
```

## 安装

### 1. 系统条件

- Python 3.10+
- `ffmpeg`
- Playwright Chromium
- 可访问 YouTube、Bilibili、DeepSeek、阿里云 DashScope ASR 和阿里云 OSS
- 字体已内置，无需额外安装

常见系统依赖安装：

```bash
# macOS
brew install python ffmpeg

# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg
```

如果 Linux 环境中 Chromium 启动失败，安装 Playwright 所需系统库：

```bash
.venv/bin/playwright install-deps chromium
```

### 2. 虚拟环境

在项目根目录创建虚拟环境并安装依赖：

```bash
python -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev,pdf,xhs]"
.venv/bin/playwright install chromium
```

验证 CLI 是否可用：

```bash
.venv/bin/podcast-agent --help
```

### 3. 环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

填写 `.env`：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

YOUTUBE_COOKIES_FILE=

BILIBILI_COOKIES_FILE=
BILIBILI_USER_AGENT=

ALIYUN_API_KEY=
OSS_ENDPOINT=
OSS_BUCKET_NAME=
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
```

#### 3.1 DeepSeek 模型

在 DeepSeek 控制台创建 API Key 后填写：

```env
DEEPSEEK_API_KEY=<your-deepseek-api-key>
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

如需使用其他 DeepSeek 模型，只修改 `DEEPSEEK_MODEL`。

#### 3.2 YouTube Cookies

1. 在浏览器中安装扩展 `Get cookies.txt LOCALLY`。
2. 登录 YouTube 账号。
3. 打开 YouTube 页面，点击扩展导出 `cookies.txt`。
4. 将 `cookies.txt` 放到项目根目录：

```text
Podcast-Agent/
├── cookies.txt
├── README.md
└── src/
```

5. 在 `.env` 中填写 cookies 文件路径：

```env
YOUTUBE_COOKIES_FILE=./cookies.txt
```

如果从其他工作目录启动命令，使用绝对路径：

```env
YOUTUBE_COOKIES_FILE=/absolute/path/to/Podcast-Agent/cookies.txt
```

注意：

- cookies 文件包含登录凭据，不要提交到 Git，也不要分享给他人。
- 如果 cookies 过期，需要重新导出。

#### 3.3 Bilibili Cookies

1. 在浏览器中安装扩展 `Get cookies.txt LOCALLY`。
2. 登录 Bilibili 账号。
3. 打开 Bilibili 页面，点击扩展导出 `cookies.txt`。
4. 将导出的文件放到项目根目录，例如：

```text
Podcast-Agent/
├── bilibili-cookies.txt
├── README.md
└── src/
```

5. 在 `.env` 中填写 Bilibili 配置：

```env
BILIBILI_COOKIES_FILE=./bilibili-cookies.txt
BILIBILI_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36
```

如果从其他工作目录启动命令，使用绝对路径：

```env
BILIBILI_COOKIES_FILE=/absolute/path/to/Podcast-Agent/bilibili-cookies.txt
```

#### 3.4 阿里云转录

准备阿里云 DashScope API Key 和 OSS Bucket 配置。

填写：

- `ALIYUN_API_KEY`：在阿里云百炼 / DashScope 控制台创建 API Key。
- `OSS_ENDPOINT`：在 OSS Bucket 概览页查看 Endpoint，例如 `https://oss-cn-hangzhou.aliyuncs.com`。
- `OSS_BUCKET_NAME`：填写 OSS Bucket 名称。
- `OSS_ACCESS_KEY_ID`：在阿里云 RAM 访问控制中创建 AccessKey。
- `OSS_ACCESS_KEY_SECRET`：填写对应的 AccessKey Secret。

`.env` 示例：

```env
ALIYUN_API_KEY=<your-dashscope-api-key>
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=<your-oss-bucket-name>
OSS_ACCESS_KEY_ID=<your-oss-access-key-id>
OSS_ACCESS_KEY_SECRET=<your-oss-access-key-secret>
```

## 快速开始

使用默认示例运行批处理脚本：

```bash
scripts/run-full-batch.sh
```

指定 cases 文件、输出目录或并发数：

```bash
CASES_PATH=examples/full-report-cases.jsonl \
OUTPUT_ROOT=output \
MAX_JOBS=3 \
scripts/run-full-batch.sh
```

最终报告会生成到：

```text
output/<case-id>/reports/report.md
output/<case-id>/reports/report.html
output/<case-id>/reports/report.pdf
output/<case-id>/reports/xhs/images/
```

## CLI 使用

运行完整流程：

```bash
.venv/bin/podcast-agent full \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "这个视频讲了什么？" \
  --output-dir output/my-report
```

Bilibili 链接也可以使用同一个命令：

```bash
.venv/bin/podcast-agent full \
  --url "https://www.bilibili.com/video/<BV-id>" \
  --question "这个视频讲了什么？" \
  --output-dir output/my-bilibili-report
```

完整命令参考：[CLI 使用指南](usage-docs/cli.md)。
