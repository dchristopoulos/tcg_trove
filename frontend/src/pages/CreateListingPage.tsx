import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Home,
  DollarSign,
  MapPin,
  Bed,
  Bath,
  FileText,
  Upload,
  X,
  CheckCircle,
} from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Input, Textarea, Select } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { useToast } from '../components/ui/Toast';
import { listingsApi } from '../lib/api';
import { PROPERTY_TYPES, getErrorMessage } from '../lib/utils';
import { listingKeys } from '../hooks/useListings';

export default function CreateListingPage() {
  const navigate = useNavigate();
  const { success, error: toastError } = useToast();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState({
    title: '',
    price: '',
    location: '',
    property_type: '',
    bedrooms: '',
    bathrooms: '',
    description: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (formData: FormData) => listingsApi.create(formData),
    onSuccess: (listing) => {
      queryClient.invalidateQueries({ queryKey: listingKeys.all });
      success('Listing Published!', 'Your property is now live.');
      navigate(`/listings/${listing.id}`);
    },
    onError: (err) => toastError('Failed to create listing', getErrorMessage(err)),
  });

  const handleField = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => { const n = { ...prev }; delete n[key]; return n; });
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      toastError('Image too large', 'Max file size is 10MB');
      return;
    }
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.title.trim()) errs.title = 'Title is required';
    if (!form.price || isNaN(Number(form.price)) || Number(form.price) <= 0) errs.price = 'Enter a valid price';
    if (!form.location.trim()) errs.location = 'Location is required';
    if (!form.property_type) errs.property_type = 'Select a property type';
    if (!form.bedrooms || Number(form.bedrooms) < 0) errs.bedrooms = 'Enter number of bedrooms';
    if (!form.bathrooms || Number(form.bathrooms) < 0) errs.bathrooms = 'Enter number of bathrooms';
    if (!form.description.trim()) errs.description = 'Description is required';
    return errs;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    const formData = new FormData();
    formData.append('title', form.title);
    formData.append('price', String(Number(form.price)));
    formData.append('location', form.location);
    formData.append('property_type', form.property_type);
    formData.append('bedrooms', String(Number(form.bedrooms)));
    formData.append('bathrooms', String(Number(form.bathrooms)));
    formData.append('description', form.description);
    if (imageFile) formData.append('image', imageFile);

    createMutation.mutate(formData);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Post a Property</h1>
        <p className="text-slate-500 mt-1">Fill in the details below to list your property on TCG Trove.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <section className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
          <h2 className="font-semibold text-slate-900 mb-5 flex items-center gap-2">
            <Home className="w-5 h-5 text-blue-500" />
            Basic Information
          </h2>
          <div className="space-y-4">
            <Input
              label="Property Title"
              value={form.title}
              onChange={(e) => handleField('title', e.target.value)}
              placeholder="e.g. Modern 3-Bedroom Apartment in Downtown"
              error={errors.title}
              required
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Price (USD)"
                type="number"
                value={form.price}
                onChange={(e) => handleField('price', e.target.value)}
                placeholder="e.g. 250000"
                leftIcon={<DollarSign className="w-4 h-4" />}
                error={errors.price}
                min="0"
                required
              />

              <Select
                label="Property Type"
                value={form.property_type}
                onChange={(e) => handleField('property_type', e.target.value)}
                options={PROPERTY_TYPES.map(t => ({ value: t.value, label: t.label }))}
                placeholder="Select type..."
                error={errors.property_type}
              />
            </div>

            <Input
              label="Location"
              value={form.location}
              onChange={(e) => handleField('location', e.target.value)}
              placeholder="e.g. 123 Main Street, New York, NY"
              leftIcon={<MapPin className="w-4 h-4" />}
              error={errors.location}
              required
            />

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Bedrooms"
                type="number"
                value={form.bedrooms}
                onChange={(e) => handleField('bedrooms', e.target.value)}
                leftIcon={<Bed className="w-4 h-4" />}
                error={errors.bedrooms}
                min="0"
                max="20"
                required
              />
              <Input
                label="Bathrooms"
                type="number"
                value={form.bathrooms}
                onChange={(e) => handleField('bathrooms', e.target.value)}
                leftIcon={<Bath className="w-4 h-4" />}
                error={errors.bathrooms}
                min="0"
                max="20"
                step="0.5"
                required
              />
            </div>
          </div>
        </section>

        {/* Description */}
        <section className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
          <h2 className="font-semibold text-slate-900 mb-5 flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-500" />
            Description
          </h2>
          <Textarea
            label="Property Description"
            value={form.description}
            onChange={(e) => handleField('description', e.target.value)}
            placeholder="Describe the property in detail — location highlights, amenities, features, nearby schools, transport links..."
            rows={6}
            error={errors.description}
          />
        </section>

        {/* Photo */}
        <section className="bg-white rounded-3xl border border-slate-100 shadow-sm p-6">
          <h2 className="font-semibold text-slate-900 mb-5 flex items-center gap-2">
            <Upload className="w-5 h-5 text-blue-500" />
            Property Photo
          </h2>

          {imagePreview ? (
            <div className="relative">
              <img
                src={imagePreview}
                alt="Preview"
                className="w-full h-60 object-cover rounded-2xl"
              />
              <button
                type="button"
                onClick={() => {
                  setImageFile(null);
                  setImagePreview(null);
                  if (fileRef.current) fileRef.current.value = '';
                }}
                className="absolute top-3 right-3 w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-md hover:bg-red-50 transition-colors"
              >
                <X className="w-4 h-4 text-slate-600" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="w-full h-48 border-2 border-dashed border-slate-300 hover:border-blue-400 rounded-2xl flex flex-col items-center justify-center gap-3 transition-colors group"
            >
              <div className="w-12 h-12 bg-slate-100 group-hover:bg-blue-50 rounded-2xl flex items-center justify-center transition-colors">
                <Upload className="w-6 h-6 text-slate-400 group-hover:text-blue-500 transition-colors" />
              </div>
              <div className="text-center">
                <p className="font-medium text-slate-700 text-sm">Click to upload a photo</p>
                <p className="text-xs text-slate-400 mt-0.5">PNG, JPG, WEBP up to 10MB</p>
              </div>
            </button>
          )}

          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleImageChange}
          />
        </section>

        {/* Preview card */}
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-blue-800">Ready to publish?</p>
            <p className="text-blue-600 mt-0.5">
              Your listing will be visible to thousands of home seekers immediately after submission.
            </p>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-4">
          <Button
            type="submit"
            size="lg"
            isLoading={createMutation.isPending}
            className="flex-1"
          >
            Publish Listing
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => navigate(-1)}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
