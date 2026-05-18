import { useApp } from './context/AppContext';
import { AppLayout } from './components/layout/AppLayout';
import { ProcessingModal } from './components/modals/ProcessingModal';
import { Dashboard } from './pages/Dashboard';
import { Upload } from './pages/Upload';
import { Processing } from './pages/Processing';
import { Extraction } from './pages/Extraction';
import { Agents } from './pages/Agents';
import { Workflows } from './pages/Workflows';
import { Analytics } from './pages/Analytics';
import { Validation } from './pages/Validation';

const pageMap = {
  dashboard: Dashboard,
  upload: Upload,
  processing: Processing,
  extraction: Extraction,
  agents: Agents,
  workflows: Workflows,
  analytics: Analytics,
  validation: Validation,
};

function AppContent() {
  const { activePage, showModal } = useApp();
  const PageComponent = pageMap[activePage] || Dashboard;

  return (
    <AppLayout>
      <PageComponent key={activePage} />
      {showModal && <ProcessingModal />}
    </AppLayout>
  );
}

export default AppContent;
