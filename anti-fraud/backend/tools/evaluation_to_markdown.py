"""Convert an exported evaluation JSON into a reviewable Markdown report."""
import argparse
import json
from pathlib import Path

def pct(value): return f"{value * 100:.1f}%"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", default="evaluation-report.md")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    metrics = data["metrics"]
    lines = [
        "# 安知真实模型评估报告", "",
        f"- 评测编号：{data.get('id', '未记录')}",
        f"- 评测时间：{data.get('created', '未记录')}",
        f"- 模式：{data['mode']}", f"- 模型链路：{data['model']}",
        f"- 样本数：{metrics['total']}（自建固定测试集）", "", "## 核心指标", "",
        "| 指标 | 结果 |", "| --- | ---: |",
        f"| Accuracy | {pct(metrics['accuracy'])} |", f"| Precision | {pct(metrics['precision'])} |",
        f"| Recall | {pct(metrics['recall'])} |", f"| F1-score | {pct(metrics['f1'])} |",
        f"| 误报率 | {pct(metrics['false_positive_rate'])} |", f"| 类型准确率 | {pct(metrics['type_accuracy'])} |",
        f"| 平均时延 | {metrics['average_latency_ms']} ms |", "",
        "## 分模态结果", "",
        "| 模态 | 样本 | 完成 | Accuracy | F1 | 类型准确率 | 平均时延 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in data.get("modality_metrics", {}).items():
        lines.append(
            f"| {name} | {item['total']} | {item['completed']} | {pct(item['accuracy'])} | "
            f"{pct(item['f1'])} | {pct(item['type_accuracy'])} | {item['average_latency_ms']} ms |"
        )
    lines += [
        "", "## 逐条结果", "",
        "| ID | 模态 | 真实类型 | 预测类型 | 正确 | 时延(ms) |", "| --- | --- | --- | --- | --- | ---: |"
    ]
    for item in data["items"]:
        lines.append(f"| {item['id']} | {item['modality']} | {item['type']} | {item['predicted_type']} | {'是' if item['correct'] else '否'} | {item['latency_ms']} |")
    lines += [
        "", "## 结果说明与限制", "",
        "- 本报告只反映当前 20 条固定自建样本的运行结果，不能直接推断真实未知数据的泛化准确率。",
        "- 二分类 Accuracy 和 F1 均为 100%，但诈骗类型准确率为 70%，说明细分类仍需优化。",
        "- 平均时延约 35.8 秒，尚未达到赛题对文本/图片小于 10 秒的要求。",
        "- 音频结果来自语音转写后的诈骗话术分析，不等同于 AI 合成语音、声纹或深伪鉴定。",
        "- 规则基线使用测试集关键词，只用于校验评测管线，不能作为模型效果成绩。",
    ]
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
