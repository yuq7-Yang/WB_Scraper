from __future__ import annotations

import os


def parse_env_file(path: str = ".env") -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.lstrip("\ufeff").strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            values[key] = value
    return values


def load_env_file(path: str = ".env") -> None:
    for key, value in parse_env_file(path).items():
        os.environ.setdefault(key, value)


def _split_cookies(raw: str) -> list[str]:
    if not raw.strip():
        return []
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for chunk in normalized.split("||"):
        parts.extend(chunk.split("\n"))
    return [part.strip() for part in parts if part.strip()]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


load_env_file()

DB_PATH = os.getenv("WEIBO_DB_PATH", "weibo.db")
SCRAPFLY_KEY = os.getenv("SCRAPFLY_KEY", "").strip()
WEIBO_COOKIES = os.getenv("WEIBO_COOKIES", "")
COOKIES = _split_cookies(WEIBO_COOKIES)

KEYWORDS = [
    "美睫店",
    "美甲店",
    "美甲",
    "美睫",
    "美发",
    "美容",
    "护肤",
    "彩妆",
    "美业",
    "美妆",
    "指甲",
    "睫毛",
    "发型",
    "面膜",
    "美体",
    "纹眉",
    "纹绣",
    "脱毛",
    "美白",
    "祛斑",
    "spa",
    "美容院",
    "沙龙",
    "耗材",
    "胶水",
    "培训",
    "穿戴甲",
    "可穿戴甲",
    "甲片",
    "饰品",
    "工具设备",
    "甲油胶",
    "果冻胶",
    "果冻贴",
    "光疗甲",
    "延长甲",
    "半永久",
    "皮肤管理",
    "美容仪器",
    "开店",
    "加盟",
    "进货",
    "拿货",
    "采购",
    "批发",
    "供应商",
    "原材料",
]

EAST_CHINA = ["上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"]

BEAUTY_TERMS = [
    "美甲",
    "美睫",
    "美发",
    "美容",
    "护肤",
    "彩妆",
    "美业",
    "美妆",
    "指甲",
    "睫毛",
    "发型",
    "面膜",
    "美体",
    "纹眉",
    "纹绣",
    "脱毛",
    "美白",
    "祛斑",
    "spa",
    "美容院",
    "沙龙",
    "耗材",
    "胶水",
    "培训",
    "穿戴甲",
    "可穿戴甲",
    "甲片",
    "饰品",
    "工具设备",
    "甲油胶",
    "果冻胶",
    "果冻贴",
    "光疗甲",
    "延长甲",
    "半永久",
    "皮肤管理",
    "美容仪器",
    "开店",
    "加盟",
    "进货",
    "拿货",
    "采购",
    "批发",
    "供应商",
    "原材料",
]

INTENT_KEYWORDS = [
    "想买",
    "在哪买",
    "哪里买",
    "怎么买",
    "多少钱",
    "价格",
    "费用",
    "收费",
    "哪家好",
    "推荐",
    "求推荐",
    "好用吗",
    "值得买",
    "性价比",
    "想做",
    "想去",
    "想试",
    "哪里有",
    "哪家",
    "附近有",
    "怎么预约",
    "怎么联系",
    "联系方式",
    "微信",
    "加我",
    "私聊",
    "想学",
    "怎么学",
    "学费",
    "培训",
    "哪里学",
    "教程",
    "自学",
    "进货",
    "批发",
    "拿货",
    "代理",
    "加盟",
    "开店",
    "货源",
    "供货",
    "什么牌子",
    "哪个品牌",
    "用什么",
    "怎么用",
    "好不好",
    "种草",
    "想要",
    "求链接",
    "链接",
    "下单",
    "想贴",
    "求同款",
    "蹲",
    "在哪里买",
    "买了",
    "想入",
    "求店铺",
    "果冻胶",
    "果冻贴",
    "卸甲",
]

B2B_INTENT_TERMS = [
    "开店",
    "加盟",
    "进货",
    "拿货",
    "批发",
    "供应链",
    "供货",
    "培训",
    "学校",
    "代理",
    "选品",
    "品牌",
    "项目",
]

CONSUMER_INTENT_TERMS = [
    "推荐",
    "链接",
    "同款",
    "教程",
    "封层",
    "胶水",
    "甲油胶",
    "果冻胶",
    "果冻贴",
    "款式",
    "想做",
    "想买",
    "在哪里买",
    "怎么买",
    "有没有",
    "好不好用",
    "种草",
]

