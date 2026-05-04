import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Bed, Bath, Heart, Trash2 } from 'lucide-react';
import { formatPrice, getImageUrl } from '../../lib/api';
import { PropertyTypeBadge } from '../ui/Badge';
import { useToast } from '../ui/Toast';
import { useAuth } from '../../hooks/useAuth';
import { useToggleFavorite, useFavorites } from '../../hooks/useFavorites';
import type { Listing } from '../../types';
import { cn } from '../../lib/utils';

interface ListingCardProps {
  listing: Listing;
  onDelete?: (id: string) => void;
  showDelete?: boolean;
}

export function ListingCard({ listing, onDelete, showDelete = false }: ListingCardProps) {
  const { isAuthenticated } = useAuth();
  const { data: favorites } = useFavorites();
  const { addMutation, removeMutation } = useToggleFavorite();
  const { success, error } = useToast();
  const [imgError, setImgError] = useState(false);

  const isFavorited = favorites?.some((f) => f.listing_id === listing.id) ?? listing.is_favorited;
  const isToggling = addMutation.isPending || removeMutation.isPending;

  const handleFavorite = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isAuthenticated) {
      error('Sign in required', 'Please log in to save listings');
      return;
    }
    try {
      if (isFavorited) {
        await removeMutation.mutateAsync(listing.id);
        success('Removed from favorites');
      } else {
        await addMutation.mutateAsync(listing.id);
        success('Added to favorites');
      }
    } catch {
      error('Failed to update favorites');
    }
  };

  return (
    <div className="bg-white rounded-2xl overflow-hidden border border-slate-100 shadow-sm card-hover group">
      <Link to={`/listings/${listing.id}`}>
        {/* Image */}
        <div className="relative h-52 overflow-hidden bg-slate-100">
          <img
            src={imgError ? 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&q=80' : getImageUrl(listing.image_url)}
            alt={listing.title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            onError={() => setImgError(true)}
          />
          {/* Overlay gradient */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

          {/* Favorite button */}
          <button
            onClick={handleFavorite}
            disabled={isToggling}
            className={cn(
              'absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center transition-all duration-200 shadow-sm',
              isFavorited
                ? 'bg-red-500 text-white'
                : 'bg-white/90 text-slate-400 hover:text-red-500 hover:bg-white'
            )}
          >
            <Heart className={cn('w-4 h-4', isFavorited && 'fill-current')} />
          </button>

          {/* Property type badge */}
          <div className="absolute top-3 left-3">
            <PropertyTypeBadge type={listing.property_type} />
          </div>

          {/* Delete button */}
          {showDelete && onDelete && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete(listing.id);
              }}
              className="absolute bottom-3 right-3 w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600 transition-colors shadow-sm"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-5">
          <div className="mb-2">
            <p className="text-xl font-bold text-blue-600">
              {formatPrice(listing.price)}
            </p>
          </div>

          <h3 className="font-semibold text-slate-900 line-clamp-1 mb-1 group-hover:text-blue-600 transition-colors">
            {listing.title}
          </h3>

          <div className="flex items-center gap-1 text-slate-500 text-sm mb-3">
            <MapPin className="w-3.5 h-3.5 shrink-0" />
            <span className="line-clamp-1">{listing.location}</span>
          </div>

          <div className="flex items-center gap-4 text-slate-600 text-sm pt-3 border-t border-slate-50">
            <span className="flex items-center gap-1.5">
              <Bed className="w-4 h-4 text-slate-400" />
              <span>{listing.bedrooms} bed{listing.bedrooms !== 1 ? 's' : ''}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <Bath className="w-4 h-4 text-slate-400" />
              <span>{listing.bathrooms} bath{listing.bathrooms !== 1 ? 's' : ''}</span>
            </span>
          </div>
        </div>
      </Link>
    </div>
  );
}
