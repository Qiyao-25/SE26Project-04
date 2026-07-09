/*
 * PaperMate 前端原型重设计版
 * 说明：当前版本只做前端展示与页面跳转，不绑定后端和数据库。
 * 后续接入接口时，优先替换 mockApi 中的方法即可。
 */

const MOCK_DB = {
  papers: [
    {
      id: 'attention',
      title: 'Attention Is All You Need',
      authors: 'Vaswani, Shazeer, Parmar, et al.',
      date: '2017-06-12',
      category: 'cs.CL',
      arxiv: '1706.03762',
      match: 96,
      readingTime: '35 min',
      keywords: ['Transformer', 'Self-Attention', 'Seq2Seq'],
      summary: '提出 Transformer 架构，完全基于注意力机制，显著提升序列建模的并行效率。',
      concepts: ['Multi-Head Attention', 'Scaled Dot-Product Attention', 'Positional Encoding'],
      methods: ['Encoder-Decoder 堆叠结构', '多头注意力机制', '位置编码补充序列顺序信息'],
      qaHint: '可以问：Transformer 为什么不需要 RNN？',
      status: '已解析'
    },
    {
      id: 'bert',
      title: 'BERT: Pre-training of Deep Bidirectional Transformers',
      authors: 'Devlin, Chang, Lee, Toutanova',
      date: '2018-10-11',
      category: 'cs.CL',
      arxiv: '1810.04805',
      match: 91,
      readingTime: '28 min',
      keywords: ['BERT', 'Pre-training', 'Masked LM'],
      summary: '提出双向 Transformer 预训练语言模型，形成预训练与下游任务微调的典型范式。',
      concepts: ['Masked Language Model', 'Next Sentence Prediction', 'Fine-tuning'],
      methods: ['双向上下文建模', 'MLM 预训练任务', '分类/问答等任务微调'],
      qaHint: '可以问：BERT 和 GPT 的训练目标有什么区别？',
      status: '已收藏'
    },
    {
      id: 'gpt3',
      title: 'Language Models are Few-Shot Learners',
      authors: 'Brown, Mann, Ryder, et al.',
      date: '2020-05-28',
      category: 'cs.LG',
      arxiv: '2005.14165',
      match: 89,
      readingTime: '45 min',
      keywords: ['GPT-3', 'Few-Shot', 'Scaling Law'],
      summary: '展示大规模自回归语言模型在少样本场景下的泛化能力，推动上下文学习研究。',
      concepts: ['In-Context Learning', 'Few-Shot Prompting', 'Emergent Ability'],
      methods: ['自回归语言建模', '大规模参数扩展', '多任务 prompt 评估'],
      qaHint: '可以问：什么是 in-context learning？',
      status: '待读'
    },
    {
      id: 'lora',
      title: 'LoRA: Low-Rank Adaptation of Large Language Models',
      authors: 'Hu, Shen, Wallis, et al.',
      date: '2021-06-17',
      category: 'cs.LG',
      arxiv: '2106.09685',
      match: 94,
      readingTime: '22 min',
      keywords: ['LoRA', 'PEFT', 'Fine-tuning'],
      summary: '通过低秩矩阵注入实现参数高效微调，降低大模型适配成本。',
      concepts: ['Low-Rank Adaptation', 'Adapter', 'Trainable Parameters'],
      methods: ['冻结原模型参数', '新增低秩矩阵 A/B', '只训练少量适配参数'],
      qaHint: '可以问：LoRA 为什么能减少训练参数？',
      status: '已笔记'
    },
    {
      id: 'rag',
      title: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP',
      authors: 'Lewis, Perez, Piktus, et al.',
      date: '2020-05-22',
      category: 'cs.CL',
      arxiv: '2005.11401',
      match: 87,
      readingTime: '30 min',
      keywords: ['RAG', 'Retrieval', 'Knowledge Base'],
      summary: '将检索模型与生成模型结合，用外部知识提升知识密集型问答任务效果。',
      concepts: ['Dense Retrieval', 'Generator', 'Knowledge-Intensive QA'],
      methods: ['检索候选文档', '文档条件生成', '端到端概率建模'],
      qaHint: '可以问：RAG 的检索器和生成器怎么配合？',
      status: '已解析'
    },
    {
      id: 'vlm-doc',
      title: 'Vision-Language Models for Scientific Document Understanding',
      authors: 'Li, Zhang, Wang',
      date: '2026-07-07',
      category: 'cs.CV',
      arxiv: '2607.01001',
      match: 82,
      readingTime: '26 min',
      keywords: ['VLM', 'Document Understanding', 'OCR'],
      summary: '探索视觉语言模型在科学文档版面解析、图表理解与跨模态问答中的应用。',
      concepts: ['Layout Understanding', 'Multimodal Fusion', 'Chart QA'],
      methods: ['版面区域识别', '图文联合编码', '多模态检索问答'],
      qaHint: '可以问：VLM 如何理解论文中的图表？',
      status: '新论文'
    }
  ],
  notes: [
    { id: 1, paperId: 'attention', paperTitle: 'Attention Is All You Need', content: '重点理解 Q、K、V 的矩阵乘法含义。', date: '2026-07-08' },
    { id: 2, paperId: 'lora', paperTitle: 'LoRA: Low-Rank Adaptation of Large Language Models', content: '可以和 Adapter、Prefix Tuning 做对比。', date: '2026-07-07' },
    { id: 3, paperId: 'rag', paperTitle: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP', content: '后续项目里可以把论文片段向量化后做检索增强问答。', date: '2026-07-06' }
  ],
  history: [
    { time: '今天 15:20', paperId: 'attention', action: '阅读 methods.md 25 分钟' },
    { time: '今天 10:05', paperId: 'bert', action: '查看 concept.md' },
    { time: '昨天 20:30', paperId: 'lora', action: '新增高亮笔记' },
    { time: '昨天 18:15', paperId: 'rag', action: '进行问答追问' }
  ],
  agents: [
    { name: '抓取 Agent', status: '正常', load: '18%', job: 'arXiv cs.LG 每日抓取' },
    { name: '解析 Agent', status: '正常', load: '42%', job: 'PDF/HTML 结构化解析' },
    { name: '摘要 Agent', status: '繁忙', load: '68%', job: '生成 summary.md / concept.md' },
    { name: '问答 Agent', status: '异常', load: '--', job: '连接超时，等待重启' }
  ],
  tasks: [
    { id: 'T-1024', name: 'BERT 摘要生成', owner: '摘要 Agent', progress: 60, status: '处理中' },
    { id: 'T-1025', name: 'GPT-3 PDF 解析', owner: '解析 Agent', progress: 35, status: '处理中' },
    { id: 'T-1026', name: 'LoRA 一致性校验', owner: '校验 Agent', progress: 90, status: '待人工确认' },
    { id: 'T-1027', name: 'RAG 抓取队列', owner: '抓取 Agent', progress: 0, status: '等待中' }
  ]
};

const mockDelay = (value) => new Promise((resolve) => setTimeout(() => resolve(value), 100));

const mockApi = {
  login({ email }) {
    const role = email.trim().toLowerCase() === 'admin' ? 'admin' : 'user';
    return mockDelay({
      id: role === 'admin' ? 1 : 2,
      name: role === 'admin' ? '管理员' : (email.trim() || '普通用户'),
      role,
      persona: role === 'admin' ? '管理' : '研究',
      topics: role === 'admin' ? ['cs.AI', 'cs.LG'] : ['cs.CL', 'cs.LG']
    });
  },
  register({ email }) {
    return mockDelay({ id: 3, name: email.trim() || '新用户', role: 'user', persona: '新手', topics: [] });
  },
  getDashboard() {
    return mockDelay({
      metrics: [
        { label: '今日推荐', value: 12, trend: '+4 篇新论文' },
        { label: '已收藏', value: 28, trend: '+2 条笔记' },
        { label: '待读论文', value: 7, trend: '建议优先阅读 3 篇' },
        { label: '本周阅读', value: '6.5h', trend: '比上周 +18%' }
      ],
      recommended: MOCK_DB.papers.slice(0, 4),
      history: MOCK_DB.history
    });
  },
  searchPapers({ query = '', category = 'all' }) {
    const lower = query.trim().toLowerCase();
    const result = MOCK_DB.papers.filter((paper) => {
      const hitCategory = category === 'all' || paper.category === category;
      const haystack = [paper.title, paper.authors, paper.summary, paper.category, ...paper.keywords].join(' ').toLowerCase();
      const hitQuery = !lower || haystack.includes(lower);
      return hitCategory && hitQuery;
    });
    return mockDelay(result);
  },
  getPaper(id) {
    return mockDelay(MOCK_DB.papers.find((paper) => paper.id === id) || MOCK_DB.papers[0]);
  },
  getLibrary() {
    return mockDelay({ collected: MOCK_DB.papers.filter((p) => ['bert', 'lora', 'rag'].includes(p.id)), notes: MOCK_DB.notes, history: MOCK_DB.history });
  },
  getAdmin() {
    return mockDelay({ agents: MOCK_DB.agents, tasks: MOCK_DB.tasks });
  },
  saveUserSetting(setting) {
    return mockDelay({ ok: true, setting });
  }
};

const PAGE_META = {
  dashboard: { title: '工作台', eyebrow: 'Overview' },
  search: { title: '论文检索', eyebrow: 'Search' },
  detail: { title: '论文详情', eyebrow: 'Reading' },
  library: { title: '学习空间', eyebrow: 'Library' },
  admin: { title: '管理员后台', eyebrow: 'Admin Console' },
  settings: { title: '设置', eyebrow: 'Settings' }
};

const NAV_ITEMS = [
  { id: 'dashboard', label: '工作台', icon: '🏠' },
  { id: 'search', label: '论文检索', icon: '🔎' },
  { id: 'library', label: '学习空间', icon: '📚' },
  { id: 'admin', label: '管理员后台', icon: '🧩', adminOnly: true },
  { id: 'settings', label: '设置', icon: '⚙️' }
];

const state = {
  user: null,
  route: 'dashboard',
  authPanel: 'login',
  selectedPaperId: 'attention',
  searchQuery: '',
  searchCategory: 'all',
  searchResults: [],
  detailTab: 'summary',
  libraryTab: 'collect',
  adminTab: 'overview',
  detailChat: [{ role: 'bot', text: '我可以基于当前论文进行解释、总结和对比。' }]
};

function $(selector) {
  return document.querySelector(selector);
}

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => el.classList.remove('show'), 1800);
}