UNRELATED_COMMENT_TERMS = [
    "奶茶",
    "袜子",
    "分趾袜",
    "拖鞋",
    "鞋子",
    "衣服",
    "裤子",
    "包包",
    "投诉",
    "皮肤用物",
    "头皮精华",
]

SPAM_COMMENT_TERMS = [
    "点赞关注",
    "关注我",
    "关注一下",
    "互粉",
    "互关",
    "关注回关",
    "转发抽",
    "转发微博",
    "抽奖",
    "中奖",
    "免费送",
    "免费领取",
    "福利链接",
    "扫码",
    "扫我",
    "加V",
    "加微信",
    "加v信",
    "加vx",
    "戳我头像",
    "点我头像",
    "主页有",
    "主页置顶",
    "私我发你",
    "广告位",
    "打榜",
    "应援",
    "代打",
    "推广",
    "外推",
    "刷赞",
    "刷粉",
    "接单",
    "vx同号",
    "v同号",
]

AI_LIKE_PATTERNS = [
    "作为一名",
    "作为一个",
    "作为专业",
    "作为一位",
    "综上所述",
    "总的来说，",
    "首先，",
    "其次，",
    "再者，",
    "综合考虑",
    "在当今",
    "随着社会的发展",
    "值得注意的是",
    "希望对你有帮助",
    "希望对您有帮助",
    "以上内容仅供参考",
    "仅供参考",
    "从专业角度",
    "建议您在选择",
    "我们致力于",
    "我们专注于",
    "我们秉承",
    "为您提供专业",
]

REPLY_TEMPLATES = [
    "您好！我们专注美甲美睫耗材批发，品质有保障，欢迎私聊了解～",
    "看到您对美甲感兴趣，我们有专业培训课程，欢迎咨询！",
    "您好，我们提供美甲美睫全套耗材，支持小批量，欢迎了解～",
]

SCRAPE_PAGE_DELAY = _env_float("SCRAPE_PAGE_DELAY", 0.0)
SCRAPE_POST_DELAY = _env_float("SCRAPE_POST_DELAY", 0.2)
SCRAPE_KEYWORD_DELAY = _env_float("SCRAPE_KEYWORD_DELAY", 0.5)
REPLY_DELAY = _env_float("REPLY_DELAY", 3.0)
REPLIES_PER_ACCOUNT = max(1, _env_int("REPLIES_PER_ACCOUNT", 3))
MAX_REPLIES_PER_RUN = _env_int("MAX_REPLIES_PER_RUN", 20)
MAX_COMMENTS_PER_KEYWORD = _env_int("MAX_COMMENTS_PER_KEYWORD", 2)
DEFAULT_MAX_PER_KEYWORD = _env_int("DEFAULT_MAX_PER_KEYWORD", MAX_COMMENTS_PER_KEYWORD)
DEFAULT_MAX_TOTAL = _env_int("DEFAULT_MAX_TOTAL", 20)
DRY_RUN_REPLIES = _env_bool("DRY_RUN_REPLIES", True)
ENABLE_REAL_REPLIES = _env_bool("ENABLE_REAL_REPLIES", False)
LOCAL_LLM_ENABLED = _env_bool("LOCAL_LLM_ENABLED", False)
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434").strip() or "http://127.0.0.1:11434"
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5").strip() or "qwen2.5"
LOCAL_LLM_TIMEOUT = _env_float("LOCAL_LLM_TIMEOUT", 20.0)
MIN_B2B_INTENT_SCORE = _env_int("MIN_B2B_INTENT_SCORE", 3)
MIN_CONSUMER_INTENT_SCORE = _env_int("MIN_CONSUMER_INTENT_SCORE", 3)
LOCAL_LLM_TICKET_CTA = (
    os.getenv("LOCAL_LLM_TICKET_CTA", "感兴趣的话私信我，我发你门票链接。").strip()
    or "感兴趣的话私信我，我发你门票链接。"
)


