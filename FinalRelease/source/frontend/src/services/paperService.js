import apiClient from './apiClient';
import { API_TIMEOUT_MS, USE_MOCK } from './runtimeConfig';
import { PAPERS, PAPER_LIST } from '../data/papers';
import detailMock from '../mocks/paper-detail.json';
import contentMock from '../mocks/paper-content.json';

const delay = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms));
const MOCK_PARSED_KEY = 'papermate.mock.parsedPapers';

function isMockParsed(paperId) {
  try { return JSON.parse(localStorage.getItem(MOCK_PARSED_KEY) || '[]').map(String).includes(String(paperId)); } catch { return false; }
}

function markMockParsed(paperId) {
  try {
    const ids = JSON.parse(localStorage.getItem(MOCK_PARSED_KEY) || '[]').map(String);
    if (!ids.includes(String(paperId))) localStorage.setItem(MOCK_PARSED_KEY, JSON.stringify([...ids, String(paperId)]));
  } catch { /* local demo state is optional */ }
}

export function normalizeAuthors(authors) {
  if (Array.isArray(authors)) return authors.map((author) => (typeof author === 'string' ? author : author?.name)).filter(Boolean);
  return String(authors || '').split(',').map((author) => author.trim()).filter(Boolean);
}

export function toPaperListItem(paper) {
  return {
    paperId: paper.paperId || paper.paper_id || paper.id,
    title: paper.title,
    authors: normalizeAuthors(paper.authors),
    primaryCategory: paper.primaryCategory || paper.primary_category || paper.tag || '未分类',
    topic: paper.topic || '',
    arxivId: paper.arxivId || paper.arxiv_id || paper.arxiv || '',
    publishedAt: paper.publishedAt || paper.published_at || paper.date || '',
    createdAt: paper.createdAt || paper.created_at || '',
    summary: paper.summary || paper.abstract || '',
    keywords: paper.keywords || [],
    researchDirection: paper.researchDirection || paper.direction || paper.primary_category || paper.primaryCategory || '',
    conceptTags: paper.conceptTags || paper.concept_tags || [],
    parseStatus: paper.parseStatus || paper.parse_status || 'pending',
    chunkCount: paper.chunkCount ?? paper.chunk_count ?? 0,
    qaReady: Boolean(paper.qaReady ?? paper.qa_ready),
    isFavorite: Boolean(paper.isFavorite)
  };
}

export function createCompatibleDetail(paper, { forcePending = false } = {}) {
  const normalized = toPaperListItem(forcePending ? { ...paper, parseStatus: 'pending', chunkCount: 0, qaReady: false } : paper);
  return {
    ...paper,
    ...normalized,
    id: normalized.paperId,
    tag: normalized.primaryCategory,
    arxiv: normalized.arxivId,
    date: normalized.publishedAt,
    direction: normalized.researchDirection,
    authorsText: normalized.authors.join(', '),
    categories: paper.categories || [normalized.primaryCategory],
    abstract: paper.abstract || normalized.summary,
    updatedAt: paper.updatedAt || normalized.publishedAt,
    doi: paper.doi || null,
    pdfUrl: paper.pdfUrl || paper.pdf_url || `https://arxiv.org/pdf/${normalized.arxivId}`,
    sourceUrl: paper.sourceUrl || paper.source_url || `https://arxiv.org/abs/${normalized.arxivId}`,
    codeUrl: paper.codeUrl || null
  };
}

