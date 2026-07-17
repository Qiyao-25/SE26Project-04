export const PAPERS = {
  attention: {
    id: 'attention',
    title: 'Attention Is All You Need',
    authors: 'Vaswani, Shazeer, Parmar, et al.',
    date: '2017-06-12',
    arxiv: '1706.03762',
    tag: 'cs.CL',
    summary: '提出 Transformer 架构，完全基于注意力机制，在机器翻译任务达到 SOTA。',
    keywords: ['Transformer', 'Self-Attention', 'Machine Translation', 'Seq2Seq'],
    direction: '序列建模 / 神经机器翻译',
    conceptTags: ['Multi-Head Attention', 'Positional Encoding', 'Encoder-Decoder']
  },
  bert: {
    id: 'bert',
    title: 'BERT: Pre-training of Deep Bidirectional Transformers',
    authors: 'Devlin, Chang, Lee, Toutanova',
    date: '2018-10-11',
    arxiv: '1810.04805',
    tag: 'cs.CL',
    summary: '双向预训练语言表示模型，奠定预训练-微调范式。',
    keywords: ['BERT', 'Pre-training', 'Bidirectional', 'NLU'],
    direction: '预训练语言模型 / NLP',
    conceptTags: ['Masked LM', 'Pre-training', 'Fine-tuning']
  },
  gpt3: {
    id: 'gpt3',
    title: 'GPT-3: Language Models are Few-Shot Learners',
    authors: 'Brown, Mann, Ryder, et al.',
    date: '2020-05-28',
    arxiv: '2005.14165',
    tag: 'cs.LG',
    summary: '规模化语言模型展示少样本学习能力与涌现特性。',
    keywords: ['GPT-3', 'Few-Shot', 'In-Context Learning', 'Scaling'],
    direction: '大语言模型 / 生成式 AI',
    conceptTags: ['Emergent Ability', 'In-Context Learning', 'Autoregressive LM']
  },
  lora: {
    id: 'lora',
    title: 'LoRA: Low-Rank Adaptation of Large Language Models',
    authors: 'Hu, Shen, Wallis, et al.',
    date: '2021-06-17',
    arxiv: '2106.09685',
    tag: 'cs.LG',
    summary: '低秩适配实现参数高效微调，适用于大模型。',
    keywords: ['LoRA', 'PEFT', 'Fine-tuning', 'Low-Rank'],
    direction: '参数高效微调 / 大模型适配',
    conceptTags: ['Low-Rank Adaptation', 'PEFT', 'Adapter']
  },
  rag: {
    id: 'rag',
    title: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP',
    authors: 'Lewis, Perez, Piktus, et al.',
    date: '2020-05-22',
    arxiv: '2005.11401',
    tag: 'cs.CL',
    summary: '检索增强生成架构，结合外部知识库提升问答质量。',
    keywords: ['RAG', 'Retrieval', 'Knowledge-Intensive', 'QA'],
    direction: '检索增强生成 / 知识密集型 NLP',
    conceptTags: ['Retrieval-Augmented Generation', 'Dense Passage Retrieval', 'Knowledge Base']
  },
  vlm: {
    id: 'vlm',
    title: 'Vision-Language Models for Scientific Document Understanding',
    authors: 'Li, Zhang, Wang',
    date: '2026-07-07',
    arxiv: '2607.01001',
    tag: 'cs.CV',
    summary: '多模态模型用于科学文档解析与理解。',
    keywords: ['VLM', 'Multimodal', 'Scientific Document', 'OCR'],
    direction: '多模态理解 / 科学文献解析',
    conceptTags: ['Vision-Language Model', 'Document Understanding', 'Multimodal Fusion']
  }
};

export const PAPER_LIST = Object.values(PAPERS);

