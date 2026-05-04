import React from 'react';
import { ListingCard } from './ListingCard';
import { ListingCardSkeleton } from '../ui/Skeleton';
import { SearchX } from 'lucide-react';
import type { Listing } from '../../types';

interface ListingGridProps {
  listings: Listing[];
  isLoading?: boolean;
  skeletonCount?: number;
  onDelete?: (id: string) => void;
  showDelete?: boolean;
  emptyMessage?: string;
}

export function ListingGrid({
  listings,
  isLoading = false,
  skeletonCount = 6,
  onDelete,
  showDelete = false,
  emptyMessage = 'No listings found',
}: ListingGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <ListingCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (listings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mb-4">
          <SearchX className="w-8 h-8 text-slate-400" />
        </div>
        <h3 className="text-lg font-semibold text-slate-700 mb-1">{emptyMessage}</h3>
        <p className="text-slate-500 text-sm">Try adjusting your filters or search terms</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
      {listings.map((listing) => (
        <ListingCard
          key={listing.id}
          listing={listing}
          onDelete={onDelete}
          showDelete={showDelete}
        />
      ))}
    </div>
  );
}
