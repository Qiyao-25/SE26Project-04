/**
 * PaperMate 低保真线框图 v2 — 完整交互逻辑
 * 依据《页面设计.docx》实现页面跳转与交互
 */

const PAPERS = {
  attention: {
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

const WIREFRAME_DEMO = true; // 线框演示：管理员侧栏入口常驻显示

const PAGE_META = {
  workspace:    { title: '论文检索与发现（工作空间）', subtitle: '页面二 · 推荐与搜索' },
  'paper-detail': { title: '论文详情', subtitle: '页面三 · 论文主体 / 智能总结 / 知识图谱' },
  learning:     { title: '学习空间', subtitle: '页面四 · 收藏/笔记/画像/模式切换' },
  agent:        { title: '管理员后台（系统管理端）', subtitle: '页面五 · 概览 / Agent / 任务 / 质量 / 配置 / 审计' },
  settings:     { title: '设置', subtitle: '页面六 · 抓取订阅/账户/网页' }
};

const READING_HISTORY = {
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

const MODE_DESC = {
  '新手': '新手模式：提供背景解释、术语翻译与白话总结，降低阅读门槛',
  '研究': '研究模式：侧重创新点、方法、实验设计与局限性分析',
  '工程': '工程模式：关注实现流程、依赖数据与复现难度',
  '教学': '教学模式：生成讲义结构、思考题与课堂讨论点',
  '管理': '管理模式：分析研究趋势、应用价值、风险与前景'
};

const MODE_ASSIST = {
  '新手': (p) => `【白话总结】${p.title}\n\n这篇论文在讲什么：${p.summary}\n\n通俗理解：作者用「注意力机制」替代了传统 RNN，让模型能并行处理句子，翻译效果更好、训练更快。`,
  '研究': (p) => `【研究视角】${p.title}\n\n核心创新：${p.summary}\n\n需关注：方法设计（纯 Attention 架构）、实验设置（WMT 翻译基准）、与 RNN+Attention 的对比及局限性。`,
  '工程': (p) => `【工程视角】${p.title}\n\n实现要点：Encoder-Decoder 堆叠、Multi-Head Attention、位置编码。\n\n复现难度：中等 · 需 GPU 资源 · 有开源实现可参考。`,
  '教学': (p) => `【教学讲义】${p.title}\n\n课堂要点：① 为什么需要 Self-Attention ② 缩放点积注意力公式 ③ 与 RNN 的优劣对比\n\n讨论题：Transformer 为何能完全替代循环结构？`,
  '管理': (p) => `【管理视角】${p.title}\n\n趋势价值：开创 Transformer 范式，影响 NLP/CV 全领域。\n\n应用前景：机器翻译、文本生成、后续 LLM 基础架构。`
};

const state = {
  loggedIn: false,
  isFirstLogin: false,
  persona: '研究',
  topics: ['cs.CL'],
  currentPaper: 'attention',
  workspaceSearched: false,
  lastSearchQuery: '',
  isAdmin: false,
  paperNotes: {},
  comparePaperA: 'attention',
  comparePaperB: 'bert',
  compareActiveSlot: 'a'
};

const DEFAULT_PAPER_NOTES = {
  attention: {
    notes: [
      { id: 1, highlight: 'Multi-Head Attention 允许模型关注不同表示子空间', text: '核心创新在于完全用注意力替代 RNN，训练并行度大幅提升。', date: '2026-07-01' }
    ],
    comments: [
      { id: 1, text: '这篇是 Transformer 的奠基之作，建议配合 BERT 一起读。', date: '2026-06-28' }
    ]
  },
  bert: {
    notes: [
      { id: 1, highlight: '双向预训练表示', text: '预训练-微调范式的里程碑，与 GPT 单向生成形成对比。', date: '2026-06-18' }
    ],
    comments: []
  }
};

const ADMIN_AGENTS = [
  { id: 'fetch', name: '抓取Agent', health: 'ok', status: '运行中', task: 'arXiv cs.LG 批量抓取', lastActive: '刚刚', latency: '120ms', cpu: '18%', mem: '256MB', processed24h: 342, avgTime: '2.1s', successRate: 99.2, failRate: 0.8 },
  { id: 'read', name: '阅读Agent', health: 'ok', status: '运行中', task: 'GPT-3 PDF 解析', lastActive: '1 分钟前', latency: '340ms', cpu: '42%', mem: '1.2GB', processed24h: 128, avgTime: '8.4s', successRate: 97.5, failRate: 2.5 },
  { id: 'summary', name: '摘要Agent', health: 'warn', status: '运行中', task: 'BERT summary/concept 生成', lastActive: '30 秒前', latency: '1.2s', cpu: '68%', mem: '2.1GB', processed24h: 96, avgTime: '45s', successRate: 94.1, failRate: 5.9 },
  { id: 'verify', name: '校验Agent', health: 'ok', status: '空闲', task: '—', lastActive: '3 分钟前', latency: '210ms', cpu: '8%', mem: '512MB', processed24h: 89, avgTime: '12s', successRate: 91.0, failRate: 9.0 },
  { id: 'qa', name: '问答Agent', health: 'err', status: '异常', task: '队列积压 · 待恢复', lastActive: '12 分钟前', latency: '—', cpu: '—', mem: '—', processed24h: 0, avgTime: '—', successRate: 0, failRate: 100 }
];

const ADMIN_TASKS = [
  { id: 't1', paper: 'bert', title: 'BERT: Pre-training of Deep Bidirectional Transformers', agent: '摘要Agent', status: 'processing', progress: 60, start: '11:02', duration: '3m 20s', log: '[11:02:01] 任务入队\n[11:02:05] 阅读Agent 完成 PDF 解析\n[11:03:12] 摘要Agent 开始生成 summary.md\n[11:05:20] 正在生成 concept.md...' },
  { id: 't2', paper: 'gpt3', title: 'GPT-3: Language Models are Few-Shot Learners', agent: '阅读Agent', status: 'processing', progress: 30, start: '11:08', duration: '1m 45s', log: '[11:08:10] 任务入队\n[11:08:15] 抓取Agent 完成下载\n[11:09:00] 阅读Agent 解析 PDF 第 12/40 页' },
  { id: 't3', paper: 'lora', title: 'LoRA: Low-Rank Adaptation of LLMs', agent: '校验Agent', status: 'processing', progress: 90, start: '10:45', duration: '8m 10s', log: '[10:45:00] 摘要生成完成\n[10:52:30] 校验Agent 开始一致性检查\n[10:53:55] 标记 1 处不确定内容' },
  { id: 't4', paper: 'attention', title: 'Attention Is All You Need', agent: '校验Agent', status: 'done', progress: 100, start: '09:30', duration: '12m 00s', log: '[09:30:00] 全流程完成\n[09:42:00] 校验通过，已入库' },
  { id: 't5', paper: 'rag', title: 'Retrieval-Augmented Generation', agent: '抓取Agent', status: 'pending', progress: 0, start: '—', duration: '—', log: '[11:15:00] 等待抓取队列空闲' },
  { id: 't6', paper: 'vlm', title: 'Vision-Language Model Survey', agent: '问答Agent', status: 'failed', progress: 15, start: '10:20', duration: '2m 30s', log: '[10:20:00] 任务分配至问答Agent\n[10:22:30] Error: Agent 连接超时\n[10:22:30] 任务标记为失败' }
];

const ADMIN_EXCEPTIONS = [
  { id: 'e1', paper: 'bert', title: 'BERT · §4.2 实验结果', type: '数值不一致', detail: '摘要中 F1 分数 (91.2) 与原文 Table 2 (91.8) 不一致', time: '2026-07-09 10:53', status: '待处理', confidence: 58 },
  { id: 'e2', paper: 'gpt3', title: 'GPT-3 · 概念「emergent ability」', type: '概念模糊', detail: '概念定义抽取置信度较低，原文表述模糊', time: '2026-07-09 09:12', status: '待处理', confidence: 62 },
  { id: 'e3', paper: 'lora', title: 'LoRA · methods.md 训练参数', type: '参数不匹配', detail: '学习率数值与原文 Appendix 不完全匹配', time: '2026-07-08 18:40', status: '复核中', confidence: 71 }
];

const ADMIN_ACTIVITY = [
  { text: '已抓取 37 篇新论文（cs.LG / cs.CL）', time: '11:28' },
  { text: '摘要生成完成 12 篇 · 平均耗时 42s', time: '11:15' },
  { text: '校验Agent 标记 3 篇论文需人工复核', time: '10:53' },
  { text: '问答Agent 异常 · 已触发告警', time: '10:22' },
  { text: '用户 admin 重启了摘要Agent', time: '09:45' },
  { text: '今日新增用户 8 人 · 活跃用户 486', time: '09:00' }
];

const ADMIN_TODOS = [
  { text: '3 篇论文校验未通过', action: 'quality', label: '前往质量异常' },
  { text: '2 个任务处理超时', action: 'tasks', label: '查看任务队列' },
  { text: '问答Agent 处于异常状态', action: 'fleet', label: '管理 Agent' }
];

const ADMIN_SUBSCRIPTIONS = [
  { type: '学科', value: 'cs.AI' },
  { type: '学科', value: 'cs.LG' },
  { type: '学科', value: 'cs.CL' },
  { type: '关键词', value: 'Transformer' }
];

const ADMIN_USERS = [
  { email: 'admin@papermate.io', role: '管理员', status: '启用' },
  { email: 'user@example.com', role: '普通用户', status: '启用' },
  { email: 'researcher@lab.edu', role: '高级用户', status: '启用' },
  { email: 'spam@test.com', role: '普通用户', status: '禁用' }
];

const ADMIN_AUDIT_LOGS = [
  { user: 'admin', time: '2026-07-09 09:45', type: '重启Agent', detail: '重启摘要Agent' },
  { user: 'admin', time: '2026-07-08 16:20', type: '人工修正', detail: '修正 Attention 论文 methods.md' },
  { user: 'admin', time: '2026-07-08 14:00', type: '用户管理', detail: '禁用账户 spam@test.com' },
  { user: 'admin', time: '2026-07-07 11:30', type: '订阅变更', detail: '添加学科 cs.AI' }
];

const ADMIN_SYSTEM_LOGS = [
  { level: 'Info', time: '11:28:03', msg: 'FetchAgent: completed batch, 37 papers ingested' },
  { level: 'Info', time: '11:15:22', msg: 'SummaryAgent: batch done, 12 papers summarized' },
  { level: 'Warning', time: '10:53:11', msg: 'VerifyAgent: 3 papers flagged for manual review' },
  { level: 'Error', time: '10:22:30', msg: 'QAAgent: connection timeout, task t6 failed' },
  { level: 'Warning', time: '10:20:05', msg: 'SummaryAgent: high memory usage 2.1GB / 2.5GB limit' },
  { level: 'Info', time: '09:45:18', msg: 'SummaryAgent: restarted by admin' }
];

const ADMIN_STATUS_LABELS = { pending: '待处理', processing: '处理中', done: '已完成', failed: '失败' };

let adminSelectedAgent = null;

/* ===== 工具函数 ===== */
function toast(msg) {
  const el = document.getElementById('wf-toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2200);
}

function enterApp(pageId, opts = {}) {
  document.getElementById('page-login').classList.remove('active');
  document.getElementById('wf-app').classList.remove('wf-hidden');
  document.getElementById('wf-app').style.display = 'flex';
  state.loggedIn = true;
  updateUserBadge();
  updateAdminNav();
  showPage(pageId || 'workspace', opts);
}

function exitApp() {
  document.getElementById('wf-app').classList.add('wf-hidden');
  document.getElementById('wf-app').style.display = 'none';
  document.getElementById('page-login').classList.add('active');
  state.loggedIn = false;
}

function showPage(pageId, opts = {}) {
  document.querySelectorAll('#wf-app .wf-page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.wf-nav-item').forEach(n => n.classList.remove('active'));

  const page = document.getElementById('page-' + pageId);
  if (page) page.classList.add('active');

  const nav = document.querySelector(`.wf-nav-item[data-page="${pageId}"]`);
  if (nav) nav.classList.add('active');

  const meta = PAGE_META[pageId];
  if (meta) {
    document.getElementById('wf-title').textContent = meta.title;
    document.getElementById('wf-subtitle').textContent = meta.subtitle;
  }

  if (pageId === 'workspace' && opts.query) {
    initWorkspaceWithQuery(opts.query);
  }
  if (pageId === 'paper-detail') {
    const pid = opts.paperId || state.currentPaper;
    loadPaperDetail(pid);
  }
}

function updateUserBadge() {
  const role = state.isAdmin ? '管理员' : `画像: ${state.persona}`;
  document.getElementById('user-badge').textContent =
    `${role} · ${state.topics.join(', ')}`;
}

function updateAdminNav() {
  const nav = document.getElementById('nav-agent');
  const note = document.getElementById('admin-nav-note');
  if (!nav) return;
  const show = WIREFRAME_DEMO || state.isAdmin;
  nav.classList.toggle('wf-hidden', !show);
  if (note) {
    note.textContent = WIREFRAME_DEMO
      ? '线框演示中常驻显示 · 正式环境仅管理员可见'
      : (state.isAdmin ? '管理员账户已登录' : '');
    note.classList.toggle('wf-hidden', !WIREFRAME_DEMO && !state.isAdmin);
  }
}

function checkIsAdmin(email) {
  return (email || '').trim().toLowerCase() === 'admin';
}

function loadPaperDetail(paperId) {
  const p = PAPERS[paperId];
  if (!p) return;
  state.currentPaper = paperId;
  const tagsHtml = `<span class="wf-tag">${p.tag}</span> <span class="wf-tag">arXiv:${p.arxiv}</span>`;
  const dateHtml = `${p.date} · <a href="#">[ 原文链接 ]</a>`;

  document.querySelectorAll('.pd-info-tags').forEach(el => { el.innerHTML = tagsHtml; });
  document.querySelectorAll('.pd-info-title').forEach(el => { el.textContent = p.title; });
  document.querySelectorAll('.pd-info-authors').forEach(el => { el.textContent = p.authors; });
  document.querySelectorAll('.pd-info-date').forEach(el => { el.innerHTML = dateHtml; });
  document.querySelectorAll('.pd-info-abstract').forEach(el => { el.textContent = p.summary; });

  const summaryEl = document.getElementById('pd-summary');
  if (summaryEl) summaryEl.textContent = p.summary;

  syncModeBarUI(state.persona);
  updateAssistPanels();
  renderNotesUI(paperId);
  renderPaperWiki(paperId);
  state.comparePaperA = paperId;
  if (state.comparePaperB === paperId) {
    state.comparePaperB = getDefaultCompareTarget(paperId);
  }
  renderComparePanel();
}

const WIKI_MODE_LABELS = {
  all: '综合', title: '标题', author: '作者', keyword: '关键词', direction: '研究方向', concept: '概念标签'
};

let wikiSearchMode = 'all';

function getWikiRelatedScore(a, b) {
  let score = 0;
  if (a.tag === b.tag) score += 2;
  if (a.direction === b.direction) score += 3;
  const kw = new Set((a.keywords || []).map(k => k.toLowerCase()));
  (b.keywords || []).forEach(k => { if (kw.has(k.toLowerCase())) score += 2; });
  const ct = new Set((a.conceptTags || []).map(c => c.toLowerCase()));
  (b.conceptTags || []).forEach(c => { if (ct.has(c.toLowerCase())) score += 3; });
  return score;
}

function collectWikiMatches(paper, mode, query) {
  const matches = [];
  const q = query.toLowerCase();
  const hit = (text) => !q || (text || '').toLowerCase().includes(q);

  if ((mode === 'all' || mode === 'title') && hit(paper.title)) {
    matches.push({ field: 'title', label: '标题', text: paper.title });
  }
  if (mode === 'all' || mode === 'author') {
    paper.authors.split(/,| et al\./).forEach(a => {
      const name = a.trim();
      if (name && hit(name)) matches.push({ field: 'author', label: '作者', text: name });
    });
  }
  if (mode === 'all' || mode === 'keyword') {
    (paper.keywords || []).forEach(k => {
      if (hit(k)) matches.push({ field: 'keyword', label: '关键词', text: k });
    });
  }
  if ((mode === 'all' || mode === 'direction') && paper.direction && hit(paper.direction)) {
    matches.push({ field: 'direction', label: '研究方向', text: paper.direction });
  }
  if (mode === 'all' || mode === 'concept') {
    (paper.conceptTags || []).forEach(c => {
      if (hit(c)) matches.push({ field: 'concept', label: '概念标签', text: c });
    });
  }
  return matches;
}

function searchPaperWiki(query, mode, currentPaperId) {
  const q = (query || '').trim();
  if (!q) {
    const current = PAPERS[currentPaperId];
    if (!current) return [];
    return Object.entries(PAPERS)
      .filter(([id]) => id !== currentPaperId)
      .map(([id, p]) => ({ id, paper: p, matches: collectWikiMatches(p, 'all', ''), score: getWikiRelatedScore(current, p) }))
      .filter(r => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .map(r => ({
        ...r,
        matches: [
          ...(r.paper.direction ? [{ field: 'direction', label: '研究方向', text: r.paper.direction }] : []),
          ...(r.paper.conceptTags || []).slice(0, 2).map(c => ({ field: 'concept', label: '概念标签', text: c }))
        ]
      }));
  }
  return Object.entries(PAPERS)
    .map(([id, p]) => ({ id, paper: p, matches: collectWikiMatches(p, mode, q) }))
    .filter(r => r.matches.length > 0);
}

function renderWikiResultItem(r, currentPaperId) {
  const matchHtml = r.matches.slice(0, 3).map(m =>
    `<span class="pd-wiki-result-match">${m.label}: ${m.text}</span>`
  ).join(' ');
  return `<div class="pd-wiki-result-item${r.id === currentPaperId ? ' current' : ''}" data-paper="${r.id}">
    <div class="pd-wiki-result-title">${r.paper.title}</div>
    <div class="pd-wiki-result-meta">${r.paper.authors} · ${r.paper.tag} · ${r.paper.date}</div>
    <div>${matchHtml}</div>
  </div>`;
}

function renderPaperWikiResults(results, currentPaperId) {
  const el = document.getElementById('pd-wiki-results');
  const countEl = document.getElementById('pd-wiki-count');
  if (!el) return;
  const q = (document.getElementById('pd-wiki-search')?.value || '').trim();
  if (!results.length) {
    el.innerHTML = '<div class="pd-wiki-empty">未找到匹配的 Wiki 条目</div>';
  } else {
    const hint = q ? '' : '<div class="pd-wiki-empty" style="padding:8px;border-bottom:1px dashed var(--wf-border-light);">关联推荐（基于研究方向与概念标签）</div>';
    el.innerHTML = hint + results.map(r => renderWikiResultItem(r, currentPaperId)).join('');
    el.querySelectorAll('.pd-wiki-result-item[data-paper]').forEach(item => {
      item.addEventListener('click', () => {
        if (item.dataset.paper === currentPaperId) return;
        loadPaperDetail(item.dataset.paper);
        renderPaperWiki(item.dataset.paper);
        toast('Wiki 跳转：' + PAPERS[item.dataset.paper]?.title);
      });
    });
  }
  if (countEl) countEl.textContent = results.length + ' 条';
}

function renderPaperWiki(paperId) {
  const p = PAPERS[paperId];
  if (!p) return;
  const tagsEl = document.getElementById('pd-wiki-quick-tags');
  if (tagsEl) {
    let html = '';
    if (p.direction) html += `<button class="pd-wiki-tag direction" data-wiki-q="${p.direction}" data-wiki-mode="direction">${p.direction}</button>`;
    (p.keywords || []).forEach(k => {
      html += `<button class="pd-wiki-tag" data-wiki-q="${k}" data-wiki-mode="keyword">${k}</button>`;
    });
    (p.conceptTags || []).forEach(c => {
      html += `<button class="pd-wiki-tag concept" data-wiki-q="${c}" data-wiki-mode="concept">${c}</button>`;
    });
    const firstAuthor = p.authors.split(',')[0].trim();
    if (firstAuthor) html += `<button class="pd-wiki-tag" data-wiki-q="${firstAuthor}" data-wiki-mode="author">${firstAuthor}</button>`;
    tagsEl.innerHTML = html;
  }
  const searchEl = document.getElementById('pd-wiki-search');
  if (searchEl && document.activeElement !== searchEl) searchEl.value = '';
  runPaperWikiSearch(paperId);
}

function runPaperWikiSearch(paperId) {
  const q = document.getElementById('pd-wiki-search')?.value || '';
  const results = searchPaperWiki(q, wikiSearchMode, paperId || state.currentPaper);
  renderPaperWikiResults(results, paperId || state.currentPaper);
}

function setWikiSearchMode(mode) {
  wikiSearchMode = mode;
  document.querySelectorAll('#pd-wiki-filters .pd-wiki-filter').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.wikiMode === mode);
  });
  runPaperWikiSearch(state.currentPaper);
}

function getPaperNotes(paperId) {
  if (!state.paperNotes[paperId]) {
    state.paperNotes[paperId] = DEFAULT_PAPER_NOTES[paperId]
      ? JSON.parse(JSON.stringify(DEFAULT_PAPER_NOTES[paperId]))
      : { notes: [], comments: [] };
  }
  return state.paperNotes[paperId];
}

function renderNoteCard(note) {
  return `<div class="pd-note-card">
    ${note.highlight ? `<div class="pd-note-highlight">「${note.highlight}」</div>` : ''}
    <div class="pd-note-text">${note.text}</div>
    <div class="pd-note-meta">${note.date}</div>
  </div>`;
}

function renderCommentCard(c) {
  return `<div class="pd-comment-card">
    <div>${c.text}</div>
    <div class="pd-comment-meta">${c.date}</div>
  </div>`;
}

function renderNotesUI(paperId) {
  const data = getPaperNotes(paperId);
  const listEl = document.getElementById('pd-notes-list');
  const commentsEl = document.getElementById('pd-comments-list');
  const previewEl = document.getElementById('pd-notes-preview-all');
  const countEl = document.getElementById('pd-notes-count');

  if (listEl) {
    listEl.innerHTML = data.notes.length
      ? data.notes.map(renderNoteCard).join('')
      : '<p class="pd-notes-preview-empty">暂无笔记，选中文本后添加</p>';
  }
  if (commentsEl) {
    commentsEl.innerHTML = data.comments.length
      ? data.comments.map(renderCommentCard).join('')
      : '<p class="pd-notes-preview-empty">暂无评论</p>';
  }
  if (countEl) countEl.textContent = data.notes.length + ' 条';
  if (previewEl) {
    if (!data.notes.length && !data.comments.length) {
      previewEl.innerHTML = '<p class="pd-notes-preview-empty">暂无笔记与评论</p>';
    } else {
      let html = '';
      if (data.notes.length) {
        html += renderNoteCard(data.notes[0]);
        if (data.notes.length > 1) html += `<p class="wf-annotation">还有 ${data.notes.length - 1} 条笔记...</p>`;
      }
      if (data.comments.length) {
        html += renderCommentCard(data.comments[0]);
      }
      previewEl.innerHTML = html;
    }
  }
}

function switchSidebarTab(side, opts = {}) {
  document.getElementById('pd-sidebar-tabs').querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.pd-side-panel').forEach(p => p.classList.remove('active'));
  const tab = document.querySelector(`#pd-sidebar-tabs [data-pdside="${side}"]`);
  if (tab) tab.classList.add('active');
  const panel = document.getElementById('pdside-' + side);
  if (panel) panel.classList.add('active');
  if (opts.toast) toast(opts.toast);
}

const PDSIDE_LABELS = { all: '全部', info: '信息', qa: '问答', assist: '辅助', notes: '笔记', compare: '对比阅读' };

function getDefaultCompareTarget(paperId) {
  const related = searchPaperWiki('', 'all', paperId);
  if (related.length) return related[0].id;
  const ids = Object.keys(PAPERS).filter(id => id !== paperId);
  return ids[0] || paperId;
}

function shortPaperTitle(paperId) {
  const t = PAPERS[paperId]?.title || '';
  const idx = t.indexOf(':');
  return idx > 0 ? t.slice(0, idx) : (t.length > 28 ? t.slice(0, 28) + '…' : t);
}

function renderCompareSelects() {
  const opts = Object.entries(PAPERS).map(([id, p]) =>
    `<option value="${id}">${shortPaperTitle(id)}</option>`
  ).join('');
  const selA = document.getElementById('pd-compare-select-a');
  const selB = document.getElementById('pd-compare-select-b');
  if (selA) { selA.innerHTML = opts; selA.value = state.comparePaperA; }
  if (selB) { selB.innerHTML = opts; selB.value = state.comparePaperB; }
}

function renderCompareQuickList() {
  const el = document.getElementById('pd-compare-quick');
  if (!el) return;
  el.innerHTML = Object.keys(PAPERS).map(id => {
    const inA = id === state.comparePaperA;
    const inB = id === state.comparePaperB;
    const cls = ['pd-compare-chip', inA ? 'in-a' : '', inB ? 'in-b' : ''].filter(Boolean).join(' ');
    return `<button class="${cls}" data-paper="${id}">${shortPaperTitle(id)}</button>`;
  }).join('');
}

function renderCompareBody() {
  const el = document.getElementById('pd-compare-body');
  if (!el) return;
  const a = PAPERS[state.comparePaperA];
  const b = PAPERS[state.comparePaperB];
  if (!a || !b) return;

  const rows = [
    { label: '标题', a: a.title, b: b.title },
    { label: '作者', a: a.authors, b: b.authors },
    { label: '学科', a: a.tag, b: b.tag },
    { label: '研究方向', a: a.direction || '—', b: b.direction || '—' },
    { label: '关键词', a: (a.keywords || []).join(' · ') || '—', b: (b.keywords || []).join(' · ') || '—' },
    { label: '概念标签', a: (a.conceptTags || []).join(' · ') || '—', b: (b.conceptTags || []).join(' · ') || '—' },
    { label: '摘要', a: a.summary, b: b.summary }
  ];

  el.innerHTML = rows.map(r => `
    <div class="pd-compare-row">
      <div class="pd-compare-row-label">${r.label}</div>
      <div class="pd-compare-cols">
        <div class="pd-compare-col${r.a === r.b ? '' : ' diff'}">
          <span class="pd-compare-col-tag">A</span>${r.a}
        </div>
        <div class="pd-compare-col${r.a === r.b ? '' : ' diff'}">
          <span class="pd-compare-col-tag">B</span>${r.b}
        </div>
      </div>
    </div>
  `).join('');
}

function renderComparePreview() {
  const el = document.getElementById('pd-compare-preview-all');
  if (!el) return;
  const a = shortPaperTitle(state.comparePaperA);
  const b = shortPaperTitle(state.comparePaperB);
  el.innerHTML = `<p class="pd-compare-preview-text"><span class="pd-compare-col-tag">A</span> ${a}</p>
    <p class="pd-compare-preview-text"><span class="pd-compare-col-tag">B</span> ${b}</p>`;
}

function renderComparePanel() {
  renderCompareSelects();
  renderCompareQuickList();
  renderCompareBody();
  renderComparePreview();
  document.querySelectorAll('#pd-compare-slots .pd-compare-slot').forEach(slot => {
    slot.classList.toggle('active', slot.dataset.slot === state.compareActiveSlot);
  });
}

function setCompareSlot(slot) {
  state.compareActiveSlot = slot;
  document.querySelectorAll('#pd-compare-slots .pd-compare-slot').forEach(el => {
    el.classList.toggle('active', el.dataset.slot === slot);
  });
}

function setComparePaper(slot, paperId) {
  if (slot === 'a') {
    state.comparePaperA = paperId;
    if (state.comparePaperB === paperId) state.comparePaperB = getDefaultCompareTarget(paperId);
  } else {
    state.comparePaperB = paperId;
    if (state.comparePaperA === paperId) state.comparePaperA = getDefaultCompareTarget(paperId);
  }
  renderComparePanel();
}

function swapComparePapers() {
  const tmp = state.comparePaperA;
  state.comparePaperA = state.comparePaperB;
  state.comparePaperB = tmp;
  renderComparePanel();
  toast('已互换对比论文');
}

function syncModeBarUI(persona) {
  document.querySelectorAll('#learn-mode-bar, #pd-mode-bar').forEach(bar => {
    bar.querySelectorAll('.wf-mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.persona === persona);
    });
  });
  ['pd-mode-badge', 'pd-mode-badge-all'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = persona + '模式';
  });
}

