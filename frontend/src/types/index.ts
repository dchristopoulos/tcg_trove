// User types
export type UserRole = 'buyer' | 'seller' | 'supervisor' | 'admin';

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  must_reset_password?: boolean;
  email_verified?: boolean;
}

export interface AuthState {
  user: User | null;
  userId: string | null;
  sessionToken: string | null;
  isAuthenticated: boolean;
}

// Listing types
export type PropertyType = 'house' | 'apartment' | 'villa' | 'studio' | 'condo' | 'townhouse';

export interface Listing {
  id: string;
  title: string;
  price: number;
  location: string;
  property_type: PropertyType;
  bedrooms: number;
  bathrooms: number;
  description: string;
  image_url?: string;
  seller_id: string;
  created_at: string;
  is_favorited?: boolean;
}

export interface ListingsResponse {
  items: Listing[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SearchParams {
  q?: string;
  property_type?: string;
  min_price?: number;
  max_price?: number;
  min_bedrooms?: number;
  page?: number;
  page_size?: number;
}

// Favorite
export interface Favorite {
  id: string;
  listing_id: string;
  user_id: string;
  listing: Listing;
  created_at: string;
}

// Inquiry / Messages
export interface Inquiry {
  id: string;
  listing_id: string;
  user_id: string;
  message: string;
  status: 'open' | 'closed' | 'pending';
  listing?: Listing;
  created_at: string;
}

export interface Message {
  id: string;
  inquiry_id: string;
  sender_id: string;
  content: string;
  created_at: string;
}

// Viewing
export interface Viewing {
  id: string;
  listing_id: string;
  user_id: string;
  scheduled_at: string;
  status: 'pending' | 'confirmed' | 'cancelled';
  listing?: Listing;
  created_at: string;
}

// Reservation
export interface Reservation {
  id: string;
  listing_id: string;
  user_id: string;
  check_in: string;
  check_out: string;
  status: 'pending' | 'confirmed' | 'cancelled';
  listing?: Listing;
  created_at: string;
}

// Create listing form
export interface CreateListingForm {
  title: string;
  price: number;
  location: string;
  property_type: PropertyType;
  bedrooms: number;
  bathrooms: number;
  description: string;
  image?: File;
}

// Toast
export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

// API error
export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
