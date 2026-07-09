import { PAPERS } from '../data/papers';

export function mockWorkspaceReply(query) {
  const q = query.toLowerCase();
  if (q.includes('transformer') || q.includes('attention')) {
    return '已为您检索 Transformer 相关论文，结果见下方列表。';
  }
  if (q.includes('预训练') || q.includes('bert')) {
    return '已检索预训练语言模型方向论文。';
  }
  return `已理解您的问题「${query}」，为您更新了检索结果。`;
}

export function mockPaperReply(query, paperId) {
  const p = PAPERS[paperId];
  if (!p) return '暂无该论文的问答数据。';
  return `关于《${p.title.split(':')[0]}》：${p.summary} 如需深入某章节可继续追问。`;
}