function setPersona(persona) {
  state.persona = persona;
  updateUserBadge();
  syncModeBarUI(persona);
  updateAssistPanels();
  const desc = document.getElementById('learn-mode-desc');
  if (desc) desc.textContent = MODE_DESC[persona] || '';
}

function updateAssistPanels() {
  const p = PAPERS[state.currentPaper];
  if (!p) return;
  const fn = MODE_ASSIST[state.persona] || MODE_ASSIST['研究'];
  const text = fn(p);
  ['pd-assist-content', 'pd-assist-content-all'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  });
}

function bindPersonaBars() {
  document.querySelectorAll('#learn-mode-bar, #pd-mode-bar').forEach(bar => {
    bar.querySelectorAll('.wf-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        setPersona(btn.dataset.persona);
        toast(`已切换至${btn.dataset.persona}模式`);
      });
    });
  });
}

function addChatBubble(containerId, text, role) {
  const container = document.getElementById(containerId);
  const bubble = document.createElement('div');
  bubble.className = `wf-bubble ${role}`;
  bubble.style.maxWidth = role === 'user' ? '80%' : '90%';
  bubble.style.fontSize = '12px';
  bubble.style.marginBottom = '6px';
  if (role === 'user') bubble.style.alignSelf = 'flex-end';
  bubble.textContent = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function mockWorkspaceReply(query) {
  const q = query.toLowerCase();
  if (q.includes('transformer') || q.includes('attention'))
    return '找到 3 篇 Transformer 相关论文，已更新下方列表。您可以继续追问，例如"BERT和GPT的区别"。';
  if (q.includes('bert') && q.includes('gpt'))
    return 'BERT 是双向编码器预训练，GPT 是单向生成式预训练。已为您筛选相关论文。';
  if (q.includes('lora') || q.includes('微调'))
    return '推荐 LoRA 等参数高效微调论文，列表已更新。';
  return `已理解您的问题"${query}"，为您检索到 ${Math.floor(Math.random() * 3) + 2} 篇相关论文。可继续追问。`;
}

function mockPaperReply(query, paperId) {
  const p = PAPERS[paperId];
  return `【基于《${p.title}》】针对"${query}"的回答占位。出处：摘要 / 核心概念。校验Agent：高置信度。`;
}

function getSearchResultIds(query) {
  const q = query.toLowerCase();
  if (q.includes('transformer') || q.includes('attention')) return ['attention', 'bert', 'gpt3'];
  if (q.includes('bert') && q.includes('gpt')) return ['bert', 'gpt3'];
  if (q.includes('lora') || q.includes('微调')) return ['lora', 'bert'];
  if (q.includes('rag') || q.includes('检索')) return ['rag', 'bert', 'attention'];
  if (q.includes('vision') || q.includes('vlm')) return ['vlm', 'attention'];
  return ['attention', 'bert', 'lora', 'rag'];
}

function renderPaperListItem(paperId) {
  const p = PAPERS[paperId];
  if (!p) return '';
  return `<div class="wf-list-item wf-paper-card" data-paper="${paperId}">
    <div class="wf-img-placeholder" style="width:50px;height:50px;flex-shrink:0;">PDF</div>
    <div style="flex:1;">
      <span class="wf-tag">${p.tag}</span>
      <div class="wf-card-title">${p.title}</div>
      <div class="wf-card-meta">${p.authors} · ${p.date} · arXiv:${p.arxiv}</div>
      <div class="wf-card-body">${p.summary}</div>
    </div>
  </div>`;
}

function renderSearchResults(query) {
  const ids = getSearchResultIds(query);
  document.getElementById('ws-paper-list').innerHTML = ids.map(renderPaperListItem).join('');
  document.getElementById('ws-result-count').textContent = ids.length + ' 篇';
}

function switchToSearchResults(query) {
  const recommend = document.getElementById('ws-recommend');
  if (recommend) recommend.remove();
  const results = document.getElementById('ws-search-results');
  results.classList.remove('wf-hidden');
  renderSearchResults(query);
  state.workspaceSearched = true;
}

function initWorkspaceWithQuery(query) {
  if (!query) return;
  state.lastSearchQuery = query;
  document.getElementById('ws-chat-input').value = '';
  addChatBubble('ws-chat-messages', query, 'user');
  setTimeout(() => {
    addChatBubble('ws-chat-messages', mockWorkspaceReply(query), 'bot');
    switchToSearchResults(query);
    toast('已快速抓取相关论文，展示检索结果');
  }, 300);
}

function sendWorkspaceMessage() {
  const input = document.getElementById('ws-chat-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  state.lastSearchQuery = text;
  addChatBubble('ws-chat-messages', text, 'user');

  if (!state.workspaceSearched) {
    switchToSearchResults(text);
  } else {
    renderSearchResults(text);
  }

  setTimeout(() => {
    addChatBubble('ws-chat-messages', mockWorkspaceReply(text), 'bot');
  }, 400);
}

function sendPaperChatMessage(fromInput) {
  const input = fromInput || document.getElementById('pd-chat-input');
  const text = input.value.trim();
  if (!text) return;
  const fromAll = fromInput && fromInput.id === 'pd-chat-input-all';
  input.value = '';
  if (fromAll) {
    document.getElementById('pd-chat-input').value = '';
  } else if (fromInput && fromInput.id === 'pd-chat-input') {
    const other = document.getElementById('pd-chat-input-all');
    if (other) other.value = '';
  }
  ['pd-chat-messages', 'pd-chat-messages-all'].forEach(id => {
    addChatBubble(id, text, 'user');
  });
  setTimeout(() => {
    const reply = mockPaperReply(text, state.currentPaper);
    ['pd-chat-messages', 'pd-chat-messages-all'].forEach(id => {
      addChatBubble(id, reply, 'bot');
    });
    if (fromAll) {
      switchSidebarTab('qa', { toast: '已展开智能问答' });
    }
  }, 400);
}

function switchSubview(tabBarId, attr, targetPrefix) {
  const tabBar = document.getElementById(tabBarId);
  if (!tabBar) return;
  tabBar.querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      tabBar.querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const key = tab.dataset[attr];
      document.querySelectorAll(`[id^="${targetPrefix}"]`).forEach(v => v.classList.remove('active'));
      const target = document.getElementById(`${targetPrefix}${key}`);
      if (target) target.classList.add('active');
    });
  });
}

