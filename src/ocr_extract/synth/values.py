"""随机生成虚构的字段值,以及它们在图上的不同写法。

标准答案(canonical)直接由源值构造,不经过 schema 的归一化函数:
否则"归一化(渲染写法) == 标签"的测试就成了自己验证自己。
"""

import datetime as dt
import random
from decimal import Decimal

PREFIXES = ["星河", "云帆", "澜川", "青禾", "远拓", "朗峰", "嘉澍", "北辰", "启明", "沐阳", "恒岳", "锦程"]
INDUSTRIES = ["科技", "贸易", "物流", "建材", "餐饮管理", "信息技术", "医疗器械", "文化传媒", "机械设备", "农业发展"]
CITIES = ["北京", "上海", "杭州", "成都", "武汉", "苏州"]
BANK = "星海银行"  # 虚构

DATE_START = dt.date(2024, 1, 1)
DATE_END = dt.date(2026, 10, 23)


def company(rng: random.Random) -> tuple[str, str]:
    """返回 (标准答案, 图上写法)。标准答案用半角括号,图上随机全角/半角。"""
    city = f"({rng.choice(CITIES)})" if rng.random() < 0.4 else ""
    canonical = f"{rng.choice(PREFIXES)}{rng.choice(INDUSTRIES)}{city}有限公司"
    rendered = canonical.replace("(", "\uff08").replace(")", "\uff09") if rng.random() < 0.5 else canonical
    return canonical, rendered


def amount(rng: random.Random, low: float = 1.0, high: float = 9_999_999.99) -> Decimal:
    # 对数均匀:个位数到百万级的金额出现得一样多,而不是几乎全是百万级
    value = 10 ** rng.uniform(0, 7)
    return Decimal(f"{min(max(value, low), high):.2f}")


def render_amount(value: Decimal, rng: random.Random) -> str:
    # \uffe5 是全角 ¥,中文票据上更常见
    fmt = rng.choice(["¥{:,.2f}", "\uffe5{:,.2f}", "{:,.2f}", "RMB {:,.2f}"])
    return fmt.format(value)


def date(rng: random.Random) -> dt.date:
    return DATE_START + dt.timedelta(days=rng.randint(0, (DATE_END - DATE_START).days))


def render_date(value: dt.date, rng: random.Random) -> str:
    return value.strftime(rng.choice(["%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d"]))


def digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))


def masked_account(rng: random.Random) -> str:
    # 首段避开 62 开头(银联卡号段),中间脱敏,不做成银行卡号的样子
    return f"{rng.randint(1000, 5999)} **** **** {rng.randint(1000, 9999)}"


_DIGITS = "零壹贰叁肆伍陆柒捌玖"


def _group_to_chinese(g: int) -> str:
    """1~9999 → 大写,组内连续的 0 只读一个"零"。"""
    out, pending_zero = "", False
    for unit, d in zip("仟佰拾 ", f"{g:04d}"):
        d = int(d)
        if d == 0:
            pending_zero = bool(out)
            continue
        if pending_zero:
            out += "零"
            pending_zero = False
        out += _DIGITS[d] + unit.strip()
    return out


def _int_to_chinese(n: int) -> str:
    groups = []
    while n:
        n, g = divmod(n, 10000)
        groups.append(g)
    out, skipped = "", False
    for i in reversed(range(len(groups))):
        g = groups[i]
        if g == 0:
            skipped = bool(out)
            continue
        if out and (g < 1000 or skipped):
            out += "零"
        out += _group_to_chinese(g) + ["", "万", "亿"][i]
        skipped = False
    return out


def amount_to_chinese(value: Decimal) -> str:
    """12500.00 → 壹万贰仟伍佰元整。用于回单、发票上的大写金额。"""
    yuan, rem = divmod(int(value * 100), 100)
    jiao, fen = divmod(rem, 10)
    out = _int_to_chinese(yuan) + "元" if yuan else ""
    if jiao:
        out += _DIGITS[jiao] + "角"
    elif yuan and fen:
        out += "零"
    out += _DIGITS[fen] + "分" if fen else "整"
    return out
