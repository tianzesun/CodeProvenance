'use client';

import { ReactNode, useEffect } from 'react';
import Lenis from 'lenis';

interface SmoothScrollProps {
  children: ReactNode;
}

export default function SmoothScroll({ children }: SmoothScrollProps) {
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
      touchMultiplier: 2,
      // Lenis intercepts every wheel event and calls preventDefault. Without
      // this, wheel scrolling is swallowed anywhere inside a nested scrollable
      // region (e.g. the sidebar's nav list), leaving the user to drag the
      // scrollbar. With it, Lenis yields to any inner scroller that can still
      // move in the wheel direction, and only takes over once that region hits
      // its edge — so the sidebar scrolls natively and still chains to the page.
      allowNestedScroll: true,
    });
    let frameId = 0;

    function raf(time: number) {
      lenis.raf(time);
      frameId = requestAnimationFrame(raf);
    }

    frameId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(frameId);
      lenis.destroy();
    };
  }, []);

  return <>{children}</>;
}