function renderHistoryCards(period) {
  const data = READING_HISTORY[period];
  if (!data) return;
  document.getElementById('history-panel-title').textContent = data.label;
  const list = document.getElementById('history-cards-list');
  list.innerHTML = data.items.map(item => {
    const p = PAPERS[item.paper];
    return `<div class="wf-paper-card-compact" data-paper="${item.paper}">
      <div class="compact-thumb">PDF</div>
      <div class="compact-info">
        <div class="compact-title">${p.title}</div>
        <div class="compact-meta">${item.time} · ${item.section} · ${item.duration}</div>
      </div>
      <span class="wf-tag">${p.tag}</span>
    </div>`;
  }).join('');
  list.querySelectorAll('.wf-paper-card-compact').forEach(card => {
    card.addEventListener('click', () => {
      showPage('paper-detail', { paperId: card.dataset.paper });
      toast(`打开：${PAPERS[card.dataset.paper]?.title}`);
    });
  });
}

function switchAdminModule(module) {
  document.getElementById('admin-tabs').querySelectorAll('.wf-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.admin === module);
  });
  document.querySelectorAll('[id^="admin-"]').forEach(v => {
    if (v.classList.contains('wf-subview') && v.id.startsWith('admin-') && v.id !== 'admin-tabs') {
      v.classList.remove('active');
    }
  });
  const panel = document.getElementById('admin-' + module);
  if (panel) panel.classList.add('active');
}

