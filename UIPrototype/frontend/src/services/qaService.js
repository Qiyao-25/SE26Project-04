import apiClient from './apiClient';
import { USE_MOCK } from './runtimeConfig';
import qaMock from '../mocks/paper-qa.json';
import { PAPERS } from '../data/papers';

const delay = (ms = 500) => new Promise((resolve) => setTimeout(resolve, ms));

async function askMockPaper({ conversationId, paperId, question, history = [] }) {
  await delay();
  const normalizedQuestion = question?.trim();
  if (!normalizedQuestion) throw new Error('问题不能为空');

  if (paperId === qaMock.data.paperId) {
    return {
      ...qaMock.data,
      conversationId: conversationId || qaMock.data.conversationId,
      messageId: `assistant-${Date.now()}`,
      createdAt: new Date().toISOString()
    };
  }

  const paper = PAPERS[paperId];
  if (!paper) throw new Error('论文不存在');

  return {
    conversationId: conversationId || `conversation-${paperId}-${Date.now()}`,
    messageId: `assistant-${Date.now()}`,
    paperId,
    answer: `关于《${paper.title}》：${paper.summary} 你可以继续追问论文的方法、实验、创新点或局限性。`,
    createdAt: new Date().toISOString(),
    citations: [{
      citationId: `citation-${paperId}-${Date.now()}`,
      paperId,
      paperTitle: paper.title,
      sectionId: 'mock-summary',
      sectionTitle: '结构化摘要',
      pageNumber: 1,
      quote: paper.summary
    }],
    historyCount: history.length
  };
}

export async function askPaper(payload) {
  if (USE_MOCK) return askMockPaper(payload);
  const { paperId, ...requestBody } = payload;
  return apiClient.post(`/papers/${paperId}/qa`, requestBody);
}
