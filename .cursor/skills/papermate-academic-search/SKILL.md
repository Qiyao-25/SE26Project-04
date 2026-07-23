---
name: papermate-academic-search
description: PaperMate 智能检索规划与约束。用于中英文混合检索、可信作者映射、术语别名、年份/排除硬过滤、服务端检索会话分页，以及仅基于命中论文的受约束回答。
---

# PaperMate 智能论文检索

## 目标

把自然语言转为可验证、可分页的检索计划；回答只能引用实际命中论文。

## 硬规则

1. `must` 级条件（arXiv ID、作者、分类、年份、排除项）不可被 LLM 擅自放宽。
2. 中文人名：仅可信别名表可断言英文等价；否则 warning=`AUTHOR_TRANSLITERATION_UNVERIFIED`。
3. 禁止泛词单独召回：`model/method/paper/research/研究/方法`。
4. 分页使用服务端 `search_session_id`，不重新规划，不信任客户端 keywords。
5. 回答中的论文 ID 必须属于候选集合；失败时用模板，不拖垮列表。

## 与后端对接

- API：`POST /api/papers/smart-search`
- 计划字段：`keywords`、`author_hints`、`category_hints`、`search_mode`、`year_from/to`、`exclude_terms`、`warnings`
- 响应：`search_session_id`、`warnings`；翻页传 `search_session_id + page`

## 验收要点

- `找一下沈备军老师的论文` → Beijun Shen（可信别名）
- `不要综述的 LoRA` → 排除 survey/review
- `近几年多模态` → 默认近 3 年并说明范围
- 第 2 页 → 同一 `search_session_id`，顺序稳定