function renderAdminHealth() {
  const el = document.getElementById('admin-health-list');
  if (!el) return;
  el.innerHTML = ADMIN_AGENTS.map(a => `
    <div class="admin-health-item">
      <span class="admin-status-dot ${a.health}"></span>
      <div>
        <strong>${a.name}</strong>
        <div style="font-size:10px;color:var(--wf-muted);margin-top:2px;">${a.status} · ${a.task}</div>
      </div>
      <div class="admin-health-meta">延迟 ${a.latency}<br>CPU ${a.cpu} · 内存 ${a.mem}</div>
    </div>
  `).join('');
}

function renderAdminTodos() {
  const el = document.getElementById('admin-todo-list');
  if (!el) return;
  el.innerHTML = ADMIN_TODOS.map(t => `
    <div class="admin-todo-card" data-admin-goto="${t.action}">
      <strong>${t.text}</strong>
      <span class="wf-annotation">${t.label} →</span>
    </div>
  `).join('');
  el.querySelectorAll('[data-admin-goto]').forEach(card => {
    card.addEventListener('click', () => {
      switchAdminModule(card.dataset.adminGoto);
      toast('已跳转：' + card.querySelector('.wf-annotation').textContent.replace(' →', ''));
    });
  });
}

function renderAdminActivity() {
  const el = document.getElementById('admin-activity-feed');
  if (!el) return;
  const items = ADMIN_ACTIVITY.map(a => `
    <div class="admin-activity-item"><span>${a.text}</span><time>${a.time}</time></div>
  `).join('');
  el.innerHTML = items;
}

