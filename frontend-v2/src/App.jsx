import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { AppProvider } from './store/AppStore';
import { AppShell } from './components/layout/AppShell';
import { Dashboard }  from './pages/Dashboard';
import { Upload }     from './pages/Upload';
import { Processing } from './pages/Processing';
import { Extraction } from './pages/Extraction';
import { Validation } from './pages/Validation';
import { Documents }  from './pages/Documents';
import { Agents }     from './pages/Agents';
import { Analytics }  from './pages/Analytics';
import { Settings }   from './pages/Settings';
import { Templates }  from './pages/Templates';
import { ClaimProcess }  from './pages/ClaimProcess';
import { ClaimWorkflow } from './pages/ClaimWorkflow';
import { KycVerdict }    from './pages/KycVerdict';
import { KycProcess }    from './pages/KycProcess';

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true,          element: <Dashboard />  },
      { path: 'upload',       element: <Upload />     },
      { path: 'processing',   element: <Processing /> },
      { path: 'extraction',   element: <Extraction /> },
      { path: 'validation',   element: <Validation /> },
      { path: 'documents',    element: <Documents />  },
      { path: 'agents',       element: <Agents />     },
      { path: 'analytics',    element: <Analytics />  },
      { path: 'settings',     element: <Settings />   },
      { path: 'templates',       element: <Templates />  },
      { path: 'claim-process',   element: <ClaimProcess /> },
      { path: 'claim-workflow',  element: <ClaimWorkflow /> },
      { path: 'kyc-verdict',     element: <KycVerdict /> },
      { path: 'kyc-process',     element: <KycProcess /> },
    ],
  },
]);

export default function App() {
  return (
    <AppProvider>
      <RouterProvider router={router} />
    </AppProvider>
  );
}
