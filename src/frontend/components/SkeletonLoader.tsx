'use client';

interface SkeletonLoaderProps {
  variant?: 'page' | 'card' | 'text';
  lines?: number;
  className?: string;
}

function SkeletonBlock({ className = '' }: { className?: string }) {
  return (
    <div
      className={`skeleton rounded-lg ${className}`}
      aria-hidden="true"
    />
  );
}

function PageSkeleton({ className }: { className?: string }) {
  return (
    <div className={`flex min-h-screen items-center justify-center px-4 py-12 ${className || ''}`}>
      <div className="w-full max-w-3xl space-y-8">
        <div className="theme-card rounded-[30px] p-8">
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <SkeletonBlock className="h-14 w-14 rounded-3xl" />
              <div className="space-y-3">
                <SkeletonBlock className="h-5 w-48 rounded-full" />
                <SkeletonBlock className="h-4 w-32 rounded-full" />
              </div>
            </div>
            <SkeletonBlock className="h-8 w-3/4 rounded-full" />
            <SkeletonBlock className="h-4 w-full rounded-full" />
            <SkeletonBlock className="h-4 w-5/6 rounded-full" />
            <div className="flex gap-3 pt-2">
              <SkeletonBlock className="h-12 w-40 rounded-2xl" />
              <SkeletonBlock className="h-12 w-36 rounded-2xl" />
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-12">
          <div className="theme-card lg:col-span-8 rounded-[30px] p-6">
            <div className="space-y-4">
              <SkeletonBlock className="h-4 w-24 rounded-full" />
              <SkeletonBlock className="h-6 w-1/2 rounded-full" />
              <div className="space-y-3 pt-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="theme-card-muted flex items-center gap-4 rounded-[22px] p-4">
                    <SkeletonBlock className="h-12 w-12 shrink-0 rounded-2xl" />
                    <div className="flex-1 space-y-2">
                      <SkeletonBlock className="h-4 w-3/4 rounded-full" />
                      <SkeletonBlock className="h-3 w-1/2 rounded-full" />
                    </div>
                    <SkeletonBlock className="h-6 w-16 rounded-full" />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="theme-card lg:col-span-4 rounded-[30px] p-6">
            <div className="space-y-4">
              <SkeletonBlock className="h-4 w-28 rounded-full" />
              <SkeletonBlock className="h-5 w-2/3 rounded-full" />
              <div className="space-y-3 pt-2">
                <SkeletonBlock className="h-20 w-full rounded-[22px]" />
                <SkeletonBlock className="h-16 w-full rounded-[22px]" />
                <SkeletonBlock className="h-16 w-full rounded-[22px]" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={`theme-card rounded-[30px] p-6 ${className || ''}`}>
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <SkeletonBlock className="h-12 w-12 shrink-0 rounded-2xl" />
          <div className="flex-1 space-y-2">
            <SkeletonBlock className="h-4 w-3/4 rounded-full" />
            <SkeletonBlock className="h-3 w-1/2 rounded-full" />
          </div>
        </div>
        <SkeletonBlock className="h-3 w-full rounded-full" />
        <SkeletonBlock className="h-3 w-5/6 rounded-full" />
        <SkeletonBlock className="h-3 w-2/3 rounded-full" />
      </div>
    </div>
  );
}

function TextSkeleton({ lines = 4, className }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-3 ${className || ''}`}>
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonBlock
          key={i}
          className={`h-4 rounded-full ${
            i === lines - 1 ? 'w-2/3' : i % 3 === 2 ? 'w-4/5' : 'w-full'
          }`}
        />
      ))}
    </div>
  );
}

export default function SkeletonLoader({
  variant = 'page',
  lines = 4,
  className,
}: SkeletonLoaderProps) {
  switch (variant) {
    case 'card':
      return <CardSkeleton className={className} />;
    case 'text':
      return <TextSkeleton lines={lines} className={className} />;
    case 'page':
    default:
      return <PageSkeleton className={className} />;
  }
}
