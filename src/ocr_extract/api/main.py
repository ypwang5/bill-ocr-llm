"""FastAPI 服务:上传票据图片,选择方案 A/B/C/D,返回字段、耗时、所用方案、是否回退。

启动:uv run uvicorn ocr_extract.api.main:app --port 8000
"""

import contextlib
import hashlib
import io
import json
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIError
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from ocr_extract.ocr import paddle_engine

MAX_BYTES = 5 * 1024 * 1024  # 票据照片一般 <2MB;再大多半是传错了文件,也防止被大文件拖垮
ALLOWED_TYPES = {"image/png": ".png", "image/jpeg": ".jpg"}
STATIC = Path(__file__).parent / "static"
DEMO = STATIC / "demo"  # scripts/build_demo_samples.py 生成:18 张样本的缩略图 + 测试集上的真实结果
SAMPLE_IMAGES = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "images"
Method = Literal["A", "B", "C", "D"]

# 上传的图片和它们的 OCR 缓存放临时目录,不混进 results/ 里的实验数据。
# 目录结构 uploads/images/<sha>.png 让缓存落到 <临时目录>/ocr_cache/uvdoc_on/uploads/;同一张图重复上传直接命中缓存
WORK = Path(tempfile.mkdtemp(prefix="ocr_api_"))
UPLOADS = WORK / "uploads" / "images"
paddle_engine.CACHE_DIR = WORK / "ocr_cache"


class ExtractResponse(BaseModel):
    method: Method
    fields: dict[str, str | None]
    field_errors: dict[str, str]
    fallback: bool  # 只对 D 有意义:是否回退到了多模态
    route_reasons: list[str]
    latency_s: float
    ocr_latency_s: float
    tokens_in: int
    tokens_out: int


def warmup() -> None:
    """启动时把 OCR 模型加载好:加载要好几秒,放在请求里每次都等不起(单独成函数,测试里替换掉)。"""
    paddle_engine.get_engine(True)


def build_extractors() -> dict:
    from ocr_extract.extractors import rule_based
    from ocr_extract.extractors.hybrid import HybridExtractor
    from ocr_extract.extractors.ocr_llm import OcrLlmExtractor
    from ocr_extract.extractors.vlm_direct import VlmExtractor

    b, c = OcrLlmExtractor(), VlmExtractor()
    return {"A": rule_based.extract, "B": b.extract, "C": c.extract, "D": HybridExtractor(b=b.extract, c=c.extract).extract}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    app.state.sample_ids = {s["id"] for s in json.loads((DEMO / "samples.json").read_text(encoding="utf-8"))["samples"]}
    warmup()
    app.state.extractors = build_extractors()
    yield


app = FastAPI(title="票据字段抽取", lifespan=lifespan)
app.mount("/demo", StaticFiles(directory=DEMO), name="demo")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/samples/{sample_id}.png")
def sample_image(sample_id: str) -> FileResponse:
    # 只认白名单里的 id,不拿用户输入去拼任意路径
    if sample_id not in app.state.sample_ids:
        raise HTTPException(404, "没有这张样本")
    return FileResponse(SAMPLE_IMAGES / f"{sample_id}.png")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# 用普通 def 而不是 async def:OCR 和 LLM 调用都是阻塞的,FastAPI 会把它放进线程池,不卡住其他请求
@app.post("/extract", response_model=ExtractResponse)
def extract(file: UploadFile | None = File(None), sample_id: str | None = Form(None),
            method: Method = Form("D")) -> ExtractResponse:
    # 二选一:上传自己的图,或者对内置样本"实时重跑"(演示页上没有图的人也能看到真实调用)
    if (file is None) == (sample_id is None):
        raise HTTPException(400, "file 和 sample_id 必须且只能给一个")
    if sample_id is not None:
        if sample_id not in app.state.sample_ids:
            raise HTTPException(404, "没有这张样本")
        path = SAMPLE_IMAGES / f"{sample_id}.png"
    else:
        path = save_upload(file)
    try:
        r = app.state.extractors[method](path)
    except APIError as e:
        raise HTTPException(502, f"大模型服务调用失败:{type(e).__name__}")  # 不回传原始错误,里面可能带请求细节
    return ExtractResponse(method=method, fields=r.fields, field_errors=r.field_errors, fallback=r.fallback,
                           route_reasons=r.route_reasons, latency_s=r.latency_s, ocr_latency_s=r.ocr_latency_s,
                           tokens_in=r.tokens_in, tokens_out=r.tokens_out)


def save_upload(file: UploadFile) -> Path:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"只支持 PNG/JPEG,收到 {file.content_type}")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"文件超过 {MAX_BYTES // 1024 // 1024}MB")
    try:
        Image.open(io.BytesIO(data)).verify()  # content_type 是客户端说的,不可信,要真的解一次
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "文件不是有效的图片")
    path = UPLOADS / f"{hashlib.sha256(data).hexdigest()[:16]}{ALLOWED_TYPES[file.content_type]}"
    path.write_bytes(data)
    return path
