"""Reading-mode assist Agent: mode-specific prompts for readable guidance."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agents.llm_client import LlmError, chat_completion
from app.core.config import Settings


PERSONAS = ("新手", "研究", "工程", "教学", "管理")

MODE_SPECS: dict[str, dict[str, str]] = {
    "新手": {
        "audience": "刚接触该领域的读者",
        "goal": "降低门槛：解释背景、翻译术语、用白话讲清论文在做什么",
        "sections": "一句话看懂｜这篇论文在讲什么｜关键术语白话解释｜你可以先记住的3点｜阅读建议",
        "style": "口语化、短句、少公式；术语首次出现必须用「术语（通俗说法）」解释；禁止堆砌英文缩写而不解释",
        "avoid": "不要假设读者懂 Transformer/预训练等背景；不要大段英文；不要写成论文摘要复读",
    },
    "研究": {
        "audience": "研究生/科研人员",
        "goal": "突出贡献、方法要点、实验设计与可检验的局限，便于写综述或开题",
        "sections": "核心贡献｜方法要点｜实验与证据｜与同类工作的差异｜局限与可追问点",
        "style": "学术但清晰；用条目；标明「论文声称」与「依据不足」；可保留必要专有名词",
        "avoid": "不要空泛夸奖；不要编造对比结果或未出现的数字；不要写成科普故事",
    },
    "工程": {
        "audience": "要复现或落地的工程师",
        "goal": "给出可执行视角：模块、数据、训练/推理成本、复现步骤与坑",
        "sections": "系统怎么搭｜关键模块/算法｜数据与评测｜复现清单｜落地风险与替代方案",
        "style": "清单化、动词开头；写清依赖与大概资源；不确定处标注「原文未明确」",
        "avoid": "不要只复述摘要；不要给无法核实的硬件报价；不要忽略工程约束",
    },
    "教学": {
        "audience": "授课教师或助教",
        "goal": "组织成一节课：学习目标、讲解顺序、板书要点、思考题与讨论",
        "sections": "本节学习目标｜推荐讲解顺序｜板书/幻灯要点｜课堂思考题｜讨论与作业建议",
        "style": "讲义口吻；步骤清晰；思考题要能检验理解而非死记硬背",
        "avoid": "不要写成论文翻译；不要缺少互动环节；不要题目过大无法当堂完成",
    },
    "管理": {
        "audience": "技术负责人/产品或科研管理",
        "goal": "用决策语言说明价值、趋势、投入产出与风险",
        "sections": "一句话价值｜趋势与定位｜可能的应用场景｜投入与门槛｜风险与建议动作",
        "style": "结论先行；短段落；少公式；用「建议关注/暂缓」给出可执行建议",
        "avoid": "不要技术细节堆砌；不要夸大商业前景；不要缺少风险提示",
    },
}

OUTPUT_SCHEMA = """只输出一个 JSON 对象：
{
  "headline": "不超过40字的中文总览",
  "sections": [
    {"title": "小节标题", "bullets": ["要点1", "要点2"]}
  ],
  "takeaways": ["可带走的结论1", "结论2", "结论3"],
  "next_steps": ["下一步阅读/行动建议"]
}
要求：
1. sections 3-5 个，顺序符合该模式「章节结构」。
2. 每个 section 的 bullets 2-5 条；每条不超过60字；全中文为主。
3. takeaways 恰好 3 条；next_steps 1-3 条。
4. 只能依据输入的论文信息，不要编造实验数字、未给出的对比结论或虚假引用。
5. 内容必须明显符合当前阅读模式，换模式后侧重点应明显不同。
"""


@dataclass
class ReadingAssistResult:
    mode: str
    headline: str
    sections: list[dict[str, Any]] = field(default_factory=list)
    takeaways: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    source: str = "llm_reading_mode_agent"

    def to_content_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "headline": self.headline,
            "sections": self.sections,
            "takeaways": self.takeaways,
            "next_steps": self.next_steps,
            "source": self.source,
        }


class ReadingModeAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        *,
        mode: str,
        title: str,
        abstract: str = "",
        summary: str = "",
        concepts: list[dict[str, Any]] | None = None,
        methods: list[dict[str, Any]] | None = None,
        experiments: list[dict[str, Any]] | None = None,
        limitations: list[str] | None = None,
        primary_category: str = "",
        arxiv_id: str = "",
    ) -> ReadingAssistResult:
        persona = mode if mode in MODE_SPECS else "研究"
        spec = MODE_SPECS[persona]
        system = (
            f"你是 PaperMate 的「{persona}模式」辅助阅读 Agent。\n"
            f"读者画像：{spec['audience']}。\n"
            f"目标：{spec['goal']}。\n"
            f"章节结构（请按此组织 sections.title）：{spec['sections']}。\n"
            f"文风：{spec['style']}。\n"
            f"禁止：{spec['avoid']}。\n"
            f"{OUTPUT_SCHEMA}"
        )
        payload = {
            "mode": persona,
            "paper": {
                "arxiv_id": arxiv_id,
                "title": title,
                "primary_category": primary_category,
                "abstract": (abstract or "")[:1600],
                "structured_summary": (summary or "")[:1600],
                "concepts": [
                    {"name": c.get("name"), "description": str(c.get("description") or "")[:160]}
                    for c in (concepts or [])[:8]
                    if isinstance(c, dict)
                ],
                "methods": [
                    {"title": m.get("title") or m.get("name"), "description": str(m.get("description") or "")[:160]}
                    for m in (methods or [])[:6]
                    if isinstance(m, dict)
                ],
                "experiments": [
                    {"title": e.get("title"), "description": str(e.get("description") or "")[:120]}
                    for e in (experiments or [])[:4]
                    if isinstance(e, dict)
                ],
                "limitations": [str(x)[:120] for x in (limitations or [])[:5]],
            },
        }
        raw = chat_completion(
            api_key=self.settings.llm_api_key,
            api_base=self.settings.llm_api_base,
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            timeout_s=float(getattr(self.settings, "assist_agent_timeout_s", 60.0)),
            temperature=0.35,
            json_mode=True,
        )
        data = json.loads(_strip_fence(raw))
        if not isinstance(data, dict):
            raise LlmError("ReadingMode Agent JSON 根节点必须是对象")
        return _normalize(persona, data)


def build_fallback_assist(
    *,
    mode: str,
    title: str,
    summary: str = "",
    abstract: str = "",
    concepts: list[dict[str, Any]] | None = None,
    methods: list[dict[str, Any]] | None = None,
    limitations: list[str] | None = None,
) -> ReadingAssistResult:
    """Deterministic readable fallback when LLM is unavailable."""
    persona = mode if mode in MODE_SPECS else "研究"
    blurb = (summary or abstract or "暂无结构化摘要，请先完成解析。").strip()
    concept_names = [str(c.get("name")) for c in (concepts or [])[:4] if isinstance(c, dict) and c.get("name")]
    method_names = [
        str(m.get("title") or m.get("name"))
        for m in (methods or [])[:4]
        if isinstance(m, dict) and (m.get("title") or m.get("name"))
    ]
    limits = [str(x) for x in (limitations or [])[:3] if str(x).strip()]

    templates: dict[str, ReadingAssistResult] = {
        "新手": ReadingAssistResult(
            mode=persona,
            headline=f"用大白话读懂《{_short(title, 24)}》",
            sections=[
                {"title": "这篇论文在讲什么", "bullets": [blurb[:120], "先抓住它要解决的问题，再看它提出的办法。"]},
                {
                    "title": "关键术语白话解释",
                    "bullets": [f"{name}：先把它当成文中的重要概念记住即可" for name in (concept_names or ["核心概念"])],
                },
                {
                    "title": "你可以先记住的3点",
                    "bullets": [
                        "它想改进什么阅读/计算/预测问题",
                        f"主要手段：{'、'.join(method_names) if method_names else '文中提出的核心方法'}",
                        "读完后能用自己的话复述「问题-方法-效果」",
                    ],
                },
            ],
            takeaways=["先看问题与动机", "术语不懂就回查概念卡片", "不必一开始抠公式细节"],
            next_steps=["打开智能总结页扫一遍概念", "遇到不懂的词再问侧边栏问答"],
            source="heuristic",
        ),
        "研究": ReadingAssistResult(
            mode=persona,
            headline=f"研究视角：{_short(title, 28)}",
            sections=[
                {"title": "核心贡献", "bullets": [blurb[:140]]},
                {
                    "title": "方法要点",
                    "bullets": method_names or ["结合智能总结中的方法步骤核对原文"],
                },
                {
                    "title": "局限与可追问点",
                    "bullets": limits or ["原文局限表述不足，建议对照实验设置追问可泛化性"],
                },
            ],
            takeaways=["明确贡献陈述", "核对实验是否支撑结论", "记下可延续的研究问题"],
            next_steps=["对比同领域 1-2 篇相关工作", "用问答核对实验设置细节"],
            source="heuristic",
        ),
        "工程": ReadingAssistResult(
            mode=persona,
            headline=f"工程视角：如何落地 {_short(title, 24)}",
            sections=[
                {"title": "系统怎么搭", "bullets": [blurb[:120], "先定位输入/输出与关键模块边界"]},
                {
                    "title": "关键模块/算法",
                    "bullets": method_names or ["从方法章节抽出可实现组件清单"],
                },
                {
                    "title": "复现清单",
                    "bullets": ["确认数据与评测协议", "估算训练/推理资源", "寻找开源实现或最小可运行原型"],
                },
            ],
            takeaways=["模块边界先画清楚", "复现成本要提前估", "不确定处回原文核对"],
            next_steps=["整理依赖与数据入口", "用问答追问实现超参与训练细节"],
            source="heuristic",
        ),
        "教学": ReadingAssistResult(
            mode=persona,
            headline=f"一节课讲清：{_short(title, 24)}",
            sections=[
                {
                    "title": "本节学习目标",
                    "bullets": ["能用自己的话说明论文问题与贡献", "能解释 2-3 个核心概念", "能提出一个有依据的追问"],
                },
                {
                    "title": "推荐讲解顺序",
                    "bullets": ["动机与背景", f"概念：{'、'.join(concept_names) if concept_names else '核心概念'}", "方法与小例子", "实验结论与局限"],
                },
                {
                    "title": "课堂思考题",
                    "bullets": ["如果去掉文中关键机制，性能可能如何变化？", "该方法最依赖什么假设？", "适合布置什么小型对比作业？"],
                },
            ],
            takeaways=["目标可检验", "讲解有节奏", "用问题驱动讨论"],
            next_steps=["选 1 个概念做板书推导", "布置阅读智能总结后的简答"],
            source="heuristic",
        ),
        "管理": ReadingAssistResult(
            mode=persona,
            headline=f"决策速览：{_short(title, 24)}",
            sections=[
                {"title": "一句话价值", "bullets": [blurb[:120]]},
                {
                    "title": "可能的应用场景",
                    "bullets": ["评估是否匹配当前业务/研究方向", "判断是否值得跟进原型验证"],
                },
                {
                    "title": "风险与建议动作",
                    "bullets": limits[:2] or ["技术成熟度与数据门槛需再评估"],
                },
            ],
            takeaways=["先看价值与匹配度", "再看门槛与风险", "决定跟进或观望"],
            next_steps=["安排技术同学做 1 页可行性评估", "关注同主题后续脉络论文"],
            source="heuristic",
        ),
    }
    return templates.get(persona, templates["研究"])


def _short(text: str, max_len: int) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value if len(value) <= max_len else value[: max_len - 1] + "…"


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _normalize(mode: str, data: dict[str, Any]) -> ReadingAssistResult:
    headline = str(data.get("headline") or "").strip() or f"{mode}模式辅助阅读"
    sections: list[dict[str, Any]] = []
    for item in data.get("sections") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        bullets_raw = item.get("bullets") or item.get("points") or item.get("body")
        bullets: list[str] = []
        if isinstance(bullets_raw, list):
            bullets = [str(x).strip() for x in bullets_raw if str(x).strip()]
        elif isinstance(bullets_raw, str) and bullets_raw.strip():
            bullets = [line.strip(" •-\t") for line in bullets_raw.splitlines() if line.strip()]
        if title and bullets:
            sections.append({"title": title[:40], "bullets": bullets[:6]})
    takeaways = [str(x).strip() for x in (data.get("takeaways") or []) if str(x).strip()][:5]
    next_steps = [str(x).strip() for x in (data.get("next_steps") or []) if str(x).strip()][:4]
    if not sections:
        raise LlmError("ReadingMode Agent 未返回有效 sections")
    if not takeaways:
        takeaways = ["抓住本模式关注的重点再精读原文"]
    if not next_steps:
        next_steps = ["结合智能总结与问答继续深入"]
    return ReadingAssistResult(
        mode=mode,
        headline=headline[:80],
        sections=sections[:6],
        takeaways=takeaways,
        next_steps=next_steps,
        source="llm_reading_mode_agent",
    )


__all__ = [
    "PERSONAS",
    "MODE_SPECS",
    "ReadingAssistResult",
    "ReadingModeAgent",
    "build_fallback_assist",
]
