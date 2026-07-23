import apiClient from './apiClient';
import { USE_MOCK } from './runtimeConfig';

export function isPersistedPaperId(paperId) {
  return !USE_MOCK && /^\d+$/.test(String(paperId));
}

export async function listActions({ userId, paperId, actionType } = {}) {
  if (USE_MOCK) return [];
  return apiClient.get('/learning/actions', {
    params: {
      user_id: userId,
      paper_id: paperId,
      action_type: actionType
    }
  });
}

export async function createAction({ userId, paperId, actionType, payload = {} }) {
  if (USE_MOCK) return null;
  return apiClient.post('/learning/actions', {
    user_id: userId,
    paper_id: Number(paperId),
    action_type: actionType,
    payload_json: payload
  });
}

export async function updateAction(actionId, payload = {}) {
  if (USE_MOCK) return null;
  return apiClient.patch(`/learning/actions/${actionId}`, { payload_json: payload });
}

export async function deleteAction(actionId) {
  if (USE_MOCK) return null;
  return apiClient.delete(`/learning/actions/${actionId}`);
}

export async function deleteActionsByType(userId, actionType) {
  if (USE_MOCK) return { deleted: 0 };
  return apiClient.delete('/learning/actions/bulk', {
    params: { user_id: userId, action_type: actionType }
  });
}

export async function setFavorite({ userId, paperId, favorite }) {
  const actions = await listActions({ userId, paperId, actionType: 'favorite' });
  const current = actions[0];
  if (favorite && !current) {
    return createAction({ userId, paperId, actionType: 'favorite', payload: { favorite: true } });
  }
  if (!favorite && current) {
    await deleteAction(current.id);
  }
  return favorite ? current : null;
}

export async function listPaperNotes(userId, paperId) {
  return listActions({ userId, paperId, actionType: 'note' });
}

export async function getLearningProfile(userId) {
  if (USE_MOCK) return { user_id: userId, persona: '研究', topics: ['cs.CL'], preferences: {} };
  return apiClient.get('/learning/profile', { params: { user_id: userId } });
}

export async function updateLearningProfile(userId, payload) {
  if (USE_MOCK) return { user_id: userId, ...payload };
  return apiClient.put('/learning/profile', payload, { params: { user_id: userId } });
}

export async function getConceptDictionary(userId) {
  if (USE_MOCK) return [];
  return apiClient.get('/learning/dictionary', { params: { user_id: userId } });
}

export async function clearConceptDictionary(userId) {
  if (USE_MOCK) return { cleared: 0, hidden_total: 0 };
  return apiClient.delete('/learning/dictionary', { params: { user_id: userId } });
}
