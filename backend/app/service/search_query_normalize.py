"""Normalize smart-search queries: Chinese names, fillers, topics, arXiv ids."""

from __future__ import annotations

import re

# Course / demo scholars and common Chinese academic name aliases.
KNOWN_AUTHOR_ALIASES: dict[str, list[str]] = {
    "沈备军": ["Beijun Shen", "Shen Beijun", "B. Shen", "Shen"],
    "备军": ["Beijun Shen", "Shen Beijun"],
}

# Single-character surnames → academic English surname.
_SURNAMES: dict[str, str] = {
    "赵": "Zhao", "钱": "Qian", "孙": "Sun", "李": "Li", "周": "Zhou", "吴": "Wu",
    "郑": "Zheng", "王": "Wang", "冯": "Feng", "陈": "Chen", "褚": "Chu", "卫": "Wei",
    "蒋": "Jiang", "沈": "Shen", "韩": "Han", "杨": "Yang", "朱": "Zhu", "秦": "Qin",
    "尤": "You", "许": "Xu", "何": "He", "吕": "Lv", "施": "Shi", "张": "Zhang",
    "孔": "Kong", "曹": "Cao", "严": "Yan", "华": "Hua", "金": "Jin", "魏": "Wei",
    "陶": "Tao", "姜": "Jiang", "戚": "Qi", "谢": "Xie", "邹": "Zou", "喻": "Yu",
    "柏": "Bai", "水": "Shui", "窦": "Dou", "章": "Zhang", "云": "Yun", "苏": "Su",
    "潘": "Pan", "葛": "Ge", "奚": "Xi", "范": "Fan", "彭": "Peng", "郎": "Lang",
    "鲁": "Lu", "韦": "Wei", "昌": "Chang", "马": "Ma", "苗": "Miao", "凤": "Feng",
    "花": "Hua", "方": "Fang", "俞": "Yu", "任": "Ren", "袁": "Yuan", "柳": "Liu",
    "酆": "Feng", "鲍": "Bao", "史": "Shi", "唐": "Tang", "费": "Fei", "廉": "Lian",
    "岑": "Cen", "薛": "Xue", "雷": "Lei", "贺": "He", "倪": "Ni", "汤": "Tang",
    "滕": "Teng", "殷": "Yin", "罗": "Luo", "毕": "Bi", "郝": "Hao", "邬": "Wu",
    "安": "An", "常": "Chang", "乐": "Le", "于": "Yu", "时": "Shi", "傅": "Fu",
    "皮": "Pi", "卞": "Bian", "齐": "Qi", "康": "Kang", "伍": "Wu", "余": "Yu",
    "元": "Yuan", "卜": "Bu", "顾": "Gu", "孟": "Meng", "平": "Ping", "黄": "Huang",
    "和": "He", "穆": "Mu", "萧": "Xiao", "尹": "Yin", "姚": "Yao", "邵": "Shao",
    "湛": "Zhan", "汪": "Wang", "祁": "Qi", "毛": "Mao", "禹": "Yu", "狄": "Di",
    "米": "Mi", "贝": "Bei", "明": "Ming", "臧": "Zang", "计": "Ji", "伏": "Fu",
    "成": "Cheng", "戴": "Dai", "谈": "Tan", "宋": "Song", "茅": "Mao", "庞": "Pang",
    "熊": "Xiong", "纪": "Ji", "舒": "Shu", "屈": "Qu", "项": "Xiang", "祝": "Zhu",
    "董": "Dong", "梁": "Liang", "杜": "Du", "阮": "Ruan", "蓝": "Lan", "闵": "Min",
    "席": "Xi", "季": "Ji", "麻": "Ma", "强": "Qiang", "贾": "Jia", "路": "Lu",
    "娄": "Lou", "危": "Wei", "江": "Jiang", "童": "Tong", "颜": "Yan", "郭": "Guo",
    "梅": "Mei", "盛": "Sheng", "林": "Lin", "钟": "Zhong", "徐": "Xu", "邱": "Qiu",
    "骆": "Luo", "高": "Gao", "夏": "Xia", "蔡": "Cai", "田": "Tian", "樊": "Fan",
    "胡": "Hu", "凌": "Ling", "霍": "Huo", "虞": "Yu", "万": "Wan", "支": "Zhi",
    "柯": "Ke", "昝": "Zan", "管": "Guan", "卢": "Lu", "莫": "Mo", "经": "Jing",
    "房": "Fang", "裘": "Qiu", "缪": "Miao", "干": "Gan", "解": "Xie", "应": "Ying",
    "宗": "Zong", "丁": "Ding", "宣": "Xuan", "贲": "Ben", "邓": "Deng", "郁": "Yu",
    "单": "Shan", "杭": "Hang", "洪": "Hong", "包": "Bao", "诸": "Zhu", "左": "Zuo",
    "石": "Shi", "崔": "Cui", "吉": "Ji", "钮": "Niu", "龚": "Gong", "程": "Cheng",
    "嵇": "Ji", "邢": "Xing", "滑": "Hua", "裴": "Pei", "陆": "Lu", "荣": "Rong",
    "翁": "Weng", "荀": "Xun", "羊": "Yang", "於": "Yu", "惠": "Hui", "甄": "Zhen",
    "曲": "Qu", "家": "Jia", "封": "Feng", "芮": "Rui", "羿": "Yi", "储": "Chu",
    "靳": "Jin", "汲": "Ji", "邴": "Bing", "糜": "Mi", "松": "Song", "井": "Jing",
    "段": "Duan", "富": "Fu", "巫": "Wu", "乌": "Wu", "焦": "Jiao", "巴": "Ba",
    "弓": "Gong", "牧": "Mu", "隗": "Kui", "山": "Shan", "谷": "Gu", "车": "Che",
    "侯": "Hou", "宓": "Mi", "蓬": "Peng", "全": "Quan", "郗": "Xi", "班": "Ban",
    "仰": "Yang", "秋": "Qiu", "仲": "Zhong", "伊": "Yi", "宫": "Gong", "宁": "Ning",
    "仇": "Qiu", "栾": "Luan", "暴": "Bao", "甘": "Gan", "钭": "Tou", "厉": "Li",
    "戎": "Rong", "祖": "Zu", "武": "Wu", "符": "Fu", "刘": "Liu", "景": "Jing",
    "詹": "Zhan", "束": "Shu", "龙": "Long", "叶": "Ye", "幸": "Xing", "司": "Si",
    "韶": "Shao", "郜": "Gao", "黎": "Li", "蓟": "Ji", "薄": "Bo", "印": "Yin",
    "宿": "Su", "白": "Bai", "怀": "Huai", "蒲": "Pu", "邰": "Tai", "从": "Cong",
    "鄂": "E", "索": "Suo", "咸": "Xian", "籍": "Ji", "赖": "Lai", "卓": "Zhuo",
    "蔺": "Lin", "屠": "Tu", "蒙": "Meng", "池": "Chi", "乔": "Qiao", "阴": "Yin",
    "郁": "Yu", "胥": "Xu", "能": "Neng", "苍": "Cang", "双": "Shuang", "闻": "Wen",
    "莘": "Shen", "党": "Dang", "翟": "Zhai", "谭": "Tan", "贡": "Gong", "劳": "Lao",
    "逄": "Pang", "姬": "Ji", "申": "Shen", "扶": "Fu", "堵": "Du", "冉": "Ran",
    "宰": "Zai", "郦": "Li", "雍": "Yong", "却": "Que", "璩": "Qu", "桑": "Sang",
    "桂": "Gui", "濮": "Pu", "牛": "Niu", "寿": "Shou", "通": "Tong", "边": "Bian",
    "扈": "Hu", "燕": "Yan", "冀": "Ji", "郏": "Jia", "浦": "Pu", "尚": "Shang",
    "农": "Nong", "温": "Wen", "别": "Bie", "庄": "Zhuang", "晏": "Yan", "柴": "Chai",
    "瞿": "Qu", "阎": "Yan", "充": "Chong", "慕": "Mu", "连": "Lian", "茹": "Ru",
    "习": "Xi", "宦": "Huan", "艾": "Ai", "鱼": "Yu", "容": "Rong", "向": "Xiang",
    "古": "Gu", "易": "Yi", "慎": "Shen", "戈": "Ge", "廖": "Liao", "庾": "Yu",
    "终": "Zhong", "暨": "Ji", "居": "Ju", "衡": "Heng", "步": "Bu", "都": "Du",
    "耿": "Geng", "满": "Man", "弘": "Hong", "匡": "Kuang", "国": "Guo", "文": "Wen",
    "寇": "Kou", "广": "Guang", "禄": "Lu", "阙": "Que", "东": "Dong", "欧": "Ou",
    "殳": "Shu", "沃": "Wo", "利": "Li", "蔚": "Wei", "越": "Yue", "夔": "Kui",
    "隆": "Long", "师": "Shi", "巩": "Gong", "厍": "She", "聂": "Nie", "晁": "Chao",
    "勾": "Gou", "敖": "Ao", "融": "Rong", "冷": "Leng", "訾": "Zi", "辛": "Xin",
    "阚": "Kan", "那": "Na", "简": "Jian", "饶": "Rao", "空": "Kong", "曾": "Zeng",
    "毋": "Wu", "沙": "Sha", "乜": "Nie", "养": "Yang", "鞠": "Ju", "须": "Xu",
    "丰": "Feng", "巢": "Chao", "关": "Guan", "蒯": "Kuai", "相": "Xiang", "查": "Zha",
    "后": "Hou", "荆": "Jing", "红": "Hong", "游": "You", "竺": "Zhu", "权": "Quan",
    "逯": "Lu", "盖": "Gai", "益": "Yi", "桓": "Huan", "公": "Gong", "万俟": "Moqi",
    "司马": "Sima", "上官": "Shangguan", "欧阳": "Ouyang", "夏侯": "Xiahou",
    "诸葛": "Zhuge", "闻人": "Wenren", "东方": "Dongfang", "赫连": "Helian",
    "皇甫": "Huangfu", "尉迟": "Yuchi", "公羊": "Gongyang", "澹台": "Tantai",
    "公冶": "Gongye", "宗政": "Zongzheng", "濮阳": "Puyang", "淳于": "Chunyu",
    "单于": "Chanyu", "太叔": "Taishu", "申屠": "Shentu", "公孙": "Gongsun",
    "仲孙": "Zhongsun", "轩辕": "Xuanyuan", "令狐": "Linghu", "钟离": "Zhongli",
    "宇文": "Yuwen", "长孙": "Zhangsun", "慕容": "Murong", "鲜于": "Xianyu",
    "闾丘": "Luqiu", "司徒": "Situ", "司空": "Sikong", "亓官": "Qiguan",
    "司寇": "Sikou", "仉": "Zhang", "督": "Du", "子车": "Ziche", "颛孙": "Zhuansun",
    "端木": "Duanmu", "巫马": "Wuma", "公西": "Gongxi", "漆雕": "Qidiao",
    "乐正": "Yuezheng", "壤驷": "Rangsi", "公良": "Gongliang", "拓跋": "Tuoba",
    "夹谷": "Jiagu", "宰父": "Zaifu", "谷梁": "Guliang", "晋": "Jin", "楚": "Chu",
    "闫": "Yan", "法": "Fa", "汝": "Ru", "鄢": "Yan", "涂": "Tu", "钦": "Qin",
    "段干": "Duangan", "百里": "Baili", "东郭": "Dongguo", "南门": "Nanmen",
    "呼延": "Huyan", "归": "Gui", "海": "Hai", "羊舌": "Yangshe", "微生": "Weisheng",
    "岳": "Yue", "帅": "Shuai", "缑": "Gou", "亢": "Kang", "况": "Kuang", "后": "Hou",
    "有": "You", "琴": "Qin", "梁丘": "Liangqiu", "左丘": "Zuoqiu", "东门": "Dongmen",
    "西门": "Ximen", "商": "Shang", "牟": "Mou", "佘": "She", "佴": "Nai", "伯": "Bo",
    "赏": "Shang", "南宫": "Nangong", "墨": "Mo", "哈": "Ha", "谯": "Qiao", "笪": "Da",
    "年": "Nian", "爱": "Ai", "阳": "Yang", "佟": "Tong",
}

