/**
 * 首页推荐服务。
 *
 * - 每日精选：从数据库随机抽取论文
 * - 画像推荐：当前同样从库中抽样（可按 topics 粗过滤），函数签名预留给后续 AI 画像总结
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

function uniqueByPaperId(items) {
  const seen = new Set();
  return items.filter((item) => {
    const id = String(item.paperId);
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

async function sampleFromDatabase({ limit = 3, category, excludeIds = [] } = {}) {
  const exclude = new Set(excludeIds.map(String));
  // 多取一些再随机，避免首页每次同一批
  const pageSize = Math.min(50, Math.max(limit * 8, 12));
  const page = 1 + Math.floor(Math.random() * 3);

  const data = await searchPapers({
    query: '',
    categories: category ? [category] : [],
    page,
    pageSize,
    sortBy: 'date'
  });

  let pool = uniqueByPaperId(data.items || []).filter((item) => !exclude.has(String(item.paperId)));

  // 若随机页偏空，回退第一页
  if (pool.length < limit) {
    const fallback = await searchPapers({
      query: '',
      categories: category ? [category] : [],
      page: 1,
      pageSize: 50,
      sortBy: 'date'
    });
    pool = uniqueByPaperId([...(fallback.items || []), ...pool]).filter(
      (item) => !exclude.has(String(item.paperId))
    );
  }

  return shuffle(pool).slice(0, limit);
}

/** 每日 ArXiv 精选：数据库随机论文 */
export async function fetchDailyArxivPicks({ limit = 3 } = {}) {
  if (USE_MOCK) {
    const data = await searchPapers({ page: 1, pageSize: 12, sortBy: 'date' });
    return shuffle(data.items || []).slice(0, limit);
  }
  return apiClient.get('/recommendations/daily', { params: { limit } });
}

/**
 * 基于画像推荐论文。
 *
 * @param {{ persona?: string, topics?: string[], limit?: number, excludeIds?: Array<string|number> }} options
 * @returns {Promise<Array>} 论文列表（与 searchPapers items 同结构）
 *
 * 当前通过后端画像推荐接口读取数据库结果；后续可在后端替换为更复杂的画像模型。
 */
export async function fetchProfileRecommendations({
  userId = 'demo-user',
  persona = '',
  topics = [],
  limit = 3,
  excludeIds = []
} = {}) {
  // 预留：画像上下文写入，便于后续 AI 管线消费
  const profileContext = {
    userId,
    persona,
    topics: Array.isArray(topics) ? topics : [],
    source: 'heuristic-random', // 将来改为 'ai-profile'
    generatedAt: new Date().toISOString()
  };

  if (USE_MOCK) {
    const data = await searchPapers({ page: 1, pageSize: 12 });
    return shuffle(data.items || []).slice(0, limit);
  }

  return apiClient.get('/recommendations/profile', {
    params: {
      user_id: profileContext.userId || 'demo-user',
      persona,
      topics: profileContext.topics.join(','),
      limit,
      exclude_ids: excludeIds.join(',')
    }
  });
}
