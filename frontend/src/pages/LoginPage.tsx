import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Home, Mail, Lock, ShieldCheck, Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { useToast } from '../components/ui/Toast';
import { useAuth } from '../hooks/useAuth';
import { authApi } from '../lib/api';
import { getErrorMessage } from '../lib/utils';

type Step = 'credentials' | 'otp';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const { success, error: toastError } = useToast();

  const from = (location.state as { from?: string })?.from ?? '/dashboard';

  const [step, setStep] = useState<Step>('credentials');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [otp, setOtp] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password.trim()) return;
    setIsLoading(true);
    try {
      const res = await authApi.loginInit({ identifier, password });
      setChallengeId(res.challenge_id);
      setStep('otp');
      success('Check your email', 'We sent a verification code to your email.');
    } catch (err) {
      toastError('Login failed', getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp.trim()) return;
    setIsLoading(true);
    try {
      const { data: user, userId, sessionToken } = await authApi.loginVerify({
        challenge_id: challengeId,
        otp_code: otp,
      });
      if (userId && sessionToken) {
        login(user, userId, sessionToken);
        success('Welcome back!', `Good to see you, ${user.username}`);
        navigate(from, { replace: true });
      } else {
        toastError('Verification failed', 'Invalid session data received');
      }
    } catch (err) {
      toastError('Verification failed', getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-64px)] flex">
      {/* Left panel — hero */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 items-center justify-center p-12 relative overflow-hidden">
        <div className="absolute top-20 left-20 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-20 w-48 h-48 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="relative text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-blue-500/30">
            <Home className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-3">Welcome Back</h2>
          <p className="text-slate-400 max-w-sm">
            Sign in to your TCG Trove account to access your saved listings, messages, and dashboard.
          </p>
          <div className="mt-8 grid grid-cols-2 gap-4 max-w-xs mx-auto">
            {[
              { label: 'Saved Homes', value: 'Favorites' },
              { label: 'Messages', value: 'Inbox' },
              { label: 'Viewings', value: 'Schedule' },
              { label: 'Bookings', value: 'Reservations' },
            ].map((item) => (
              <div key={item.label} className="bg-white/10 rounded-xl p-3 text-center">
                <p className="text-white font-semibold text-sm">{item.value}</p>
                <p className="text-slate-400 text-xs mt-0.5">{item.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Logo (mobile only) */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
              <Home className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold">
              Home<span className="text-blue-500">Finder</span>
            </span>
          </div>

          {step === 'credentials' ? (
            <>
              <div className="mb-8">
                <h1 className="text-2xl font-bold text-slate-900">Sign in to your account</h1>
                <p className="text-slate-500 mt-1 text-sm">
                  Don&apos;t have an account?{' '}
                  <Link to="/register" className="text-blue-600 font-medium hover:text-blue-700">
                    Create one
                  </Link>
                </p>
              </div>

              <form onSubmit={handleCredentials} className="space-y-4">
                <Input
                  label="Email or Username"
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="you@example.com"
                  leftIcon={<Mail className="w-4 h-4" />}
                  required
                  autoFocus
                />

                <Input
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  leftIcon={<Lock className="w-4 h-4" />}
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="hover:text-slate-600 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  }
                  required
                />

                <Button
                  type="submit"
                  fullWidth
                  size="lg"
                  isLoading={isLoading}
                  className="mt-2"
                >
                  Continue
                </Button>
              </form>
            </>
          ) : (
            <>
              <div className="mb-8">
                <div className="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center mb-4">
                  <ShieldCheck className="w-6 h-6 text-blue-600" />
                </div>
                <h1 className="text-2xl font-bold text-slate-900">Two-factor verification</h1>
                <p className="text-slate-500 mt-1 text-sm">
                  Enter the 6-digit code we sent to your email address.
                </p>
              </div>

              <form onSubmit={handleOtp} className="space-y-4">
                <Input
                  label="Verification Code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  className="text-center text-2xl tracking-widest font-mono"
                  required
                  autoFocus
                />

                <Button
                  type="submit"
                  fullWidth
                  size="lg"
                  isLoading={isLoading}
                  disabled={otp.length < 6}
                >
                  Verify & Sign In
                </Button>

                <button
                  type="button"
                  onClick={() => {
                    setStep('credentials');
                    setOtp('');
                    setChallengeId('');
                  }}
                  className="w-full text-sm text-slate-500 hover:text-slate-700 text-center py-2"
                >
                  Back to login
                </button>
              </form>
            </>
          )}

          <p className="mt-6 text-center text-xs text-slate-400">
            By continuing, you agree to our{' '}
            <a href="#" className="text-blue-500 hover:underline">Terms</a>
            {' '}and{' '}
            <a href="#" className="text-blue-500 hover:underline">Privacy Policy</a>
          </p>
        </div>
      </div>
    </div>
  );
}