function renderAdminAgents() {
  const tbody = document.getElementById('admin-agent-tbody');
  if (!tbody) return;
  tbody.innerHTML = ADMIN_AGENTS.map(a => `
    <tr class="admin-row-clickable" data-agent-id="${a.id}">
      <td><span class="admin-agent-status"><span class="admin-status-dot ${a.health}"></span>${a.name}</span></td>
      <td>${a.status}</td>
      <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${a.task}</td>
      <td>${a.lastActive}</td>
      <td class="admin-ops-btns" onclick="event.stopPropagation()">
        <button class="wf-btn sm admin-agent-op" data-op="restart" data-id="${a.id}">重启</button>
        <button class="wf-btn sm admin-agent-op" data-op="stop" data-id="${a.id}">停止</button>
        <button class="wf-btn sm admin-agent-op" data-op="log" data-id="${a.id}">日志</button>
      </td>
    </tr>
  `).join('');
}

function showAgentDetail(agentId) {
  const a = ADMIN_AGENTS.find(x => x.id === agentId);
  if (!a) return;
  adminSelectedAgent = agentId;
  document.querySelectorAll('#admin-agent-tbody tr').forEach(tr => {
    tr.classList.toggle('admin-row-active', tr.dataset.agentId === agentId);
  });
  const body = document.getElementById('admin-agent-detail-body');
  if (!body) return;
  body.className = 'admin-detail-metrics';
  body.innerHTML = `
    <p class="wf-label">${a.name} · 过去 24 小时</p>
    <div class="admin-metric-row"><span>处理量</span><strong>${a.processed24h} 篇</strong></div>
    <div class="admin-metric-row"><span>平均耗时</span><strong>${a.avgTime}</strong></div>
    <div class="admin-metric-row"><span>成功率</span><strong>${a.successRate}%</strong></div>
    <div class="admin-metric-row"><span>失败率</span><strong>${a.failRate}%</strong></div>
    <div class="admin-metric-row"><span>当前状态</span><strong>${a.status}</strong></div>
    <p class="wf-annotation" style="margin-top:12px;">延迟 ${a.latency} · CPU ${a.cpu} · 内存 ${a.mem}</p>
  `;
}