function setAuthPanel(panel) {
  state.authPanel = panel;
  document.querySelectorAll('.auth-tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.authPanel === panel));
  $('#login-panel').classList.toggle('active', panel === 'login');
  $('#register-panel').classList.toggle('active', panel === 'register');
}

function enterApp(user) {
  state.user = user;
  state.route = 'dashboard';
  $('#auth-view').classList.add('hidden');
  $('#app-view').classList.remove('hidden');
  renderShell();
  renderPage();
}

function logout() {
  state.user = null;
  state.route = 'dashboard';
  $('#app-view').classList.add('hidden');
  $('#auth-view').classList.remove('hidden');
  toast('已退出，返回登录页');
}

function renderShell() {
  const nav = NAV_ITEMS.filter((item) => !item.adminOnly || state.user?.role === 'admin');
  $('#main-nav').innerHTML = nav.map((item) => `
    <button class="nav-item ${state.route === item.id ? 'active' : ''}" data-route="${item.id}">
      <span class="nav-icon">${item.icon}</span>
      <span>${item.label}</span>
    </button>
  `).join('');

  $('#user-chip').innerHTML = `
    <strong>${escapeHtml(state.user.name)}</strong><br />
    <span>${state.user.role === 'admin' ? '管理员' : '普通用户'} · ${escapeHtml(state.user.persona)}模式</span><br />
    <span>${state.user.topics.length ? state.user.topics.join(' / ') : '未选择方向'}</span>
  `;
}

async function navigate(route, extra = {}) {
  if (route === 'admin' && state.user?.role !== 'admin') {
    toast('管理员后台仅 admin 演示账号显示');
    return;
  }
  state.route = route;
  Object.assign(state, extra);
  renderShell();
  await renderPage();
}

function updatePageTitle() {
  const meta = PAGE_META[state.route] || PAGE_META.dashboard;
  $('#page-title').textContent = meta.title;
  $('#page-eyebrow').textContent = meta.eyebrow;
}

async function renderPage() {
  updatePageTitle();
  const root = $('#page-root');
  root.innerHTML = '<div class="empty-state"><strong>加载中...</strong><span>正在读取前端 Mock 数据</span></div>';
  if (state.route === 'dashboard') return renderDashboard();
  if (state.route === 'search') return renderSearch();
  if (state.route === 'detail') return renderDetail();
  if (state.route === 'library') return renderLibrary();
  if (state.route === 'admin') return renderAdmin();
  if (state.route === 'settings') return renderSettings();
}

function paperCard(paper, options = {}) {
  const primaryText = options.primaryText || '查看详情';
  const secondaryText = options.secondaryText || '收藏';
  return `
    <article class="paper-card">
      <div class="paper-thumb">PDF</div>
      <div>
        <div class="tag-list" style="margin-bottom:8px;">
          <span class="tag primary">${paper.category}</span>
          <span class="tag">匹配 ${paper.match}%</span>
          <span class="tag">${paper.status}</span>
        </div>
        <h4>${escapeHtml(paper.title)}</h4>
        <p class="paper-meta">${escapeHtml(paper.authors)} · ${paper.date} · arXiv:${paper.arxiv}</p>
        <p class="paper-summary">${escapeHtml(paper.summary)}</p>
      </div>
      <div class="paper-actions">
        <button class="btn small primary" data-action="open-paper" data-paper-id="${paper.id}">${primaryText}</button>
        <button class="btn small" data-action="demo-only">${secondaryText}</button>
      </div>
    </article>
  `;
}

async function renderDashboard() {
  const data = await mockApi.getDashboard();
  $('#page-root').innerHTML = `
    <div class="section-grid">
      ${data.metrics.map((item) => `
        <div class="card metric-card col-3">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
          <p>${item.trend}</p>
        </div>
      `).join('')}

      <div class="card col-8">
        <div class="card-title-row">
          <h3>推荐论文</h3>
          <button class="btn soft small" data-route="search">进入完整检索</button>
        </div>
        <div class="paper-list">
          ${data.recommended.map((paper) => paperCard(paper)).join('')}
        </div>
      </div>

      <div class="card col-4">
        <div class="card-title-row">
          <h3>阅读动态</h3>
          <span class="badge primary">Mock 展示</span>
        </div>
        <div class="timeline">
          ${data.history.map((item) => {
            const paper = MOCK_DB.papers.find((p) => p.id === item.paperId);
            return `
              <div class="timeline-item">
                <div class="timeline-time">${item.time}</div>
                <div class="timeline-body"><strong>${escapeHtml(paper?.title || '论文')}</strong><br>${item.action}</div>
              </div>
            `;
          }).join('')}
        </div>
      </div>

      <div class="card col-12">
        <div class="card-title-row">
          <h3>后续接口接入建议</h3>
          <span class="badge success">结构已预留</span>
        </div>
        <div class="content-block">
          现在页面调用的是 <strong>mockApi.getDashboard()</strong>、<strong>mockApi.searchPapers()</strong>、<strong>mockApi.getPaper()</strong> 等前端假接口。
          后端完成后，只需要把这些函数内部替换成 fetch 请求，页面按钮和渲染逻辑可以先不动。
        </div>
      </div>
    </div>
  `;
}

async function renderSearch() {
  if (!state.searchResults.length) {
    state.searchResults = await mockApi.searchPapers({ query: state.searchQuery, category: state.searchCategory });
  }
  $('#page-root').innerHTML = `
    <div class="card">
      <div class="card-title-row">
        <h3>论文检索与发现</h3>
        <span class="badge primary">${state.searchResults.length} 篇结果</span>
      </div>
      <div class="toolbar">
        <input id="search-input" value="${escapeHtml(state.searchQuery)}" placeholder="输入标题、作者、关键词，例如 Transformer / RAG / LoRA" />
        <select id="category-select">
          <option value="all" ${state.searchCategory === 'all' ? 'selected' : ''}>全部分类</option>
          <option value="cs.CL" ${state.searchCategory === 'cs.CL' ? 'selected' : ''}>cs.CL</option>
          <option value="cs.LG" ${state.searchCategory === 'cs.LG' ? 'selected' : ''}>cs.LG</option>
          <option value="cs.CV" ${state.searchCategory === 'cs.CV' ? 'selected' : ''}>cs.CV</option>
        </select>
        <button class="btn primary" data-action="search-papers">搜索</button>
        <button class="btn" data-action="reset-search">重置</button>
      </div>
      <div class="paper-list">
        ${state.searchResults.length ? state.searchResults.map((paper) => paperCard(paper)).join('') : '<div class="empty-state"><strong>没有匹配结果</strong><span>换一个关键词或分类试试</span></div>'}
      </div>
    </div>
  `;
}

function tabButton(label, tab, activeTab, action) {
  return `<button class="tab-btn ${tab === activeTab ? 'active' : ''}" data-action="${action}" data-tab="${tab}">${label}</button>`;
}

async function renderDetail() {
  const paper = await mockApi.getPaper(state.selectedPaperId);
  const detailContent = getDetailContent(paper);
  $('#page-root').innerHTML = `
    <div class="split-layout">
      <div class="card">
        <div class="paper-hero">
          <div>
            <div class="tag-list">
              <span class="tag primary">${paper.category}</span>
              <span class="tag">arXiv:${paper.arxiv}</span>
              <span class="tag">${paper.readingTime}</span>
            </div>
            <h2>${escapeHtml(paper.title)}</h2>
            <p>${escapeHtml(paper.authors)} · ${paper.date}</p>
          </div>
          <button class="btn" data-route="search">返回检索</button>
        </div>

        <div class="tab-bar">
          ${tabButton('智能总结', 'summary', state.detailTab, 'switch-detail-tab')}
          ${tabButton('核心概念', 'concepts', state.detailTab, 'switch-detail-tab')}
          ${tabButton('方法流程', 'methods', state.detailTab, 'switch-detail-tab')}
          ${tabButton('知识图谱', 'graph', state.detailTab, 'switch-detail-tab')}
          ${tabButton('原文占位', 'paper', state.detailTab, 'switch-detail-tab')}
        </div>

        ${detailContent}
      </div>

      <aside class="side-panel">
        <div class="card">
          <div class="card-title-row">
            <h3>辅助阅读</h3>
            <span class="badge primary">${escapeHtml(state.user.persona)}模式</span>
          </div>
          <p class="paper-summary">${buildModeText(paper)}</p>
          <div class="tag-list" style="margin-top:12px;">
            ${paper.keywords.map((keyword) => `<span class="tag">${escapeHtml(keyword)}</span>`).join('')}
          </div>
        </div>

        <div class="card">
          <h3>论文问答</h3>
          <div class="chat-box" id="detail-chat-box">
            ${state.detailChat.map((msg) => `<div class="chat-message ${msg.role === 'user' ? 'user' : ''}">${escapeHtml(msg.text)}</div>`).join('')}
          </div>
          <div class="chat-input" style="margin-top:12px;">
            <input id="detail-question" placeholder="${escapeHtml(paper.qaHint)}" />
            <button class="btn primary" data-action="ask-paper">发送</button>
          </div>
        </div>

        <div class="card">
          <h3>展示按钮</h3>
          <div class="paper-actions" style="justify-content:flex-start;">
            <button class="btn small" data-action="demo-only">收藏本文</button>
            <button class="btn small" data-action="demo-only">新增笔记</button>
            <button class="btn small" data-action="demo-only">加入对比</button>
          </div>
          <p class="hint">这些按钮目前只给出提示，不会写入数据库。</p>
        </div>
      </aside>
    </div>
  `;
}

function getDetailContent(paper) {
  if (state.detailTab === 'summary') {
    return `
      <div class="content-block">
        <h4>结构化摘要</h4>
        <p>${escapeHtml(paper.summary)}</p>
        <ul>
          <li>研究对象：${escapeHtml(paper.category)} 方向论文</li>
          <li>阅读目标：先理解核心问题，再看方法与实验</li>
          <li>原型说明：这里后续可接 /papers/{id}/summary 接口</li>
        </ul>
      </div>
    `;
  }
  if (state.detailTab === 'concepts') {
    return `
      <div class="content-block">
        <h4>核心概念</h4>
        <div class="tag-list">${paper.concepts.map((concept) => `<span class="tag primary">${escapeHtml(concept)}</span>`).join('')}</div>
        <p style="margin-top:14px;">后续可以把概念解释拆成独立接口，例如 /papers/{id}/concepts。</p>
      </div>
    `;
  }
  if (state.detailTab === 'methods') {
    return `
      <div class="content-block">
        <h4>方法流程</h4>
        <ul>${paper.methods.map((method) => `<li>${escapeHtml(method)}</li>`).join('')}</ul>
      </div>
    `;
  }
  if (state.detailTab === 'graph') {
    return `
      <div class="graph-box">
        <span class="graph-node main" style="top:42%;left:38%;">${escapeHtml(paper.keywords[0])}</span>
        <span class="graph-node" style="top:14%;left:12%;">${escapeHtml(paper.concepts[0])}</span>
        <span class="graph-node" style="top:16%;right:12%;">${escapeHtml(paper.concepts[1])}</span>
        <span class="graph-node" style="bottom:18%;left:16%;">BERT</span>
        <span class="graph-node" style="bottom:16%;right:15%;">GPT-3</span>
      </div>
    `;
  }
  return `
    <div class="content-block">
      <h4>PDF / HTML 原文区域</h4>
      <p>这里暂时是原文阅读器占位。正式版本可以接 PDF.js、HTML 解析内容，或者从后端返回的结构化 sections 渲染。</p>
    </div>
  `;
}

function buildModeText(paper) {
  const mode = state.user?.persona || '研究';
  const map = {
    新手: `这篇论文可以先看成：${paper.summary}。建议先理解关键词 ${paper.keywords[0]}。`,
    研究: `研究视角建议关注：创新点、方法假设、实验对比和局限性。本文核心是：${paper.summary}`,
    工程: `工程视角建议关注：数据输入、模型结构、训练成本和能否复现。可从 ${paper.methods[0]} 入手。`,
    教学: `教学视角可以拆成背景问题、核心公式、方法流程和课堂讨论题。`,
    管理: `管理视角建议关注应用价值、趋势方向和落地风险。本文方向为 ${paper.category}。`
  };
  return map[mode] || map.研究;
}

async function renderLibrary() {
  const data = await mockApi.getLibrary();
  const tab = state.libraryTab;
  const content = tab === 'collect'
    ? `<div class="paper-list">${data.collected.map((paper) => paperCard(paper, { secondaryText: '移出收藏' })).join('')}</div>`
    : tab === 'notes'
      ? `<div class="timeline">${data.notes.map((note) => `<div class="timeline-item"><div class="timeline-time">${note.date}</div><div class="timeline-body"><strong>${escapeHtml(note.paperTitle)}</strong><br>${escapeHtml(note.content)}</div></div>`).join('')}</div>`
      : `<div class="timeline">${data.history.map((item) => { const paper = MOCK_DB.papers.find((p) => p.id === item.paperId); return `<div class="timeline-item"><div class="timeline-time">${item.time}</div><div class="timeline-body"><strong>${escapeHtml(paper?.title || '')}</strong><br>${item.action}</div></div>`; }).join('')}</div>`;

  $('#page-root').innerHTML = `
    <div class="card">
      <div class="card-title-row">
        <h3>学习空间</h3>
        <span class="badge primary">收藏 / 笔记 / 历史</span>
      </div>
      <div class="tab-bar">
        ${tabButton('我的收藏', 'collect', tab, 'switch-library-tab')}
        ${tabButton('阅读笔记', 'notes', tab, 'switch-library-tab')}
        ${tabButton('阅读历史', 'history', tab, 'switch-library-tab')}
      </div>
      ${content}
    </div>
  `;
}

async function renderAdmin() {
  const data = await mockApi.getAdmin();
  const content = state.adminTab === 'overview'
    ? `
      <div class="section-grid">
        <div class="card metric-card col-3"><span>今日抓取</span><strong>37</strong><p>+12%</p></div>
        <div class="card metric-card col-3"><span>解析成功率</span><strong>97%</strong><p>稳定</p></div>
        <div class="card metric-card col-3"><span>异常任务</span><strong>3</strong><p style="color:var(--warning);">待处理</p></div>
        <div class="card metric-card col-3"><span>活跃用户</span><strong>486</strong><p>+8 今日新增</p></div>
      </div>
    `
    : state.adminTab === 'agents'
      ? `<table class="table"><thead><tr><th>Agent</th><th>状态</th><th>负载</th><th>当前任务</th><th>操作</th></tr></thead><tbody>${data.agents.map((agent) => `<tr><td>${agent.name}</td><td>${statusBadge(agent.status)}</td><td>${agent.load}</td><td>${agent.job}</td><td><button class="btn small" data-action="demo-only">重启</button></td></tr>`).join('')}</tbody></table>`
      : `<table class="table"><thead><tr><th>任务ID</th><th>任务名称</th><th>负责人</th><th>进度</th><th>状态</th></tr></thead><tbody>${data.tasks.map((task) => `<tr><td>${task.id}</td><td>${task.name}</td><td>${task.owner}</td><td>${task.progress}%</td><td>${statusBadge(task.status)}</td></tr>`).join('')}</tbody></table>`;

  $('#page-root').innerHTML = `
    <div class="card">
      <div class="card-title-row">
        <h3>管理员后台</h3>
        <span class="badge warning">演示账号：admin</span>
      </div>
      <div class="tab-bar">
        ${tabButton('系统概览', 'overview', state.adminTab, 'switch-admin-tab')}
        ${tabButton('Agent 状态', 'agents', state.adminTab, 'switch-admin-tab')}
        ${tabButton('任务队列', 'tasks', state.adminTab, 'switch-admin-tab')}
      </div>
      ${content}
    </div>
  `;
}

function statusBadge(status) {
  const cls = status.includes('异常') ? 'danger' : status.includes('繁忙') || status.includes('待') ? 'warning' : 'success';
  return `<span class="badge ${cls}">${status}</span>`;
}

function renderSettings() {
  $('#page-root').innerHTML = `
    <div class="section-grid">
      <div class="card col-7">
        <h3>个人阅读偏好</h3>
        <div class="setting-row">
          <div><strong>默认阅读模式</strong><p class="hint">影响论文详情右侧辅助阅读展示</p></div>
          <div class="mode-options">
            ${['新手', '研究', '工程', '教学', '管理'].map((mode) => `<button class="mode-card ${state.user.persona === mode ? 'active' : ''}" data-action="set-persona" data-persona="${mode}">${mode}</button>`).join('')}
          </div>
        </div>
        <div class="setting-row">
          <div><strong>研究方向</strong><p class="hint">原型阶段只更新页面状态</p></div>
          <div class="tag-list">
            ${['cs.CL', 'cs.LG', 'cs.CV', 'cs.AI'].map((topic) => `<button class="tag ${state.user.topics.includes(topic) ? 'primary' : ''}" data-action="toggle-topic" data-topic="${topic}">${topic}</button>`).join('')}
          </div>
        </div>
      </div>
      <div class="card col-5">
        <h3>接口接入占位</h3>
        <div class="content-block">
          <h4>当前不绑定后端</h4>
          <p>保存、订阅、抓取等按钮目前只展示提示。后续可替换为：</p>
          <ul>
            <li>GET /api/papers</li>
            <li>GET /api/papers/{id}</li>
            <li>POST /api/auth/login</li>
            <li>POST /api/users/profile</li>
          </ul>
        </div>
      </div>
    </div>
  `;
}

function openOnboarding(user) {
  state.user = user;
  $('#modal-root').classList.remove('hidden');
  $('#modal-root').innerHTML = `
    <div class="modal-card">
      <h3>首次登录引导</h3>
      <p class="hint">选择研究方向和阅读模式。此处仅保存到前端状态，方便展示个性化推荐。</p>
      <label>选择研究方向</label>
      <div class="choice-grid">
        ${['cs.CL', 'cs.LG', 'cs.CV', 'cs.AI'].map((topic) => `<button class="choice-btn" data-action="onboard-topic" data-topic="${topic}"><strong>${topic}</strong><br><span class="hint">点击选择/取消</span></button>`).join('')}
      </div>
      <label>选择默认模式</label>
      <div class="mode-options">
        ${['新手', '研究', '工程', '教学', '管理'].map((mode) => `<button class="mode-card ${mode === '新手' ? 'active' : ''}" data-action="onboard-persona" data-persona="${mode}">${mode}</button>`).join('')}
      </div>
      <div class="modal-actions">
        <button class="btn" data-action="close-modal">取消</button>
        <button class="btn primary" data-action="finish-onboarding">完成并进入</button>
      </div>
    </div>
  `;
}

function closeModal() {
  $('#modal-root').classList.add('hidden');
  $('#modal-root').innerHTML = '';
}

async function handleAction(action, target) {
  if (action === 'login') {
    const email = $('#login-email').value;
    const password = $('#login-password').value;
    const user = await mockApi.login({ email, password });
    enterApp(user);
    toast('登录成功，进入前端演示');
  }

  if (action === 'register') {
    const email = $('#register-email').value;
    const password = $('#register-password').value;
    const user = await mockApi.register({ email, password });
    openOnboarding(user);
  }

  if (action === 'logout') logout();

  if (action === 'quick-search') {
    await navigate('search', { searchQuery: 'Transformer', searchCategory: 'all', searchResults: [] });
  }

  if (action === 'search-papers') {
    state.searchQuery = $('#search-input').value;
    state.searchCategory = $('#category-select').value;
    state.searchResults = await mockApi.searchPapers({ query: state.searchQuery, category: state.searchCategory });
    renderSearch();
    toast('已根据前端 Mock 数据刷新结果');
  }

  if (action === 'reset-search') {
    state.searchQuery = '';
    state.searchCategory = 'all';
    state.searchResults = await mockApi.searchPapers({ query: '', category: 'all' });
    renderSearch();
  }

  if (action === 'open-paper') {
    const paperId = target.dataset.paperId;
    state.detailTab = 'summary';
    state.detailChat = [{ role: 'bot', text: '我可以基于当前论文进行解释、总结和对比。' }];
    await navigate('detail', { selectedPaperId: paperId });
  }

  if (action === 'switch-detail-tab') {
    state.detailTab = target.dataset.tab;
    renderDetail();
  }

  if (action === 'switch-library-tab') {
    state.libraryTab = target.dataset.tab;
    renderLibrary();
  }

  if (action === 'switch-admin-tab') {
    state.adminTab = target.dataset.tab;
    renderAdmin();
  }

  if (action === 'ask-paper') {
    const input = $('#detail-question');
    const question = input.value.trim();
    if (!question) return toast('请输入问题');
    const paper = await mockApi.getPaper(state.selectedPaperId);
    state.detailChat.push({ role: 'user', text: question });
    state.detailChat.push({ role: 'bot', text: `这是前端演示回答：你问的是「${question}」。正式接入后这里可调用 /papers/${paper.id}/qa。` });
    renderDetail();
  }

  if (action === 'set-persona') {
    state.user.persona = target.dataset.persona;
    await mockApi.saveUserSetting({ persona: state.user.persona });
    renderShell();
    renderSettings();
    toast(`已切换为${state.user.persona}模式`);
  }

  if (action === 'toggle-topic') {
    const topic = target.dataset.topic;
    if (state.user.topics.includes(topic)) {
      state.user.topics = state.user.topics.filter((item) => item !== topic);
    } else {
      state.user.topics.push(topic);
    }
    renderShell();
    renderSettings();
  }

  if (action === 'demo-only') {
    toast('原型阶段：按钮只做展示，暂不写入后端/数据库');
  }

  if (action === 'onboard-topic') {
    target.classList.toggle('active');
  }

  if (action === 'onboard-persona') {
    document.querySelectorAll('[data-action="onboard-persona"]').forEach((btn) => btn.classList.remove('active'));
    target.classList.add('active');
  }

  if (action === 'finish-onboarding') {
    const topics = Array.from(document.querySelectorAll('[data-action="onboard-topic"].active')).map((btn) => btn.dataset.topic);
    const persona = document.querySelector('[data-action="onboard-persona"].active')?.dataset.persona || '新手';
    state.user.topics = topics.length ? topics : ['cs.CL'];
    state.user.persona = persona;
    closeModal();
    enterApp(state.user);
    toast('引导完成，进入工作台');
  }

  if (action === 'close-modal') {
    closeModal();
  }
}

document.addEventListener('click', async (event) => {
  const authTab = event.target.closest('[data-auth-panel]');
  if (authTab) {
    setAuthPanel(authTab.dataset.authPanel);
    return;
  }

  const routeTarget = event.target.closest('[data-route]');
  if (routeTarget && state.user) {
    await navigate(routeTarget.dataset.route, routeTarget.dataset.route === 'search' ? { searchResults: [] } : {});
    return;
  }

  const actionTarget = event.target.closest('[data-action]');
  if (actionTarget) {
    await handleAction(actionTarget.dataset.action, actionTarget);
  }
});

document.addEventListener('keydown', async (event) => {
  if (event.key !== 'Enter') return;
  if (event.target.id === 'search-input') await handleAction('search-papers', event.target);
  if (event.target.id === 'detail-question') await handleAction('ask-paper', event.target);
  if (event.target.id === 'login-password') await handleAction('login', event.target);
});

// 默认准备一份搜索结果，便于用户直接进入检索页查看。
mockApi.searchPapers({ query: '', category: 'all' }).then((result) => {
  state.searchResults = result;
});
