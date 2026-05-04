import React, { useState } from 'react';
import {
  Shield,
  Users,
  FileText,
  Activity,
  Trash2,
  ChevronDown,
  RefreshCw,
  Eye,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiClient, listingsApi } from '../lib/api';
import { useToast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Skeleton } from '../components/ui/Skeleton';
import { formatDateTime, getErrorMessage, capitalize } from '../lib/utils';
import type { User, UserRole } from '../types';

type AdminTab = 'users' | 'listings' | 'audit';

const ROLE_COLORS: Record<UserRole, string> = {
  buyer: 'default',
  seller: 'blue',
  supervisor: 'purple',
  admin: 'red',
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<AdminTab>('users');

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center gap-3">
        <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-red-600 rounded-2xl flex items-center justify-center shadow-sm shadow-red-500/30">
          <Shield className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Admin Panel</h1>
          <p className="text-slate-500 mt-0.5">Manage users, listings, and platform activity</p>
        </div>
      </div>

      {/* Stats row */}
      <AdminStats />

      {/* Tabs */}
      <div className="flex gap-1 bg-white rounded-2xl border border-slate-100 shadow-sm p-1 my-6">
        {[
          { id: 'users' as AdminTab, label: 'Users', icon: <Users className="w-4 h-4" /> },
          { id: 'listings' as AdminTab, label: 'Listings', icon: <FileText className="w-4 h-4" /> },
          { id: 'audit' as AdminTab, label: 'Audit Log', icon: <Activity className="w-4 h-4" /> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-slate-900 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="fade-in">
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'listings' && <ListingsTab />}
        {activeTab === 'audit' && <AuditTab />}
      </div>
    </div>
  );
}

// ── Stats ─────────────────────────────────────────────────────────────────────

function AdminStats() {
  const { data: listings } = useQuery({
    queryKey: ['admin', 'listings-count'],
    queryFn: () => listingsApi.getAll({ page: 1, page_size: 1 }),
  });

  const { data: users } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => apiClient.get('/api/v1/users/').then((r) => r.data),
  });

  const usersArray: User[] = Array.isArray(users) ? users : [];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[
        { label: 'Total Users', value: usersArray.length || '—', color: 'text-blue-600', bg: 'bg-blue-50' },
        { label: 'Total Listings', value: listings?.total ?? '—', color: 'text-emerald-600', bg: 'bg-emerald-50' },
        {
          label: 'Sellers',
          value: usersArray.filter((u) => u.role === 'seller').length || '—',
          color: 'text-purple-600',
          bg: 'bg-purple-50',
        },
        {
          label: 'Admins',
          value: usersArray.filter((u) => u.role === 'admin').length || '—',
          color: 'text-red-600',
          bg: 'bg-red-50',
        },
      ].map((stat) => (
        <div key={stat.label} className={`${stat.bg} rounded-2xl p-5 text-center`}>
          <div className={`text-3xl font-extrabold ${stat.color} mb-1`}>{stat.value}</div>
          <div className="text-slate-500 text-sm font-medium">{stat.label}</div>
        </div>
      ))}
    </div>
  );
}

// ── Users Tab ────────────────────────────────────────────────────────────────

