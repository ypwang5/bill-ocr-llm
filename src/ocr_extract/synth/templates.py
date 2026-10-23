"""三种票据模板:转账回单、发票、对账单。

每个模板返回 Rendered:图片、5 个字段的标准答案和图上写法、字段值在图上的位置
(遮挡档要把印章压在上面),以及正常盖章的空白位置。
银行名虚构,账号脱敏,右下角/左下角标"合成样本",不仿造任何真实票据。
"""

import datetime as dt
import random
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from . import values as V

FONTS = {
    "simhei": "C:/Windows/Fonts/simhei.ttf",
    "simsun": "C:/Windows/Fonts/simsun.ttc",
    "msyh": "C:/Windows/Fonts/msyh.ttc",
}
COLON = "\uff1a"
LP, RP = "\uff08", "\uff09"
FOOTER = "合成样本 仅供测试"

Box = tuple[int, int, int, int]


@dataclass
class Rendered:
    image: Image.Image
    fields: dict[str, str | None]  # 标准答案,即 ReceiptFields 序列化后的格式
    rendered: dict[str, str | None]  # 图上实际画的写法
    boxes: dict[str, Box]  # 字段值在图上的位置
    blank: tuple[int, int]  # 非遮挡档盖章的位置
    stamp_text: tuple[str, str]
    texts: list[str]  # 画过的所有文字,测试用来检查字体缺字


@lru_cache
def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _render_glyph(path: str, ch: str) -> bytes:
    im = Image.new("L", (60, 60), 0)
    ImageDraw.Draw(im).text((10, 10), ch, font=font(path, 30), fill=255)
    return im.tobytes()


@lru_cache
def has_glyph(path: str, ch: str) -> bool:
    """字体缺字时会画出方框(.notdef)。用私有区码位 U+E000 得到方框的样子来比对。"""
    return ch.isspace() or _render_glyph(path, ch) != _render_glyph(path, "")


# 黑体没有半角 ¥(U+00A5),画出来是方框;换成全角 ¥,两者归一化结果相同
_FALLBACK = {"¥": "\uffe5"}


class Canvas:
    def __init__(self, w: int, h: int, font_path: str) -> None:
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.font_path = font_path
        self.texts: list[str] = []

    def fix(self, s: str) -> str:
        """把字体里没有的字符换成备用字符。标签里的 rendered 也要先过一遍,保证记的就是图上画的。"""
        return "".join(_FALLBACK.get(ch, ch) if not has_glyph(self.font_path, ch) else ch for ch in s)

    def text(self, xy: tuple[int, int], s: str, size: int = 24, fill: str = "black", anchor: str = "la") -> Box:
        s = self.fix(s)
        self.texts.append(s)
        f = font(self.font_path, size)
        self.draw.text(xy, s, font=f, fill=fill, anchor=anchor)
        return self.draw.textbbox(xy, s, font=f, anchor=anchor)

    def kv(self, x: int, y: int, label: str, value: str, size: int = 24) -> Box:
        """画"标签:值",返回值的位置。"""
        x1 = self.text((x, y), label + COLON, size)[2]
        return self.text((x1 + 4, y), value, size)

    def line(self, xy: tuple[int, int, int, int]) -> None:
        self.draw.line(xy, fill="black", width=2)

    def rect(self, xy: tuple[int, int, int, int]) -> None:
        self.draw.rectangle(xy, outline="black", width=2)

    def footer(self) -> None:
        self.text((20, self.image.height - 12), FOOTER, 16, fill="gray", anchor="lb")


def _two_companies(rng: random.Random) -> tuple[tuple[str, str], tuple[str, str]]:
    a = V.company(rng)
    b = V.company(rng)
    while b[0] == a[0]:
        b = V.company(rng)
    return a, b


def _split(total: Decimal, n: int, rng: random.Random) -> list[Decimal]:
    weights = [rng.uniform(1, 3) for _ in range(n)]
    parts = [(total * Decimal(w / sum(weights))).quantize(Decimal("0.01")) for w in weights[:-1]]
    return parts + [total - sum(parts)]