function renderAdminKanban() {
  const el = document.getElementById('admin-kanban');
  if (!el) return;
  const cols = [
    { key: 'pending', label: '待处理' },
    { key: 'processing', label: '处理中' },
    { key: 'done', label: '已完成' },
    { key: 'failed', label: '失败' }
  ];
  el.innerHTML = cols.map(c => {
    const tasks = ADMIN_TASKS.filter(t => t.status === c.key);
    const sample = tasks.slice(0, 2).map(t => t.title.split(':')[0]).join('、') || '—';
    return `<div class="admin-kanban-col ${c.key}">
      <h4>${c.label}</h4>
      <div class="admin-kanban-count">${tasks.length}</div>
      <div class="admin-kanban-sample">${sample}</div>
    </div>`;
  }).join('');
}

function renderAdminTasks(filter = 'all', sort = 'start') {
  const tbody = document.getElementById('admin-task-tbody');
  if (!tbody) return;
  let tasks = [...ADMIN_TASKS];
  if (filter !== 'all') tasks = tasks.filter(t => t.status === filter);
  if (sort === 'duration') {
    tasks.sort((a, b) => (b.progress || 0) - (a.progress || 0));
  }
  tbody.innerHTML = tasks.map(t => `
    <tr>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${t.title}</td>
      <td>${t.agent}</td>
      <td><span class="wf-tag">${ADMIN_STATUS_LABELS[t.status]}</span></td>
      <td><div class="wf-progress"><div class="wf-progress-bar" style="width:${t.progress}%"></div></div>${t.progress}%</td>
      <td>${t.start}</td>
      <td>${t.duration}</td>
      <td><button class="wf-btn sm admin-task-log" data-task-id="${t.id}">日志</button></td>
    </tr>
  `).join('');
}

function openTaskLog(taskId) {
  const t = ADMIN_TASKS.find(x => x.id === taskId);
  if (!t) return;
  document.getElementById('admin-task-modal-title').textContent = '任务日志 · ' + t.title.split(':')[0];
  document.getElementById('admin-task-modal-body').textContent = t.log;
  document.getElementById('admin-task-modal').classList.remove('hidden');
}

function renderAdminExceptions() {
  const el = document.getElementById('admin-exception-list');
  if (!el) return;
  el.innerHTML = ADMIN_EXCEPTIONS.map(e => `
    <div class="admin-exception-item" data-exc-id="${e.id}">
      <div class="wf-card-title">${e.title}</div>
      <div class="wf-card-body">${e.detail}</div>
      <div class="wf-card-meta">${e.type} · 置信度 ${e.confidence}% · ${e.time} · ${e.status}</div>
      <button class="wf-btn sm admin-fix-paper" data-paper="${e.paper}" style="margin-top:6px;">[ 人工修正 ]</button>
    </div>
  `).join('');
}

function renderAdminCharts() {
  const errorData = [
    { label: '抓取', val: 0.8 },
    { label: '阅读', val: 2.5 },
    { label: '摘要', val: 5.9 },
    { label: '校验', val: 9.0 },
    { label: '问答', val: 12.0 }
  ];
  const excData = [
    { label: '数值不一致', val: 38 },
    { label: '概念模糊', val: 27 },
    { label: '参数不匹配', val: 22 },
    { label: '引用缺失', val: 13 }
  ];
  const renderBars = (data, maxVal) => data.map(d => `
    <div class="admin-bar-row">
      <span class="admin-bar-label">${d.label}</span>
      <div class="admin-bar-track"><div class="admin-bar-fill" style="width:${(d.val / maxVal) * 100}%"></div></div>
      <span class="admin-bar-val">${d.val}${maxVal <= 15 ? '%' : ''}</span>
    </div>
  `).join('');
  const errEl = document.getElementById('admin-error-chart');
  const excEl = document.getElementById('admin-exception-chart');
  if (errEl) errEl.innerHTML = renderBars(errorData, 15);
  if (excEl) excEl.innerHTML = renderBars(excData, 40);
}

function renderAdminSubscriptions() {
  const tbody = document.getElementById('admin-sub-table');
  if (!tbody) return;
  tbody.innerHTML = ADMIN_SUBSCRIPTIONS.map((s, i) => `
    <tr><td>${s.type}</td><td>${s.value}</td>
    <td><button class="wf-btn sm admin-sub-del" data-idx="${i}">删</button></td></tr>
  `).join('');
}

function renderAdminUsers() {
  const tbody = document.getElementById('admin-user-table');
  if (!tbody) return;
  tbody.innerHTML = ADMIN_USERS.map((u, i) => `
    <tr>
      <td>${u.email}</td>
      <td>
        <select class="wf-select sm admin-user-role" data-idx="${i}">
          <option${u.role === '普通用户' ? ' selected' : ''}>普通用户</option>
          <option${u.role === '高级用户' ? ' selected' : ''}>高级用户</option>
          <option${u.role === '管理员' ? ' selected' : ''}>管理员</option>
        </select>
      </td>
      <td>${u.status}</td>
      <td>
        <button class="wf-btn sm admin-user-toggle" data-idx="${i}">${u.status === '启用' ? '禁用' : '启用'}</button>
      </td>
    </tr>
  `).join('');
}

function renderAdminAuditLogs(userFilter = '', typeFilter = '') {
  const el = document.getElementById('admin-audit-list');
  if (!el) return;
  let logs = ADMIN_AUDIT_LOGS;
  if (userFilter) logs = logs.filter(l => l.user.includes(userFilter));
  if (typeFilter) logs = logs.filter(l => l.type === typeFilter);
  el.innerHTML = logs.length
    ? logs.map(l => `<div class="admin-log-entry"><div>${l.detail}</div><div class="log-meta">${l.user} · ${l.time} · ${l.type}</div></div>`).join('')
    : '<div class="admin-log-entry"><div class="wf-annotation">无匹配记录</div></div>';
}

function renderAdminSysLogs(levelFilter = '', keyword = '') {
  const el = document.getElementById('admin-syslog-list');
  if (!el) return;
  let logs = ADMIN_SYSTEM_LOGS;
  if (levelFilter) logs = logs.filter(l => l.level === levelFilter);
  if (keyword) logs = logs.filter(l => l.msg.toLowerCase().includes(keyword.toLowerCase()));
  el.innerHTML = logs.length
    ? logs.map(l => `<div class="admin-log-entry level-${l.level}">[${l.level}] ${l.time} ${l.msg}</div>`).join('')
    : '<div class="admin-log-entry"><span class="wf-annotation">无匹配日志</span></div>';
}

