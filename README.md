# Podcast-Agent

<p align="center">
  <strong>A tool for understanding podcasts and long-form videos.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue">
  <img alt="CLI" src="https://img.shields.io/badge/Interface-CLI-green">
  <img alt="Input" src="https://img.shields.io/badge/Input-YouTube-red">
  <img alt="Output" src="https://img.shields.io/badge/Output-Markdown-black">
</p>

Podcast-Agent turns YouTube podcasts and long-form videos into structured reports for faster understanding and analysis.

[Overview](#-overview) | [Key Features](#-key-features) | [Pipeline](#-pipeline) | [Installation](#-installation) | [Quick Start](#-quick-start) | [CLI Usage](#-cli-usage) | [Output Artifacts](#-output-artifacts) | [Project Structure](#-project-structure) | [Future Support](#future-support)

## ✨ Overview

Podcast-Agent is useful when you want to:

- Quickly understand what a podcast or long-form video is about.
- Ask a focused question about a video and collect relevant evidence.
- Turn video content into viewpoints, summaries, and reports.
- Save intermediate artifacts for review, debugging, or downstream analysis.

Current input support is centered on YouTube videos.

## 🚀 Key Features

- Generate a structured report from a podcast or long-form video.
- Quickly understand the core content without watching the full episode.
- Organize and interpret the key viewpoints discussed in the podcast.
- Jump from important report moments directly back to the original video.

## 🧩 Pipeline

```text
YouTube URL
  -> source detection
  -> basic elements
  -> evidence extraction
  -> outline planning
  -> viewpoint generation
  -> summary
  -> Markdown report
```

Each stage writes artifacts to the output directory, so the result is easy to inspect and individual steps can be reused.

## 🛠️ Installation

Podcast-Agent requires Python 3.10 or later.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Create a local environment file:

```bash
cp .env.example .env
```

Then fill in the configuration needed for your runtime, such as LLM credentials, YouTube cookies, Aliyun ASR, OSS, and the ffmpeg binary path.

## ⚡ Quick Start

Run the full pipeline with a YouTube URL:

```bash
.venv/bin/podcast-agent full \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "What is this video about?" \
  --output-dir output/my-report
```

The final report will be generated at:

```text
output/my-report/reports/report.md
```

## 💻 CLI Usage

The main entry point is the full pipeline command:

```bash
.venv/bin/podcast-agent full \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "Your question about the video" \
  --output-dir output/my-report
```

Podcast-Agent also provides step-by-step CLI commands for debugging a single stage or reusing existing artifacts.

For the full pipeline command, see [Full Pipeline CLI](usage-docs/full-pipeline-cli.md).

## 📦 Output Artifacts

A typical full run creates an output directory like this:

```text
output/my-report/
├── input.json
├── source.json
├── elements/
│   ├── metadata.json
│   ├── transcript.txt
│   ├── transcript.vtt
│   └── transcript_info.json
├── insights/
│   ├── intent.json
│   ├── evidence.json
│   ├── outline.json
│   ├── viewpoints.json
│   ├── viewpoint_V1.json
│   ├── viewpoint_V2.json
│   └── summary.json
└── reports/
    ├── report.md
    ├── report.html
    └── cover.<ext>        # optional, copied when a local thumbnail is available
```

## 🗂️ Project Structure

```text
src/podcast_agent/
├── sources/       Source detection and source adapters
├── elements/      Metadata, transcript fetching, and formatting
├── transcribers/  Audio transcription fallback
├── insights/      Evidence, outline, viewpoint, and summary generation
├── pipeline/      Pipeline orchestration, context, and artifact handling
├── reports/       Markdown report rendering
└── cli/           Command-line entry points
```

## Future Support

Information sources:

- Xiaoyuzhou
- Apple Podcasts

Report formats:

- Xiaohongshu posts
- WeChat Official Account articles
