"""从测试集的一次正式实验里,抽出演示页用的 18 张样本(3 类票据 x 6 种形态)及其 A/B/C/D 真实结果。

挑选规则事先定死:每个"类型x形态"组合取编号 _00 的那张,不看结果好坏,失败案例照样展示。
用法:uv run python scripts/build_demo_samples.py
"""

import json
from pathlib import Path

from PIL import Image

from ocr_extract.llm.client import cost

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results" / "20261024_004217_benchmark_test"
IMAGES = ROOT / "data" / "synthetic" / "images"
OUT = ROOT / "src" / "ocr_extract" / "api" / "static" / "demo"
TEMPLATES = ["receipt", "invoice", "statement"]
DIFFICULTIES = ["clean", "blur", "rotate", "lowres", "perspective", "occlusion"]
METHODS = ["A", "B", "C", "D"]
KEEP = ["fields", "correct", "field_errors", "fallback", "route_reasons", "latency_s", "ocr_latency_s",
        "tokens_in", "tokens_out"]
DEFAULTS = {"fallback": False, "route_reasons": []}  # 只有 D 的结果里记了路由信息


def main() -> None:
    llm = json.loads((RUN / "config.json").read_text(encoding="utf-8"))["llm"]
    metrics = json.loads((RUN / "metrics.json").read_text(encoding="utf-8"))
    ids = [f"{t}_{d}_00" for t in TEMPLATES for d in DIFFICULTIES]
    results: dict[str, dict] = {i: {} for i in ids}
    for m in METHODS:
        for line in (RUN / f"{m}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["id"] in results:
                # A 不调大模型;B/C/D 的 token 都按同一单价估算(本次实验文本和视觉是同一个模型)
                results[r["id"]][m] = {k: r.get(k, DEFAULTS.get(k)) for k in KEEP} | {
                    "cost_yuan": round(cost(r["tokens_in"], r["tokens_out"], llm["price_text_in"], llm["price_text_out"]), 5)}

    (OUT / "thumbs").mkdir(parents=True, exist_ok=True)
    samples = []
    for i in ids:
        label = json.loads((ROOT / "data" / "synthetic" / "labels" / f"{i}.json").read_text(encoding="utf-8"))
        assert set(results[i]) == set(METHODS), f"{i} 缺少方案结果"
        im = Image.open(IMAGES / f"{i}.png").convert("RGB")
        im.thumbnail((320, 320))  # 缩略图只用来挑图,原图走接口按需加载
        im.save(OUT / "thumbs" / f"{i}.jpg", quality=80)
        samples.append({"id": i, "template": label["template"], "difficulty": label["difficulty"],
                        "gold": label["fields"], "results": results[i]})

    summary = {m: {"doc_acc": metrics[m]["all"]["doc_acc"], "latency_p50": metrics[m]["all"]["latency_p50"],
                   "cost_per_doc": metrics[m]["all"]["cost_per_doc"]} for m in METHODS}
    data = {"run": RUN.name, "n_test": metrics["A"]["all"]["n"], "summary": summary, "samples": samples}
    (OUT / "samples.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写入 {len(samples)} 张样本 -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
