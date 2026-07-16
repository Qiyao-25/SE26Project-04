import qaMock from '../mocks/paper-qa.json';
import { PAPERS } from '../data/papers';
import { isApiEnabled, requestApi } from './apiClient';

const delay = (ms = 500) => new Promise((resolve) => setTimeout(resolve, ms));

export async function askPaper({
  conversationId,
  paperId,
  question,
  history = []
}) {
  if (isApiEnabled() && /^\d+$/.test(String(paperId))) {
    const data = await requestApi(`/papers/${paperId}/qa`, {
      method: 'POST',
      body: JSON.stringify({ question, history })
    });
    return {
      ...data,
      conversationId: data.conversation_id,
      messageId: data.message_id,
      createdAt: data.created_at
    };
  }
  await delay();

  const normalizedQuestion = question?.trim();
  if (!normalizedQuestion) {
    throw new Error('问题不能为空');
  }

  if (paperId === qaMock.data.paperId) {
    return {
      ...qaMock.data,
      conversationId: conversationId || qaMock.data.conversationId,
      messageId: `assistant-${Date.now()}`,
      createdAt: new Date().toISOString()
    };
  }

  const paper = PAPERS[paperId];
  if (!paper) {
    throw new Error('论文不存在');
  }

  return {
    conversationId: conversationId || `conversation-${paperId}-${Date.now()}`,
    messageId: `assistant-${Date.now()}`,
    paperId,
    answer: `关于《${paper.title}》：${paper.summary} 你可以继续追问论文的方法、实验、创新点或局限性。`,
    createdAt: new Date().toISOString(),
    citations: [
      {
        citationId: `citation-${paperId}-${Date.now()}`,
        paperId,
        paperTitle: paper.title,
        sectionId: 'mock-summary',
        sectionTitle: '结构化摘要',
        pageNumber: 1,
        quote: paper.summary
      }
    ],
    historyCount: history.length
  };
}
