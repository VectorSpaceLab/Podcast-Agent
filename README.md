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

[Overview](#overview) | [Architecture](#architecture) | [Project Structure](#project-structure) | [Installation](#installation) | [Quick Start](#quick-start) | [CLI Usage](#cli-usage)

## Overview

Podcast-Agent is useful when you want to:

- Quickly understand what a podcast or long-form video is about.
- Generate shareable reports in multiple formats for easier distribution.
- Save intermediate artifacts for review, debugging, or downstream analysis.

Current input support is centered on YouTube videos.

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

## Quick Start

Run the bundled batch script with the default example cases:

```bash
scripts/run-full-batch.sh
```

To use a custom cases file, output directory, or concurrency level:

```bash
CASES_PATH=examples/full-report-cases.json \
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

For a complete command reference, see [CLI Usage Guide](usage-docs/cli.md).
