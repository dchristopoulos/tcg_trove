import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, LayoutGrid, List, ArrowUpDown } from 'lucide-react';
import { ListingFilters } from '../components/listings/ListingFilters';
import { ListingGrid } from '../components/listings/ListingGrid';
import { Button } from '../components/ui/Button';
import { useSearchListings } from '../hooks/useListings';
import type { SearchParams } from '../types';

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest First' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
];

export default function ListingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [filters, setFilters] = useState<SearchParams>({
    q: searchParams.get('q') ?? undefined,
    property_type: searchParams.get('property_type') ?? undefined,
    min_price: searchParams.get('min_price') ? Number(searchParams.get('min_price')) : undefined,
    max_price: searchParams.get('max_price') ? Number(searchParams.get('max_price')) : undefined,
    min_bedrooms: searchParams.get('min_bedrooms') ? Number(searchParams.get('min_bedrooms')) : undefined,
    page: 1,
    page_size: 9,
  });

  const [sortBy, setSortBy] = useState('newest');

  // Sync filters to URL
  useEffect(() => {
    const params: Record<string, string> = {};
    if (filters.q) params.q = filters.q;
    if (filters.property_type) params.property_type = filters.property_type;
    if (filters.min_price) params.min_price = String(filters.min_price);
    if (filters.max_price) params.max_price = String(filters.max_price);
    if (filters.min_bedrooms) params.min_bedrooms = String(filters.min_bedrooms);
    setSearchParams(params, { replace: true });
  }, [filters, setSearchParams]);

  const { data, isLoading, error } = useSearchListings(filters);

  const handleFiltersChange = (newFilters: SearchParams) => {
    setFilters({ ...newFilters, page: 1 });
  };

  const handleReset = () => {
    setFilters({ page: 1, page_size: 9 });
  };

  const handlePageChange = (page: number) => {
    setFilters((prev) => ({ ...prev, page }));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const totalPages = data?.total_pages ?? 1;
  const currentPage = filters.page ?? 1;
  const totalCount = data?.total ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-1">Property Listings</h1>
        <p className="text-slate-500">
          {isLoading ? 'Searching...' : `${totalCount.toLocaleString()} propert${totalCount === 1 ? 'y' : 'ies'} found`}
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar filters */}
        <aside className="lg:w-72 shrink-0">
          <ListingFilters
            params={filters}
            onChange={handleFiltersChange}
            onReset={handleReset}
          />
        </aside>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-5 bg-white rounded-2xl border border-slate-100 shadow-sm px-4 py-3">
            <p className="text-sm text-slate-500">
              {isLoading ? (
                <span className="inline-block w-24 h-4 bg-slate-200 rounded skeleton" />
              ) : (
                `${totalCount} result${totalCount === 1 ? '' : 's'}`
              )}
            </p>

            <div className="flex items-center gap-3">
              {/* Sort */}
              <div className="flex items-center gap-1.5 text-sm">
                <ArrowUpDown className="w-4 h-4 text-slate-400" />
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="text-slate-700 bg-transparent border-none outline-none cursor-pointer font-medium text-sm"
                >
                  {SORT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* View toggle (visual only) */}
              <div className="flex items-center bg-slate-100 rounded-lg p-1 gap-1">
                <button className="p-1.5 rounded-md bg-white shadow-sm text-blue-600">
                  <LayoutGrid className="w-3.5 h-3.5" />
                </button>
                <button className="p-1.5 rounded-md text-slate-400 hover:text-slate-600">
                  <List className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl p-4 mb-5 text-sm">
              Failed to load listings. Please try again.
            </div>
          )}

          {/* Grid */}
          <ListingGrid
            listings={data?.items ?? []}
            isLoading={isLoading}
            skeletonCount={9}
            emptyMessage="No listings match your search"
          />

          {/* Pagination */}
          {!isLoading && totalPages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                leftIcon={<ChevronLeft className="w-4 h-4" />}
              >
                Prev
              </Button>

              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let page: number;
                  if (totalPages <= 7) {
                    page = i + 1;
                  } else if (currentPage <= 4) {
                    page = i + 1;
                  } else if (currentPage >= totalPages - 3) {
                    page = totalPages - 6 + i;
                  } else {
                    page = currentPage - 3 + i;
                  }

                  return (
                    <button
                      key={page}
                      onClick={() => handlePageChange(page)}
                      className={`w-9 h-9 rounded-xl text-sm font-medium transition-all ${
                        page === currentPage
                          ? 'bg-blue-500 text-white shadow-sm'
                          : 'bg-white text-slate-600 border border-slate-200 hover:border-blue-300 hover:text-blue-600'
                      }`}
                    >
                      {page}
                    </button>
                  );
                })}
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                rightIcon={<ChevronRight className="w-4 h-4" />}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
