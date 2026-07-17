import apiClient from './apiClient';
import { USE_MOCK } from './runtimeConfig';
import { PAPERS, PAPER_LIST } from '../data/papers';
import detailMock from '../mocks/paper-detail.json';
import contentMock from '../mocks/paper-content.json';

const delay = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms));

function normalizeAuthors(authors) {
  if (Array.isArray(authors)) return authors.map((author) => (typeof author === 'string' ? author : author?.name)).filter(Boolean);
  return String(authors || '').split(',').map((author) => author.trim()).filter(Boolean);
}

function toPaperListItem(paper) {
  return {
    paperId: paper.paperId || paper.paper_id || paper.id,
    title: paper.title,
    authors: normalizeAuthors(paper.authors),
    primaryCategory: paper.primaryCategory || paper.primary_category || paper.tag || '未分类',
    arxivId: paper.arxivId || paper.arxiv_id || paper.arxiv || '',
    publishedAt: paper.publishedAt || paper.published_at || paper.date || '',
    summary: paper.summary || paper.abstract || '',
    keywords: paper.keywords || [],
    researchDirection: paper.researchDirection || paper.direction || '',
    conceptTags: paper.conceptTags || [],
    parseStatus: paper.parseStatus || paper.parse_status || 'pending',
    chunkCount: paper.chunkCount ?? paper.chunk_count ?? 0,
    qaReady: Boolean(paper.qaReady ?? paper.qa_ready),
    isFavorite: Boolean(paper.isFavorite)
  };
}

function createCompatibleDetail(paper, { forcePending = false } = {}) {
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

async function searchMockPapers({ query = '', searchType = 'keyword', categories = [], sortBy = 'relevance', page = 1, pageSize = 12 } = {}) {
  const startedAt = performance.now();
  await delay();
  const normalizedQuery = query.trim().toLowerCase();
  let items = PAPER_LIST.map(toPaperListItem).filter((paper) => {
    if (categories.length && !categories.includes(paper.primaryCategory)) return false;
    if (!normalizedQuery) return true;
    return [paper.title, paper.summary, paper.primaryCategory, paper.arxivId, paper.researchDirection, ...paper.authors, ...paper.keywords, ...paper.conceptTags].join(' ').toLowerCase().includes(normalizedQuery);
  });
  if (sortBy === 'date') items = [...items].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
  const start = (page - 1) * pageSize;
  return { searchId: `mock-search-${Date.now()}`, query, searchType, sortBy, total: items.length, page, pageSize, searchTimeMs: Math.max(1, Math.round(performance.now() - startedAt)), items: items.slice(start, start + pageSize) };
}

async function getMockPaperDetail(paperId) {
  await delay(150);
  if (paperId === detailMock.data.paperId) return createCompatibleDetail(detailMock.data, { forcePending: true });
  const paper = PAPERS[paperId];
  return paper ? createCompatibleDetail(paper, { forcePending: true }) : null;
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
  return {
    paperId,
    parseStatus: 'pending',
    summary: '',
    concepts: [],
    methods: [],
    experiments: [],
    limitations: [],
    validationFlags: [],
    chunkCount: 0,
    qaReady: false
  };
}

export async function searchPapers(params = {}) {
  if (USE_MOCK) return searchMockPapers(params);
  const { query = '', categories = [], page = 1, pageSize = 12 } = params;
  const data = await apiClient.get('/papers', { params: { keyword: query || undefined, category: categories[0] || undefined, page, page_size: pageSize } });
  return { searchId: `search-${Date.now()}`, query, searchType: 'keyword', sortBy: 'relevance', total: data.total, page: data.page, pageSize: data.page_size, searchTimeMs: 0, items: data.items.map(toPaperListItem) };
}

export async function smartSearchPapers({ query = '', page = 1, pageSize = 12, category } = {}) {
  if (USE_MOCK) {
    const data = await searchMockPapers({ query, page, pageSize });
    return {
      ...data,
      rewrittenQuery: query,
      keywords: query ? [query] : [],
      intent: '',
      answer: data.total > 0 ? `（Mock）检索完成，共找到 ${data.total} 篇与“${query}”相关的论文。` : `（Mock）未找到与“${query}”匹配的论文。`,
      highlights: [],
      planSource: 'mock',
      answerSource: 'mock'
    };
  }
  const data = await apiClient.post('/papers/smart-search', {
    query,
    page,
    page_size: pageSize,
    category: category || undefined
  });
  return {
    searchId: `smart-search-${Date.now()}`,
    query: data.query || query,
    rewrittenQuery: data.rewritten_query || data.rewrittenQuery || query,
    keywords: data.keywords || [],
    intent: data.intent || '',
    answer: data.answer || '',
    highlights: data.highlights || [],
    planSource: data.plan_source || data.planSource || '',
    answerSource: data.answer_source || data.answerSource || '',
    searchType: 'smart',
    sortBy: 'relevance',
    total: data.total || 0,
    page: data.page || page,
    pageSize: data.page_size || data.pageSize || pageSize,
    searchTimeMs: 0,
    items: (data.items || []).map(toPaperListItem)
  };
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
    chunkCount: data.chunkCount ?? data.chunk_count ?? 0,
    qaReady: Boolean(data.qaReady ?? data.qa_ready)
  };
}

