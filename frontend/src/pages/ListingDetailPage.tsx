import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  MapPin,
  Bed,
  Bath,
  Heart,
  Calendar,
  MessageSquare,
  BookOpen,
  ArrowLeft,
  Home,
  Share2,
  CheckCircle,
} from 'lucide-react';
import { useListing, useSimilarListings } from '../hooks/useListings';
import { useToggleFavorite, useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { PropertyTypeBadge } from '../components/ui/Badge';
import { ListingCardSkeleton, ListingDetailSkeleton } from '../components/ui/Skeleton';
import { ListingCard } from '../components/listings/ListingCard';
import { Input, Textarea } from '../components/ui/Input';
import { formatPrice, getImageUrl, inquiriesApi, viewingsApi, reservationsApi } from '../lib/api';
import { formatDate, getErrorMessage, capitalize } from '../lib/utils';
import { useMutation } from '@tanstack/react-query';

type ModalType = 'viewing' | 'reservation' | 'inquiry' | null;

export default function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { success, error: toastError } = useToast();

  const { data: listing, isLoading, error } = useListing(id!);
  const { data: similarListings, isLoading: similarLoading } = useSimilarListings(id!);
  const { data: favorites } = useFavorites();
  const { addMutation, removeMutation } = useToggleFavorite();

  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [imgError, setImgError] = useState(false);

  // Viewing form
  const [viewingDate, setViewingDate] = useState('');
  // Reservation form
  const [checkIn, setCheckIn] = useState('');
  const [checkOut, setCheckOut] = useState('');
  // Inquiry form
  const [inquiryMsg, setInquiryMsg] = useState('');

  const isFavorited = favorites?.some((f) => f.listing_id === id) ?? listing?.is_favorited;

  const scheduleViewingMutation = useMutation({
    mutationFn: () => viewingsApi.create({ listing_id: id!, scheduled_at: viewingDate }),
    onSuccess: () => {
      success('Viewing Scheduled', 'We will confirm your appointment soon.');
      setActiveModal(null);
      setViewingDate('');
    },
    onError: (err) => toastError('Failed to schedule', getErrorMessage(err)),
  });

  const bookReservationMutation = useMutation({
    mutationFn: () => reservationsApi.create({ listing_id: id!, check_in: checkIn, check_out: checkOut }),
    onSuccess: () => {
      success('Reservation Made', 'Your booking request has been sent.');
      setActiveModal(null);
      setCheckIn('');
      setCheckOut('');
    },
    onError: (err) => toastError('Reservation failed', getErrorMessage(err)),
  });

  const sendInquiryMutation = useMutation({
    mutationFn: () => inquiriesApi.create({ listing_id: id!, message: inquiryMsg }),
    onSuccess: () => {
      success('Message Sent', 'The seller will get back to you shortly.');
      setActiveModal(null);
      setInquiryMsg('');
    },
    onError: (err) => toastError('Failed to send', getErrorMessage(err)),
  });

  const handleFavorite = async () => {
    if (!isAuthenticated) {
      toastError('Sign in required', 'Please log in to save listings');
      navigate('/login');
      return;
    }
    try {
      if (isFavorited) {
        await removeMutation.mutateAsync(id!);
        success('Removed from favorites');
      } else {
        await addMutation.mutateAsync(id!);
        success('Added to favorites');
      }
    } catch {
      toastError('Failed to update favorites');
    }
  };

  const requireAuth = (action: () => void) => {
    if (!isAuthenticated) {
      toastError('Sign in required', 'Please log in to continue');
      navigate('/login');
      return;
    }
    action();
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <ListingDetailSkeleton />
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <div className="text-6xl mb-4">🏚</div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Listing Not Found</h2>
        <p className="text-slate-500 mb-6">This property may have been removed or doesn&apos;t exist.</p>
        <Link to="/listings">
          <Button leftIcon={<ArrowLeft className="w-4 h-4" />}>Back to Listings</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <Link to="/" className="hover:text-blue-600 flex items-center gap-1 transition-colors">
          <Home className="w-4 h-4" /> Home
        </Link>
        <span>/</span>
        <Link to="/listings" className="hover:text-blue-600 transition-colors">Listings</Link>
        <span>/</span>
        <span className="text-slate-900 font-medium line-clamp-1 max-w-xs">{listing.title}</span>
      </nav>

      {/* Hero Image */}
      <div className="relative h-72 sm:h-96 md:h-[480px] rounded-3xl overflow-hidden mb-8 bg-slate-100">
        <img
          src={imgError ? 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=1200&q=80' : getImageUrl(listing.image_url)}
          alt={listing.title}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />

        {/* Top actions */}
        <div className="absolute top-4 left-4 right-4 flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="glass rounded-xl px-3 py-2 text-white text-sm font-medium flex items-center gap-1.5 hover:bg-white/25 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                navigator.clipboard.writeText(window.location.href);
                success('Link copied!');
              }}
              className="glass w-9 h-9 rounded-xl flex items-center justify-center text-white hover:bg-white/25 transition-colors"
            >
              <Share2 className="w-4 h-4" />
            </button>
            <button
              onClick={handleFavorite}
              className={`glass w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                isFavorited ? 'bg-red-500/80 text-white' : 'text-white hover:bg-white/25'
              }`}
            >
              <Heart className={`w-4 h-4 ${isFavorited ? 'fill-current' : ''}`} />
            </button>
          </div>
        </div>

        {/* Bottom overlay info */}
        <div className="absolute bottom-5 left-5">
          <PropertyTypeBadge type={listing.property_type} />
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Title + Price */}
          <div>
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">{listing.title}</h1>
              <div className="text-2xl sm:text-3xl font-extrabold text-blue-600 shrink-0">
                {formatPrice(listing.price)}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-slate-500">
              <MapPin className="w-4 h-4 text-blue-400" />
              <span>{listing.location}</span>
            </div>
          </div>

          {/* Property details grid */}
          <Card>
            <h2 className="font-semibold text-slate-900 mb-4">Property Details</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <DetailItem
                icon={<Home className="w-5 h-5 text-blue-500" />}
                label="Type"
                value={capitalize(listing.property_type)}
              />
              <DetailItem
                icon={<Bed className="w-5 h-5 text-blue-500" />}
                label="Bedrooms"
                value={`${listing.bedrooms} bed${listing.bedrooms !== 1 ? 's' : ''}`}
              />
              <DetailItem
                icon={<Bath className="w-5 h-5 text-blue-500" />}
                label="Bathrooms"
                value={`${listing.bathrooms} bath${listing.bathrooms !== 1 ? 's' : ''}`}
              />
              <DetailItem
                icon={<Calendar className="w-5 h-5 text-blue-500" />}
                label="Listed"
                value={formatDate(listing.created_at)}
              />
              <DetailItem
                icon={<CheckCircle className="w-5 h-5 text-emerald-500" />}
                label="Status"
                value="Available"
              />
            </div>
          </Card>

          {/* Description */}
          <Card>
            <h2 className="font-semibold text-slate-900 mb-3">Description</h2>
            <p className="text-slate-600 leading-relaxed whitespace-pre-line">{listing.description}</p>
          </Card>

          {/* Similar listings */}
          <div>
            <h2 className="text-xl font-bold text-slate-900 mb-4">Similar Properties</h2>
            {similarLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ListingCardSkeleton />
                <ListingCardSkeleton />
              </div>
            ) : similarListings && similarListings.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {similarListings.slice(0, 4).map((sl) => (
                  <ListingCard key={sl.id} listing={sl} />
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-sm">No similar properties found.</p>
            )}
          </div>
        </div>

        {/* Right: Actions */}
        <div className="space-y-4">
          {/* Action card */}
          <Card className="sticky top-24">
            <div className="mb-5 pb-4 border-b border-slate-100">
              <p className="text-2xl font-extrabold text-blue-600">{formatPrice(listing.price)}</p>
              <p className="text-sm text-slate-500 mt-0.5">{listing.property_type === 'studio' || listing.property_type === 'apartment' ? 'per month' : 'listing price'}</p>
            </div>

            <div className="space-y-3">
              <Button
                fullWidth
                leftIcon={<Heart className="w-4 h-4" />}
                variant={isFavorited ? 'danger' : 'outline'}
                onClick={handleFavorite}
              >
                {isFavorited ? 'Remove Favorite' : 'Save Property'}
              </Button>

              <Button
                fullWidth
                leftIcon={<Calendar className="w-4 h-4" />}
                onClick={() => requireAuth(() => setActiveModal('viewing'))}
              >
                Schedule Viewing
              </Button>

              <Button
                fullWidth
                variant="secondary"
                leftIcon={<BookOpen className="w-4 h-4" />}
                onClick={() => requireAuth(() => setActiveModal('reservation'))}
              >
                Book Reservation
              </Button>

              <Button
                fullWidth
                variant="outline"
                leftIcon={<MessageSquare className="w-4 h-4" />}
                onClick={() => requireAuth(() => setActiveModal('inquiry'))}
              >
                Contact Seller
              </Button>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-100 text-center">
              <p className="text-xs text-slate-400">
                Listed on {formatDate(listing.created_at)}
              </p>
            </div>
          </Card>
        </div>
      </div>

      {/* ── Modals ── */}
      {activeModal && (
        <div
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setActiveModal(null);
          }}
        >
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md p-6 fade-in">
            {/* Viewing */}
            {activeModal === 'viewing' && (
              <>
                <h3 className="text-xl font-bold text-slate-900 mb-1">Schedule a Viewing</h3>
                <p className="text-slate-500 text-sm mb-5">Choose a date and time to visit this property.</p>
                <Input
                  label="Preferred Date & Time"
                  type="datetime-local"
                  value={viewingDate}
                  onChange={(e) => setViewingDate(e.target.value)}
                  min={new Date().toISOString().slice(0, 16)}
                />
                <div className="flex gap-3 mt-5">
                  <Button variant="outline" fullWidth onClick={() => setActiveModal(null)}>Cancel</Button>
                  <Button
                    fullWidth
                    isLoading={scheduleViewingMutation.isPending}
                    disabled={!viewingDate}
                    onClick={() => scheduleViewingMutation.mutate()}
                  >
                    Confirm
                  </Button>
                </div>
              </>
            )}

            {/* Reservation */}
            {activeModal === 'reservation' && (
              <>
                <h3 className="text-xl font-bold text-slate-900 mb-1">Book a Reservation</h3>
                <p className="text-slate-500 text-sm mb-5">Select your check-in and check-out dates.</p>
                <div className="space-y-4">
                  <Input
                    label="Check-in"
                    type="date"
                    value={checkIn}
                    onChange={(e) => setCheckIn(e.target.value)}
                    min={new Date().toISOString().slice(0, 10)}
                  />
                  <Input
                    label="Check-out"
                    type="date"
                    value={checkOut}
                    onChange={(e) => setCheckOut(e.target.value)}
                    min={checkIn || new Date().toISOString().slice(0, 10)}
                  />
                </div>
                <div className="flex gap-3 mt-5">
                  <Button variant="outline" fullWidth onClick={() => setActiveModal(null)}>Cancel</Button>
                  <Button
                    fullWidth
                    isLoading={bookReservationMutation.isPending}
                    disabled={!checkIn || !checkOut}
                    onClick={() => bookReservationMutation.mutate()}
                  >
                    Book Now
                  </Button>
                </div>
              </>
            )}

            {/* Inquiry */}
            {activeModal === 'inquiry' && (
              <>
                <h3 className="text-xl font-bold text-slate-900 mb-1">Contact the Seller</h3>
                <p className="text-slate-500 text-sm mb-5">Send a message about this property.</p>
                <Textarea
                  label="Your Message"
                  rows={4}
                  value={inquiryMsg}
                  onChange={(e) => setInquiryMsg(e.target.value)}
                  placeholder="Hi, I'm interested in this property and would like to know more..."
                />
                <div className="flex gap-3 mt-5">
                  <Button variant="outline" fullWidth onClick={() => setActiveModal(null)}>Cancel</Button>
                  <Button
                    fullWidth
                    isLoading={sendInquiryMutation.isPending}
                    disabled={!inquiryMsg.trim()}
                    onClick={() => sendInquiryMutation.mutate()}
                  >
                    Send Message
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DetailItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 bg-slate-50 rounded-xl p-3">
      <div className="w-9 h-9 bg-white rounded-lg flex items-center justify-center shadow-sm shrink-0">
        {icon}
      </div>
      <div>
        <p className="text-xs text-slate-400 font-medium">{label}</p>
        <p className="text-sm font-semibold text-slate-900">{value}</p>
      </div>
    </div>
  );
}
