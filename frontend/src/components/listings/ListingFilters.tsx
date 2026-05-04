import React, { useState } from 'react';
import { Search, SlidersHorizontal, X } from 'lucide-react';
import { Input, Select } from '../ui/Input';
import { Button } from '../ui/Button';
import { PROPERTY_TYPES } from '../../lib/utils';
import type { SearchParams } from '../../types';

interface ListingFiltersProps {
  params: SearchParams;
  onChange: (params: SearchParams) => void;
  onReset: () => void;
}

export function ListingFilters({ params, onChange, onReset }: ListingFiltersProps) {
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  const handleChange = (key: keyof SearchParams, value: string | number | undefined) => {
    onChange({ ...params, [key]: value, page: 1 });
  };

  const hasActiveFilters =
    params.q ||
    params.property_type ||
    params.min_price ||
    params.max_price ||
    params.min_bedrooms;

  return (
    <>
      {/* Mobile toggle */}
      <div className="lg:hidden mb-4">
        <Button
          variant="outline"
          leftIcon={<SlidersHorizontal className="w-4 h-4" />}
          onClick={() => setShowMobileFilters(!showMobileFilters)}
        >
          Filters {hasActiveFilters && <span className="ml-1 w-2 h-2 bg-blue-500 rounded-full inline-block" />}
        </Button>
      </div>

      {/* Filter panel */}
      <div
        className={`
          bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-5
          lg:block
          ${showMobileFilters ? 'block' : 'hidden lg:block'}
        `}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-blue-500" />
            Filters
          </h3>
          {hasActiveFilters && (
            <button
              onClick={onReset}
              className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1 font-medium transition-colors"
            >
              <X className="w-3 h-3" />
              Clear all
            </button>
          )}
        </div>

        {/* Search */}
        <Input
          label="Search"
          placeholder="Keywords..."
          value={params.q ?? ''}
          leftIcon={<Search className="w-4 h-4" />}
          onChange={(e) => handleChange('q', e.target.value || undefined)}
        />

        {/* Property type */}
        <Select
          label="Property Type"
          value={params.property_type ?? ''}
          placeholder="All types"
          options={[...PROPERTY_TYPES]}
          onChange={(e) => handleChange('property_type', e.target.value || undefined)}
        />

        {/* Price range */}
        <div>
          <p className="text-sm font-medium text-slate-700 mb-1.5">Price Range</p>
          <div className="grid grid-cols-2 gap-2">
            <Input
              placeholder="Min $"
              type="number"
              value={params.min_price ?? ''}
              onChange={(e) =>
                handleChange('min_price', e.target.value ? Number(e.target.value) : undefined)
              }
            />
            <Input
              placeholder="Max $"
              type="number"
              value={params.max_price ?? ''}
              onChange={(e) =>
                handleChange('max_price', e.target.value ? Number(e.target.value) : undefined)
              }
            />
          </div>
        </div>

        {/* Min bedrooms */}
        <Select
          label="Min Bedrooms"
          value={params.min_bedrooms?.toString() ?? ''}
          placeholder="Any"
          options={[
            { value: '1', label: '1+' },
            { value: '2', label: '2+' },
            { value: '3', label: '3+' },
            { value: '4', label: '4+' },
            { value: '5', label: '5+' },
          ]}
          onChange={(e) =>
            handleChange('min_bedrooms', e.target.value ? Number(e.target.value) : undefined)
          }
        />

        {/* Active filter chips */}
        {hasActiveFilters && (
          <div className="flex flex-wrap gap-2 pt-1">
            {params.q && (
              <FilterChip label={`"${params.q}"`} onRemove={() => handleChange('q', undefined)} />
            )}
            {params.property_type && (
              <FilterChip
                label={params.property_type}
                onRemove={() => handleChange('property_type', undefined)}
              />
            )}
            {params.min_price && (
              <FilterChip
                label={`Min $${params.min_price.toLocaleString()}`}
                onRemove={() => handleChange('min_price', undefined)}
              />
            )}
            {params.max_price && (
              <FilterChip
                label={`Max $${params.max_price.toLocaleString()}`}
                onRemove={() => handleChange('max_price', undefined)}
              />
            )}
            {params.min_bedrooms && (
              <FilterChip
                label={`${params.min_bedrooms}+ beds`}
                onRemove={() => handleChange('min_bedrooms', undefined)}
              />
            )}
          </div>
        )}
      </div>
    </>
  );
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs font-medium px-2.5 py-1 rounded-full">
      {label}
      <button onClick={onRemove} className="hover:text-blue-900">
        <X className="w-3 h-3" />
      </button>
    </span>
  );
}