async function searchMockPapers({
  query = '',
  author = '',
  searchType = 'keyword',
  categories = [],
  category = '',
  topic = '',
  sortBy = 'published_desc',
  page = 1,
  pageSize = 12,
} = {}) {
  const startedAt = performance.now();
  await delay();
  const normalizedQuery = query.trim().toLowerCase();
  const resolvedCategory = category || categories[0] || '';
  let items = PAPER_LIST.map(toPaperListItem).filter((paper) => {
    if (topic) {
      const paperTopic = (paper.topic || paper.primaryCategory || '').split('.')[0];
      if (paperTopic !== topic && !(paper.primaryCategory || '').startsWith(`${topic}.`)) return false;
    }
    if (resolvedCategory && paper.primaryCategory !== resolvedCategory) return false;
    if (author && !(paper.authors || []).some((name) => String(name).toLowerCase().includes(author.toLowerCase()))) return false;
    if (!normalizedQuery) return true;
    const blob = [paper.title, paper.summary, paper.primaryCategory, paper.arxivId, paper.researchDirection, ...paper.authors, ...paper.keywords, ...paper.conceptTags].join(' ').toLowerCase();
    return blob.includes(normalizedQuery);
  });
  if (sortBy === 'title_asc') items = [...items].sort((a, b) => a.title.localeCompare(b.title));
  else if (sortBy === 'title_desc') items = [...items].sort((a, b) => b.title.localeCompare(a.title));
  else if (sortBy === 'id_asc') items = [...items].sort((a, b) => Number(a.paperId) - Number(b.paperId));
  else if (sortBy === 'id_desc') items = [...items].sort((a, b) => Number(b.paperId) - Number(a.paperId));
  else if (sortBy === 'author_asc') items = [...items].sort((a, b) => String(a.authors?.[0] || '').localeCompare(String(b.authors?.[0] || '')));
  else if (sortBy === 'author_desc') items = [...items].sort((a, b) => String(b.authors?.[0] || '').localeCompare(String(a.authors?.[0] || '')));
  else if (sortBy === 'topic_asc' || sortBy === 'category_asc') items = [...items].sort((a, b) => String(a.primaryCategory || '').localeCompare(String(b.primaryCategory || '')));
  else if (sortBy === 'topic_desc' || sortBy === 'category_desc') items = [...items].sort((a, b) => String(b.primaryCategory || '').localeCompare(String(a.primaryCategory || '')));
  else if (sortBy === 'arxiv_asc') items = [...items].sort((a, b) => String(a.arxivId || '').localeCompare(String(b.arxivId || '')));
  else if (sortBy === 'arxiv_desc') items = [...items].sort((a, b) => String(b.arxivId || '').localeCompare(String(a.arxivId || '')));
  else if (sortBy === 'status_asc') items = [...items].sort((a, b) => String(a.parseStatus || '').localeCompare(String(b.parseStatus || '')));
  else if (sortBy === 'status_desc') items = [...items].sort((a, b) => String(b.parseStatus || '').localeCompare(String(a.parseStatus || '')));
  else if (sortBy === 'created_asc') items = [...items].sort((a, b) => String(a.createdAt || a.publishedAt).localeCompare(String(b.createdAt || b.publishedAt)));
  else if (sortBy === 'created_desc') items = [...items].sort((a, b) => String(b.createdAt || b.publishedAt).localeCompare(String(a.createdAt || a.publishedAt)));
  else if (sortBy === 'published_asc') items = [...items].sort((a, b) => String(a.publishedAt).localeCompare(String(b.publishedAt)));
  else items = [...items].sort((a, b) => String(b.publishedAt).localeCompare(String(a.publishedAt)));
  const start = (page - 1) * pageSize;
  return {
    searchId: `mock-search-${Date.now()}`,
    query,
    searchType,
    sortBy,
    total: items.length,
    page,
    pageSize,
    searchTimeMs: Math.max(1, Math.round(performance.now() - startedAt)),
    items: items.slice(start, start + pageSize),
  };
}

async function getMockPaperDetail(paperId) {
  await delay(150);
  if (paperId === detailMock.data.paperId) return createCompatibleDetail(detailMock.data, { forcePending: !isMockParsed(paperId) });
  const paper = PAPERS[paperId];
  return paper ? createCompatibleDetail(paper, { forcePending: !isMockParsed(paperId) }) : null;
}

async function getMockPaperContent(paperId) {
  await delay(150);
  if (paperId === contentMock.data.paperId) return contentMock.data;
  const detail = await getMockPaperDetail(paperId);
  return detail ? { paperId, contentType: 'pdf', pdfUrl: detail.pdfUrl, htmlUrl: null, pageCount: null, defaultPage: 1, sections: [] } : null;
}

