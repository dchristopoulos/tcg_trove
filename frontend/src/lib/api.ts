import axios from 'axios';
import type {
  Listing,
  ListingsResponse,
  SearchParams,
  Favorite,
  Inquiry,
  Message,
  Viewing,
  Reservation,
  User,
} from '../types';

const BASE_URL = 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Inject auth headers on every request
apiClient.interceptors.request.use((config) => {
  const userId = localStorage.getItem('x-user-id');
  const sessionToken = localStorage.getItem('x-session-token');
  if (userId && sessionToken) {
    config.headers['x-user-id'] = userId;
    config.headers['x-session-token'] = sessionToken;
  }
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('x-user-id');
      localStorage.removeItem('x-session-token');
      localStorage.removeItem('hf-user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ─── Auth ────────────────────────────────────────────────────────────────────

export const authApi = {
  register: async (data: { username: string; email: string; password: string }) => {
    const res = await apiClient.post('/api/v1/users/', data);
    return res.data;
  },

  loginInit: async (data: { identifier: string; password: string }) => {
    const res = await apiClient.post('/api/v1/users/login-init', data);
    return res.data as { challenge_id: string; message: string };
  },

  loginVerify: async (data: { challenge_id: string; otp_code: string }) => {
    const res = await apiClient.post('/api/v1/users/login-verify', data);
    const userId = String(res.data.user_id);
    const sessionToken = res.data.session_token as string;
    // Set auth in localStorage so the /me interceptor picks it up immediately
    localStorage.setItem('x-user-id', userId);
    localStorage.setItem('x-session-token', sessionToken);
    const userRes = await apiClient.get('/api/v1/users/me');
    return { data: userRes.data as User, userId, sessionToken };
  },

  health: async () => {
    const res = await apiClient.get('/health');
    return res.data;
  },
};

// ─── Listings ────────────────────────────────────────────────────────────────

export const listingsApi = {
  getAll: async (params?: { page?: number; page_size?: number }): Promise<ListingsResponse> => {
    const res = await apiClient.get('/api/v1/listings/search/page', { params });
    return res.data;
  },

  search: async (params: SearchParams): Promise<ListingsResponse> => {
    const res = await apiClient.get('/api/v1/listings/search/page', { params });
    return res.data;
  },

  getById: async (id: string): Promise<Listing> => {
    const res = await apiClient.get(`/api/v1/listings/${id}`);
    return res.data;
  },

  getSimilar: async (id: string): Promise<Listing[]> => {
    const res = await apiClient.get(`/api/v1/listings/${id}/similar`);
    return res.data;
  },

  create: async (formData: FormData): Promise<Listing> => {
    const res = await apiClient.post('/api/v1/listings/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/listings/${id}`);
  },
};

// ─── Favorites ───────────────────────────────────────────────────────────────

export const favoritesApi = {
  getAll: async (): Promise<Favorite[]> => {
    const res = await apiClient.get('/api/v1/favorites/');
    return res.data;
  },

  add: async (listingId: string): Promise<Favorite> => {
    const res = await apiClient.post(`/api/v1/favorites/${listingId}`);
    return res.data;
  },

  remove: async (listingId: string): Promise<void> => {
    await apiClient.delete(`/api/v1/favorites/${listingId}`);
  },
};

// ─── Inquiries ───────────────────────────────────────────────────────────────

export const inquiriesApi = {
  create: async (data: { listing_id: string; message: string }): Promise<Inquiry> => {
    const res = await apiClient.post('/api/v1/inquiries/', data);
    return res.data;
  },

  getMyInquiries: async (): Promise<Inquiry[]> => {
    const res = await apiClient.get('/api/v1/inquiries/me');
    return res.data;
  },

  getMessages: async (inquiryId: string): Promise<Message[]> => {
    const res = await apiClient.get(`/api/v1/inquiries/${inquiryId}/messages`);
    return res.data;
  },

  sendMessage: async (inquiryId: string, content: string): Promise<Message> => {
    const res = await apiClient.post(`/api/v1/inquiries/${inquiryId}/messages`, { content });
    return res.data;
  },
};

// ─── Viewings ────────────────────────────────────────────────────────────────

export const viewingsApi = {
  create: async (data: { listing_id: string; scheduled_at: string }): Promise<Viewing> => {
    const res = await apiClient.post('/api/v1/viewings/', data);
    return res.data;
  },

  getMyViewings: async (): Promise<Viewing[]> => {
    const res = await apiClient.get('/api/v1/viewings/me');
    return res.data;
  },
};

// ─── Reservations ────────────────────────────────────────────────────────────

export const reservationsApi = {
  create: async (data: {
    listing_id: string;
    check_in: string;
    check_out: string;
  }): Promise<Reservation> => {
    const res = await apiClient.post('/api/v1/reservations/', data);
    return res.data;
  },

  getMyReservations: async (): Promise<Reservation[]> => {
    const res = await apiClient.get('/api/v1/reservations/me');
    return res.data;
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

export function getImageUrl(path?: string): string {
  if (!path) return 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&q=80';
  if (path.startsWith('http')) return path;
  return `${BASE_URL}${path}`;
}

export function formatPrice(price: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(price);
}