function UsersTab() {
  const { success, error: toastError } = useToast();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');

  const { data: users, isLoading, refetch } = useQuery<User[]>({
    queryKey: ['admin', 'users'],
    queryFn: () => apiClient.get('/api/v1/users/').then((r) => r.data),
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      apiClient.put(`/api/v1/users/${userId}/role`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      success('Role updated successfully');
    },
    onError: (err) => toastError('Failed to update role', getErrorMessage(err)),
  });

  const filteredUsers = (users ?? []).filter(
    (u) =>
      u.username.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase())
  );

  if (isLoading) return <TableSkeleton cols={4} rows={6} />;

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search users..."
          className="flex-1 max-w-xs rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RefreshCw className="w-4 h-4" />}
          onClick={() => refetch()}
        >
          Refresh
        </Button>
      </div>

      <Card padding="none" className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                {['User', 'Email', 'Role', 'Actions'].map((h) => (
                  <th key={h} className="text-left px-5 py-3 font-semibold text-slate-700">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center py-10 text-slate-400">No users found</td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-xs font-bold">
                          {user.username.charAt(0).toUpperCase()}
                        </div>
                        <span className="font-medium text-slate-900">{user.username}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{user.email}</td>
                    <td className="px-5 py-3">
                      <RoleSelect
                        userId={user.id}
                        currentRole={user.role}
                        onUpdate={(role) => updateRoleMutation.mutate({ userId: user.id, role })}
                        isUpdating={updateRoleMutation.isPending}
                      />
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-slate-400 text-xs">ID: {String(user.id).slice(0, 8)}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function RoleSelect({
  userId,
  currentRole,
  onUpdate,
  isUpdating,
}: {
  userId: string;
  currentRole: UserRole;
  onUpdate: (role: UserRole) => void;
  isUpdating: boolean;
}) {
  const roles: UserRole[] = ['buyer', 'seller', 'supervisor', 'admin'];

  return (
    <div className="relative inline-flex items-center gap-1">
      <Badge variant={ROLE_COLORS[currentRole] as 'default' | 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'orange'}>
        {capitalize(currentRole)}
      </Badge>
      <div className="relative">
        <select
          value={currentRole}
          onChange={(e) => onUpdate(e.target.value as UserRole)}
          disabled={isUpdating}
          className="absolute inset-0 opacity-0 cursor-pointer w-full"
        >
          {roles.map((r) => (
            <option key={r} value={r}>{capitalize(r)}</option>
          ))}
        </select>
        <ChevronDown className="w-3 h-3 text-slate-400" />
      </div>
    </div>
  );
}

// ── Listings Tab ──────────────────────────────────────────────────────────────

function ListingsTab() {
  const { success, error: toastError } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'all-listings'],
    queryFn: () => listingsApi.getAll({ page: 1, page_size: 50 }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => listingsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'all-listings'] });
      success('Listing deleted');
    },
    onError: (err) => toastError('Delete failed', getErrorMessage(err)),
  });

  const handleDelete = (id: string) => {
    if (!confirm('Permanently delete this listing?')) return;
    deleteMutation.mutate(id);
  };

  if (isLoading) return <TableSkeleton cols={5} rows={8} />;

  const listings = data?.items ?? [];

  return (
    <Card padding="none" className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              {['Title', 'Type', 'Price', 'Location', 'Created', 'Actions'].map((h) => (
                <th key={h} className="text-left px-5 py-3 font-semibold text-slate-700">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {listings.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-10 text-slate-400">No listings found</td>
              </tr>
            ) : (
              listings.map((listing) => (
                <tr key={listing.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3">
                    <span className="font-medium text-slate-900 line-clamp-1 max-w-[200px] block">
                      {listing.title}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant="blue">{capitalize(listing.property_type)}</Badge>
                  </td>
                  <td className="px-5 py-3 font-semibold text-blue-600">
                    ${listing.price.toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-slate-600 max-w-[150px]">
                    <span className="line-clamp-1">{listing.location}</span>
                  </td>
                  <td className="px-5 py-3 text-slate-500 text-xs">
                    {formatDateTime(listing.created_at)}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <Link to={`/listings/${listing.id}`}>
                        <Button variant="ghost" size="sm">
                          <Eye className="w-4 h-4" />
                        </Button>
                      </Link>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(listing.id)}
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ── Audit Tab ─────────────────────────────────────────────────────────────────

function AuditTab() {
  // Generate mock audit events since the backend doesn't expose this
  const events = [
    { id: 1, action: 'User registered', actor: 'system', target: 'new user', time: new Date().toISOString(), type: 'info' },
    { id: 2, action: 'Listing created', actor: 'seller', target: 'Listing #123', time: new Date(Date.now() - 3600000).toISOString(), type: 'success' },
    { id: 3, action: 'Inquiry submitted', actor: 'buyer', target: 'Listing #100', time: new Date(Date.now() - 7200000).toISOString(), type: 'info' },
    { id: 4, action: 'Listing deleted', actor: 'admin', target: 'Listing #89', time: new Date(Date.now() - 86400000).toISOString(), type: 'warning' },
    { id: 5, action: 'Role changed', actor: 'admin', target: 'user@example.com → seller', time: new Date(Date.now() - 172800000).toISOString(), type: 'warning' },
    { id: 6, action: 'Reservation booked', actor: 'buyer', target: 'Listing #77', time: new Date(Date.now() - 259200000).toISOString(), type: 'success' },
  ];

  const typeColors: Record<string, string> = {
    info: 'bg-blue-100 text-blue-700',
    success: 'bg-emerald-100 text-emerald-700',
    warning: 'bg-amber-100 text-amber-700',
    error: 'bg-red-100 text-red-700',
  };

  return (
    <Card padding="none" className="overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
        <Activity className="w-4 h-4 text-slate-400" />
        <h3 className="font-semibold text-slate-900">Recent Activity</h3>
        <span className="text-xs text-slate-400 ml-auto">Last 30 days</span>
      </div>
      <div className="divide-y divide-slate-50">
        {events.map((event) => (
          <div key={event.id} className="px-5 py-3.5 flex items-center gap-4 hover:bg-slate-50">
            <div className={`px-2.5 py-1 rounded-full text-xs font-medium shrink-0 ${typeColors[event.type]}`}>
              {event.type}
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-900">{event.action}</p>
              <p className="text-xs text-slate-500">
                by <span className="font-medium">{event.actor}</span> · {event.target}
              </p>
            </div>
            <span className="text-xs text-slate-400 shrink-0">{formatDateTime(event.time)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function TableSkeleton({ cols, rows }: { cols: number; rows: number }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      <div className="divide-y divide-slate-50">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="p-4 flex gap-4">
            {Array.from({ length: cols }).map((_, j) => (
              <Skeleton key={j} className="h-4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