async function getMockPaperSummary(paperId) {
  await delay(150);
  if (!PAPERS[paperId] && paperId !== detailMock.data.paperId) return null;
  const parsed = isMockParsed(paperId);
  const detail = await getMockPaperDetail(paperId);
  return {
    paperId,
    parseStatus: parsed ? 'qa_ready' : 'pending',
    summary: parsed ? (detail?.summary || '演示论文已完成本地解析。') : '',
    concepts: parsed ? [{ conceptId: `${paperId}-concept-1`, name: '核心概念', description: detail?.summary || '本地演示概念' }] : [],
    methods: parsed ? [{ order: 1, title: '方法概览', description: '演示模式使用本地结构化摘要展示解析结果。' }] : [],
    experiments: parsed ? [{ title: '实验与结果', description: '演示模式结果已生成，可继续使用问答功能。' }] : [],
    limitations: parsed ? ['演示模式数据用于前端联调，不代表真实论文解析结论。'] : [],
    validationFlags: [],
    chunkCount: parsed ? 1 : 0,
    qaReady: parsed
  };
}

export async function searchPapers(params = {}) {
  if (USE_MOCK) return searchMockPapers(params);
  const {
    query = '',
    author = '',
    categories = [],
    category = '',
    topic = '',
    publishedFrom,
    publishedTo,
    sortBy = 'published_desc',
    searchField = 'all',
    page = 1,
    pageSize = 12,
  } = params;
  const resolvedCategory = category || categories[0] || undefined;
  const data = await apiClient.get('/papers', {
    params: {
      keyword: query || undefined,
      author: author || undefined,
      category: resolvedCategory || undefined,
      topic: topic || undefined,
      published_from: publishedFrom || undefined,
      published_to: publishedTo || undefined,
      sort_by: sortBy || undefined,
      search_field: searchField || undefined,
      page,
      page_size: pageSize,
    },
  });
  return {
    searchId: `search-${Date.now()}`,
    query,
    searchType: searchField || 'keyword',
    sortBy: data.sort_by || sortBy,
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
    searchTimeMs: 0,
    items: data.items.map(toPaperListItem),
  };
}

export async function deletePaper(paperId) {
  if (USE_MOCK) {
    await delay(120);
    return { paperId };
  }
  return apiClient.delete(`/papers/${paperId}`);
}

export async function searchPaperWiki(query, { mode = 'all', pageSize = 20 } = {}) {
  if (USE_MOCK) return [];
  const trimmed = query?.trim() || '';
  if (!trimmed) return [];
  const field = ['title', 'author', 'keyword', 'direction', 'concept'].includes(mode) ? mode : 'all';
  const params = {
    page: 1,
    page_size: pageSize,
    search_field: field,
    sort_by: 'relevance',
  };
  if (field === 'author') {
    params.author = trimmed;
  } else if (field === 'direction') {
    // 研究方向优先按类别精确匹配，否则走字段检索
    params.category = trimmed.includes('.') ? trimmed : undefined;
    params.keyword = trimmed;
    params.topic = trimmed.includes('.') ? undefined : trimmed;
  } else {
    params.keyword = trimmed;
  }
  const data = await apiClient.get('/papers', { params });
  return (data.items || []).map((paper) => ({
    id: String(paper.paper_id),
    paper: {
      title: paper.title,
      authors: normalizeAuthors(paper.authors).join(', '),
      tag: paper.primary_category || '未分类',
      direction: paper.topic || paper.primary_category || '',
    },
  }));
}

export async function fetchOnePaper(query, { parse = true } = {}) {
  const text = String(query || '').trim();
  if (!text) {
    throw new Error('请输入 arXiv 编号或论文标题');
  }
  if (USE_MOCK) {
    await delay(300);
    return {
      query: text,
      matchedBy: 'title',
      created: true,
      message: `（Mock）已抓取：${text}`,
      item: toPaperListItem({
        paper_id: `mock-fetch-${Date.now()}`,
        title: text,
        arxiv_id: '0000.00000',
        authors: ['Mock Author'],
        abstract: 'Mock fetched paper',
        primary_category: 'cs.CL',
        parse_status: parse ? 'queued' : 'pending',
      }),
      taskId: parse ? `mock-task-${Date.now()}` : null,
    };
  }
  const data = await apiClient.post(
    '/papers/fetch-one',
    { query: text, parse },
    { timeout: Math.max(API_TIMEOUT_MS, 120000) },
  );
  return {
    query: data.query || text,
    matchedBy: data.matched_by || data.matchedBy || 'title',
    created: Boolean(data.created),
    message: data.message || '抓取完成',
    item: toPaperListItem(data.item || {}),
    taskId: data.task_id ?? data.taskId ?? data.task?.task_id ?? null,
  };
}

