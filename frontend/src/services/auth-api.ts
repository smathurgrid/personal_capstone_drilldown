import { API_BASE, apiFetch } from "./api";

const AUTH = `${API_BASE}/api/auth`;

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  avatar_url?: string | null;
};

type AuthResponse = {
  user: AuthUser;
};

async function authRequest(path: string, body?: Record<string, string>): Promise<AuthUser> {
  const res = await apiFetch(`${AUTH}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Authentication failed");
  }
  const data = (await res.json()) as AuthResponse;
  return data.user;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  return authRequest("/login", { email, password });
}

export async function register(name: string, email: string, password: string): Promise<AuthUser> {
  return authRequest("/register", { name, email, password });
}

export async function updateProfile(name: string): Promise<AuthUser> {
  return authRequest("/profile", { name });
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<AuthUser> {
  return authRequest("/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function uploadAvatar(file: File): Promise<AuthUser> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch(`${AUTH}/avatar`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Avatar upload failed");
  }
  const data = (await res.json()) as AuthResponse;
  return data.user;
}

export async function logout(): Promise<void> {
  const res = await apiFetch(`${AUTH}/logout`, { method: "POST" });
  if (!res.ok) throw new Error("Logout failed");
}

export async function fetchMe(): Promise<AuthUser | null> {
  const res = await apiFetch(`${AUTH}/session`);
  if (!res.ok) throw new Error("Session check failed");
  const data = (await res.json()) as AuthResponse;
  return data.user ?? null;
}
