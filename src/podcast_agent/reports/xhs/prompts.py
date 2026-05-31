"""Prompts for Xiaohongshu note composition."""

from __future__ import annotations

import json
from typing import Any


DEFAULT_XHS_ANGLE = "提炼这期播客中最适合小红书传播的核心判断，面向对科技、商业、AI 和创业感兴趣的读者。"


def build_xhs_composition_prompt(
    *,
    metadata: dict[str, Any],
    summary: dict[str, Any],
    viewpoints: dict[str, Any],
    angle: str | None = None,
) -> str:
    """Build a JSON-only writing prompt for XHS composition."""
    writing_angle = (angle or DEFAULT_XHS_ANGLE).strip()
    payload = {
        "metadata": _compact_metadata(metadata),
        "summary": summary,
        "viewpoints": _compact_viewpoints(viewpoints),
        "angle": writing_angle,
    }
    return "\n".join(
        [
            "你是一个擅长把长播客改写成小红书图文笔记的科技商业作者。",
            "请基于输入材料生成小红书图文报告的结构化 JSON。",
            "",
            "写作要求：",
            "- 面向小红书科技/商业读者，表达清楚、有判断，不写成营销稿。",
            "- 文章式连续表达，不做 PPT bullet 卡片。",
            "- 优先提炼最有传播价值的判断，避免逐字复述播客。",
            "- 可以适当引用嘉宾/主持人原话，但引用要短。",
            "- post_title 不超过 20 个中文字符。",
            "- tags 输出 5-10 个，标签不带 #。",
            "- sections 建议 3-6 个，每个 section 至少 1 个 paragraph。",
            "- 只输出 JSON，不要输出 Markdown、解释或代码块。",
            "",
            "JSON schema:",
            json.dumps(
                {
                    "post_title": "不超过20字的标题",
                    "post_description": "小红书发布描述",
                    "tags": ["标签1", "标签2"],
                    "cover_intro": "封面页导语",
                    "article_title": "图片内标题",
                    "sections": [
                        {
                            "heading": "核心观点标题",
                            "paragraphs": ["自然段1", "自然段2"],
                            "quotes": ["嘉宾原话"],
                        }
                    ],
                    "closing": "结尾判断，不要写成提问或自问自答",
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "输入材料：",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "title",
        "author",
        "uploader",
        "webpage_url",
        "source_url",
        "duration_seconds",
        "duration",
        "description",
    ]
    return {key: metadata[key] for key in keys if key in metadata and metadata[key]}


def _compact_viewpoints(viewpoints: dict[str, Any]) -> dict[str, Any]:
    return {
        "viewpoint_breakdown": viewpoints.get("viewpoint_breakdown", []),
        "viewpoint_details": viewpoints.get("viewpoint_details", []),
    }