export async function smartSearchPapers({
  query = '',
  page = 1,
  pageSize = 12,
  category,
  rewrittenQuery,
  keywords,
  categoryHints,
  authorHints,
  searchMode,
  searchSessionId,
  includeAnswer = true,
} = {}) {
  if (USE_MOCK) {
    const data = await searchMockPapers({ query: rewrittenQuery || query, page, pageSize });
    return {
      ...data,
      rewrittenQuery: rewrittenQuery || query,
      keywords: keywords?.length ? keywords : (query ? [query] : []),
      category: category || null,
      categoryHints: categoryHints || [],
      authorHints: authorHints || [],
      searchMode: searchMode || 'topic',
      warnings: [],
      searchSessionId: searchSessionId || `mock-ss-${Date.now()}`,
      intent: '',
      answer: includeAnswer
        ? (data.total > 0 ? `（Mock）检索完成，共找到 ${data.total} 篇与“${query}”相关的论文。` : `（Mock）未找到与“${query}”匹配的论文。`)
        : '',
      highlights: [],
      planSource: rewrittenQuery || keywords ? 'reused' : 'mock',
      answerSource: includeAnswer ? 'mock' : 'skipped'
    };
  }
  const data = await apiClient.post('/papers/smart-search', {
    query,
    page,
    page_size: pageSize,
    category: category || undefined,
    rewritten_query: page > 1 ? undefined : (rewrittenQuery || undefined),
    keywords: page > 1 ? undefined : (keywords?.length ? keywords : undefined),
    category_hints: page > 1 ? undefined : (categoryHints?.length ? categoryHints : undefined),
    author_hints: page > 1 ? undefined : (authorHints?.length ? authorHints : undefined),
    search_mode: page > 1 ? undefined : (searchMode || undefined),
    search_session_id: searchSessionId || undefined,
    include_answer: includeAnswer,
  });
  return {
    searchId: `smart-search-${Date.now()}`,
    query: data.query || query,
    rewrittenQuery: data.rewritten_query || data.rewrittenQuery || rewrittenQuery || query,
    keywords: data.keywords || keywords || [],
    category: data.category || category || null,
    categoryHints: data.category_hints || data.categoryHints || categoryHints || [],
    authorHints: data.author_hints || data.authorHints || authorHints || [],
    searchMode: data.search_mode || data.searchMode || searchMode || 'topic',
    warnings: data.warnings || [],
    searchSessionId: data.search_session_id || data.searchSessionId || searchSessionId || null,
    intent: data.intent || '',
    answer: data.answer || '',
    highlights: data.highlights || [],
    planSource: data.plan_source || data.planSource || '',
    answerSource: data.answer_source || data.answerSource || '',
    citations: data.citations || [],
    searchType: 'smart',
    sortBy: 'relevance',
    total: data.total || 0,
    page: data.page || page,
    pageSize: data.page_size || data.pageSize || pageSize,
    searchTimeMs: 0,
    items: (data.items || []).map(toPaperListItem)
  };
}

export async function listPaperChunks(paperId, { limit = 80 } = {}) {
  if (USE_MOCK) {
    return [
      {
        chunk_id: 'mock-1',
        page_no: 1,
        section: 'Abstract',
        preview: 'This is a mock abstract paragraph for annotation selection.',
        content: 'This is a mock abstract paragraph for annotation selection. Multi-head attention allows the model to jointly attend to information from different representation subspaces.',
      },
      {
        chunk_id: 'mock-2',
        page_no: 2,
        section: 'Method',
        preview: 'We propose a novel architecture based entirely on attention.',
        content: 'We propose a novel architecture based entirely on attention, dispensing with recurrence and convolutions entirely.',
      },
    ];
  }
  return apiClient.get(`/papers/${paperId}/chunks`, { params: { limit } });
}