export async function createParseTask(paperId, { force = false } = {}) {
  if (USE_MOCK) {
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

export async function getParseTask(taskId) {
  if (USE_MOCK) return { taskId, status: 'succeeded' };
  return apiClient.get(`/tasks/${taskId}`);
}

export async function getPaperGraph(paperId, { force = false } = {}) {
  if (USE_MOCK) {
    return {
      paperId,
      paper_id: paperId,
      nodes: [
        { id: 'paper-1', type: 'paper', label: 'Demo Paper', role: 'current', paper_id: Number(paperId) || 1 },
        { id: 'concept-1', type: 'concept', label: 'Attention' },
        { id: 'method-1', type: 'method', label: 'Transformer' }
      ],
      edges: [
        { id: 'e1', source: 'paper-1', target: 'concept-1', type: 'introduces', label: '提出' },
        { id: 'e2', source: 'paper-1', target: 'method-1', type: 'uses', label: '方法' }
      ],
      lineage: [
        { paper_id: Number(paperId) || 1, title: 'Demo Paper', role: 'current', note: '当前论文', published_at: '2017-06-12' }
      ],
      narrative: '（Mock）围绕注意力机制的轻量研究脉络示意。',
      source: 'mock',
      generated: false
    };
  }
  const data = await apiClient.get(`/papers/${paperId}/graph`, { params: force ? { force: true } : undefined });
  return {
    paperId: data.paper_id || data.paperId || paperId,
    nodes: data.nodes || [],
    edges: data.edges || [],
    lineage: data.lineage || [],
    narrative: data.narrative || '',
    source: data.source || '',
    generated: Boolean(data.generated)
  };
}

export async function rebuildPaperGraph(paperId) {
  if (USE_MOCK) return getPaperGraph(paperId);
  const data = await apiClient.post(`/papers/${paperId}/graph`);
  return {
    paperId: data.paper_id || data.paperId || paperId,
    nodes: data.nodes || [],
    edges: data.edges || [],
    lineage: data.lineage || [],
    narrative: data.narrative || '',
    source: data.source || '',
    generated: Boolean(data.generated)
  };
}

export async function getReadingAssist(paperId, { mode = '研究', force = false } = {}) {
  if (USE_MOCK) {
    return {
      paperId,
      mode,
      headline: `（Mock）${mode}模式导读`,
      sections: [
        { title: '模式要点', bullets: [`当前为 ${mode} 模式示例内容`, '联调后端后将生成真实导读'] },
        { title: '建议', bullets: ['先完成解析', '再切换不同模式对比侧重点'] }
      ],
      takeaways: ['模式决定侧重点', '内容应易读', '可按模式重生成'],
      next_steps: ['切换模式查看差异'],
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
    sections: (data.sections || []).map((section) => ({
      title: section.title,
      bullets: section.bullets || []
    })),
    takeaways: data.takeaways || [],
    next_steps: data.next_steps || [],
    source: data.source || '',
    generated: Boolean(data.generated)
  };
}