KEYWORD_REPLY_MAP = [
    {
        "id": "nail_franchise",
        "keywords": ["美甲店加盟", "美甲加盟", "美甲品牌加盟"],
        "template": (
            "CIBE今年美甲连锁品牌到场不少，加盟政策和选址支持可以现场直接谈，"
            "比自己找渠道效率高很多。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "nail_learn",
        "keywords": ["美甲培训", "学美甲", "美甲技术", "美甲课程", "美甲学习"],
        "template": (
            "CIBE美甲板块今年有不少实力派培训机构和大咖老师到场，"
            "现场还设有技术教学公开课可以免费参加。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "lash_learn",
        "keywords": ["美睫培训", "学美睫", "美睫技术", "美睫课程", "美睫学习"],
        "template": (
            "CIBE美睫区有头部品牌的技术演示和培训招生，"
            "手法、材料可以现场看到实物。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "tattoo_learn",
        "keywords": ["纹绣培训", "学纹绣", "纹眉培训", "纹绣技术", "纹绣课程"],
        "template": (
            "CIBE纹绣板块今年规模不小，纹眉、纹眼线、唇妆都有专项培训机构，"
            "现场谈比网上找省事很多。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "semi_learn",
        "keywords": ["半永久培训", "学半永久", "半永久技术", "半永久课程"],
        "template": (
            "CIBE有专门的半永久板块，品牌方和培训机构都在，"
            "色料、工具和技术可以一次摸清。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "skincare_learn",
        "keywords": ["美容培训", "皮肤管理培训", "学美容", "护肤培训", "美容技术"],
        "template": (
            "CIBE皮肤管理和美容板块今年引进了不少新项目，"
            "适合想拓项或转型的从业者去看。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "pressnail",
        "keywords": ["穿戴甲", "可穿戴甲", "穿戴式美甲"],
        "template": (
            "CIBE今年穿戴甲品牌挺多，款式、材质、定制方案都能现场看到，"
            "做零售或工作室选品的话值得去转转。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "supply",
        "keywords": ["进货", "拿货", "采购", "批发", "供应商", "原材料"],
        "template": (
            "CIBE聚集了几百家美业供应商，现场对接比找中间商直接，"
            "价格也更好谈。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "open_shop",
        "keywords": ["开店", "加盟", "创业", "开工作室", "开美甲店", "开美睫店"],
        "template": (
            "CIBE有专门的品牌加盟区，适合在考察阶段的人，"
            "可以一次性见到很多品牌方。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "nail",
        "keywords": [
            "美甲",
            "甲油胶",
            "光疗甲",
            "延长甲",
            "美甲产品",
            "饰品",
            "甲片",
            "工具设备",
        ],
        "template": (
            "CIBE美甲区今年品牌比较全，甲油胶、甲片、饰品、工具设备各类产品都有，"
            "新品基本都在现场。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "lash",
        "keywords": ["美睫", "嫁接睫毛", "睫毛嫁接", "睫毛材料"],
        "template": (
            "CIBE美睫区有主流品牌的新款嫁接材料和工具，"
            "最新款式设计也都在现场，可以直接试用对比。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "tattoo",
        "keywords": ["纹绣", "半永久", "纹眉", "飘眉", "雾眉", "纹眼线", "纹唇"],
        "template": (
            "CIBE纹绣板块今年色料和器械品牌都有，"
            "行业里比较主流的几家基本都到场。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "skincare",
        "keywords": ["皮肤管理", "护肤", "美容仪器", "皮肤护理", "面部护理"],
        "template": (
            "CIBE皮肤管理区有不少仪器和护肤品牌，"
            "适合想了解市场或选新项目的从业者。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "learn",
        "keywords": ["培训", "报班", "技术学习", "学技术"],
        "template": (
            "CIBE今年有不少头部培训机构到场，现场可以直接和负责人谈，"
            "比线上渠道透明很多。有需要的话私信我获取门票。"
        ),
    },
    {
        "id": "default",
        "keywords": [],
        "template": (
            "CIBE是美业比较集中的展会，资源、品牌、培训都有，"
            "看你具体需要什么。有需要的话私信我获取门票。"
        ),
    },
]


def get_template_by_keyword(keyword: str) -> str:
    kw = (keyword or "").strip()
    default = next(group["template"] for group in KEYWORD_REPLY_MAP if group["id"] == "default")
    if not kw:
        return default

    for group in KEYWORD_REPLY_MAP:
        for target in group["keywords"]:
            if target in kw or kw in target:
                return group["template"]
    return default