function initAdminPage() {
  renderAdminHealth();
  renderAdminTodos();
  renderAdminActivity();
  renderAdminAgents();
  renderAdminKanban();
  renderAdminTasks();
  renderAdminExceptions();
  renderAdminCharts();
  renderAdminSubscriptions();
  renderAdminUsers();
  renderAdminAuditLogs();
  renderAdminSysLogs();

  document.getElementById('admin-tabs').querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      switchAdminModule(tab.dataset.admin);
      const labels = { overview: '系统概览', fleet: 'Agent舰队', tasks: '任务队列', quality: '质量异常', config: '配置治理', audit: '审计日志' };
      toast('模块：' + (labels[tab.dataset.admin] || ''));
    });
  });

  document.getElementById('admin-agent-tbody').addEventListener('click', e => {
    const btn = e.target.closest('.admin-agent-op');
    if (btn) {
      e.stopPropagation();
      const a = ADMIN_AGENTS.find(x => x.id === btn.dataset.id);
      const ops = { restart: '已重启', stop: '已停止', log: '日志已加载' };
      toast(`${a.name}：${ops[btn.dataset.op]}`);
      if (btn.dataset.op === 'log') {
        document.getElementById('admin-task-modal-title').textContent = a.name + ' · 运行日志';
        document.getElementById('admin-task-modal-body').textContent =
          `[${a.lastActive}] status=${a.status}\nlatency=${a.latency} cpu=${a.cpu} mem=${a.mem}\nprocessed_24h=${a.processed24h} success=${a.successRate}%`;
        document.getElementById('admin-task-modal').classList.remove('hidden');
      }
      return;
    }
    const row = e.target.closest('[data-agent-id]');
    if (row) showAgentDetail(row.dataset.agentId);
  });

  document.getElementById('admin-task-filter').addEventListener('change', e => {
    renderAdminTasks(e.target.value, document.getElementById('admin-task-sort').value);
  });
  document.getElementById('admin-task-sort').addEventListener('change', e => {
    renderAdminTasks(document.getElementById('admin-task-filter').value, e.target.value);
  });

  document.getElementById('admin-task-tbody').addEventListener('click', e => {
    const btn = e.target.closest('.admin-task-log');
    if (btn) openTaskLog(btn.dataset.taskId);
  });

  document.getElementById('admin-exception-list').addEventListener('click', e => {
    const btn = e.target.closest('.admin-fix-paper');
    if (!btn) return;
    const item = btn.closest('.admin-exception-item');
    showPage('paper-detail', { paperId: btn.dataset.paper });
    btn.textContent = '[ 已跳转修正 ]';
    btn.disabled = true;
    if (item) item.style.opacity = '0.6';
    toast('已跳转论文详情，可编辑 summary/concept/methods');
  });

  document.getElementById('admin-sub-add').addEventListener('click', () => {
    const val = document.getElementById('admin-sub-new').value.trim();
    if (!val) return;
    const type = document.getElementById('admin-sub-type').value;
    ADMIN_SUBSCRIPTIONS.push({ type, value: val });
    renderAdminSubscriptions();
    document.getElementById('admin-sub-new').value = '';
    toast('已添加订阅：' + val);
  });

  document.getElementById('admin-sub-table').addEventListener('click', e => {
    const btn = e.target.closest('.admin-sub-del');
    if (!btn) return;
    ADMIN_SUBSCRIPTIONS.splice(+btn.dataset.idx, 1);
    renderAdminSubscriptions();
    toast('已删除订阅规则');
  });

  document.getElementById('admin-user-table').addEventListener('click', e => {
    const btn = e.target.closest('.admin-user-toggle');
    if (!btn) return;
    const u = ADMIN_USERS[+btn.dataset.idx];
    u.status = u.status === '启用' ? '禁用' : '启用';
    renderAdminUsers();
    toast(`${u.email} 已${u.status}`);
  });

  document.getElementById('admin-user-table').addEventListener('change', e => {
    const sel = e.target.closest('.admin-user-role');
    if (!sel) return;
    ADMIN_USERS[+sel.dataset.idx].role = sel.value;
    toast('角色已更新：' + sel.value);
  });

  document.getElementById('audit-filter-user').addEventListener('input', e => {
    renderAdminAuditLogs(e.target.value, document.getElementById('audit-filter-type').value);
  });
  document.getElementById('audit-filter-type').addEventListener('change', e => {
    renderAdminAuditLogs(document.getElementById('audit-filter-user').value, e.target.value);
  });

  document.getElementById('syslog-filter-level').addEventListener('change', e => {
    renderAdminSysLogs(e.target.value, document.getElementById('syslog-search').value);
  });
  document.getElementById('syslog-search').addEventListener('input', e => {
    renderAdminSysLogs(document.getElementById('syslog-filter-level').value, e.target.value);
  });

  document.getElementById('admin-task-modal-close').addEventListener('click', () => {
    document.getElementById('admin-task-modal').classList.add('hidden');
  });
  document.getElementById('admin-task-modal').addEventListener('click', e => {
    if (e.target.id === 'admin-task-modal') e.target.classList.add('hidden');
  });
}

