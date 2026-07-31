import apiClient from './apiClient';
import { USE_MOCK } from './runtimeConfig';

export async function loginUser(email, password) {
  if (USE_MOCK) return { access_token: 'mock-token', user: { user_id: email || 'demo-user', email, role: email === 'admin' ? 'admin' : 'user' } };
  return apiClient.post('/auth/login', { email, password });
}

export async function registerUser(email, password) {
  if (USE_MOCK) return loginUser(email, password);
  return apiClient.post('/auth/register', { email, password });
}

export async function getCurrentUser() {
  return apiClient.get('/auth/me');
}

export async function updateAccount(payload) {
  return apiClient.put('/auth/account', payload);
}
