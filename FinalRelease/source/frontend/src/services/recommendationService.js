/**
 * 首页推荐服务：每日精选 / 画像排序 / 订阅更新。
 */
import { searchPapers } from './paperService';
import { USE_MOCK } from './runtimeConfig';
import apiClient from './apiClient';

function shuffle(items) {
  const next = [...items];
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [next[i], next[j]] = [next[j], next[i]];
  }
  return next;
}

function normalizeRecommendedPaper(paper) {
  return {
    paperId: paper.paperId ?? paper.paper_id ?? paper.id,
    title: paper.title || '',
    authors: Array.isArray(paper.authors) ? paper.authors : [],
    primaryCategory: paper.primaryCategory || paper.primary_category || '未分类',
    arxivId: paper.arxivId || paper.arxiv_id || '',
    publishedAt: paper.publishedAt || paper.published_at || '',
    summary: paper.summary || paper.abstract || '',
    keywords: paper.keywords || [],
    researchDirection: paper.researchDirection || paper.research_direction || '',
    conceptTags: paper.conceptTags || paper.concept_tags || [],
    parseStatus: paper.parseStatus || paper.parse_status || 'pending',
    chunkCount: paper.chunkCount ?? paper.chunk_count ?? 0,
    qaReady: Boolean(paper.qaReady ?? paper.qa_ready),
    sourceUrl: paper.sourceUrl || paper.source_url || '',
    pdfUrl: paper.pdfUrl || paper.pdf_url || '',
    reason: paper.reason || '',
    recommendSource: paper.recommendSource || paper.recommend_source || ''
  };
}

function normalizeRecommendations(items) {
  return (items || []).map(normalizeRecommendedPaper).filter((item) => item.paperId !== undefined && item.paperId !== null);
}

/** 每日精选：近期 + 可问答 + 类别多样性 */
export async function fetchDailyArxivPicks({ limit = 3, excludeIds = [] } = {}) {
  if (USE_MOCK) {
    const data = await searchPapers({ page: 1, pageSize: 24, sortBy: 'date' });
    const excluded = new Set((excludeIds || []).map(String));
    const pool = shuffle((data.items || []).filter((item) => !excluded.has(String(item.paperId))));
    return (pool.length ? pool : shuffle(data.items || [])).slice(0, limit);
  }
  const data = await apiClient.get('/recommendations/daily', {
    params: {
      limit,
      exclude_ids: (excludeIds || []).join(',') || undefined,
      _t: Date.now()
    }
  });
  return normalizeRecommendations(data);
}

/**
 * 基于画像推荐论文（多信号排序：兴趣主题、阅读/收藏亲和、词典概念、人格权重等）。
 */
export async function fetchProfileRecommendations({
  userId = 'demo-user',
  persona = '',
  topics = [],
  limit = 3,
  excludeIds = []
} = {}) {
  if (USE_MOCK) {
    const data = await searchPapers({ page: 1, pageSize: 12 });
    return shuffle(data.items || []).slice(0, limit);
  }

  const data = await apiClient.get('/recommendations/profile', {
    params: {
      user_id: userId || 'demo-user',
      persona,
      topics: (Array.isArray(topics) ? topics : []).join(','),
      limit,
      exclude_ids: excludeIds.join(','),
      _t: Date.now()
    }
  });
  return normalizeRecommendations(data);
}

/** 订阅同步论文流 */
export async function fetchSubscriptionRecommendations({
  userId = 'demo-user',
  limit = 6,
  excludeIds = []
} = {}) {
  if (USE_MOCK) {
    const data = await searchPapers({ page: 1, pageSize: 12, sortBy: 'date' });
    return shuffle(data.items || []).slice(0, limit);
  }
  const data = await apiClient.get('/recommendations/subscriptions', {
    params: {
      user_id: userId,
      limit,
      exclude_ids: excludeIds.join(','),
      _t: Date.now()
    }
  });
  return normalizeRecommendations(data);
}

export async function syncSubscriptions(userId, { maxPerSubscription = 5 } = {}) {
  if (USE_MOCK) {
    return { fetched: 0, created: 0, updated: 0, message: 'Mock 模式跳过同步', paper_ids: [] };
  }
  // arXiv 可能限流/慢响应；同步单独放宽超时（默认 API_TIMEOUT 可能只有 90s）
  return apiClient.post('/subscriptions/sync', {}, {
    params: { user_id: userId, max_per_subscription: maxPerSubscription },
    timeout: 180000,
  });
}
