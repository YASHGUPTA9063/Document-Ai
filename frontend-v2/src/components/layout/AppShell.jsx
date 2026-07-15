import { useState, useCallback, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar, applyTheme, getInitialTheme } from './TopBar';
import { ToastContainer } from '../ui/ToastContainer';

// Apply saved theme immediately (before first render)
applyTheme(getInitialTheme());

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);

  const openMobile  = useCallback(() => setMobileOpen(true), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  // Close drawer on Escape key
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') closeMobile(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [closeMobile]);

  return (
    <>
      <Sidebar mobileOpen={mobileOpen} onMobileClose={closeMobile} />
      <div className="main-wrapper">
        <TopBar onMobileMenuToggle={openMobile} />
        <main className="main-content">
          <Outlet />
        </main>
        {/* Mistral signature: sunset stripe at the foot of every page */}
        <div className="sunset-stripe" aria-hidden="true" />
      </div>
      <ToastContainer />
    </>
  );
}