export async function getPaperDetail(paperId) {
  if (USE_MOCK) return getMockPaperDetail(paperId);
  try { return createCompatibleDetail(await apiClient.get(`/papers/${paperId}`)); } catch (error) { if (error.message.includes('论文不存在')) return null; throw error; }
}

export async function getPaperContent(paperId) {
  if (USE_MOCK) return getMockPaperContent(paperId);
  return apiClient.get(`/papers/${paperId}/content`);
}

export async function getPaperSummary(paperId) {
  if (USE_MOCK) return getMockPaperSummary(paperId);
  const data = await apiClient.get(`/papers/${paperId}/summary`);
  return {
    paperId: String(data.paperId || data.paper_id || paperId),
    parseStatus: data.parseStatus || data.parse_status || 'pending',
    summary: data.summary || '',
    concepts: (data.concepts || []).map((concept, index) => ({
      conceptId: concept.conceptId || concept.concept_id || `${paperId}-concept-${index + 1}`,
      name: concept.name || concept.title || `概念 ${index + 1}`,
      description: concept.description || concept.desc || ''
    })),
    methods: (data.methods || []).map((method, index) => ({
      order: method.order || index + 1,
      title: method.title || method.name || `步骤 ${index + 1}`,
      description: method.description || method.desc || ''
    })),
    experiments: (data.experiments || []).map((experiment) => ({
      title: experiment.title || experiment.name || '实验',
      description: experiment.description || experiment.desc || ''
    })),
    limitations: data.limitations || [],
    validationFlags: data.validationFlags || data.validation_flags || [],
    validationLabels: data.validationLabels || data.validation_labels || [],
    uncertainFields: data.uncertainFields || data.uncertain_fields || [],
    chunkCount: data.chunkCount ?? data.chunk_count ?? 0,
    qaReady: Boolean(data.qaReady ?? data.qa_ready)
  };
}

export async function generatePaperCompare(paperId, otherPaperId) {
  const leftId = String(paperId);
  const rightId = String(otherPaperId);
  if (USE_MOCK) {
    const left = PAPERS[leftId] || { title: `论文 ${leftId}` };
    const right = PAPERS[rightId] || { title: `论文 ${rightId}` };
    return {
      paperId: leftId,
      otherPaperId: rightId,
      summary: `（Mock）对比《${left.title}》与《${right.title}》：二者问题设定与方法路径不同，可从贡献主张与实验证据强度并排阅读。`,
      similarities: ['均属于可检索的学术论文材料', '都可通过摘要快速把握研究动机'],
      differences: ['标题与核心主张不同', '适用场景与证据侧重点可能不同'],
      dimensions: [
        {
          aspect: '问题/目标',
          paperA: left.summary || left.title || '原文未给出',
          paperB: right.summary || right.title || '原文未给出',
          comment: 'Mock 模式仅作界面联调'
        }
      ],
      recommendation: '正式环境将调用 LLM 生成更细的对比总结。',
      source: 'mock'
    };
  }
  const numericOther = Number(otherPaperId);
  if (!Number.isFinite(numericOther) || numericOther < 1) {
    throw new Error('对比论文 ID 无效');
  }
  const data = await apiClient.post(`/papers/${paperId}/compare`, {
    other_paper_id: numericOther
  });
  return {
    paperId: String(data.paper_id || data.paperId || paperId),
    otherPaperId: String(data.other_paper_id || data.otherPaperId || otherPaperId),
    summary: data.summary || '',
    similarities: data.similarities || [],
    differences: data.differences || [],
    dimensions: (data.dimensions || []).map((item) => ({
      aspect: item.aspect || '',
      paperA: item.paper_a || item.paperA || '',
      paperB: item.paper_b || item.paperB || '',
      comment: item.comment || ''
    })),
    recommendation: data.recommendation || '',
    source: data.source || 'llm'
  };
}