/* ===== 初始化 ===== */
document.addEventListener('DOMContentLoaded', () => {

  /* --- 页面一：登录/注册 --- */
  document.getElementById('auth-tabs').querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.getElementById('auth-tabs').querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const isLogin = tab.dataset.auth === 'login';
      document.getElementById('auth-login').classList.toggle('wf-hidden', !isLogin);
      document.getElementById('auth-register').classList.toggle('wf-hidden', isLogin);
    });
  });

  document.getElementById('btn-login').addEventListener('click', () => {
    const email = document.getElementById('login-email').value.trim();
    state.isAdmin = checkIsAdmin(email);
    enterApp('workspace');
    toast(state.isAdmin ? '管理员登录成功 → 工作空间' : '登录成功 → 工作空间');
  });

  document.getElementById('btn-register').addEventListener('click', () => {
    state.isFirstLogin = true;
    document.getElementById('onboarding-overlay').classList.remove('hidden');
  });

  document.getElementById('onboard-topics').querySelectorAll('.wf-topic-btn').forEach(btn => {
    btn.classList.add('active');
    btn.addEventListener('click', () => {
      btn.classList.toggle('active');
      const topic = btn.dataset.topic;
      if (btn.classList.contains('active')) {
        if (!state.topics.includes(topic)) state.topics.push(topic);
      } else {
        state.topics = state.topics.filter(t => t !== topic);
      }
      if (state.topics.length === 0) { state.topics = [topic]; btn.classList.add('active'); }
    });
  });

  document.getElementById('onboard-persona').querySelectorAll('.wf-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('onboard-persona').querySelectorAll('.wf-mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.persona = btn.dataset.persona;
    });
  });

  document.getElementById('btn-onboard-done').addEventListener('click', () => {
    document.getElementById('onboarding-overlay').classList.add('hidden');
    enterApp('workspace');
    toast('首次引导完成 → 工作空间');
  });

  document.getElementById('btn-logout').addEventListener('click', () => {
    exitApp();
    location.reload();
  });

  /* --- 页面二：工作空间 --- */
  document.getElementById('ws-chat-send').addEventListener('click', sendWorkspaceMessage);
  document.getElementById('ws-chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') sendWorkspaceMessage();
  });

  document.getElementById('page-workspace').addEventListener('click', e => {
    const card = e.target.closest('.wf-paper-card');
    if (!card || !card.dataset.paper) return;
    showPage('paper-detail', { paperId: card.dataset.paper });
    toast(`打开：${PAPERS[card.dataset.paper]?.title}`);
  });

  /* --- 页面三：论文详情 --- */
  document.getElementById('pd-view-tabs').querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.getElementById('pd-view-tabs').querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('[id^="pdview-"]').forEach(v => v.classList.remove('active'));
      document.getElementById('pdview-' + tab.dataset.pdview).classList.add('active');
      const labels = { content: 'a·论文主体', summary: 'b·智能总结', graph: 'c·知识图谱&脉络' };
      toast('切换至 ' + (labels[tab.dataset.pdview] || ''));
    });
  });

  document.getElementById('pd-sidebar-tabs').querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      switchSidebarTab(tab.dataset.pdside);
    });
  });

  document.getElementById('pdside-all').addEventListener('click', e => {
    const section = e.target.closest('.pd-side-jump');
    if (!section) return;
    if (e.target.closest('button, input, textarea, a, .wf-chat-input-row')) return;
    const side = section.dataset.pdside;
    if (!side) return;
    switchSidebarTab(side, { toast: '已展开' + (PDSIDE_LABELS[side] || '') });
  });

  document.getElementById('pd-wiki-filters').addEventListener('click', e => {
    const btn = e.target.closest('.pd-wiki-filter');
    if (!btn) return;
    setWikiSearchMode(btn.dataset.wikiMode);
    toast('检索维度：' + (WIKI_MODE_LABELS[btn.dataset.wikiMode] || ''));
  });

  document.getElementById('pd-wiki-search-btn').addEventListener('click', () => {
    runPaperWikiSearch(state.currentPaper);
    toast('Wiki 检索完成');
  });
  document.getElementById('pd-wiki-search').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      runPaperWikiSearch(state.currentPaper);
      toast('Wiki 检索完成');
    }
  });
  document.getElementById('pd-wiki-search').addEventListener('input', () => {
    runPaperWikiSearch(state.currentPaper);
  });

  document.getElementById('pd-wiki-quick-tags').addEventListener('click', e => {
    const tag = e.target.closest('.pd-wiki-tag');
    if (!tag) return;
    setWikiSearchMode(tag.dataset.wikiMode || 'all');
    const input = document.getElementById('pd-wiki-search');
    input.value = tag.dataset.wikiQ;
    runPaperWikiSearch(state.currentPaper);
    toast('Wiki 检索：' + tag.dataset.wikiQ);
  });

  document.getElementById('pd-compare-slots').addEventListener('click', e => {
    const slot = e.target.closest('.pd-compare-slot');
    if (!slot || e.target.closest('select')) return;
    setCompareSlot(slot.dataset.slot);
  });
  document.getElementById('pd-compare-select-a').addEventListener('change', e => {
    setComparePaper('a', e.target.value);
    toast('论文 A：' + shortPaperTitle(e.target.value));
  });
  document.getElementById('pd-compare-select-b').addEventListener('change', e => {
    setComparePaper('b', e.target.value);
    toast('论文 B：' + shortPaperTitle(e.target.value));
  });
  document.getElementById('pd-compare-quick').addEventListener('click', e => {
    const chip = e.target.closest('.pd-compare-chip');
    if (!chip) return;
    setComparePaper(state.compareActiveSlot, chip.dataset.paper);
    toast(`论文 ${state.compareActiveSlot.toUpperCase()}：` + shortPaperTitle(chip.dataset.paper));
  });
  document.getElementById('pd-compare-swap').addEventListener('click', swapComparePapers);
  document.getElementById('pd-compare-open-a').addEventListener('click', () => {
    loadPaperDetail(state.comparePaperA);
    toast('当前阅读：' + PAPERS[state.comparePaperA]?.title);
  });
  document.getElementById('pd-compare-open-b').addEventListener('click', () => {
    loadPaperDetail(state.comparePaperB);
    toast('当前阅读：' + PAPERS[state.comparePaperB]?.title);
  });

  document.getElementById('pd-note-save').addEventListener('click', () => {
    const text = document.getElementById('pd-note-input').value.trim();
    if (!text) { toast('请输入笔记内容'); return; }
    const data = getPaperNotes(state.currentPaper);
    const today = '2026-07-09';
    data.notes.unshift({
      id: Date.now(),
      highlight: 'Multi-Head Attention 允许模型关注不同表示子空间...',
      text,
      date: today
    });
    document.getElementById('pd-note-input').value = '';
    renderNotesUI(state.currentPaper);
    toast('笔记已保存');
  });

  document.getElementById('pd-comment-add').addEventListener('click', () => {
    const input = document.getElementById('pd-comment-input');
    const text = input.value.trim();
    if (!text) return;
    const data = getPaperNotes(state.currentPaper);
    data.comments.unshift({ id: Date.now(), text, date: '2026-07-09' });
    input.value = '';
    renderNotesUI(state.currentPaper);
    toast('评论已发表');
  });
  document.getElementById('pd-comment-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('pd-comment-add').click();
  });

  document.querySelectorAll('.pd-chat-send').forEach(btn => {
    btn.addEventListener('click', () => {
      const inputId = btn.dataset.target === 'all' ? 'pd-chat-input-all' : 'pd-chat-input';
      sendPaperChatMessage(document.getElementById(inputId));
    });
  });
  document.getElementById('pd-chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') sendPaperChatMessage(document.getElementById('pd-chat-input'));
  });
  document.getElementById('pd-chat-input-all').addEventListener('keydown', e => {
    if (e.key === 'Enter') sendPaperChatMessage(document.getElementById('pd-chat-input-all'));
  });

  document.getElementById('btn-collect').addEventListener('click', () => toast('已收藏至学习空间'));
  document.getElementById('btn-collect-info').addEventListener('click', () => toast('已收藏至学习空间'));

  bindPersonaBars();

  /* --- 页面四：学习空间 --- */
  document.getElementById('learn-tabs').querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.getElementById('learn-tabs').querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('[id^="learn-"]').forEach(v => {
        if (v.id.startsWith('learn-') && v.classList.contains('wf-subview')) v.classList.remove('active');
      });
      document.getElementById('learn-' + tab.dataset.learn).classList.add('active');
    });
  });

  bindPersonaBars();

  document.querySelectorAll('.wf-history-date').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.wf-history-date').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderHistoryCards(btn.dataset.history);
    });
  });
  renderHistoryCards('today');

  document.querySelectorAll('#learn-favorites .wf-paper-card').forEach(card => {
    card.addEventListener('click', () => {
      showPage('paper-detail', { paperId: card.dataset.paper });
    });
  });

  /* --- 页面五：管理员后台 --- */
  initAdminPage();

  updateAdminNav();

  /* --- 页面六：设置 --- */
  document.getElementById('settings-tabs').querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.getElementById('settings-tabs').querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('[id^="settings-"]').forEach(v => {
        if (v.classList.contains('wf-subview')) v.classList.remove('active');
      });
      document.getElementById('settings-' + tab.dataset.settings).classList.add('active');
    });
  });

  document.getElementById('sub-add').addEventListener('click', () => {
    const val = document.getElementById('sub-new').value.trim();
    if (!val) return;
    const tbody = document.getElementById('sub-table');
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>关键词</td><td>${val}</td><td><button class="wf-btn sm sub-del">删</button></td>`;
    tbody.appendChild(tr);
    tr.querySelector('.sub-del').addEventListener('click', () => { tr.remove(); toast('已删除订阅'); });
    document.getElementById('sub-new').value = '';
    toast('已添加订阅：' + val);
  });

  document.querySelectorAll('.sub-del').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('tr').remove();
      toast('已删除订阅');
    });
  });

  document.getElementById('btn-save-account').addEventListener('click', () => toast('账户设置已保存'));
  document.getElementById('btn-save-web').addEventListener('click', () => toast('网页设置已保存'));

  document.querySelectorAll('[data-toggle]').forEach(sw => {
    sw.addEventListener('click', () => sw.classList.toggle('on'));
  });

  /* --- 全局导航 --- */
  document.querySelectorAll('[data-goto]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      const target = el.dataset.goto;
      if (!state.loggedIn && target !== 'login') {
        toast('请先登录');
        return;
      }
      if (PAGE_META[target]) showPage(target);
    });
  });

  document.querySelectorAll('.wf-nav-item[data-page]').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      showPage(item.dataset.page);
    });
  });
});
