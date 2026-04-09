const ACCESS_TOKEN_KEY = 'adaptix-ai.access-token';
const ROLE_KEY = 'adaptix-ai.role';
const TENANT_KEY = 'adaptix-ai.tenant-id';
const USER_KEY = 'adaptix-ai.user-id';
const API_BASE = process.env.NEXT_PUBLIC_AI_API_BASE ?? 'http://127.0.0.1:8014';

type LoginResponse = { access_token: string; role: string; tenant_id: string; user_id: string };

export function getStoredAuthToken() { return typeof window === 'undefined' ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY); }
export function getStoredAuthRole() { return typeof window === 'undefined' ? '' : window.localStorage.getItem(ROLE_KEY) ?? ''; }
export function getStoredTenantId() { return typeof window === 'undefined' ? '' : window.localStorage.getItem(TENANT_KEY) ?? ''; }
export function getStoredUserId() { return typeof window === 'undefined' ? '' : window.localStorage.getItem(USER_KEY) ?? ''; }

export async function loginDev(payload: { role: string; tenant_id: string; user_id: string }) {
  const response = await fetch(`${API_BASE}/api/v1/auth/dev-login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(await response.text() || `Login failed with ${response.status}`);
  const json = await response.json() as LoginResponse;
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, json.access_token);
    window.localStorage.setItem(ROLE_KEY, json.role);
    window.localStorage.setItem(TENANT_KEY, json.tenant_id);
    window.localStorage.setItem(USER_KEY, json.user_id);
  }
  return json;
}
