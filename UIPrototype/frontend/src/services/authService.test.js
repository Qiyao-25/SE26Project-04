import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loginUser, registerUser } from './authService';

vi.mock('./runtimeConfig', () => ({
  USE_MOCK: true,
  API_BASE_URL: '/api',
  API_TIMEOUT_MS: 10000
}));

vi.mock('./apiClient');

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loginUser', () => {
    it('should return mock token and user data for regular user', async () => {
      const result = await loginUser('user@example.com', 'password');

      expect(result).toHaveProperty('access_token', 'mock-token');
      expect(result.user).toHaveProperty('user_id', 'user@example.com');
      expect(result.user).toHaveProperty('email', 'user@example.com');
      expect(result.user).toHaveProperty('role', 'user');
    });

    it('should return admin role when email is admin', async () => {
      const result = await loginUser('admin', 'password');

      expect(result.user.role).toBe('admin');
    });

    it('should return demo-user as user_id when email is empty', async () => {
      const result = await loginUser('', 'password');

      expect(result.user.user_id).toBe('demo-user');
    });

    it('should handle undefined email gracefully', async () => {
      const result = await loginUser(undefined, 'password');

      expect(result.user.user_id).toBe('demo-user');
    });
  });

  describe('registerUser', () => {
    it('should return same result as loginUser in mock mode', async () => {
      const email = 'newuser@example.com';
      const password = 'newpassword';

      const registerResult = await registerUser(email, password);
      const loginResult = await loginUser(email, password);

      expect(registerResult).toEqual(loginResult);
      expect(registerResult.access_token).toBe('mock-token');
      expect(registerResult.user.email).toBe(email);
      expect(registerResult.user.role).toBe('user');
    });
  });
});