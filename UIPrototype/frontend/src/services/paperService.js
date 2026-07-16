import { PAPERS, PAPER_LIST } from '../data/papers';
import { isApiEnabled, requestApi } from './apiClient';
import detailMock from '../mocks/paper-detail.json';
import contentMock from '../mocks/paper-content.json';
import summaryMock from '../mocks/paper-summary.json';

const delay = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms));

function normalizeAuthors(authors) {
  if (Array.isArray(authors)) {
    return authors
      .map((author) => (typeof author === 'string' ? author : author?.name))
      .filter(Boolean);
  }

  return String(authors || '')
    .split(',')
    .map((author) => author.trim())
    .filter(Boolean);
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
    pdfUrl: paper.pdfUrl || `https://arxiv.org/pdf/${normalized.arxivId}`,
    sourceUrl: paper.sourceUrl || `https://arxiv.org/abs/${normalized.arxivId}`,
    codeUrl: paper.codeUrl || null
  };
}

async function searchPapersMock({
  query = '',
  searchType = 'keyword',
  categories = [],
  sortBy = 'relevance',
  page = 1,
  pageSize = 12
} = {}) {
  const startedAt = performance.now();
  await delay();

  const normalizedQuery = query.trim().toLowerCase();

  let items = PAPER_LIST.map(toPaperListItem).filter((paper) => {
    const matchesCategory =
      categories.length === 0 || categories.includes(paper.primaryCategory);

    if (!matchesCategory) return false;
    if (!normalizedQuery) return true;

    const searchableText = [
      paper.title,
      paper.summary,
      paper.primaryCategory,
      paper.arxivId,
      paper.researchDirection,
      ...paper.authors,
      ...paper.keywords,
      ...paper.conceptTags
    ]
      .join(' ')
      .toLowerCase();

    return searchableText.includes(normalizedQuery);
  });

  if (sortBy === 'date') {
    items = [...items].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
  }

  const start = (page - 1) * pageSize;
  const total = items.length;

  return {
    searchId: `search-${Date.now()}`,
    query,
    searchType,
    sortBy,
    total,
    page,
    pageSize,
    searchTimeMs: Math.max(1, Math.round(performance.now() - startedAt)),
    items: items.slice(start, start + pageSize)
  };
}

export async function searchPapers(options = {}) {
  if (!isApiEnabled()) return searchPapersMock(options);

  const { query = '', categories = [], page = 1, pageSize = 12 } = options;
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (query.trim()) params.set('keyword', query.trim());
  if (categories[0]) params.set('category', categories[0]);
  const data = await requestApi(`/papers?${params.toString()}`);
  return {
    searchId: `search-${Date.now()}`,
    query,
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
    searchTimeMs: 0,
    items: data.items.map(toPaperListItem)
  };
}

export async function getPaperDetail(paperId) {
  if (isApiEnabled() && /^\d+$/.test(String(paperId))) {
    const data = await requestApi(`/papers/${paperId}`);
    return createCompatibleDetail({
      ...data,
      paperId: data.paper_id,
      primaryCategory: data.primary_category,
      arxivId: data.arxiv_id,
      publishedAt: data.published_at,
      parseStatus: data.parse_status,
      pdfUrl: data.pdf_url,
      sourceUrl: data.source_url
    });
  }
  await delay(150);

  if (paperId === detailMock.data.paperId) {
    return createCompatibleDetail(detailMock.data);
  }

  const paper = PAPERS[paperId];
  return paper ? createCompatibleDetail(paper) : null;
}

export async function getPaperContent(paperId) {
  if (isApiEnabled() && /^\d+$/.test(String(paperId))) {
    const detail = await getPaperDetail(paperId);
    if (!detail) return null;
    return { paperId: detail.paperId, contentType: 'pdf', pdfUrl: detail.pdfUrl, htmlUrl: null, pageCount: null, defaultPage: 1, sections: [] };
  }
  await delay(150);

  if (paperId === contentMock.data.paperId) {
    return contentMock.data;
  }

  const detail = await getPaperDetail(paperId);
  if (!detail) return null;

  return {
    paperId,
    contentType: 'pdf',
    pdfUrl: detail.pdfUrl,
    htmlUrl: null,
    pageCount: null,
    defaultPage: 1,
    sections: []
  };
}

export async function getPaperSummary(paperId) {
  if (isApiEnabled() && /^\d+$/.test(String(paperId))) {
    const data = await requestApi(`/papers/${paperId}/wiki`);
    return { ...data, paperId: data.paper_id, parseStatus: data.parse_status };
  }
  await delay(150);

  if (paperId === summaryMock.data.paperId) {
    return summaryMock.data;
  }

  const paper = PAPERS[paperId];
  if (!paper) return null;

  return {
    paperId,
    parseStatus: paper.parseStatus || 'completed',
    summary: paper.summary,
    concepts: (paper.conceptTags || []).map((name, index) => ({
      conceptId: `${paperId}-concept-${index + 1}`,
      name,
      description: `${name} 是该论文结构化解析得到的核心概念。`
    })),
    methods: [
      {
        order: 1,
        title: '研究问题定义',
        description: `围绕“${paper.direction}”方向明确研究问题与任务目标。`
      },
      {
        order: 2,
        title: '模型与方法设计',
        description: '分析论文提出的模型结构、训练方式和关键技术模块。'
      },
      {
        order: 3,
        title: '实验验证',
        description: '使用实验结果和评价指标验证所提方法的有效性。'
      }
    ],
    limitations: ['当前为前端 Mock 解析结果，完整局限性将在后端解析接口接入后返回。']
  };
}
