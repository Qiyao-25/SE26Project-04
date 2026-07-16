import apiClient from './apiClient';
import { USE_MOCK } from './runtimeConfig';
import { PAPERS, PAPER_LIST } from '../data/papers';
import detailMock from '../mocks/paper-detail.json';
import contentMock from '../mocks/paper-content.json';
import summaryMock from '../mocks/paper-summary.json';

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
    parseStatus: paper.parseStatus || paper.parse_status || 'completed',
    isFavorite: Boolean(paper.isFavorite)
  };
}

function createCompatibleDetail(paper) {
  const normalized = toPaperListItem(paper);
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
  if (paperId === detailMock.data.paperId) return createCompatibleDetail(detailMock.data);
  const paper = PAPERS[paperId];
  return paper ? createCompatibleDetail(paper) : null;
}

async function getMockPaperContent(paperId) {
  await delay(150);
  if (paperId === contentMock.data.paperId) return contentMock.data;
  const detail = await getMockPaperDetail(paperId);
  return detail ? { paperId, contentType: 'pdf', pdfUrl: detail.pdfUrl, htmlUrl: null, pageCount: null, defaultPage: 1, sections: [] } : null;
}

async function getMockPaperSummary(paperId) {
  await delay(150);
  if (paperId === summaryMock.data.paperId) return summaryMock.data;
  const paper = PAPERS[paperId];
  if (!paper) return null;
  return { paperId, parseStatus: paper.parseStatus || 'completed', summary: paper.summary, concepts: (paper.conceptTags || []).map((name, index) => ({ conceptId: `${paperId}-concept-${index + 1}`, name, description: `${name} 是该论文结构化解析得到的核心概念。` })), methods: [{ order: 1, title: '研究问题定义', description: `围绕“${paper.direction}”方向明确研究问题与任务目标。` }, { order: 2, title: '模型与方法设计', description: '分析论文提出的模型结构、训练方式和关键技术模块。' }, { order: 3, title: '实验验证', description: '使用实验结果和评价指标验证所提方法的有效性。' }], limitations: ['当前为前端 Mock 解析结果，可通过 VITE_USE_MOCK=false 切换到后端接口。'] };
}

export async function searchPapers(params = {}) {
  if (USE_MOCK) return searchMockPapers(params);
  const { query = '', categories = [], page = 1, pageSize = 12 } = params;
  const data = await apiClient.get('/papers', { params: { keyword: query || undefined, category: categories[0] || undefined, page, page_size: pageSize } });
  return { searchId: `search-${Date.now()}`, query, searchType: 'keyword', sortBy: 'relevance', total: data.total, page: data.page, pageSize: data.page_size, searchTimeMs: 0, items: data.items.map(toPaperListItem) };
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
