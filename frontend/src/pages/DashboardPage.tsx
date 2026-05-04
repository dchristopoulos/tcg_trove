import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Heart,
  MessageSquare,
  Calendar,
  BookOpen,
  Home,
  Plus,
  Trash2,
  MapPin,
  Bed,
  Bath,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../hooks/useAuth';
import { useFavorites } from '../hooks/useFavorites';
import { useDeleteListing } from '../hooks/useListings';
import { useToast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { StatusBadge, PropertyTypeBadge } from '../components/ui/Badge';
import { Skeleton } from '../components/ui/Skeleton';
import { favoritesApi, inquiriesApi, viewingsApi, reservationsApi, listingsApi, formatPrice, getImageUrl } from '../lib/api';
import { formatDate, formatDateTime, getErrorMessage } from '../lib/utils';
import type { Listing } from '../types';

type Tab = 'favorites' | 'inquiries' | 'reservations' | 'viewings' | 'my-listings';

const TABS: { id: Tab; label: string; icon: React.ReactNode; sellerOnly?: boolean }[] = [
  { id: 'favorites', label: 'Favorites', icon: <Heart className="w-4 h-4" /> },
  { id: 'inquiries', label: 'Inquiries', icon: <MessageSquare className="w-4 h-4" /> },
  { id: 'reservations', label: 'Reservations', icon: <BookOpen className="w-4 h-4" /> },
  { id: 'viewings', label: 'Viewings', icon: <Calendar className="w-4 h-4" /> },
  { id: 'my-listings', label: 'My Listings', icon: <Home className="w-4 h-4" />, sellerOnly: true },
];

export default function DashboardPage() {
  const { user, hasRole } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = (searchParams.get('tab') as Tab) ?? 'favorites';
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const { success, error: toastError } = useToast();

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    setSearchParams(tab !== 'favorites' ? { tab } : {}, { replace: true });
  };

  const isSellerOrAdmin = hasRole(['seller', 'admin']);
  const availableTabs = TABS.filter((t) => !t.sellerOnly || isSellerOrAdmin);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Welcome back, {user?.username}!
            </h1>
            <p className="text-slate-500 mt-1">Manage your activity and listings from here.</p>
          </div>
          {isSellerOrAdmin && (
            <Link to="/listings/new">
              <Button leftIcon={<Plus className="w-4 h-4" />}>Post Listing</Button>
            </Link>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-white rounded-2xl border border-slate-100 shadow-sm p-1 mb-6 overflow-x-auto">
        {availableTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-blue-500 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="fade-in">
        {activeTab === 'favorites' && <FavoritesTab />}
        {activeTab === 'inquiries' && <InquiriesTab />}
        {activeTab === 'reservations' && <ReservationsTab />}
        {activeTab === 'viewings' && <ViewingsTab />}
        {activeTab === 'my-listings' && isSellerOrAdmin && (
          <MyListingsTab
            onSuccess={success}
            onError={(msg) => toastError('Error', msg)}
          />
        )}
      </div>
    </div>
  );
}

// ── Favorites Tab ──────────────────────────────────────────────────────────────

function FavoritesTab() {
  const { data: favorites, isLoading } = useFavorites();

  if (isLoading) return <TabSkeleton count={4} />;

  if (!favorites?.length) {
    return (
      <EmptyState
        icon={<Heart className="w-8 h-8 text-slate-400" />}
        title="No saved properties"
        desc="Browse listings and click the heart icon to save properties you love."
        cta={{ label: 'Browse Listings', to: '/listings' }}
      />
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      {favorites.map((fav) => (
        <Link
          key={fav.id}
          to={`/listings/${fav.listing_id}`}
          className="group bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden card-hover"
        >
          <div className="relative h-40 bg-slate-100">
            <img
              src={getImageUrl(fav.listing?.image_url)}
              alt={fav.listing?.title}
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=600&q=60';
              }}
            />
            {fav.listing && (
              <div className="absolute top-2 left-2">
                <PropertyTypeBadge type={fav.listing.property_type} />
              </div>
            )}
          </div>
          <div className="p-4">
            {fav.listing ? (
              <>
                <p className="font-bold text-blue-600">{formatPrice(fav.listing.price)}</p>
                <p className="font-semibold text-slate-900 text-sm mt-0.5 line-clamp-1 group-hover:text-blue-600 transition-colors">
                  {fav.listing.title}
                </p>
                <div className="flex items-center gap-1 text-slate-500 text-xs mt-1">
                  <MapPin className="w-3 h-3" />
                  <span className="line-clamp-1">{fav.listing.location}</span>
                </div>
                <div className="flex items-center gap-3 mt-2 text-slate-500 text-xs">
                  <span className="flex items-center gap-1"><Bed className="w-3 h-3" /> {fav.listing.bedrooms}</span>
                  <span className="flex items-center gap-1"><Bath className="w-3 h-3" /> {fav.listing.bathrooms}</span>
                </div>
              </>
            ) : (
              <p className="text-slate-500 text-sm">Listing #{fav.listing_id}</p>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}

// ── Inquiries Tab ──────────────────────────────────────────────────────────────

function InquiriesTab() {
  const { data: inquiries, isLoading } = useQuery({
    queryKey: ['inquiries', 'me'],
    queryFn: inquiriesApi.getMyInquiries,
  });

  if (isLoading) return <TabSkeleton count={3} />;

  if (!inquiries?.length) {
    return (
      <EmptyState
        icon={<MessageSquare className="w-8 h-8 text-slate-400" />}
        title="No inquiries yet"
        desc="Send a message to a seller to start a conversation."
        cta={{ label: 'Browse Listings', to: '/listings' }}
      />
    );
  }

  return (
    <div className="space-y-4">
      {inquiries.map((inq) => (
        <Card key={inq.id} className="hover:border-blue-200 transition-colors">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <StatusBadge status={inq.status} />
                <span className="text-xs text-slate-400">{formatDateTime(inq.created_at)}</span>
              </div>
              <p className="text-slate-700 text-sm leading-relaxed">{inq.message}</p>
              {inq.listing && (
                <Link
                  to={`/listings/${inq.listing_id}`}
                  className="inline-flex items-center gap-1 mt-2 text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  <Home className="w-3 h-3" />
                  {inq.listing.title}
                </Link>
              )}
            </div>
            <Link to="/messages">
              <Button variant="outline" size="sm" leftIcon={<MessageSquare className="w-4 h-4" />}>
                Reply
              </Button>
            </Link>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── Reservations Tab ──────────────────────────────────────────────────────────

function ReservationsTab() {
  const { data: reservations, isLoading } = useQuery({
    queryKey: ['reservations', 'me'],
    queryFn: reservationsApi.getMyReservations,
  });

  if (isLoading) return <TabSkeleton count={3} />;

  if (!reservations?.length) {
    return (
      <EmptyState
        icon={<BookOpen className="w-8 h-8 text-slate-400" />}
        title="No reservations"
        desc="Book a property to see your reservations here."
        cta={{ label: 'Browse Listings', to: '/listings' }}
      />
    );
  }

  return (
    <div className="space-y-4">
      {reservations.map((res) => (
        <Card key={res.id} className="hover:border-blue-200 transition-colors">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex-1">
              {res.listing && (
                <Link
                  to={`/listings/${res.listing_id}`}
                  className="font-semibold text-slate-900 hover:text-blue-600 transition-colors block mb-1"
                >
                  {res.listing.title}
                </Link>
              )}
              <div className="flex items-center gap-4 text-sm text-slate-500">
                <span>Check-in: <strong className="text-slate-700">{formatDate(res.check_in)}</strong></span>
                <span>Check-out: <strong className="text-slate-700">{formatDate(res.check_out)}</strong></span>
              </div>
              {res.listing && (
                <div className="flex items-center gap-1 text-slate-400 text-xs mt-1">
                  <MapPin className="w-3 h-3" />
                  {res.listing.location}
                </div>
              )}
            </div>
            <StatusBadge status={res.status} />
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── Viewings Tab ──────────────────────────────────────────────────────────────

function ViewingsTab() {
  const { data: viewings, isLoading } = useQuery({
    queryKey: ['viewings', 'me'],
    queryFn: viewingsApi.getMyViewings,
  });

  if (isLoading) return <TabSkeleton count={3} />;

  if (!viewings?.length) {
    return (
      <EmptyState
        icon={<Calendar className="w-8 h-8 text-slate-400" />}
        title="No viewings scheduled"
        desc="Schedule a viewing for a property you're interested in."
        cta={{ label: 'Browse Listings', to: '/listings' }}
      />
    );
  }

  return (
    <div className="space-y-4">
      {viewings.map((v) => (
        <Card key={v.id} className="hover:border-blue-200 transition-colors">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex-1">
              {v.listing && (
                <Link
                  to={`/listings/${v.listing_id}`}
                  className="font-semibold text-slate-900 hover:text-blue-600 transition-colors block mb-1"
                >
                  {v.listing.title}
                </Link>
              )}
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Calendar className="w-4 h-4 text-blue-400" />
                <span>{formatDateTime(v.scheduled_at)}</span>
              </div>
              {v.listing && (
                <div className="flex items-center gap-1 text-slate-400 text-xs mt-1">
                  <MapPin className="w-3 h-3" />
                  {v.listing.location}
                </div>
              )}
            </div>
            <StatusBadge status={v.status} />
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── My Listings Tab ───────────────────────────────────────────────────────────

function MyListingsTab({
  onSuccess,
  onError,
}: {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const { data: listings, isLoading } = useQuery({
    queryKey: ['my-listings'],
    queryFn: () => listingsApi.getAll({ page: 1, page_size: 50 }),
  });

  const deleteMutation = useDeleteListing();

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this listing? This action cannot be undone.')) return;
    try {
      await deleteMutation.mutateAsync(id);
      onSuccess('Listing deleted successfully');
    } catch (err) {
      onError(getErrorMessage(err));
    }
  };

  if (isLoading) return <TabSkeleton count={3} />;

  const myListings: Listing[] = listings?.items ?? [];

  if (!myListings.length) {
    return (
      <EmptyState
        icon={<Home className="w-8 h-8 text-slate-400" />}
        title="No listings yet"
        desc="Create your first property listing to start getting inquiries."
        cta={{ label: 'Post a Listing', to: '/listings/new' }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-slate-500 text-sm">{myListings.length} listing{myListings.length !== 1 ? 's' : ''}</p>
        <Link to="/listings/new">
          <Button size="sm" leftIcon={<Plus className="w-4 h-4" />}>Add New</Button>
        </Link>
      </div>
      {myListings.map((listing) => (
        <Card key={listing.id} className="hover:border-blue-200 transition-colors">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-xl overflow-hidden bg-slate-100 shrink-0">
              <img
                src={getImageUrl(listing.image_url)}
                alt={listing.title}
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=200&q=60';
                }}
              />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <PropertyTypeBadge type={listing.property_type} />
              </div>
              <Link
                to={`/listings/${listing.id}`}
                className="font-semibold text-slate-900 hover:text-blue-600 transition-colors block line-clamp-1"
              >
                {listing.title}
              </Link>
              <div className="flex items-center gap-3 text-slate-500 text-sm mt-1">
                <span className="font-semibold text-blue-600">{formatPrice(listing.price)}</span>
                <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {listing.location}</span>
                <span className="flex items-center gap-1"><Bed className="w-3 h-3" /> {listing.bedrooms}</span>
                <span className="flex items-center gap-1"><Bath className="w-3 h-3" /> {listing.bathrooms}</span>
              </div>
            </div>
            <button
              onClick={() => handleDelete(listing.id)}
              disabled={deleteMutation.isPending}
              className="shrink-0 w-9 h-9 rounded-xl bg-red-50 text-red-500 hover:bg-red-100 flex items-center justify-center transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function TabSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-2xl border border-slate-100 p-5 space-y-3">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  icon,
  title,
  desc,
  cta,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  cta: { label: string; to: string };
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mb-4">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-slate-700 mb-1">{title}</h3>
      <p className="text-slate-500 text-sm mb-5 max-w-xs">{desc}</p>
      <Link to={cta.to}>
        <Button variant="outline">{cta.label}</Button>
      </Link>
    </div>
  );
}