# Given-name characters used in Chinese academic names (romanized, title case later).
_GIVEN_CHARS: dict[str, str] = {
    "备": "bei", "军": "jun", "伟": "wei", "强": "qiang", "磊": "lei", "勇": "yong",
    "杰": "jie", "涛": "tao", "超": "chao", "鹏": "peng", "辉": "hui", "明": "ming",
    "华": "hua", "建": "jian", "国": "guo", "文": "wen", "武": "wu", "斌": "bin",
    "浩": "hao", "宇": "yu", "轩": "xuan", "然": "ran", "博": "bo", "思": "si",
    "远": "yuan", "航": "hang", "晨": "chen", "阳": "yang", "飞": "fei", "龙": "long",
    "虎": "hu", "峰": "feng", "岭": "ling", "海": "hai", "波": "bo", "洋": "yang",
    "清": "qing", "平": "ping", "安": "an", "康": "kang", "宁": "ning", "静": "jing",
    "丽": "li", "娜": "na", "敏": "min", "慧": "hui", "芳": "fang", "婷": "ting",
    "雪": "xue", "梅": "mei", "兰": "lan", "竹": "zhu", "菊": "ju", "蓉": "rong",
    "霞": "xia", "红": "hong", "艳": "yan", "玉": "yu", "珠": "zhu", "玲": "ling",
    "琳": "lin", "瑶": "yao", "嘉": "jia", "怡": "yi", "欣": "xin", "悦": "yue",
    "乐": "le", "天": "tian", "子": "zi", "一": "yi", "二": "er", "三": "san",
    "志": "zhi", "成": "cheng", "德": "de", "仁": "ren", "义": "yi", "礼": "li",
    "智": "zhi", "信": "xin", "晓": "xiao", "东": "dong", "西": "xi", "南": "nan",
    "北": "bei", "中": "zhong", "正": "zheng", "宏": "hong", "伟": "wei", "新": "xin",
    "春": "chun", "夏": "xia", "秋": "qiu", "冬": "dong", "永": "yong", "长": "chang",
    "青": "qing", "松": "song", "柏": "bai", "林": "lin", "森": "sen", "木": "mu",
    "金": "jin", "银": "yin", "铜": "tong", "铁": "tie", "石": "shi", "岩": "yan",
    "山": "shan", "川": "chuan", "河": "he", "湖": "hu", "江": "jiang", "河": "he",
    "启": "qi", "维": "wei", "哲": "zhe", "翰": "han", "泽": "ze", "润": "run",
    "霖": "lin", "霆": "ting", "雷": "lei", "电": "dian", "光": "guang", "亮": "liang",
    "灿": "can", "炫": "xuan", "熠": "yi", "煜": "yu", "炜": "wei", "炎": "yan",
    "焱": "yan", "煜": "yu", "煜": "yu", "昊": "hao", "昱": "yu", "昭": "zhao",
    "晖": "hui", "晟": "sheng", "昌": "chang", "盛": "sheng", "兴": "xing", "旺": "wang",
    "达": "da", "通": "tong", "进": "jin", "升": "sheng", "腾": "teng", "翔": "xiang",
    "驰": "chi", "骏": "jun", "骐": "qi", "骥": "ji", "鹏": "peng", "鹤": "he",
    "鸿": "hong", "雁": "yan", "鸽": "ge", "鹰": "ying", "燕": "yan", "雀": "que",
    "智": "zhi", "聪": "cong", "敏": "min", "捷": "jie", "锐": "rui", "锋": "feng",
    "钢": "gang", "铁": "tie", "坚": "jian", "固": "gu", "稳": "wen", "定": "ding",
    "祥": "xiang", "瑞": "rui", "福": "fu", "禄": "lu", "寿": "shou", "喜": "xi",
    "庆": "qing", "贺": "he", "祝": "zhu", "祈": "qi", "愿": "yuan", "望": "wang",
    "梦": "meng", "幻": "huan", "奇": "qi", "妙": "miao", "玄": "xuan", "奥": "ao",
    "深": "shen", "浅": "qian", "高": "gao", "低": "di", "宽": "kuan", "广": "guang",
    "厚": "hou", "薄": "bo", "大": "da", "小": "xiao", "多": "duo", "少": "shao",
    "元": "yuan", "亨": "heng", "利": "li", "贞": "zhen", "吉": "ji", "祥": "xiang",
    "学": "xue", "习": "xi", "书": "shu", "诗": "shi", "词": "ci", "赋": "fu",
    "章": "zhang", "程": "cheng", "科": "ke", "技": "ji", "工": "gong", "程": "cheng",
    "软": "ruan", "件": "jian", "硬": "ying", "网": "wang", "络": "luo", "云": "yun",
    "计": "ji", "算": "suan", "数": "shu", "据": "ju", "智": "zhi", "能": "neng",
    "机": "ji", "器": "qi", "人": "ren", "工": "gong", "智": "zhi", "能": "neng",
    "研": "yan", "究": "jiu", "院": "yuan", "所": "suo", "教": "jiao", "授": "shou",
    "士": "shi", "博": "bo", "硕": "shuo", "本": "ben", "科": "ke", "生": "sheng",
    "俊": "jun", "彦": "yan", "豪": "hao", "杰": "jie", "英": "ying", "雄": "xiong",
    "才": "cai", "贤": "xian", "良": "liang", "善": "shan", "美": "mei", "好": "hao",
    "君": "jun", "臣": "chen", "民": "min", "众": "zhong", "群": "qun", "队": "dui",
    "家": "jia", "庭": "ting", "族": "zu", "宗": "zong", "祖": "zu", "先": "xian",
    "后": "hou", "代": "dai", "世": "shi", "纪": "ji", "年": "nian", "月": "yue",
    "日": "ri", "时": "shi", "分": "fen", "秒": "miao", "刻": "ke", "瞬": "shun",
    "启": "qi", "发": "fa", "展": "zhan", "开": "kai", "放": "fang", "创": "chuang",
    "新": "xin", "造": "zao", "作": "zuo", "为": "wei", "成": "cheng", "就": "jiu",
    "功": "gong", "业": "ye", "绩": "ji", "效": "xiao", "果": "guo", "实": "shi",
    "验": "yan", "证": "zheng", "明": "ming", "白": "bai", "清": "qing", "楚": "chu",
    "贝": "bei", "军": "jun", "钧": "jun", "均": "jun", "君": "jun", "峻": "jun",
}

