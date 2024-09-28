const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8000";

export function getAuthToken(): string | null {
  return localStorage.getItem("fetagram_jwt_token");
}

export function setAuthToken(token: string | null): void {
  if (token) {
    localStorage.setItem("fetagram_jwt_token", token);
  } else {
    localStorage.removeItem("fetagram_jwt_token");
  }
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `API Error (${response.status})`);
  }
  return data as T;
}

export const FetagramApiClient = {
  register: (payload: { username: string; email: string; password: string; full_name?: string }) =>
    apiRequest<{ access_token: string; user: any }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { username: string; password: string }) =>
    apiRequest<{ access_token: string; user: any }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getMe: () => apiRequest<any>("/api/auth/me"),

  getFeed: (page = 1, userId?: number) =>
    apiRequest<{ posts: any[]; announcement: any }>(
      `/api/posts/feed?page=${page}${userId ? `&user_id=${userId}` : ""}`
    ),

  createPost: (payload: { media_url: string; caption: string; filter_name: string; location?: string }) =>
    apiRequest<any>("/api/posts/create", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  toggleLike: (postId: number) =>
    apiRequest<any>(`/api/posts/${postId}/like`, {
      method: "POST",
    }),

  addComment: (postId: number, text: string) =>
    apiRequest<any>(`/api/posts/${postId}/comment`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  getStories: () => apiRequest<any[]>("/api/stories"),

  getReels: () => apiRequest<any[]>("/api/reels"),

  getUsers: () => apiRequest<any[]>("/api/admin/users"),

  sendMessage: (receiver_id: number, content: string) =>
    apiRequest<any>("/api/messages", {
      method: "POST",
      body: JSON.stringify({ receiver_id, content }),
    }),
};
