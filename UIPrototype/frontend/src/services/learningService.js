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
