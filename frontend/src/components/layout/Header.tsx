import React, { useState, useRef, useEffect } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import {
  Home,
  Search,
  Heart,
  MessageSquare,
  LayoutDashboard,
  LogOut,
  User,
  ChevronDown,
  Menu,
  X,
  Plus,
  Shield,
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../ui/Button';
import { cn } from '../../lib/utils';

export function Header() {
  const { user, isAuthenticated, logout, hasRole } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close user menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
    setUserMenuOpen(false);
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'text-sm font-medium transition-colors',
      isActive ? 'text-blue-600' : 'text-slate-600 hover:text-slate-900'
    );

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-slate-100 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 shrink-0">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center shadow-sm shadow-blue-500/30">
              <Home className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-slate-900">
              Home<span className="text-blue-500">Finder</span>
            </span>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-6">
            <NavLink to="/" end className={navLinkClass}>
              Home
            </NavLink>
            <NavLink to="/listings" className={navLinkClass}>
              Listings
            </NavLink>
            {isAuthenticated && (
              <>
                <NavLink to="/dashboard" className={navLinkClass}>
                  Dashboard
                </NavLink>
                <NavLink to="/messages" className={navLinkClass}>
                  Messages
                </NavLink>
                {hasRole(['admin', 'seller']) && (
                  <NavLink to="/listings/new" className={navLinkClass}>
                    Post
                  </NavLink>
                )}
                {hasRole(['admin']) && (
                  <NavLink to="/admin" className={navLinkClass}>
                    Admin
                  </NavLink>
                )}
              </>
            )}
          </nav>

          {/* Desktop Right */}
          <div className="hidden md:flex items-center gap-3">
            {isAuthenticated ? (
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-2 rounded-xl px-3 py-2 hover:bg-slate-50 transition-colors"
                >
                  <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-xs font-bold">
                    {user?.username.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm font-medium text-slate-700">{user?.username}</span>
                  <ChevronDown
                    className={cn(
                      'w-4 h-4 text-slate-400 transition-transform',
                      userMenuOpen && 'rotate-180'
                    )}
                  />
                </button>

                {/* Dropdown */}
                {userMenuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-52 bg-white rounded-2xl shadow-lg shadow-slate-200/80 border border-slate-100 overflow-hidden">
                    <div className="px-4 py-3 border-b border-slate-100">
                      <p className="text-sm font-semibold text-slate-900">{user?.username}</p>
                      <p className="text-xs text-slate-500">{user?.email}</p>
                      <span className="inline-flex mt-1 text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium">
                        {user?.role.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="p-2">
                      <DropdownItem to="/dashboard" icon={<LayoutDashboard className="w-4 h-4" />} onClick={() => setUserMenuOpen(false)}>
                        Dashboard
                      </DropdownItem>
                      <DropdownItem to="/messages" icon={<MessageSquare className="w-4 h-4" />} onClick={() => setUserMenuOpen(false)}>
                        Messages
                      </DropdownItem>
                      <DropdownItem to="/dashboard?tab=favorites" icon={<Heart className="w-4 h-4" />} onClick={() => setUserMenuOpen(false)}>
                        Favorites
                      </DropdownItem>
                      {hasRole(['admin', 'seller']) && (
                        <DropdownItem to="/listings/new" icon={<Plus className="w-4 h-4" />} onClick={() => setUserMenuOpen(false)}>
                          Post Listing
                        </DropdownItem>
                      )}
                      {hasRole(['admin']) && (
                        <DropdownItem to="/admin" icon={<Shield className="w-4 h-4" />} onClick={() => setUserMenuOpen(false)}>
                          Admin Panel
                        </DropdownItem>
                      )}
                    </div>
                    <div className="p-2 border-t border-slate-100">
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <LogOut className="w-4 h-4" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" size="sm">Sign in</Button>
                </Link>
                <Link to="/register">
                  <Button size="sm">Get Started</Button>
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-xl transition-colors"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden border-t border-slate-100 bg-white">
          <div className="px-4 py-4 space-y-1">
            <MobileNavLink to="/" onClick={() => setMenuOpen(false)}>Home</MobileNavLink>
            <MobileNavLink to="/listings" onClick={() => setMenuOpen(false)}>Listings</MobileNavLink>
            {isAuthenticated ? (
              <>
                <MobileNavLink to="/dashboard" onClick={() => setMenuOpen(false)}>Dashboard</MobileNavLink>
                <MobileNavLink to="/messages" onClick={() => setMenuOpen(false)}>Messages</MobileNavLink>
                {hasRole(['admin', 'seller']) && (
                  <MobileNavLink to="/listings/new" onClick={() => setMenuOpen(false)}>Post Listing</MobileNavLink>
                )}
                {hasRole(['admin']) && (
                  <MobileNavLink to="/admin" onClick={() => setMenuOpen(false)}>Admin</MobileNavLink>
                )}
                <div className="pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-2 px-3 py-2 mb-2">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-xs font-bold">
                      {user?.username.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{user?.username}</p>
                      <p className="text-xs text-slate-500">{user?.email}</p>
                    </div>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 rounded-xl transition-colors font-medium"
                  >
                    <LogOut className="w-4 h-4" />
                    Sign out
                  </button>
                </div>
              </>
            ) : (
              <div className="flex flex-col gap-2 pt-2 border-t border-slate-100">
                <Link to="/login" onClick={() => setMenuOpen(false)}>
                  <Button variant="outline" fullWidth>Sign in</Button>
                </Link>
                <Link to="/register" onClick={() => setMenuOpen(false)}>
                  <Button fullWidth>Get Started</Button>
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

function DropdownItem({
  to,
  icon,
  onClick,
  children,
}: {
  to: string;
  icon: React.ReactNode;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-lg transition-colors"
    >
      <span className="text-slate-400">{icon}</span>
      {children}
    </Link>
  );
}

function MobileNavLink({
  to,
  onClick,
  children,
}: {
  to: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      onClick={onClick}
      className={({ isActive }) =>
        cn(
          'block px-3 py-2.5 text-sm font-medium rounded-xl transition-colors',
          isActive
            ? 'bg-blue-50 text-blue-600'
            : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900'
        )
      }
    >
      {children}
    </NavLink>
  );
}
