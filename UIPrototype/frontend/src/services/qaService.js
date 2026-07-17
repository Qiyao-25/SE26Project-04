import apiClient from './apiClient';
import { USE_MOCK } from './runtimeConfig';
import qaMock from '../mocks/paper-qa.json';
import { PAPERS } from '../data/papers';

const delay = (ms = 500) => new Promise((resolve) => setTimeout(resolve, ms));

function normalizeQaResult(data, paperId, historyCount = 0) {
  return {
    conversationId: data.conversationId || data.conversation_id || `conversation-${paperId}`,
    messageId: data.messageId || data.message_id || `assistant-${Date.now()}`,
    paperId: String(data.paperId || data.paper_id || paperId),
    answer: data.answer || '',
    createdAt: data.createdAt || data.created_at || new Date().toISOString(),
    citations: (data.citations || []).map((citation, index) => ({
      citationId: citation.citationId || citation.citation_id || `citation-${paperId}-${index + 1}`,
      paperId: String(citation.paperId || citation.paper_id || paperId),
      paperTitle: citation.paperTitle || citation.paper_title || '',
      sectionId: citation.sectionId || citation.section_id || '',
      sectionTitle: citation.sectionTitle || citation.section_title || '原文',
      pageNumber: citation.pageNumber ?? citation.page_number ?? null,
      quote: citation.quote || ''
    })),
    historyCount: data.historyCount ?? data.history_count ?? historyCount
  };
}

async function askMockPaper({ conversationId, paperId, question, history = [] }) {
  await delay();
  const normalizedQuestion = question?.trim();
  if (!normalizedQuestion) throw new Error('问题不能为空');
  if (paperId === qaMock.data.paperId) {
    return normalizeQaResult({ ...qaMock.data, conversationId: conversationId || qaMock.data.conversationId, messageId: `assistant-${Date.now()}`, createdAt: new Date().toISOString() }, paperId, history.length);
  }
  const paper = PAPERS[paperId];
  if (!paper) throw new Error('论文不存在');
  return normalizeQaResult({ conversationId: conversationId || `conversation-${paperId}-${Date.now()}`, messageId: `assistant-${Date.now()}`, paperId, answer: `关于《${paper.title}》：${paper.summary} 你可以继续追问论文的方法、实验、创新点或局限性。`, createdAt: new Date().toISOString(), citations: [{ citationId: `citation-${paperId}-${Date.now()}`, paperId, paperTitle: paper.title, sectionId: 'mock-summary', sectionTitle: '结构化摘要', pageNumber: 1, quote: paper.summary }], historyCount: history.length }, paperId, history.length);
}

export async function askPaper(payload) {
  if (USE_MOCK) return askMockPaper(payload);
  const data = await apiClient.post(`/papers/${payload.paperId}/qa`, {
    conversationId: payload.conversationId || null,
    question: payload.question,
    history: payload.history || []
  });
  return normalizeQaResult(data, payload.paperId, (payload.history || []).length);
}
