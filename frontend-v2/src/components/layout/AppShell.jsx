import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { ToastContainer } from '../ui/ToastContainer';

export function AppShell() {
  return (
    <>
      <Sidebar />
      <div className="main-wrapper">
        <TopBar />
        <main className="main-content">
          <Outlet />
        </main>
      </div>
      <ToastContainer />
    </>
  );
}
