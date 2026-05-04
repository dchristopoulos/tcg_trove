import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Search,
  ArrowRight,
  Users,
  ShieldCheck,
  TrendingUp,
  Clock,
  Home,
  Building2,
  TreePine,
  SquareStack,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { ListingGrid } from '../components/listings/ListingGrid';
import { useListings } from '../hooks/useListings';

const STATS = [
  { label: 'Happy Buyers', value: '12,000+', icon: Users, color: 'text-blue-500' },
  { label: 'Verified Listings', value: '98%', icon: ShieldCheck, color: 'text-emerald-500' },
  { label: 'New This Week', value: '350+', icon: TrendingUp, color: 'text-amber-500' },
  { label: 'Avg. Response', value: '< 24h', icon: Clock, color: 'text-purple-500' },
];

const PROPERTY_TYPES = [
  { label: 'Houses', value: 'house', icon: Home, color: 'from-blue-500 to-blue-600', desc: 'Spacious family homes' },
  { label: 'Apartments', value: 'apartment', icon: Building2, color: 'from-purple-500 to-purple-600', desc: 'Modern urban living' },
  { label: 'Villas', value: 'villa', icon: TreePine, color: 'from-emerald-500 to-emerald-600', desc: 'Luxury & exclusivity' },
  { label: 'Studios', value: 'studio', icon: SquareStack, color: 'from-amber-500 to-amber-600', desc: 'Compact & efficient' },
];

export default function HomePage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const { data, isLoading } = useListings({ page: 1, page_size: 3 });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    navigate(`/listings${searchQuery ? `?q=${encodeURIComponent(searchQuery)}` : ''}`);
  };

  return (
    <div>
      {/* ── Hero ── */}
      <section className="relative min-h-[80vh] flex items-center justify-center overflow-hidden bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900">
        {/* Background decoration */}
        <div className="absolute inset-0">
          <div className="absolute top-20 left-20 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-20 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-600/5 rounded-full blur-3xl" />
        </div>

        {/* Grid pattern overlay */}
        <div
          className="absolute inset-0 opacity-5"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 text-center">
          {/* Tag */}
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm border border-white/20 rounded-full px-4 py-1.5 mb-6 text-sm text-blue-200">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            350+ new listings this week
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white mb-6 leading-tight">
            Find Your Perfect{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
              Dream Home
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-slate-300 mb-10 max-w-2xl mx-auto leading-relaxed">
            Discover thousands of verified listings — from cozy studios to luxury villas. Your next chapter starts here.
          </p>

          {/* Search bar */}
          <form
            onSubmit={handleSearch}
            className="glass rounded-2xl p-2 max-w-2xl mx-auto flex items-center gap-2"
          >
            <div className="flex-1 flex items-center gap-3 px-4">
              <Search className="w-5 h-5 text-white/60 shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by location, type, or keyword..."
                className="flex-1 bg-transparent text-white placeholder:text-white/50 text-sm outline-none py-2"
              />
            </div>
            <Button type="submit" size="lg" className="shrink-0 rounded-xl">
              Search
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </form>

          {/* Popular searches */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
            <span className="text-slate-400 text-sm">Popular:</span>
            {['Apartments in NYC', 'Villas in Miami', '2-bedroom homes', 'Studios under $1,500'].map((s) => (
              <button
                key={s}
                onClick={() => {
                  setSearchQuery(s);
                  navigate(`/listings?q=${encodeURIComponent(s)}`);
                }}
                className="text-sm text-slate-300 hover:text-white bg-white/10 hover:bg-white/20 px-3 py-1 rounded-full transition-all"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-8 relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {STATS.map((stat) => (
            <div
              key={stat.label}
              className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 text-center hover:shadow-md transition-shadow"
            >
              <div className={`text-3xl font-extrabold ${stat.color} mb-1`}>{stat.value}</div>
              <div className="text-slate-500 text-sm font-medium">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Featured Listings ── */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-3xl font-bold text-slate-900 mb-1">Featured Listings</h2>
            <p className="text-slate-500">Handpicked properties for you</p>
          </div>
          <Link to="/listings">
            <Button variant="outline" rightIcon={<ArrowRight className="w-4 h-4" />}>
              View all
            </Button>
          </Link>
        </div>

        <ListingGrid
          listings={data?.items ?? []}
          isLoading={isLoading}
          skeletonCount={3}
        />
      </section>

      {/* ── Browse by type ── */}
      <section className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-2">Browse by Property Type</h2>
            <p className="text-slate-500 max-w-xl mx-auto">
              Explore our curated selection of property types to find exactly what you're looking for
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            {PROPERTY_TYPES.map((type) => {
              const Icon = type.icon;
              return (
                <Link
                  key={type.value}
                  to={`/listings?property_type=${type.value}`}
                  className="group relative rounded-2xl overflow-hidden card-hover"
                >
                  <div className={`bg-gradient-to-br ${type.color} p-8 text-white text-center`}>
                    <div className="w-14 h-14 bg-white/20 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform duration-300">
                      <Icon className="w-7 h-7" />
                    </div>
                    <h3 className="text-lg font-bold mb-1">{type.label}</h3>
                    <p className="text-sm text-white/75">{type.desc}</p>
                  </div>
                  <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="relative rounded-3xl overflow-hidden bg-gradient-to-r from-blue-600 to-blue-700 p-10 md:p-16 text-center">
          {/* Background decoration */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />

          <div className="relative">
            <h2 className="text-3xl md:text-4xl font-extrabold text-white mb-4">
              Ready to find your next home?
            </h2>
            <p className="text-blue-100 text-lg mb-8 max-w-xl mx-auto">
              Join thousands of satisfied buyers and renters. Browse our curated listings today.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/listings">
                <Button
                  size="lg"
                  className="bg-white text-blue-600 hover:bg-blue-50 shadow-lg hover:shadow-xl"
                >
                  Browse Listings
                </Button>
              </Link>
              <Link to="/register">
                <Button
                  size="lg"
                  variant="outline"
                  className="border-white/40 text-white hover:bg-white/10 hover:border-white"
                >
                  Create Free Account
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
