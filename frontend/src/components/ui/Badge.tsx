import React from 'react';
import { cn } from '../../lib/utils';

type BadgeVariant = 'default' | 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'orange';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-slate-100 text-slate-700',
  blue: 'bg-blue-100 text-blue-700',
  green: 'bg-emerald-100 text-emerald-700',
  yellow: 'bg-amber-100 text-amber-700',
  red: 'bg-red-100 text-red-700',
  purple: 'bg-purple-100 text-purple-700',
  orange: 'bg-orange-100 text-orange-700',
};

export function Badge({ variant = 'default', className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        variantClasses[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export function PropertyTypeBadge({ type }: { type: string }) {
  const variants: Record<string, BadgeVariant> = {
    house: 'blue',
    apartment: 'purple',
    villa: 'orange',
    studio: 'green',
    condo: 'yellow',
    townhouse: 'red',
  };

  return (
    <Badge variant={variants[type] ?? 'default'}>
      {type.charAt(0).toUpperCase() + type.slice(1)}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, BadgeVariant> = {
    pending: 'yellow',
    confirmed: 'green',
    cancelled: 'red',
    open: 'blue',
    closed: 'default',
  };

  return (
    <Badge variant={variants[status] ?? 'default'}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}