_HONORIFICS = ("老师", "教授", "博士", "院士", "导师", "同学", "先生", "女士", "研究员")
_FILLERS = (
    "找一下", "帮我找", "帮我搜", "帮我查", "请帮我", "麻烦", "看一下", "查一下",
    "搜一下", "搜索一下", "有没有", "我想找", "我想看", "给我找", "给我搜",
    "请找", "请搜", "找找", "搜搜", "查询", "检索", "搜索", "查找",
)
_TOPIC_ZH_EN: dict[str, list[str]] = {
    "代码生成": ["code generation", "program synthesis"],
    "程序合成": ["program synthesis", "code generation"],
    "软件工程": ["software engineering"],
    "自然语言处理": ["natural language processing", "NLP"],
    "大语言模型": ["large language model", "LLM"],
    "大模型": ["large language model", "LLM"],
    "知识图谱": ["knowledge graph"],
    "推荐系统": ["recommender system", "recommendation"],
    "计算机视觉": ["computer vision"],
    "强化学习": ["reinforcement learning"],
    "深度学习": ["deep learning"],
    "机器学习": ["machine learning"],
    "图神经网络": ["graph neural network", "GNN"],
    "注意力": ["attention", "self-attention"],
    "预训练": ["pre-training", "pretraining"],
    "微调": ["fine-tuning", "finetuning"],
    "多模态": ["multimodal", "multi-modal"],
    "信息检索": ["information retrieval"],
    "问答": ["question answering", "QA"],
    "摘要": ["summarization", "summary"],
    "翻译": ["machine translation", "translation"],
    "语音": ["speech", "ASR"],
    "安全": ["security"],
    "隐私": ["privacy"],
    "联邦学习": ["federated learning"],
    "贝叶斯": ["Bayesian"],
    "在线学习": ["online learning"],
    "自适应": ["adaptive"],
}
_CATEGORY_ZH: dict[str, str] = {
    "自然语言处理": "cs.CL",
    "机器学习": "cs.LG",
    "计算机视觉": "cs.CV",
    "人工智能": "cs.AI",
    "软件工程": "cs.SE",
    "信息检索": "cs.IR",
    "语音": "cs.SD",
    "安全": "cs.CR",
}

