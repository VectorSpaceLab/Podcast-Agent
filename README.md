# Podcast-Agent

<p align="center">
  <strong>A tool for understanding podcasts and long-form videos.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue">
  <img alt="CLI" src="https://img.shields.io/badge/Interface-CLI-green">
  <img alt="Input" src="https://img.shields.io/badge/Input-YouTube%20%7C%20Bilibili-red">
  <img alt="Output" src="https://img.shields.io/badge/Output-Markdown-black">
</p>

Podcast-Agent turns YouTube and Bilibili podcasts or long-form videos into structured reports for faster understanding and analysis.

[Homepage](https://vectorspacelab.github.io/Podcast-Agent/) | [Overview](#overview) | [Architecture](#architecture) | [Project Structure](#project-structure) | [Installation](#installation) | [Quick Start](#quick-start) | [CLI Usage](#cli-usage)

## Overview

Podcast-Agent is useful when you want to:

- Quickly understand what a podcast or long-form video is about.
- Produce reports in multiple formats, including editable Markdown, PDF, and Xiaohongshu-style image outputs.
- Generate shareable reports in multiple formats for easier distribution.
- Save intermediate artifacts for review, debugging, or downstream analysis.

Current input support includes YouTube and Bilibili videos.

## Architecture

Podcast-Agent is organized around four core layers:

- **Content Ingestion**  
  Capture essential podcast and video elements, including metadata, transcripts, and contextual signals.

- **Semantic Extraction**  
  Analyze raw content around the user's question to identify relevant evidence, key moments, and meaningful context.

- **Insight Structuring**  
  Organize extracted information into core viewpoints, logical relationships, and a coherent analytical framework.

- **Report Generation**  
  Assemble metadata, evidence, viewpoints, and summaries into a polished structured report for fast understanding.

## Project Structure

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

## Installation

### 1. System Requirements

- Python 3.10+
- `ffmpeg`
- Playwright Chromium
- Network access to YouTube, Bilibili, DeepSeek, Aliyun DashScope ASR, and Aliyun OSS
- Fonts are bundled; no extra font installation is required

Common system dependency installation:

```bash
# macOS
brew install python ffmpeg

# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg
```

If Chromium fails to launch on Linux, install the required Playwright system libraries:

```bash
.venv/bin/playwright install-deps chromium
```

### 2. Virtual Environment

Create a virtual environment and install Python dependencies from the project root:

```bash
python -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev,pdf,xhs]"
.venv/bin/playwright install chromium
```

Verify that the CLI is available:

```bash
.venv/bin/podcast-agent --help
```

### 3. Environment Variables

Copy the environment template:

```bash
cp .env.example .env
```

Then fill in `.env`:

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

#### 3.1 DeepSeek Model

Create an API key in the DeepSeek console, then set:

```env
DEEPSEEK_API_KEY=<your-deepseek-api-key>
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

To use another DeepSeek model, only change `DEEPSEEK_MODEL`.

#### 3.2 YouTube Cookies

1. Install the browser extension `Get cookies.txt LOCALLY`.
2. Log in to your YouTube account.
3. Open YouTube and export `cookies.txt` with the extension.
4. Place `cookies.txt` in the project root:

```text
Podcast-Agent/
├── cookies.txt
├── README.md
└── src/
```

5. Set the cookies file path in `.env`:

```env
YOUTUBE_COOKIES_FILE=./cookies.txt
```

If commands are run from another working directory, use an absolute path:

```env
YOUTUBE_COOKIES_FILE=/absolute/path/to/Podcast-Agent/cookies.txt
```

Notes:

- The cookies file contains login credentials. Do not commit it or share it.
- If the cookies expire, export the file again.

#### 3.3 Bilibili Cookies

1. Install the browser extension `Get cookies.txt LOCALLY`.
2. Log in to your Bilibili account.
3. Open Bilibili and export `cookies.txt` with the extension.
4. Place the exported file in the project root, for example:

```text
Podcast-Agent/
├── bilibili-cookies.txt
├── README.md
└── src/
```

5. Set the Bilibili options in `.env`:

```env
BILIBILI_COOKIES_FILE=./bilibili-cookies.txt
BILIBILI_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36
```

If commands are run from another working directory, use an absolute path:

```env
BILIBILI_COOKIES_FILE=/absolute/path/to/Podcast-Agent/bilibili-cookies.txt
```

#### 3.4 Aliyun Transcription

Prepare an Aliyun DashScope API key and OSS bucket configuration.

Set:

- `ALIYUN_API_KEY`: Create an API key in the Aliyun Bailian / DashScope console.
- `OSS_ENDPOINT`: Find the endpoint on the OSS bucket overview page, for example `https://oss-cn-hangzhou.aliyuncs.com`.
- `OSS_BUCKET_NAME`: Use the OSS bucket name.
- `OSS_ACCESS_KEY_ID`: Create an AccessKey in Aliyun RAM.
- `OSS_ACCESS_KEY_SECRET`: Use the matching AccessKey secret.

`.env` example:

```env
ALIYUN_API_KEY=<your-dashscope-api-key>
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=<your-oss-bucket-name>
OSS_ACCESS_KEY_ID=<your-oss-access-key-id>
OSS_ACCESS_KEY_SECRET=<your-oss-access-key-secret>
```

## Quick Start

Run the bundled batch script with the default example cases:

```bash
scripts/run-full-batch.sh
```

To use a custom cases file, output directory, or concurrency level:

```bash
CASES_PATH=examples/full-report-cases.jsonl \
OUTPUT_ROOT=output \
MAX_JOBS=3 \
scripts/run-full-batch.sh
```

The final report will be generated at:

```text
output/<case-id>/reports/report.md
output/<case-id>/reports/report.html
output/<case-id>/reports/report.pdf
output/<case-id>/reports/xhs/images/
```

## CLI Usage

Run the full pipeline from the command line:

```bash
.venv/bin/podcast-agent full \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "Your question about the video" \
  --output-dir output/my-report
```

Bilibili URLs are supported in the same command:

```bash
.venv/bin/podcast-agent full \
  --url "https://www.bilibili.com/video/<BV-id>" \
  --question "Your question about the video" \
  --output-dir output/my-bilibili-report
```

For a complete command reference, see [CLI Usage Guide](usage-docs/cli.md).
