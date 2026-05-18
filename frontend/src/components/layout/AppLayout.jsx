import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppLayout({ children }) {
  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <TopBar />
        {children}
      </div>
    </div>
  );
}
