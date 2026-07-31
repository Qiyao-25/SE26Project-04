import apiClient from './apiClient';

export async function getAdminOverview() {
  return apiClient.get('/admin/overview');
}

export async function getAdminTasks(limit = 50) {
  return apiClient.get('/admin/tasks', { params: { limit } });
}

export async function getAdminUsers(limit = 100) {
  return apiClient.get('/admin/users', { params: { limit } });
}

export async function getAdminQuality(limit = 50) {
  return apiClient.get('/admin/quality', { params: { limit } });
}

export async function getAdminAudit(limit = 50) {
  return apiClient.get('/admin/audit', { params: { limit } });
}

export async function updateAdminUserStatus(userId, isActive) {
  return apiClient.patch(`/admin/users/${userId}`, { is_active: isActive });
}

export async function deleteAdminUser(userId) {
  return apiClient.delete(`/admin/users/${userId}`);
}

export async function retryAdminParseTask(taskId) {
  return apiClient.post(`/tasks/${taskId}/retry`);
}

export async function enqueuePendingParseTasks(limit = 20) {
  return apiClient.post('/tasks/enqueue-pending', null, { params: { limit } });
}

export async function deleteAdminParseTask(taskId) {
  return apiClient.delete(`/tasks/${taskId}`);
}

export async function getAdminCrawlSettings() {
  return apiClient.get('/admin/crawl-settings');
}

export async function updateAdminCrawlSettings(payload) {
  return apiClient.patch('/admin/crawl-settings', payload);
}
