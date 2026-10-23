"""PaddleOCR 封装:模型只加载一次,输出按阅读顺序排好的文本行,结果缓存到磁盘。

缓存的另一个作用:方案 A 和 B 读到完全相同的 OCR 文字,两者的差别只来自抽取方法。
"""

import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[3] / "results" / "ocr_cache"


@dataclass
class OcrLine:
    text: str
    score: float
    poly: list[list[float]]  # 4 个角点(左上、右上、右下、左下),PaddleOCR 输出的原始坐标
    box: tuple[float, float, float, float]  # 摆正后的外接矩形 (x0, y0, x1, y1),用来判断同行、同栏

    @property
    def cy(self) -> float:
        return (self.box[1] + self.box[3]) / 2

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]


@dataclass
class OcrResult:
    lines: list[OcrLine]  # 已按阅读顺序排好
    skew_deg: float  # 估计出的整图倾斜角
    latency_s: float  # 首次识别的耗时;读缓存时保留原值,不是读缓存的耗时
    config: dict

    @property
    def text(self) -> str:
        """给 LLM 用的纯文本:同一行的框用空格连接,行之间换行。"""
        rows, last_row = [], None
        for line in self.lines:
            if last_row is not None and _same_row(line, last_row[-1]):
                last_row.append(line)
            else:
                last_row = [line]
                rows.append(last_row)
        return "\n".join(" ".join(l.text for l in row) for row in rows)


def _same_row(a: OcrLine, b: OcrLine) -> bool:
    return abs(a.cy - b.cy) < 0.5 * min(a.height, b.height)


def estimate_skew(polys: list[list[list[float]]]) -> float:
    """用每个框上边的斜率估计倾斜角,取中位数:个别歪掉的框不影响整体。"""
    angles = []
    for (x0, y0), (x1, y1), *_ in polys:
        if x1 - x0 > 20:  # 太短的框斜率不可靠
            angles.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
    return statistics.median(angles) if angles else 0.0


def build_lines(texts: list[str], scores: list[float], polys: list[list[list[float]]]) -> tuple[list[OcrLine], float]:
    skew = estimate_skew(polys)
    cos, sin = math.cos(math.radians(-skew)), math.sin(math.radians(-skew))
    lines = []
    for text, score, poly in zip(texts, scores, polys):
        pts = [(x * cos - y * sin, x * sin + y * cos) for x, y in poly]  # 反向旋转摆正
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        lines.append(OcrLine(text, float(score), [list(map(float, p)) for p in poly], (min(xs), min(ys), max(xs), max(ys))))

    # 阅读顺序:先按摆正后的 y 分行,行内按 x 排
    lines.sort(key=lambda l: l.cy)
    ordered, row = [], []
    for line in lines:
        if row and not _same_row(line, row[0]):
            ordered += sorted(row, key=lambda l: l.box[0])
            row = []
        row.append(line)
    ordered += sorted(row, key=lambda l: l.box[0])
    return ordered, skew


class PaddleEngine:
    def __init__(self, use_doc_unwarping: bool = True) -> None:
        from paddleocr import PaddleOCR  # 延迟导入:只读缓存时不用加载 Paddle

        self.config = {"engine": "paddleocr", "enable_mkldnn": False, "use_doc_unwarping": use_doc_unwarping}
        # 关 oneDNN:见 docs/decisions.md D7
        self._ocr = PaddleOCR(enable_mkldnn=False, use_doc_unwarping=use_doc_unwarping)

    def run(self, image_path: Path) -> OcrResult:
        t = time.perf_counter()
        r = self._ocr.predict(str(image_path))[0]
        latency = time.perf_counter() - t
        polys = [p.tolist() for p in r["rec_polys"]]
        lines, skew = build_lines(list(r["rec_texts"]), list(r["rec_scores"]), polys)
        return OcrResult(lines, skew, latency, self.config)


def _cache_path(image_path: Path, use_doc_unwarping: bool) -> Path:
    tag = "uvdoc_on" if use_doc_unwarping else "uvdoc_off"
    return CACHE_DIR / tag / image_path.parent.parent.name / f"{image_path.stem}.json"


_engines: dict[bool, PaddleEngine] = {}


def ocr(image_path: Path, use_doc_unwarping: bool = True) -> OcrResult:
    """带缓存的 OCR。缓存里存了图片的 sha256,图片变了就重新识别。"""
    path = _cache_path(image_path, use_doc_unwarping)
    sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["sha256"] == sha:
            lines = [OcrLine(l["text"], l["score"], l["poly"], tuple(l["box"])) for l in data["lines"]]
            return OcrResult(lines, data["skew_deg"], data["latency_s"], data["config"])

    if use_doc_unwarping not in _engines:
        _engines[use_doc_unwarping] = PaddleEngine(use_doc_unwarping)
    result = _engines[use_doc_unwarping].run(image_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sha256": sha, **asdict(result)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return result