_AUTHOR_QUERY_RE = re.compile(
    r"(?:"
    r"(?:找一下|帮我找|帮我搜|搜索|查一下|查询|检索)?\s*"
    r"(?P<name>[\u4e00-\u9fff]{2,4})"
    r"(?:老师|教授|博士|院士|导师|先生|女士)?"
    r"的?(?:论文|文章|工作|著作|成果)"
    r"|"
    r"(?:作者|author)\s*[:：]?\s*(?P<name2>[\u4e00-\u9fff]{2,4}|[A-Za-z][A-Za-z.\-\s]{1,40})"
    r"|"
    r"papers?\s+(?:by|from)\s+(?P<name3>[A-Za-z][A-Za-z.\-\s]{1,40})"
    r"|"
    r"(?P<name4>[\u4e00-\u9fff]{2,4})(?:老师|教授|博士|院士)的?(?:论文|文章)?"
    r")",
    re.IGNORECASE,
)
_ARXIV_RE = re.compile(r"(?:arxiv\s*[:：]?\s*)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


def extract_arxiv_id(query: str) -> str | None:
    match = _ARXIV_RE.search(query or "")
    return match.group(1) if match else None


def strip_query_fillers(query: str) -> str:
    text = (query or "").strip()
    for filler in _FILLERS:
        if text.startswith(filler):
            text = text[len(filler) :].lstrip(" ，,。:：")
    for honor in _HONORIFICS:
        text = text.replace(honor, "")
    text = re.sub(r"的?(论文|文章|工作|著作|成果)\s*$", "", text)
    return " ".join(text.split()).strip() or (query or "").strip()


def romanize_chinese_person_name(name: str) -> list[str]:
    """Return English author variants: Given Family, Family Given, Family."""
    raw = (name or "").strip()
    if not raw:
        return []
    if raw in KNOWN_AUTHOR_ALIASES:
        return list(KNOWN_AUTHOR_ALIASES[raw])
    if re.fullmatch(r"[A-Za-z][A-Za-z.\-\s]+", raw):
        cleaned = " ".join(raw.replace(".", " ").split())
        parts = cleaned.split()
        variants = [cleaned]
        if len(parts) >= 2:
            variants.append(f"{parts[-1]} {' '.join(parts[:-1])}")
            variants.append(parts[-1])
        return _dedupe(variants)

    # Known alias substring (e.g. query still contains 沈备军)
    for zh, aliases in KNOWN_AUTHOR_ALIASES.items():
        if zh in raw:
            return list(aliases)

    surname = ""
    given = ""
    for length in (2, 1):
        prefix = raw[:length]
        if prefix in _SURNAMES:
            surname = _SURNAMES[prefix]
            given = raw[length:]
            break
    if not surname or not given:
        return []

    given_parts: list[str] = []
    for char in given:
        py = _GIVEN_CHARS.get(char)
        if not py:
            return []
        given_parts.append(py)
    given_en = "".join(given_parts).title().replace(" ", "")
    # Title-case each syllable chunk already concatenated → Beijun
    if given_en and given_en[0].islower():
        given_en = given_en[0].upper() + given_en[1:]
    family_given = f"{surname} {given_en}"
    given_family = f"{given_en} {surname}"
    return _dedupe([given_family, family_given, surname, f"{given_en[0]}. {surname}" if given_en else surname])


def extract_author_candidates(query: str) -> list[str]:
    """Chinese/English author mentions from natural-language search queries."""
    text = query or ""
    names: list[str] = []
    match = _AUTHOR_QUERY_RE.search(text)
    if match:
        for key in ("name", "name2", "name3", "name4"):
            value = (match.groupdict().get(key) or "").strip()
            if value:
                names.append(value)
                break
    # Bare known scholar name
    for zh in KNOWN_AUTHOR_ALIASES:
        if zh in text and zh not in names:
            names.append(zh)
    expanded: list[str] = []
    for name in names:
        expanded.extend(romanize_chinese_person_name(name) or [name])
    return _dedupe(expanded)


def expand_chinese_topics(query: str) -> tuple[list[str], list[str]]:
    """Return (english_keywords, category_hints) from Chinese topic phrases."""
    keywords: list[str] = []
    categories: list[str] = []
    text = query or ""
    for zh, en_list in _TOPIC_ZH_EN.items():
        if zh in text:
            keywords.extend(en_list)
    for zh, cat in _CATEGORY_ZH.items():
        if zh in text:
            categories.append(cat)
    return _dedupe(keywords), _dedupe(categories)


def infer_search_mode(query: str, *, author_hints: list[str] | None = None) -> str:
    if extract_arxiv_id(query):
        return "arxiv"
    authors = author_hints if author_hints is not None else extract_author_candidates(query)
    topic_kw, _ = expand_chinese_topics(query)
    has_author = bool(authors)
    # Topic leftovers after stripping author phrasing
    leftover = strip_query_fillers(query)
    for hint in authors:
        leftover = leftover.replace(hint, "")
    for zh in KNOWN_AUTHOR_ALIASES:
        leftover = leftover.replace(zh, "")
    leftover = re.sub(r"[的了吗呢啊呀\s]+", "", leftover)
    has_topic = bool(topic_kw) or bool(re.search(r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,}", leftover))
    if has_author and has_topic and leftover:
        # "沈备军老师关于代码生成的论文"
        if topic_kw or re.search(r"(关于|有关|方向|领域|[A-Za-z]{3,})", query or ""):
            return "mixed"
    if has_author and not topic_kw and (
        re.search(r"(论文|文章|作者|老师|教授|papers?\s+by)", query or "", re.I)
        or any(zh in (query or "") for zh in KNOWN_AUTHOR_ALIASES)
    ):
        return "author"
    if has_author and not leftover:
        return "author"
    return "topic"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold().strip()
        if not value or not key or key in seen:
            continue
        seen.add(key)
        out.append(value.strip())
    return out


__all__ = [
    "KNOWN_AUTHOR_ALIASES",
    "extract_arxiv_id",
    "strip_query_fillers",
    "romanize_chinese_person_name",
    "extract_author_candidates",
    "expand_chinese_topics",
    "infer_search_mode",
]
