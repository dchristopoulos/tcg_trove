import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { favoritesApi } from '../lib/api';
import { useAuth } from './useAuth';

export const favoriteKeys = {
  all: ['favorites'] as const,
};

export function useFavorites() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: favoriteKeys.all,
    queryFn: favoritesApi.getAll,
    enabled: isAuthenticated,
  });
}

export function useToggleFavorite() {
  const queryClient = useQueryClient();

  const addMutation = useMutation({
    mutationFn: (listingId: string) => favoritesApi.add(listingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: favoriteKeys.all });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (listingId: string) => favoritesApi.remove(listingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: favoriteKeys.all });
    },
  });

  return { addMutation, removeMutation };
}
