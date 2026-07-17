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
  return apiClient.get(`/papers/${paperId}/summary`);
}

export async function createParseTask(paperId, { force = false } = {}) {
  if (USE_MOCK) {
    return {
      taskId: `mock-task-${paperId}`,
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