export async function createParseTask(paperId, { force = false } = {}) {
  if (USE_MOCK) {
    markMockParsed(paperId);
    return {
      taskId: `mock-task-${paperId}`,
      task_id: `mock-task-${paperId}`,
      paperId,
      taskType: 'full_parse',
      status: 'succeeded',
      errorCode: null
    };
  }
  return apiClient.post(`/papers/${paperId}/parse`, { task_type: 'full_parse', force }, {
    headers: { 'Idempotency-Key': `paper-${paperId}-parse-${Date.now()}` }
  });
}

/** Prioritize existing parse job (or create one stable task). Does not flood the queue. */
export async function boostParsePriority(paperId) {
  if (USE_MOCK) {
    return {
      taskId: `mock-priority-${paperId}`,
      task_id: `mock-priority-${paperId}`,
      paperId,
      taskType: 'full_parse',
      status: 'queued',
      errorCode: null,
    };
  }
  return apiClient.post(`/papers/${paperId}/parse/priority`);
}

export async function getParseTask(taskId) {
  if (USE_MOCK) return { taskId, status: 'succeeded' };
  return apiClient.get(`/tasks/${taskId}`);
}

export async function getReadingAssist(paperId, { mode = '研究', force = false } = {}) {
  if (USE_MOCK) {
    const paper = await getMockPaperDetail(paperId);
    return {
      paperId,
      mode,
      headline: `${mode}模式导读`,
      sections: [{ title: '模式要点', bullets: [paper?.summary || '暂无摘要'] }],
      takeaways: ['结合智能总结继续阅读'],
      next_steps: ['围绕方法和实验继续提问'],
      source: 'mock',
      generated: false
    };
  }
  const data = force
    ? await apiClient.post(`/papers/${paperId}/assist`, { mode, force: true })
    : await apiClient.get(`/papers/${paperId}/assist`, { params: { mode } });
  return {
    paperId: data.paper_id || data.paperId || paperId,
    mode: data.mode || mode,
    headline: data.headline || '',
    sections: data.sections || [],
    takeaways: data.takeaways || [],
    next_steps: data.next_steps || [],
    source: data.source || '',
    generated: Boolean(data.generated)
  };
}

function normalizePaperGraph(data, paperId) {
  return {
    paperId: data.paper_id || data.paperId || paperId,
    nodes: (data.nodes || []).map((node) => ({
      ...node,
      paperId: node.paperId ?? node.paper_id,
      arxivId: node.arxivId || node.arxiv_id || '',
      publishedAt: node.publishedAt || node.published_at || '',
      score: node.score ?? null
    })),
    edges: (data.edges || []).map((edge) => ({
      ...edge,
      weight: edge.weight ?? null,
      evidence: edge.evidence || []
    })),
    lineage: (data.lineage || []).map((item) => ({
      ...item,
      paperId: item.paperId ?? item.paper_id,
      arxivId: item.arxivId || item.arxiv_id || '',
      publishedAt: item.publishedAt || item.published_at || ''
    })),
    narrative: data.narrative || '',
    source: data.source || 'heuristic',
    generated: Boolean(data.generated),
    parseStatus: data.parseStatus || data.parse_status || 'pending',
    preview: Boolean(data.preview ?? data.is_preview)
  };
}

export async function getPaperGraph(paperId, { force = false } = {}) {
  if (USE_MOCK) return {
    paperId,
    nodes: [{ id: 'paper-1', type: 'paper', label: '当前论文', role: 'current' }, { id: 'concept-1', type: 'concept', label: '核心概念' }],
    edges: [{ id: 'edge-1', source: 'paper-1', target: 'concept-1', type: 'introduces', label: '涉及' }],
    lineage: [{ paper_id: paperId, title: '当前论文', role: 'current', note: '当前阅读论文' }],
    narrative: '演示图谱数据',
    source: 'mock',
    generated: false,
    parseStatus: 'pending',
    preview: true
  };
  const data = await apiClient.get(`/papers/${paperId}/graph`, { params: force ? { force: true } : undefined });
  return normalizePaperGraph(data, paperId);
}

export async function rebuildPaperGraph(paperId) {
  if (USE_MOCK) return getPaperGraph(paperId);
  const data = await apiClient.post(`/papers/${paperId}/graph`, {});
  return normalizePaperGraph(data, paperId);
}