export const READING_HISTORY = {
  today: {
    label: '今天 · 阅读记录',
    items: [
      { paper: 'attention', time: '15:20', section: 'methods.md', duration: '25min' },
      { paper: 'bert', time: '10:05', section: 'concept.md', duration: '20min' }
    ]
  },
  yesterday: {
    label: '昨天 · 阅读记录',
    items: [
      { paper: 'lora', time: '20:30', section: 'summary.md', duration: '35min' },
      { paper: 'rag', time: '18:15', section: 'concept.md', duration: '30min' },
      { paper: 'gpt3', time: '16:00', section: 'methods.md', duration: '25min' }
    ]
  },
  earlier: {
    label: '本周更早 · 阅读记录',
    items: [
      { paper: 'attention', time: '周三 14:00', section: 'summary.md', duration: '40min' },
      { paper: 'vlm', time: '周二 11:30', section: 'concept.md', duration: '28min' },
      { paper: 'bert', time: '周一 09:15', section: 'methods.md', duration: '32min' },
      { paper: 'lora', time: '周一 08:00', section: 'summary.md', duration: '18min' },
      { paper: 'rag', time: '周日 21:00', section: 'concept.md', duration: '22min' }
    ]
  }
};

export const PERSONAS = ['新手', '研究', '工程', '教学', '管理'];

export const MODE_DESC = {
  新手: '白话解释背景与术语，先看懂「这篇在讲什么」，少公式、短句子。',
  研究: '聚焦贡献、方法、实验证据与局限，方便写综述、开题与对比。',
  工程: '面向复现与落地：模块拆分、数据评测、资源成本与风险清单。',
  教学: '按一节课组织：学习目标、讲解顺序、板书要点、思考题与讨论。',
  管理: '结论先行：价值、趋势、应用场景、投入门槛与建议动作。'
};

/** @deprecated 仅作离线兜底；详情页已改为 ReadingModeAgent 生成 */
export const MODE_ASSIST = {
  新手: (p) => `【白话总结】${p.title}\n\n这篇论文在讲什么：${p.summary || p.abstract || ''}`,
  研究: (p) => `【研究视角】${p.title}\n\n核心贡献：${p.summary || p.abstract || ''}`,
  工程: (p) => `【工程视角】${p.title}\n\n先确认可实现模块与数据评测协议，再评估复现成本。`,
  教学: (p) => `【教学讲义】${p.title}\n\n建议按「动机 → 概念 → 方法 → 实验 → 局限」讲解。`,
  管理: (p) => `【管理视角】${p.title}\n\n先看价值与匹配度，再看门槛与风险。`
};

export const DEFAULT_PAPER_NOTES = {
  attention: {
    notes: [{ id: 1, highlight: 'Multi-Head Attention 允许模型关注不同表示子空间', text: '核心创新在于完全用注意力替代 RNN。', date: '2026-07-01' }],
    comments: [{ id: 1, text: '建议配合 BERT 一起读。', date: '2026-06-28' }]
  },
  bert: {
    notes: [{ id: 1, highlight: '双向预训练表示', text: '预训练-微调范式的里程碑。', date: '2026-06-18' }],
    comments: []
  }
};

export function shortPaperTitle(paperId) {
  const t = PAPERS[paperId]?.title || '';
  const idx = t.indexOf(':');
  return idx > 0 ? t.slice(0, idx) : (t.length > 28 ? `${t.slice(0, 28)}…` : t);
}

export function getDefaultCompareTarget(paperId) {
  const current = PAPERS[paperId];
  if (!current) return 'bert';
  let best = null;
  let bestScore = 0;
  Object.entries(PAPERS).forEach(([id, p]) => {
    if (id === paperId) return;
    let score = 0;
    if (p.tag === current.tag) score += 2;
    if (p.direction === current.direction) score += 3;
    const kw = new Set((current.keywords || []).map((k) => k.toLowerCase()));
    (p.keywords || []).forEach((k) => { if (kw.has(k.toLowerCase())) score += 2; });
    if (score > bestScore) { bestScore = score; best = id; }
  });
  return best || Object.keys(PAPERS).find((id) => id !== paperId);
}
