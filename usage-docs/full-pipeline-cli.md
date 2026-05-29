# 全流程 CLI 使用

用 `podcast-agent full` 可以从 YouTube 链接直接生成 Markdown 报告。

## 命令

```bash
.venv/bin/podcast-agent full \
  --url "https://www.youtube.com/watch?v=V9eI-t3TApE&t" \
  --question "这个视频讲了什么？" \
  --output-dir output/V9eI-t3TApE-demo
```

## 参数

```text
--url         YouTube 视频链接
--question    想问这个视频的问题
--output-dir  本次运行的输出目录
```

## 输出

最终报告会生成在：

```text
output/V9eI-t3TApE-demo/reports/report.md
```

查看报告：

```bash
sed -n '1,240p' output/V9eI-t3TApE-demo/reports/report.md
```

## 换成自己的视频

```bash
.venv/bin/podcast-agent full \
  --url "https://www.youtube.com/watch?v=<video-id>" \
  --question "你想问的问题" \
  --output-dir output/my-report
```
