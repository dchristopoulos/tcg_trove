import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listingsApi } from '../lib/api';
import type { SearchParams } from '../types';

export const listingKeys = {
  all: ['listings'] as const,
  lists: () => [...listingKeys.all, 'list'] as const,
  list: (params: object) => [...listingKeys.lists(), params] as const,
  search: (params: SearchParams) => [...listingKeys.all, 'search', params] as const,
  detail: (id: string) => [...listingKeys.all, 'detail', id] as const,
  similar: (id: string) => [...listingKeys.all, 'similar', id] as const,
};

export function useListings(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: listingKeys.list(params ?? {}),
    queryFn: () => listingsApi.getAll(params),
  });
}

export function useSearchListings(params: SearchParams, enabled = true) {
  return useQuery({
    queryKey: listingKeys.search(params),
    queryFn: () => listingsApi.search(params),
    enabled,
  });
}

export function useListing(id: string) {
  return useQuery({
    queryKey: listingKeys.detail(id),
    queryFn: () => listingsApi.getById(id),
    enabled: !!id,
  });
}

export function useSimilarListings(id: string) {
  return useQuery({
    queryKey: listingKeys.similar(id),
    queryFn: () => listingsApi.getSimilar(id),
    enabled: !!id,
  });
}

export function useDeleteListing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => listingsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: listingKeys.all });
    },
  });
}