def receipt(rng: random.Random, font_path: str) -> Rendered:
    W, H = 1000, 620
    c = Canvas(W, H, font_path)
    (payer, payer_r), (payee, payee_r) = _two_companies(rng)
    amt, d = V.amount(rng), V.date(rng)
    serial = "HX" + d.strftime("%Y%m%d") + V.digits(rng, 6)
    amt_r, d_r = c.fix(V.render_amount(amt, rng)), V.render_date(d, rng)

    boxes = {}
    c.text((W // 2, 36), f"{V.BANK} 电子回单", 40, anchor="mt")
    boxes["serial_no"] = c.kv(40, 105, "流水号", serial, 22)
    boxes["date"] = c.kv(560, 105, "交易日期", d_r, 22)
    c.rect((30, 150, W - 30, 490))
    c.line((W // 2, 150, W // 2, 330))
    c.line((30, 330, W - 30, 330))
    for x, side, name, key in ((50, "付款方", payer_r, "payer_name"), (W // 2 + 20, "收款方", payee_r, "payee_name")):
        c.text((x, 165), side, 24)
        boxes[key] = c.kv(x, 210, "户名", name, 22)
        c.kv(x, 250, "账号", V.masked_account(rng), 22)
        c.kv(x, 290, "开户行", f"{V.BANK}{rng.choice(V.CITIES)}分行", 22)
    boxes["amount"] = c.kv(50, 350, f"金额{LP}小写{RP}", amt_r, 26)
    c.kv(50, 395, f"金额{LP}大写{RP}", V.amount_to_chinese(amt), 26)
    c.kv(50, 440, "用途", rng.choice(["货款", "服务费", "往来款", "工程款"]), 22)
    c.kv(40, 520, "交易机构", f"{V.BANK}{rng.choice(V.CITIES)}营业部", 20)
    c.footer()

    return Rendered(
        image=c.image,
        fields={"payer_name": payer, "payee_name": payee, "amount": f"{amt:.2f}", "date": d.isoformat(), "serial_no": serial},
        rendered={"payer_name": payer_r, "payee_name": payee_r, "amount": amt_r, "date": d_r, "serial_no": serial},
        boxes=boxes,
        blank=(W - 180, 545),
        texts=c.texts,
        stamp_text=(V.BANK, "电子回单专用章"),
    )


def invoice(rng: random.Random, font_path: str) -> Rendered:
    W, H = 1100, 720
    c = Canvas(W, H, font_path)
    (buyer, buyer_r), (seller, seller_r) = _two_companies(rng)
    total, d = V.amount(rng), V.date(rng)
    rate = rng.choice([Decimal("0.06"), Decimal("0.13")])
    net = (total / (1 + rate)).quantize(Decimal("0.01"))
    tax = total - net
    number = V.digits(rng, 20)
    amt_r, d_r = c.fix(V.render_amount(total, rng)), V.render_date(d, rng)

    boxes = {}
    c.text((W // 2, 30), "发    票", 44, anchor="mt")
    c.text((W // 2, 85), f"{LP}合成样本{RP}", 20, fill="gray", anchor="mt")
    boxes["serial_no"] = c.kv(700, 40, "发票号码", number, 20)
    boxes["date"] = c.kv(700, 75, "开票日期", d_r, 20)
    c.rect((30, 130, W - 30, 640))
    c.line((W // 2, 130, W // 2, 250))
    c.line((30, 250, W - 30, 250))
    for x, side, name, key in ((50, "购买方", buyer_r, "payer_name"), (W // 2 + 20, "销售方", seller_r, "payee_name")):
        c.text((x, 145), side, 24)
        boxes[key] = c.kv(x, 185, "名称", name, 22)
        c.kv(x, 222, "开户行及账号", f"{V.BANK} {V.masked_account(rng)}", 18)

    # 明细表:金额(不含税)、税额都是干扰项,只有价税合计是答案
    cols = [("项目名称", 50), ("数量", 330), ("单价", 430), ("金额", 620), ("税率", 790), ("税额", 900)]
    for name, x in cols:
        c.text((x, 265), name, 20)
    n = 1 if total < 100 else rng.randint(1, 3)
    for i, part in enumerate(_split(net, n, rng)):
        qty = rng.randint(1, 10)
        y = 305 + i * 40
        c.text((50, y), rng.choice(["技术服务费", "办公用品", "咨询服务", "设备维修", "软件许可"]), 20)
        c.text((330, y), str(qty), 20)
        c.text((430, y), f"{(part / qty).quantize(Decimal('0.0001'))}", 20)
        c.text((620, y), f"{part:.2f}", 20)
        c.text((790, y), f"{int(rate * 100)}%", 20)
        c.text((900, y), f"{(part * rate).quantize(Decimal('0.01')):.2f}", 20)
    c.line((30, 425, W - 30, 425))
    c.text((50, 440), "合    计", 22)
    c.text((620, 440), f"\u00a5{net:,.2f}", 22)
    c.text((900, 440), f"\u00a5{tax:,.2f}", 22)
    c.line((30, 480, W - 30, 480))
    c.kv(50, 505, f"价税合计{LP}大写{RP}", V.amount_to_chinese(total), 24)
    boxes["amount"] = c.kv(700, 505, f"{LP}小写{RP}", amt_r, 24)
    c.kv(50, 665, "开票人", rng.choice(["王某", "李某", "赵某"]), 20)
    c.footer()

    # 发票章上印的是销售方简称:和 1.1 讲的一样,印章文字本身也是干扰项
    return Rendered(
        image=c.image,
        fields={"payer_name": buyer, "payee_name": seller, "amount": f"{total:.2f}", "date": d.isoformat(), "serial_no": number},
        rendered={"payer_name": buyer_r, "payee_name": seller_r, "amount": amt_r, "date": d_r, "serial_no": number},
        boxes=boxes,
        blank=(W - 200, 580),
        texts=c.texts,
        stamp_text=(seller_r[:4], "发票专用章"),
    )


def statement(rng: random.Random, font_path: str) -> Rendered:
    W, H = 1000, 860
    c = Canvas(W, H, font_path)
    holder, holder_r = V.company(rng)
    end_balance, end = V.amount(rng), V.date(rng)
    start = end.replace(day=1)
    serial = "DZ" + end.strftime("%Y%m") + V.digits(rng, 6)
    amt_r, d_r = c.fix(V.render_amount(end_balance, rng)), V.render_date(end, rng)

    # 先定期末余额(答案),再倒推期初余额,保证账能对平且期初为正
    while True:
        txs = []
        for _ in range(rng.randint(4, 6)):
            kind = rng.choice(["转账收入", "转账支出", "转账支出", "代发工资", "手续费", "利息"])
            ratio = rng.uniform(0.001, 0.01) if kind in ("手续费", "利息") else rng.uniform(0.02, 0.4)
            mag = max((end_balance * Decimal(ratio)).quantize(Decimal("0.01")), Decimal("0.01"))
            sign = 1 if kind in ("转账收入", "利息") else -1
            party = "-" if kind in ("手续费", "利息") else V.company(rng)[1]
            txs.append((kind, party, sign * mag))
        start_balance = end_balance - sum(t[2] for t in txs)
        if start_balance > 0:
            break
    days = sorted(start + dt.timedelta(days=rng.randint(0, (end - start).days)) for _ in txs)

    boxes = {}
    c.text((W // 2, 36), f"{V.BANK} 账户对账单", 38, anchor="mt")
    boxes["serial_no"] = c.kv(40, 100, "对账单编号", serial, 22)
    c.kv(560, 100, "对账期间", f"{start:%Y-%m-%d} 至 {end:%Y-%m-%d}", 20)
    boxes["payer_name"] = c.kv(40, 140, "户名", holder_r, 22)
    c.kv(560, 140, "账号", V.masked_account(rng), 22)
    boxes["date"] = c.kv(40, 180, "对账截止日", d_r, 22)

    c.line((30, 225, W - 30, 225))
    for name, x, anchor in (("日期", 40, "la"), ("摘要", 170, "la"), ("对方户名", 310, "la"), ("金额", 790, "ra"), ("余额", 970, "ra")):
        c.text((x, 235), name, 20, anchor=anchor)
    c.line((30, 265, W - 30, 265))
    bal = start_balance
    for i, ((kind, party, amt), day) in enumerate(zip(txs, days)):
        bal += amt
        y = 280 + i * 42
        c.text((40, y), f"{day:%m-%d}", 20)
        c.text((170, y), kind, 20)
        c.text((310, y), party, 20)
        c.text((790, y), f"{amt:+,.2f}", 20, anchor="ra")
        c.text((970, y), f"{bal:,.2f}", 20, anchor="ra")
    c.line((30, 540, W - 30, 540))
    c.kv(40, 565, "期初余额", f"\u00a5{start_balance:,.2f}", 24)
    boxes["amount"] = c.kv(40, 610, "期末余额", amt_r, 26)
    c.footer()

    # 对账单没有"收款人":payee_name 固定为 null,专门测模型会不会从明细里编一个出来
    return Rendered(
        image=c.image,
        fields={"payer_name": holder, "payee_name": None, "amount": f"{end_balance:.2f}", "date": end.isoformat(), "serial_no": serial},
        rendered={"payer_name": holder_r, "payee_name": None, "amount": amt_r, "date": d_r, "serial_no": serial},
        boxes=boxes,
        blank=(W - 200, 650),
        texts=c.texts,
        stamp_text=(V.BANK, "业务专用章"),
    )
