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
