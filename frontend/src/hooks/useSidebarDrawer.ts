import { useCallback, useEffect, useState } from 'react';
import { useMediaQuery, useTheme } from '@mui/material';

export interface SidebarDrawer {
  /** Whether the drawer is open (only meaningful below `lg`). */
  isOpen: boolean;
  /** Whether the sidebar is a static column (>= lg) rather than a drawer. */
  isDesktop: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

/**
 * Sidebar state as a drawer on narrow screens (same contract as in
 * waterworks-monitoring-platform): the drawer closes when the screen becomes desktop-sized
 * and on Escape. Scroll locking of the content underneath comes from MUI's modal `Drawer`.
 */
export function useSidebarDrawer(): SidebarDrawer {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'), { noSsr: true });
  const [isDrawerOpen, setIsOpen] = useState(false);

  // Reset while rendering: the "intent to open" must not survive a switch to desktop
  // and come back by itself after a tablet rotation.
  const [prevIsDesktop, setPrevIsDesktop] = useState(isDesktop);
  if (isDesktop !== prevIsDesktop) {
    setPrevIsDesktop(isDesktop);
    if (isDesktop && isDrawerOpen) {
      setIsOpen(false);
    }
  }

  const isOpen = isDrawerOpen && !isDesktop;

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen]);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((value) => !value), []);

  return { isOpen, isDesktop, open, close, toggle };
}
