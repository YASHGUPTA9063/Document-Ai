# Frontend-v2 UI Reference (Exact Rebuild Guide)

This single file contains the **complete, literal source** of the `frontend-v2` app —
every style, component, and page — so you (or an AI assistant) can recreate the
**exact same UI** (same layout, same spacing, same copy/wording, same colors,
same icons) in a different project.

> How to use this file: copy each section below into a file at the path shown
> in its heading, inside a fresh Vite + React project. The sections are in the
> order you should create them. Do not reword, "improve", or restructure
> anything — paste it verbatim to guarantee pixel-for-pixel and word-for-word
> parity with the original.

---

## 1. Tech stack & dependencies

- **Build tool:** Vite
- **Framework:** React 19 (function components + hooks, no TypeScript — plain `.jsx`)
- **Routing:** `react-router-dom` v7
- **HTTP:** `axios`
- **Icons:** `lucide-react` (+ one custom inline SVG sprite at `public/icons.svg`)
- **Styling:** plain CSS (no Tailwind, no CSS-in-JS) — a design-token file
  (`tokens.css`) feeding a layout stylesheet, a components stylesheet, and an
  animations stylesheet, all imported globally from `index.css` / `App.jsx`.
- **State:** a single React Context store (`src/store/AppStore.jsx`), no Redux.

### Setup in the new project

```bash
npm create vite@latest my-app -- --template react
cd my-app
npm install axios lucide-react react-router-dom
```

Then recreate this exact folder structure under `src/`:

```
src/
├── api/
│   └── client.js
├── assets/
│   └── hero.png                (any placeholder image works — see note below)
├── components/
│   ├── layout/
│   │   ├── AppShell.jsx
│   │   ├── Sidebar.jsx
│   │   └── TopBar.jsx
│   └── ui/
│       ├── ConfidenceBar.jsx
│       ├── DonutChart.jsx
│       ├── Modal.jsx
│       ├── PipelineSteps.jsx
│       ├── RegionSelector.jsx
│       ├── StatCard.jsx
│       ├── StatusBadge.jsx
│       └── ToastContainer.jsx
├── hooks/
│   ├── useDocumentList.js
│   └── useDocumentPoller.js
├── pages/
│   ├── Agents.jsx
│   ├── Analytics.jsx
│   ├── ClaimProcess.jsx
│   ├── ClaimWorkflow.jsx
│   ├── Dashboard.jsx
│   ├── Documents.jsx
│   ├── Extraction.jsx
│   ├── Processing.jsx
│   ├── Settings.jsx
│   ├── Templates.jsx
│   ├── Upload.jsx
│   ├── Validation.jsx
│   └── claimData.js
├── store/
│   └── AppStore.jsx
├── styles/
│   ├── animations.css
│   ├── components.css
│   ├── layout.css
│   └── tokens.css
├── App.css
├── App.jsx
├── index.css
└── main.jsx
public/
├── favicon.svg
└── icons.svg
```

> **Note on `src/assets/hero.png`:** this is a binary image (not reproducible
> as text in this reference file). It's only referenced decoratively — drop
> in any placeholder PNG of the same name and the layout/UI around it stays
> identical.

Everything below is the literal file content. File path is the section heading.

---
## `package.json`

```json
{
  "name": "frontend-v2",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "^1.16.1",
    "lucide-react": "^1.16.0",
    "react": "^19.2.6",
    "react-dom": "^19.2.6",
    "react-router-dom": "^7.15.1"
  },
  "devDependencies": {
    "@eslint/js": "^10.0.1",
    "@types/react": "^19.2.14",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.1",
    "eslint": "^10.3.0",
    "eslint-plugin-react-hooks": "^7.1.1",
    "eslint-plugin-react-refresh": "^0.5.2",
    "globals": "^17.6.0",
    "vite": "^8.0.12"
  }
}
```

## `vite.config.js`

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
})
```

## `index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <!-- Professional SVG favicon: document with AI circuit motif -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%234f6ef7'/><stop offset='1' stop-color='%237c3aed'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><rect x='7' y='5' width='13' height='17' rx='2' fill='white' fill-opacity='0.2'/><rect x='7' y='5' width='13' height='17' rx='2' stroke='white' stroke-opacity='0.6' stroke-width='1'/><line x1='10' y1='10' x2='17' y2='10' stroke='white' stroke-opacity='0.8' stroke-width='1.2' stroke-linecap='round'/><line x1='10' y1='13' x2='17' y2='13' stroke='white' stroke-opacity='0.8' stroke-width='1.2' stroke-linecap='round'/><line x1='10' y1='16' x2='14' y2='16' stroke='white' stroke-opacity='0.5' stroke-width='1.2' stroke-linecap='round'/><circle cx='21' cy='22' r='7' fill='%2306c0db'/><path d='M18 22L20.2 24.2L24 20' stroke='white' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/></svg>" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="Intelligent Document Processing — Enterprise IDP Platform powered by AI agents for automated document extraction, validation, and analysis" />
    <meta name="theme-color" content="#080b14" />
    <title>Intelligent Document Processing — IDP Platform</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

## `src/main.jsx`

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/animations.css'
import './styles/layout.css'
import './styles/components.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

## `src/App.jsx`

```jsx
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
```

## `src/App.css`

```css
.counter {
  font-size: 16px;
  padding: 5px 10px;
  border-radius: 5px;
  color: var(--accent);
  background: var(--accent-bg);
  border: 2px solid transparent;
  transition: border-color 0.3s;
  margin-bottom: 24px;

  &:hover {
    border-color: var(--accent-border);
  }
  &:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
}

.hero {
  position: relative;

  .base,
  .framework,
  .vite {
    inset-inline: 0;
    margin: 0 auto;
  }

  .base {
    width: 170px;
    position: relative;
    z-index: 0;
  }

  .framework,
  .vite {
    position: absolute;
  }

  .framework {
    z-index: 1;
    top: 34px;
    height: 28px;
    transform: perspective(2000px) rotateZ(300deg) rotateX(44deg) rotateY(39deg)
      scale(1.4);
  }

  .vite {
    z-index: 0;
    top: 107px;
    height: 26px;
    width: auto;
    transform: perspective(2000px) rotateZ(300deg) rotateX(40deg) rotateY(39deg)
      scale(0.8);
  }
}

#center {
  display: flex;
  flex-direction: column;
  gap: 25px;
  place-content: center;
  place-items: center;
  flex-grow: 1;

  @media (max-width: 1024px) {
    padding: 32px 20px 24px;
    gap: 18px;
  }
}

#next-steps {
  display: flex;
  border-top: 1px solid var(--border);
  text-align: left;

  & > div {
    flex: 1 1 0;
    padding: 32px;
    @media (max-width: 1024px) {
      padding: 24px 20px;
    }
  }

  .icon {
    margin-bottom: 16px;
    width: 22px;
    height: 22px;
  }

  @media (max-width: 1024px) {
    flex-direction: column;
    text-align: center;
  }
}

#docs {
  border-right: 1px solid var(--border);

  @media (max-width: 1024px) {
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}

#next-steps ul {
  list-style: none;
  padding: 0;
  display: flex;
  gap: 8px;
  margin: 32px 0 0;

  .logo {
    height: 18px;
  }

  a {
    color: var(--text-h);
    font-size: 16px;
    border-radius: 6px;
    background: var(--social-bg);
    display: flex;
    padding: 6px 12px;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    transition: box-shadow 0.3s;

    &:hover {
      box-shadow: var(--shadow);
    }
    .button-icon {
      height: 18px;
      width: 18px;
    }
  }

  @media (max-width: 1024px) {
    margin-top: 20px;
    flex-wrap: wrap;
    justify-content: center;

    li {
      flex: 1 1 calc(50% - 8px);
    }

    a {
      width: 100%;
      justify-content: center;
      box-sizing: border-box;
    }
  }
}

#spacer {
  height: 88px;
  border-top: 1px solid var(--border);
  @media (max-width: 1024px) {
    height: 48px;
  }
}

.ticks {
  position: relative;
  width: 100%;

  &::before,
  &::after {
    content: '';
    position: absolute;
    top: -4.5px;
    border: 5px solid transparent;
  }

  &::before {
    left: 0;
    border-left-color: var(--border);
  }
  &::after {
    right: 0;
    border-right-color: var(--border);
  }
}
```

## `src/index.css`

```css
/* index.css — Entry point; all design system imports are handled in main.jsx */
/* This file is intentionally minimal to avoid conflicting with tokens.css */

body {
  margin: 0;
}
```


---

# CSS — Design tokens & global styles

## `src/styles/tokens.css`

```css
/* ─── Google Fonts ───────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,700;1,400&family=Inter:ital,opsz,wght@0,14..32,300;0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;0,14..32,800;0,14..32,900&display=swap');

/* ─── Reset & Base ─────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ══════════════════════════════════════════════════
   LIGHT THEME (default) — Mistral Warm Sunset
══════════════════════════════════════════════════ */
:root {
  /* ── Mistral Core Palette ── */
  --mistral-orange:       #fa520f;
  --mistral-orange-deep:  #cc3a05;
  --mistral-sunshine-300: #ffd06a;
  --mistral-sunshine-500: #ffb83e;
  --mistral-sunshine-700: #ffa110;
  --mistral-sunshine-800: #ff8105;
  --mistral-sunshine-900: #ff8a00;
  --mistral-yellow:       #ffd900;
  --mistral-cream:        #fff8e0;
  --mistral-cream-light:  #fffaeb;
  --mistral-cream-deep:   #fff0c2;
  --mistral-beige-deep:   #e6d5a8;
  --mistral-ink:          #1f1f1f;
  --mistral-ink-tint:     #3d3d3d;
  --mistral-steel:        #6a6a6a;
  --mistral-stone:        #8a8a8a;
  --mistral-hairline:     #e5e5e5;
  --mistral-hairline-soft:#ededed;

  /* ── Backgrounds & Surfaces ── */
  --bg:              #fffaeb;
  --surface:         #ffffff;
  --surface-elevated: #ffffff;
  --surface-sunken:  #fff0c2;
  --card:            #ffffff;
  --card-alt:        #fffaeb;
  --card-hi:         #fff0c2;
  --border:          #e6d5a8;
  --border-hi:       #d4bc8a;
  --border-glow:     rgba(250, 82, 15, 0.20);

  /* ── Brand Accents ── */
  --accent:          #fa520f;
  --accent-hover:    #cc3a05;
  --accent2:         #ff8105;
  --accent3:         #ffb83e;
  --accent4:         #ffd900;
  --accent-dim:      rgba(250, 82, 15, 0.10);
  --accent-dim2:     rgba(250, 82, 15, 0.05);

  /* ── Button Shadow Variables ── */
  --btn-shadow:       rgba(250, 82, 15, 0.25);
  --btn-shadow-hover: rgba(250, 82, 15, 0.35);

  /* ── Logo Shadow Variable ── */
  --logo-shadow:      0 4px 16px rgba(250, 82, 15, 0.30);

  /* ── Navigation variables ── */
  --nav-indicator-shadow: 0 0 10px rgba(250, 82, 15, 0.40);
  --nav-badge-shadow:     0 0 8px rgba(250, 82, 15, 0.30);

  /* ── Upload Zone Shadow Variables ── */
  --upload-radial-glow:       rgba(250, 82, 15, 0.06);
  --upload-radial-glow-hover: rgba(250, 82, 15, 0.12);
  --upload-icon-border:       rgba(250, 82, 15, 0.15);
  --upload-icon-inner-shadow: inset 0 2px 4px rgba(250, 82, 15, 0.05);
  --upload-icon-dashed-border: rgba(250, 82, 15, 0.18);
  --upload-icon-border-hover:  rgba(250, 82, 15, 0.35);

  /* ── Pipeline variables ── */
  --pipeline-step-glow:       0 0 16px rgba(250, 82, 15, 0.40);

  /* ── Page Hero variables ── */
  --hero-radial-glow:         rgba(250, 82, 15, 0.08);

  /* ── Animations Pulse variables ── */
  --pulse-glow-1:             rgba(250, 82, 15, 0.2);
  --pulse-glow-2:             rgba(250, 82, 15, 0);
  --glow-pulse-1:             0 0 16px rgba(250, 82, 15, 0.3);
  --glow-pulse-2:             0 0 28px rgba(250, 82, 15, 0.6);

  /* ── Gradients ── */
  --grad-brand:    linear-gradient(135deg, #fa520f 0%, #ff8105 100%);
  --grad-sunset:   linear-gradient(90deg, #fa520f 0%, #ffa110 30%, #ffb83e 60%, #ffd900 80%, #fff8e0 100%);
  --grad-cyan:     linear-gradient(135deg, #ffb83e 0%, #fa520f 100%);
  --grad-warm:     linear-gradient(135deg, #fa520f 0%, #cc3a05 100%);
  --grad-success:  linear-gradient(135deg, #10b981 0%, #059669 100%);
  --grad-surface:  linear-gradient(180deg, #ffffff 0%, #fffaeb 100%);

  /* ── Status ── */
  --success:         #10b981;
  --success-dim:     rgba(16, 185, 129, 0.10);
  --success-border:  rgba(16, 185, 129, 0.25);
  --warn:            #f59e0b;
  --warn-dim:        rgba(245, 158, 11, 0.10);
  --warn-border:     rgba(245, 158, 11, 0.25);
  --danger:          #ef4444;
  --danger-dim:      rgba(239, 68, 68, 0.10);
  --danger-border:   rgba(239, 68, 68, 0.25);
  --info:            #3b82f6;
  --info-dim:        rgba(59, 130, 246, 0.10);

  /* ── Text ── */
  --text:            #1f1f1f;
  --text-dim:        #4a4a4a;
  --muted:           #8a8a8a;

  /* ── Effects ── */
  --highlight:       rgba(250, 82, 15, 0.10);
  --glow:            0 8px 40px rgba(250, 82, 15, 0.18);
  --glow-sm:         0 4px 20px rgba(250, 82, 15, 0.12);
  --glow-success:    0 4px 20px rgba(16, 185, 129, 0.14);
  --shadow:          0 16px 40px rgba(31, 31, 31, 0.10), 0 4px 12px rgba(31, 31, 31, 0.04);
  --shadow-sm:       0 2px 8px rgba(31, 31, 31, 0.06);
  --shadow-card:     rgba(0, 0, 0, 0.04) 0px 4px 12px 0px;
  --glass:           rgba(255, 255, 255, 0.90);
  --glass-border:    rgba(230, 213, 168, 0.60);

  /* ── Layout ── */
  --sidebar-w:       220px;
  --sidebar-collapsed-w: 64px;
  --topbar-h:        60px;
  --radius:          12px;
  --radius-sm:       8px;
  --radius-lg:       16px;
  --radius-xl:       20px;

  /* ── Typography Scale ── */
  --text-xs:   10px;
  --text-sm:   11px;
  --text-base: 12px;
  --text-md:   13px;
  --text-lg:   14px;
  --text-xl:   16px;
  --text-2xl:  20px;
  --text-3xl:  28px;

  /* ── Font Families ── */
  --font-display: 'Playfair Display', 'Times New Roman', Georgia, serif;
  --font-ui:      'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
  --font-mono:    'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;

  /* ── Motion ── */
  --ease:        cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-out:    cubic-bezier(0, 0, 0.2, 1);
  --dur:         160ms;
  --dur-md:      240ms;
  --dur-lg:      360ms;
}

/* ══════════════════════════════════════════════════
   DARK THEME — warm amber-adapted dark mode
══════════════════════════════════════════════════ */
[data-theme="dark"] {
  /* ── Backgrounds & Surfaces ── */
  --bg:              #050505;
  --surface:         #0a0a0a;
  --surface-elevated: #0e0e0e;
  --surface-sunken:  #030303;
  --card:            #0a0a0a;
  --card-alt:        #0e0e0e;
  --card-hi:         #141414;
  --border:          #1e1e1e;
  --border-hi:       #2c2c2c;
  --border-glow:     rgba(204, 58, 5, 0.25);

  /* ── Brand Accents (darker orange) ── */
  --accent:          #cc3a05;
  --accent-hover:    #ad2e01;
  --accent2:         #d35400;
  --accent3:         #e67e22;
  --accent4:         #f39c12;
  --accent-dim:      rgba(204, 58, 5, 0.15);
  --accent-dim2:     rgba(204, 58, 5, 0.08);

  /* ── Button Shadow Variables ── */
  --btn-shadow:       rgba(204, 58, 5, 0.30);
  --btn-shadow-hover: rgba(204, 58, 5, 0.40);

  /* ── Logo Shadow Variable ── */
  --logo-shadow:      0 4px 16px rgba(204, 58, 5, 0.40);

  /* ── Navigation variables ── */
  --nav-indicator-shadow: 0 0 10px rgba(204, 58, 5, 0.50);
  --nav-badge-shadow:     0 0 8px rgba(204, 58, 5, 0.40);

  /* ── Upload Zone Shadow Variables ── */
  --upload-radial-glow:       rgba(204, 58, 5, 0.08);
  --upload-radial-glow-hover: rgba(204, 58, 5, 0.16);
  --upload-icon-border:       rgba(204, 58, 5, 0.25);
  --upload-icon-inner-shadow: inset 0 2px 4px rgba(204, 58, 5, 0.08);
  --upload-icon-dashed-border: rgba(204, 58, 5, 0.28);
  --upload-icon-border-hover:  rgba(204, 58, 5, 0.45);

  /* ── Pipeline variables ── */
  --pipeline-step-glow:       0 0 16px rgba(204, 58, 5, 0.50);

  /* ── Page Hero variables ── */
  --hero-radial-glow:         rgba(204, 58, 5, 0.12);

  /* ── Animations Pulse variables ── */
  --pulse-glow-1:             rgba(204, 58, 5, 0.25);
  --pulse-glow-2:             rgba(204, 58, 5, 0);
  --glow-pulse-1:             0 0 16px rgba(204, 58, 5, 0.45);
  --glow-pulse-2:             0 0 28px rgba(204, 58, 5, 0.75);

  /* ── Gradients ── */
  --grad-brand:    linear-gradient(135deg, #cc3a05 0%, #d35400 100%);
  --grad-sunset:   linear-gradient(90deg, #cc3a05 0%, #d35400 30%, #e67e22 60%, #f39c12 80%, #fff8e0 100%);
  --grad-cyan:     linear-gradient(135deg, #e67e22 0%, #cc3a05 100%);
  --grad-warm:     linear-gradient(135deg, #cc3a05 0%, #ad2e01 100%);
  --grad-success:  linear-gradient(135deg, #10b981 0%, #059669 100%);
  --grad-surface:  linear-gradient(180deg, #0a0a0a 0%, #050505 100%);

  /* ── Status ── */
  --success:         #34d399;
  --success-dim:     rgba(52, 211, 153, 0.12);
  --success-border:  rgba(52, 211, 153, 0.25);
  --warn:            #fbbf24;
  --warn-dim:        rgba(251, 191, 36, 0.12);
  --warn-border:     rgba(251, 191, 36, 0.25);
  --danger:          #f87171;
  --danger-dim:      rgba(248, 113, 113, 0.12);
  --danger-border:   rgba(248, 113, 113, 0.25);
  --info:            #60a5fa;
  --info-dim:        rgba(96, 165, 250, 0.12);

  /* ── Text ── */
  --text:            #f5f5f5;
  --text-dim:        #b8b8b8;
  --muted:           #8a8a8a;

  /* ── Effects ── */
  --highlight:       rgba(204, 58, 5, 0.12);
  --glow:            0 8px 40px rgba(204, 58, 5, 0.22);
  --glow-sm:         0 4px 20px rgba(204, 58, 5, 0.14);
  --glow-success:    0 4px 20px rgba(52, 211, 153, 0.16);
  --shadow:          0 16px 40px rgba(0, 0, 0, 0.70), 0 4px 12px rgba(0, 0, 0, 0.45);
  --shadow-sm:       0 2px 8px rgba(0, 0, 0, 0.45);
  --shadow-card:     rgba(0, 0, 0, 0.40) 0px 4px 12px 0px;
  --glass:           rgba(8, 8, 8, 0.94);
  --glass-border:    rgba(255, 255, 255, 0.06);
}

/* ══════════════════════════════════════════════════
   BASE STYLES
══════════════════════════════════════════════════ */
html { font-size: 14px; scroll-behavior: smooth; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-ui);
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-image:
    radial-gradient(ellipse 70% 50% at 50% -5%, rgba(250, 82, 15, 0.06) 0%, transparent 70%),
    radial-gradient(ellipse 50% 40% at 90% 90%, rgba(255, 165, 16, 0.05) 0%, transparent 60%);
  background-attachment: fixed;
  transition: background-color var(--dur-lg) var(--ease), color var(--dur-lg) var(--ease);
}

[data-theme="dark"] body {
  background: linear-gradient(180deg, #0e0e0e 0%, #050505 35%, #030303 100%);
  background-attachment: fixed;
}

a { color: var(--accent); text-decoration: none; }
button { cursor: pointer; font-family: inherit; }
img { max-width: 100%; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── Focus Visible Ring (Accessibility) ── */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* ── Display / Editorial font utility ── */
.font-display {
  font-family: var(--font-display);
  font-weight: 400;
  letter-spacing: -0.5px;
}

/* ── Gradient text utility ── */
.grad {
  background: var(--grad-brand);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.grad-warm {
  background: var(--grad-warm);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
[data-theme="dark"] .grad,
[data-theme="dark"] .grad-warm {
  background: none;
  -webkit-background-clip: initial;
  -webkit-text-fill-color: initial;
  background-clip: initial;
  color: var(--text);
}

/* ── Chip ── */
.chip {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--card-alt); border: 1px solid var(--border);
  border-radius: 99px; padding: 3px 10px;
  font-size: var(--text-sm); color: var(--text-dim);
}

/* ── Animated border (upload zone — only on dragover) ── */
.animated-border-active {
  position: relative; border-radius: 16px; padding: 1px;
  background: linear-gradient(135deg, var(--accent), var(--accent2), var(--accent3));
  animation: border-rotate 4s linear infinite;
}
.animated-border-active > * { border-radius: 15px; }

/* ── Glassmorphism card variant ── */
.glass-card {
  background: var(--glass);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

/* ── Divider ── */
.divider {
  height: 1px;
  background: var(--border);
  margin: 12px 0;
}

/* ── Theme transition (smooth dark/light switch) ── */
*, *::before, *::after {
  transition: background-color var(--dur-md) var(--ease),
              border-color var(--dur-md) var(--ease),
              color var(--dur-md) var(--ease),
              box-shadow var(--dur-md) var(--ease);
}
/* But don't transition transforms / widths (causes jank) */
.sidebar, .btn, .nav-item, .card, .stat-card {
  transition: all var(--dur) var(--ease);
}
```

## `src/styles/layout.css`

```css
/* ─── App Shell ─────────────────────────────────── */
#root { display: flex; height: 100vh; overflow: hidden; }

/* ─── Sidebar ───────────────────────────────────── */
.sidebar {
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: visible;
  z-index: 100;
  position: relative;
  flex-shrink: 0;
  /* Collapse transition */
  transition: width var(--dur-md) var(--ease), min-width var(--dur-md) var(--ease);
}

.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Collapsed sidebar — icon rail */
.sidebar.collapsed {
  width: var(--sidebar-collapsed-w);
  min-width: var(--sidebar-collapsed-w);
}

/* Subtle warm gradient decoration */
.sidebar::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 220px;
  background: radial-gradient(ellipse 100% 60% at 50% -10%, rgba(250, 82, 15, 0.10) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}
[data-theme="dark"] .sidebar::before {
  background: none;
}

/* ─── Logo ──────────────────────────────────────── */
.logo {
  padding: 18px 14px 16px;
  border-bottom: 1px solid var(--border);
  position: relative;
  z-index: 1;
  flex-shrink: 0;
}
.logo-mark { display: flex; align-items: center; gap: 10px; }

.logo-icon {
  width: 36px; height: 36px;
  background: var(--grad-brand);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--logo-shadow), 0 2px 8px rgba(31, 31, 31, 0.10);
  position: relative;
  overflow: hidden;
}
.logo-icon::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.18) 0%, transparent 60%);
}

.logo-text-wrap {
  overflow: hidden;
  white-space: nowrap;
  transition: opacity var(--dur-md) var(--ease), width var(--dur-md) var(--ease);
}
.sidebar.collapsed .logo-text-wrap {
  opacity: 0;
  width: 0;
  pointer-events: none;
}

.logo-text {
  font-size: var(--text-lg); font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--text);
  line-height: 1.2;
  display: block;
  font-family: var(--font-display);
}
.logo-sub {
  font-size: var(--text-xs); color: var(--muted); font-weight: 500;
  letter-spacing: 0.06em; margin-top: 3px;
  text-transform: uppercase;
}

/* ─── Collapse Toggle Button ─────────────────────── */
.sidebar-collapse-btn {
  position: absolute; top: 24px; right: -12px;
  width: 24px; height: 24px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  color: var(--muted);
  box-shadow: var(--shadow-sm);
  z-index: 200;
  transition: all var(--dur) var(--ease);
  opacity: 0;
}
.sidebar:hover .sidebar-collapse-btn { opacity: 1; }
.sidebar-collapse-btn:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }
.sidebar.collapsed .sidebar-collapse-btn { opacity: 1; }

/* ─── Nav Sections ──────────────────────────────── */
.nav-section { padding: 8px 8px 2px; position: relative; z-index: 1; }

.nav-label {
  font-size: var(--text-sm); letter-spacing: 0.10em; text-transform: uppercase;
  color: var(--muted); padding: 0 8px; margin-bottom: 4px;
  font-weight: 600;
  white-space: nowrap; overflow: hidden;
  transition: opacity var(--dur) var(--ease);
}
.sidebar.collapsed .nav-label { opacity: 0; }

/* ─── Nav Items ─────────────────────────────────── */
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: var(--radius-sm);
  color: var(--text-dim); font-size: var(--text-md); font-weight: 500;
  cursor: pointer;
  transition: background var(--dur) var(--ease), color var(--dur) var(--ease), border-color var(--dur) var(--ease);
  position: relative;
  margin-bottom: 2px;
  white-space: nowrap; overflow: hidden;
  border: 1px solid transparent;
}

.nav-item:hover {
  background: var(--accent-dim);
  color: var(--text);
}

.nav-item.active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 600;
  border-color: transparent;
}

/* Active left indicator — animated in */
.nav-item.active::before {
  content: '';
  position: absolute; left: 0; top: 18%; bottom: 18%;
  width: 3px;
  background: var(--grad-brand);
  border-radius: 0 3px 3px 0;
  box-shadow: var(--nav-indicator-shadow);
  animation: nav-indicator-in var(--dur-md) var(--ease-spring) both;
}
[data-theme="dark"] .nav-item.active::before {
  background: var(--accent);
}

@keyframes nav-indicator-in {
  from { transform: scaleY(0); opacity: 0; }
  to   { transform: scaleY(1); opacity: 1; }
}

.nav-icon { opacity: 0.75; flex-shrink: 0; }
.nav-item:hover .nav-icon { opacity: 0.95; }
.nav-item.active .nav-icon { opacity: 1; }

.nav-item-label {
  flex: 1;
  overflow: hidden;
  transition: opacity var(--dur) var(--ease), max-width var(--dur-md) var(--ease);
}
.sidebar.collapsed .nav-item-label { opacity: 0; max-width: 0; }

/* Tooltip for collapsed mode */
.nav-item[title] { position: relative; }
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
}

/* ─── Nav Badge ─────────────────────────────────── */
.nav-badge {
  background: var(--accent); color: white;
  font-size: var(--text-xs); font-weight: 700; padding: 1px 6px; border-radius: 99px;
  box-shadow: var(--nav-badge-shadow);
  flex-shrink: 0;
  transition: opacity var(--dur) var(--ease);
}
.sidebar.collapsed .nav-badge { opacity: 0; }

/* ─── Sidebar Footer ────────────────────────────── */
.sidebar-footer {
  margin-top: auto; padding: 12px 12px 14px;
  border-top: 1px solid var(--border);
  position: relative; z-index: 1;
}
.agent-status {
  display: flex; align-items: center; gap: 10px;
  background: var(--success-dim);
  border: 1px solid var(--success-border);
  border-radius: var(--radius-sm); padding: 10px 12px;
  transition: background var(--dur) var(--ease);
  overflow: hidden;
}
.agent-status:hover { background: rgba(16, 185, 129, 0.14); }

.agent-status-text {
  overflow: hidden;
  white-space: nowrap;
  transition: opacity var(--dur) var(--ease), max-width var(--dur-md) var(--ease);
}
.sidebar.collapsed .agent-status { padding: 10px; justify-content: center; }
.sidebar.collapsed .agent-status-text { opacity: 0; max-width: 0; }

/* ─── Mobile Overlay ─────────────────────────────── */
.sidebar-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 99;
  backdrop-filter: blur(2px);
  animation: fade-in 200ms var(--ease);
}

/* ─── Top Bar ───────────────────────────────────── */
.topbar {
  height: var(--topbar-h);
  background: var(--glass);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 22px; position: sticky; top: 0; z-index: 50; flex-shrink: 0;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}
.topbar-left { display: flex; align-items: center; gap: 12px; }
.topbar-breadcrumb {
  display: flex; flex-direction: column; gap: 1px;
}
.topbar-title { font-size: var(--text-lg); font-weight: 700; letter-spacing: -0.2px; font-family: var(--font-display); }
.topbar-sub { font-size: var(--text-sm); color: var(--muted); }
.topbar-right { display: flex; align-items: center; gap: 8px; }

/* Hamburger (mobile only) */
.topbar-hamburger {
  display: none;
  background: none; border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 6px 8px;
  color: var(--text-dim);
  transition: all var(--dur) var(--ease);
}
.topbar-hamburger:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }

/* ─── Notification Dropdown ─────────────────────── */
.notif-wrapper { position: relative; }
.notif-dropdown {
  position: absolute; top: calc(100% + 8px); right: 0;
  width: 300px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  animation: slide-in 150ms var(--ease) both;
  z-index: 200;
}
.notif-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  font-size: var(--text-md); font-weight: 700;
  display: flex; align-items: center; justify-content: space-between;
}
.notif-item {
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  font-size: var(--text-base); cursor: pointer;
  transition: background var(--dur) var(--ease);
  display: flex; align-items: flex-start; gap: 10px;
}
.notif-item:last-child { border-bottom: none; }
.notif-item:hover { background: var(--accent-dim); }
.notif-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--warn); flex-shrink: 0; margin-top: 4px; }
.notif-empty { padding: 20px 16px; text-align: center; color: var(--muted); font-size: var(--text-sm); }

/* ─── Theme Toggle Button ────────────────────────── */
.theme-toggle {
  width: 34px; height: 34px;
  background: var(--card-alt); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-dim);
  transition: all var(--dur) var(--ease);
}
.theme-toggle:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }

/* ─── Main Content ──────────────────────────────── */
.main-wrapper { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; background: var(--bg); }
.main-content { flex: 1; overflow-y: auto; padding: 24px; background: var(--bg); }
.page { animation: slide-in 220ms var(--ease) both; background: var(--bg); }

/* ─── Grids ─────────────────────────────────────── */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px; }

/* ─── Responsive ─────────────────────────────────── */
@media (max-width: 1100px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .grid-2 { grid-template-columns: 1fr; }
}
@media (max-width: 800px) {
  .grid-3 { grid-template-columns: 1fr 1fr; }
  :root { --sidebar-w: 220px; }
}

@media (max-width: 768px) {
  /* On mobile, sidebar is a drawer */
  .sidebar {
    position: fixed; inset-block: 0; left: 0;
    transform: translateX(-100%);
    transition: transform var(--dur-md) var(--ease);
    z-index: 200;
    box-shadow: var(--shadow);
  }
  .sidebar.mobile-open {
    transform: translateX(0);
  }
  .sidebar-overlay { display: block; }
  .topbar-hamburger { display: flex; }
  .main-content { padding: 16px; }
}

@media (max-width: 600px) {
  .grid-3 { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: 1fr 1fr; }
}
```

## `src/styles/components.css`

```css
/* ─── Card — Base ────────────────────────────────── */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
  transition: border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease), transform var(--dur) var(--ease);
  box-shadow: var(--shadow-card);
  position: relative;
}
.card:last-child { margin-bottom: 0; }
.card:hover {
  border-color: var(--border-hi);
  box-shadow: 0 6px 28px rgba(0, 0, 0, 0.10);
}

/* ── Data card (charts, visualizations) — no hover lift ── */
.card-data {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-card);
  position: relative;
  overflow: hidden;
}
.card-data::after {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent-dim), transparent 80%);
}

/* ── Action card (CTA sections) — accent left border ── */
.card-action {
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-card);
  background: linear-gradient(120deg, var(--accent-dim2) 0%, var(--card) 50%);
}

/* ── Alert card — for warnings/errors ── */
.card-alert {
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
  border: 1px solid var(--warn-border);
  background: var(--warn-dim);
  box-shadow: var(--shadow-card);
}
.card-alert.danger {
  border-color: var(--danger-border);
  background: var(--danger-dim);
}
.card-alert.success {
  border-color: var(--success-border);
  background: var(--success-dim);
}

/* ── Card with gradient top accent strip ── */
.card-accent {
  position: relative; overflow: hidden;
}
.card-accent::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--grad-brand);
}

/* ── Glassmorphism card ── */
.card-glass {
  background: var(--glass);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow);
}

/* ── Card Header ── */
.card-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  margin-bottom: 16px; gap: 12px;
}
.card-title { font-size: var(--text-lg); font-weight: 700; letter-spacing: -0.1px; color: var(--text); }
.card-sub { font-size: var(--text-sm); color: var(--muted); margin-top: 2px; font-weight: 400; }

/* ─── Stat Card ─────────────────────────────────── */
.stat-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px;
  transition: all var(--dur-md) var(--ease-spring);
  cursor: default;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}

/* Decorative background circle */
.stat-card::before {
  content: '';
  position: absolute; top: 0; right: 0;
  width: 90px; height: 90px; border-radius: 50%;
  background: var(--accent-dim2);
  transform: translate(30px, -30px);
  transition: all var(--dur-md) var(--ease);
}

/* Gradient top border strip */
.stat-card::after {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--stat-gradient, var(--grad-brand));
  opacity: 0;
  transition: opacity var(--dur-md) var(--ease);
}

.stat-card:hover {
  border-color: rgba(251, 107, 45, 0.35);
  box-shadow: var(--glow-sm), var(--shadow-card);
  transform: translateY(-3px);
}
.stat-card:hover::before {
  background: rgba(251, 107, 45, 0.08);
  transform: translate(20px, -20px) scale(1.3);
}
.stat-card:hover::after { opacity: 1; }

/* Icon container — colored based on variant */
.stat-icon {
  width: 42px; height: 42px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  margin-bottom: 14px;
  position: relative; z-index: 1;
  border: 1px solid rgba(0,0,0,0.04);
}
.stat-icon.accent  { background: var(--accent-dim);  color: var(--accent); }
.stat-icon.success { background: var(--success-dim); color: var(--success); }
.stat-icon.warn    { background: var(--warn-dim);    color: var(--warn); }
.stat-icon.danger  { background: var(--danger-dim);  color: var(--danger); }
.stat-icon.info    { background: var(--info-dim);    color: var(--info); }

.stat-label { font-size: var(--text-sm); color: var(--text-dim); font-weight: 500; margin-bottom: 6px; letter-spacing: 0.02em; position: relative; z-index: 1; }
.stat-value { font-size: var(--text-3xl); font-weight: 800; letter-spacing: -0.04em; color: var(--text); position: relative; z-index: 1; }
.stat-unit  { font-size: var(--text-xl); font-weight: 600; opacity: 0.7; margin-left: 2px; }
.stat-delta { font-size: var(--text-sm); margin-top: 8px; display: flex; align-items: center; gap: 4px; position: relative; z-index: 1; }
.stat-delta.up   { color: var(--success); }
.stat-delta.warn { color: var(--warn); }
.stat-delta.down { color: var(--danger); }
.stat-delta.neutral { color: var(--muted); }

/* ─── Badge ─────────────────────────────────────── */
.badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--text-sm); font-weight: 600; padding: 3px 9px;
  border-radius: 99px; border: 1px solid;
  letter-spacing: 0.01em; white-space: nowrap;
}
.badge-blue   { color: #2563eb; border-color: rgba(37,99,235,0.2);   background: rgba(37,99,235,0.07);   }
.badge-green  { color: #059669; border-color: rgba(5,150,105,0.2);   background: rgba(5,150,105,0.07);   }
.badge-yellow { color: #d97706; border-color: rgba(217,119,6,0.2);   background: rgba(217,119,6,0.07);   }
.badge-red    { color: #dc2626; border-color: rgba(220,38,38,0.2);   background: rgba(220,38,38,0.07);   }
.badge-cyan   { color: #0891b2; border-color: transparent;            background: rgba(8,145,178,0.07);   }
.badge-purple { color: #7c3aed; border-color: rgba(124,58,237,0.2);  background: rgba(124,58,237,0.07);  }
.badge-gray   { color: var(--text-dim); border-color: var(--border); background: var(--card-alt);        }

/* Dark mode badge overrides — brighter text for jet black bg */
[data-theme="dark"] .badge-blue   { color: #60a5fa; border-color: rgba(96,165,250,0.25);  background: rgba(96,165,250,0.10);  }
[data-theme="dark"] .badge-green  { color: #34d399; border-color: rgba(52,211,153,0.25);  background: rgba(52,211,153,0.10);  }
[data-theme="dark"] .badge-yellow { color: #fbbf24; border-color: rgba(251,191,36,0.25);  background: rgba(251,191,36,0.10);  }
[data-theme="dark"] .badge-red    { color: #f87171; border-color: rgba(248,113,113,0.25); background: rgba(248,113,113,0.10); }
[data-theme="dark"] .badge-cyan   { color: var(--muted); border-color: transparent;           background: transparent; padding: 0; }
[data-theme="dark"] .badge-purple { color: #a78bfa; border-color: rgba(167,139,250,0.25); background: rgba(167,139,250,0.10); }

/* ─── Button ─────────────────────────────────────── */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  font-size: var(--text-md); font-weight: 600; padding: 8px 16px;
  border-radius: var(--radius-sm); border: 1px solid transparent;
  cursor: pointer;
  white-space: nowrap; letter-spacing: 0.01em;
  position: relative; overflow: hidden;
  transition: background var(--dur) var(--ease),
              border-color var(--dur) var(--ease),
              color var(--dur) var(--ease),
              transform var(--dur) var(--ease),
              box-shadow var(--dur) var(--ease);
}
.btn::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, transparent 50%);
  pointer-events: none;
}
.btn:disabled { opacity: 0.38; cursor: not-allowed; }

.btn-primary {
  background: var(--accent); color: white; border-color: var(--accent);
  box-shadow: 0 2px 14px var(--btn-shadow);
}
.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 4px 24px var(--btn-shadow-hover);
  transform: translateY(-1px);
}
.btn-primary:active:not(:disabled) { transform: translateY(0); box-shadow: none; }

.btn-ghost {
  background: var(--card-alt); color: var(--text-dim); border-color: var(--border);
}
.btn-ghost:hover:not(:disabled) {
  background: var(--card-hi); color: var(--text); border-color: var(--border-hi);
  transform: translateY(-1px);
}
.btn-ghost:active:not(:disabled) { transform: translateY(0); }

.btn-danger {
  background: var(--danger-dim); color: var(--danger); border-color: transparent;
}
.btn-danger:hover:not(:disabled) { background: rgba(239,68,68,0.18); transform: translateY(-1px); }

[data-theme="dark"] .btn-danger {
  background: transparent;
}
[data-theme="dark"] .btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.10);
}

.btn-success {
  background: var(--success-dim); color: var(--success); border-color: var(--success-border);
}
.btn-success:hover:not(:disabled) { background: rgba(16,185,129,0.18); transform: translateY(-1px); }

.btn-sm { font-size: var(--text-sm); padding: 5px 11px; gap: 5px; }
.btn-lg { font-size: var(--text-lg); padding: 11px 24px; border-radius: var(--radius); }
.btn-icon { padding: 7px; }

/* ─── Table ──────────────────────────────────────── */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--text-md); }
th {
  text-align: left; font-size: var(--text-xs); font-weight: 600; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--muted); padding: 0 14px 10px;
  border-bottom: 1px solid var(--border); white-space: nowrap;
}
td {
  padding: 11px 14px; border-bottom: 1px solid var(--border);
  color: var(--text); max-width: 280px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
tbody tr { transition: background var(--dur) var(--ease); cursor: pointer; }
tbody tr:hover { background: var(--accent-dim2); }
.doc-icon { margin-right: 6px; font-size: 14px; }
.doc-filename-link {
  cursor: pointer;
  color: var(--accent);
  transition: color var(--dur) var(--ease);
}
.doc-filename-link:hover {
  text-decoration: underline;
  color: var(--accent-hover);
}
[data-theme="dark"] .doc-filename-link {
  color: #ffffff;
}
[data-theme="dark"] .doc-filename-link:hover {
  color: var(--accent);
}

/* ── Table row action (arrow indicator) ── */
.row-arrow {
  color: var(--muted); opacity: 0;
  transition: opacity var(--dur) var(--ease), color var(--dur) var(--ease);
}
tbody tr:hover .row-arrow { opacity: 1; color: var(--accent); }

/* ─── Upload Zone ───────────────────────────────── */
.upload-zone {
  position: relative;
  background: var(--surface-elevated);
  border: 1.5px dashed var(--border-hi);
  border-radius: var(--radius-lg);
  padding: 64px 32px;
  text-align: center; cursor: pointer;
  overflow: hidden;
  transition: all var(--dur-md) var(--ease);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.upload-zone::before {
  content: '';
  position: absolute; inset: 0;
  background: radial-gradient(circle at 50% 50%, var(--upload-radial-glow) 0%, transparent 60%);
  pointer-events: none;
  opacity: 0.8;
  transition: opacity var(--dur-md) var(--ease);
}
.upload-zone:hover, .upload-zone.dragover {
  border-color: var(--accent);
  background: var(--surface-elevated);
  box-shadow: var(--glow-sm), var(--shadow-card);
  transform: translateY(-2px);
}
.upload-zone:hover::before, .upload-zone.dragover::before {
  background: radial-gradient(circle at 50% 50%, var(--upload-radial-glow-hover) 0%, transparent 60%);
  opacity: 1;
}
.upload-icon-circle {
  width: 80px; height: 80px;
  border-radius: 50%;
  background: var(--accent-dim); border: 1.5px solid var(--upload-icon-border);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 24px;
  color: var(--accent);
  transition: all var(--dur-md) var(--ease-spring);
  position: relative;
  box-shadow: var(--upload-icon-inner-shadow);
}
.upload-icon-circle::after {
  content: '';
  position: absolute; inset: -6px;
  border-radius: 50%;
  border: 1.5px dashed var(--upload-icon-dashed-border);
  animation: spin 20s linear infinite;
  transition: all var(--dur-md) var(--ease);
}
.upload-zone:hover .upload-icon-circle, .upload-zone.dragover .upload-icon-circle {
  transform: scale(1.06);
  background: var(--accent);
  color: white;
  border-color: var(--accent);
  box-shadow: var(--glow);
}
.upload-zone:hover .upload-icon-circle::after, .upload-zone.dragover .upload-icon-circle::after {
  inset: -8px;
  border-color: var(--upload-icon-border-hover);
  animation: spin 10s linear infinite;
}
.upload-main-heading {
  font-size: var(--text-2xl); font-weight: 700; margin-bottom: 8px; letter-spacing: -0.02em; color: var(--text);
}
.upload-accent-text {
  color: var(--accent); text-decoration: underline; text-underline-offset: 4px; transition: color var(--dur) var(--ease);
}
.upload-sub-description {
  font-size: var(--text-md); color: var(--muted); max-width: 480px; line-height: 1.6; margin-bottom: 24px;
}
.upload-batch-strip {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  padding: 8px 16px; background: var(--card-alt); border: 1px solid var(--border);
  border-radius: 99px; margin-top: 24px; font-size: var(--text-sm); color: var(--text-dim);
  font-weight: 600; box-shadow: var(--shadow-sm); transition: all var(--dur) var(--ease);
}
.upload-batch-strip:hover {
  background: var(--card-hi); border-color: var(--border-hi);
}
.upload-types-grid {
  display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;
}
.upload-type-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 99px; background: var(--card-alt); border: 1px solid var(--border);
  font-size: var(--text-sm); font-weight: 600; color: var(--text-dim); transition: all var(--dur) var(--ease);
}
.upload-type-badge:hover {
  transform: translateY(-1px); border-color: var(--border-hi); background: var(--card-hi); box-shadow: var(--shadow-sm);
}

/* ─── Pipeline Steps ────────────────────────────── */
.pipeline { display: flex; align-items: center; gap: 0; padding: 16px 0; overflow-x: auto; }
.pipeline-step {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  flex: 1; min-width: 80px; position: relative;
}
.pipeline-step:not(:last-child)::after {
  content: ''; position: absolute; top: 19px; left: calc(50% + 20px);
  width: calc(100% - 40px); height: 1.5px;
  background: var(--border);
}
.pipeline-step.done::after { background: var(--success); }
.pipeline-step.running::after {
  background: linear-gradient(90deg, var(--accent), var(--border));
  animation: shimmer-line 2s linear infinite;
}
.step-circle {
  width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; border: 1.5px solid var(--border);
  background: var(--surface); position: relative; z-index: 1;
  transition: all var(--dur-md) var(--ease);
}
.pipeline-step.done .step-circle {
  border-color: var(--success); background: var(--success-dim);
  color: var(--success); box-shadow: 0 0 12px rgba(16,185,129,0.30);
}
.pipeline-step.running .step-circle {
  border-color: var(--accent); background: var(--accent-dim);
  color: var(--accent); animation: pulse 1.5s ease-in-out infinite;
  box-shadow: var(--pipeline-step-glow);
}
.pipeline-step.error .step-circle {
  border-color: var(--danger); background: var(--danger-dim); color: var(--danger);
}
.step-label { font-size: var(--text-xs); color: var(--muted); font-weight: 500; text-align: center; }
.pipeline-step.done .step-label { color: var(--success); }
.pipeline-step.running .step-label { color: var(--accent); }

/* ─── Progress Bar ──────────────────────────────── */
.progress-bar {
  height: 5px; border-radius: 99px;
  background: var(--border); overflow: hidden;
}
.progress-fill {
  height: 100%; border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  transition: width 0.6s var(--ease);
  position: relative;
}
.progress-fill::after {
  content: '';
  position: absolute; right: 0; top: 0; bottom: 0;
  width: 24px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.30));
}
.progress-fill.green { background: linear-gradient(90deg, var(--success), #34d399); }
.progress-fill.warn  { background: linear-gradient(90deg, var(--warn), #fbbf24); }

/* ─── Confidence Bar ────────────────────────────── */
.conf-bar-row { display: flex; flex-direction: column; gap: 4px; margin-bottom: 14px; }
.conf-bar-label { display: flex; justify-content: space-between; font-size: var(--text-base); }

/* ─── Log Container ─────────────────────────────── */
.log-container {
  background: var(--surface-sunken); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: var(--text-sm); overflow-y: auto; display: flex; flex-direction: column; gap: 3px;
}
.log-line { display: flex; align-items: flex-start; gap: 8px; line-height: 1.6; }
.log-ts    { color: var(--muted); flex-shrink: 0; }
.log-agent { color: var(--accent3); font-weight: 600; flex-shrink: 0; }
.log-text  { color: var(--text-dim); }

/* ─── Modal ─────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 999; backdrop-filter: blur(8px);
  animation: fade-in 150ms var(--ease);
  padding: 16px;
}
.modal {
  background: var(--card); border: 1px solid var(--border-hi);
  border-radius: var(--radius-lg); padding: 28px;
  min-width: 420px; max-width: 560px; width: 100%;
  box-shadow: var(--shadow);
  animation: slide-in 200ms var(--ease);
  position: relative; overflow: hidden;
}
.modal::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--grad-brand);
}
.modal-title { font-size: var(--text-xl); font-weight: 700; margin-bottom: 6px; letter-spacing: -0.2px; }
.modal-sub { font-size: var(--text-base); color: var(--muted); margin-bottom: 20px; }
.modal-wide { max-width: 720px; }
.modal-footer { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }

/* ─── Toast ─────────────────────────────────────── */
.toast-container {
  position: fixed; bottom: 24px; right: 24px;
  display: flex; flex-direction: column; gap: 10px;
  z-index: 9999;
}
.toast {
  display: flex; align-items: center; gap: 12px;
  background: var(--surface-elevated); border: 1px solid var(--border-hi);
  border-radius: var(--radius); padding: 12px 16px;
  min-width: 280px; max-width: 380px;
  box-shadow: var(--shadow); animation: toast-in 300ms var(--ease-spring);
  font-size: var(--text-md); backdrop-filter: blur(16px);
}
.toast.success { border-left: 3px solid var(--success); }
.toast.error   { border-left: 3px solid var(--danger); }
.toast.info    { border-left: 3px solid var(--accent); }
.toast.warn    { border-left: 3px solid var(--warn); }
.toast-icon { flex-shrink: 0; }
.toast-msg { flex: 1; }
.toast-close { background: none; border: none; color: var(--muted); font-size: 16px; padding: 0 2px; transition: color var(--dur) var(--ease); }
.toast-close:hover { color: var(--text); }

/* ─── Field Panel (Extraction) ──────────────────── */
.field-group { margin-bottom: 18px; }
.field-group-title {
  font-size: var(--text-xs); font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 8px; padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.field-row {
  display: grid; grid-template-columns: 1fr 1.4fr auto;
  align-items: center; gap: 8px; padding: 8px 0;
  border-bottom: 1px solid var(--border);
  transition: background var(--dur) var(--ease);
  border-radius: 4px;
}
.field-row:hover { background: var(--accent-dim2); padding-inline: 4px; }
.field-key { font-size: var(--text-base); color: var(--text-dim); }
.field-val { font-size: var(--text-base); font-weight: 500; color: var(--text); }
.field-conf { display: flex; align-items: center; gap: 5px; font-size: var(--text-sm); }
.conf-dot { width: 7px; height: 7px; border-radius: 50%; }
.conf-high { background: var(--success); box-shadow: 0 0 6px rgba(16,185,129,0.5); }
.conf-med  { background: var(--warn);    box-shadow: 0 0 6px rgba(245,158,11,0.4); }
.conf-low  { background: var(--danger);  box-shadow: 0 0 6px rgba(239,68,68,0.4); }

/* ─── Tabs ───────────────────────────────────────── */
.tabs {
  display: flex; gap: 2px; margin-bottom: 18px;
  border-bottom: 1px solid var(--border); padding-bottom: 0;
  overflow-x: auto;
  flex-wrap: nowrap;
  max-width: 100%;
  scrollbar-width: none;
  -ms-overflow-style: none;
  -webkit-overflow-scrolling: touch;
}
.tabs::-webkit-scrollbar {
  display: none;
}
.tab {
  padding: 8px 16px; font-size: var(--text-base); font-weight: 500;
  color: var(--muted); border-bottom: 2px solid transparent;
  cursor: pointer; transition: all var(--dur) var(--ease);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  flex-shrink: 0;
  white-space: nowrap;
}
.tab:hover { color: var(--text-dim); background: var(--accent-dim2); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); background: var(--accent-dim); }

/* ─── Empty State ───────────────────────────────── */
.empty-state {
  text-align: center; padding: 56px 24px; color: var(--muted);
}
.empty-icon { font-size: 36px; margin-bottom: 16px; opacity: 0.50; }
.empty-title { font-size: var(--text-lg); font-weight: 600; color: var(--text-dim); margin-bottom: 6px; letter-spacing: -0.1px; }
.empty-sub { font-size: var(--text-base); line-height: 1.6; }

/* ─── Empty state — Illustrated icon variant ── */
.empty-icon-wrap {
  width: 72px; height: 72px;
  background: var(--accent-dim); border: 1px solid rgba(251,107,45,0.15);
  border-radius: var(--radius-lg);
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 20px;
  color: var(--accent);
}

/* ─── Styled Select / Input ─────────────────────── */
.styled-select, .styled-input {
  width: 100%; background: var(--card-alt);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  color: var(--text); font-size: var(--text-md); font-family: inherit;
  padding: 9px 12px; outline: none;
  transition: border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
}
.styled-select:focus, .styled-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-dim);
}
.styled-select option { background: var(--card-alt); }

/* ─── Agent Card ────────────────────────────────── */
.agents-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }
.agent-card {
  padding: 20px;
  position: relative; overflow: hidden;
  transition: all var(--dur-md) var(--ease);
}
.agent-card:hover {
  border-color: rgba(251, 107, 45, 0.40);
  transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08), var(--glow-sm);
}
/* Mistral agent — accent blue tint */
.agent-card.mistral-live {
  background: linear-gradient(145deg, var(--accent-dim2) 0%, var(--card) 60%);
  border-color: rgba(251,107,45,0.2);
}
/* Offline agent — warn amber tint */
.agent-card.mistral-offline {
  background: linear-gradient(145deg, var(--warn-dim) 0%, var(--card) 60%);
  border-color: var(--warn-border);
}
/* Workflow agent — neutral */
.agent-card.workflow-activity {
  background: var(--card);
}

.agent-avatar {
  width: 44px; height: 44px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; margin-bottom: 14px;
  border: 1px solid var(--border);
}
.agent-name { font-size: var(--text-md); font-weight: 700; margin-bottom: 4px; letter-spacing: -0.1px; }
.agent-role { font-size: var(--text-sm); color: var(--muted); margin-bottom: 12px; }
.agent-tools { display: flex; flex-wrap: wrap; gap: 5px; }
.agent-tool {
  font-size: var(--text-xs); color: var(--text-dim);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 99px; padding: 2px 8px;
  transition: all var(--dur) var(--ease);
}
.agent-tool:hover { border-color: var(--accent); color: var(--accent); }

/* ─── Donut Chart ───────────────────────────────── */
.donut-wrap { display: flex; align-items: center; gap: 24px; padding: 8px 0; }
.donut-legend { display: flex; flex-direction: column; gap: 10px; }
.legend-item { display: flex; align-items: center; gap: 8px; font-size: var(--text-sm); color: var(--text-dim); }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

/* ─── Doc Card (Upload Queue Item) ───────────────── */
.doc-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); margin-bottom: 8px;
  background: var(--card);
  transition: all var(--dur) var(--ease);
}
.doc-card:hover { border-color: var(--border-hi); background: var(--card-alt); }
.doc-thumb {
  width: 40px; height: 40px; border-radius: var(--radius-sm);
  background: var(--accent-dim); border: 1px solid rgba(251,107,45,0.15);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.doc-info { flex: 1; min-width: 0; }
.doc-name { font-size: var(--text-md); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-meta { font-size: var(--text-sm); color: var(--muted); margin-top: 2px; }

/* ─── Extraction Split ──────────────────────────── */
.extraction-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.doc-preview {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px;
}
.fields-panel {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 18px;
  overflow-y: auto; max-height: min(680px, 70vh);
}

/* ─── Section header with gradient line ─────────── */
.section-header {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 16px;
}
.section-header-line {
  flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}

/* ─── Activity Feed ─────────────────────────────── */
.activity-feed { display: flex; flex-direction: column; gap: 2px; }
.activity-item {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 12px; border-radius: var(--radius-sm);
  transition: background var(--dur) var(--ease);
}
.activity-item:hover { background: var(--accent-dim2); }
.activity-dot {
  width: 8px; height: 8px; border-radius: 50%;
  margin-top: 5px; flex-shrink: 0;
}
.activity-content { flex: 1; min-width: 0; }
.activity-title { font-size: var(--text-md); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.activity-meta { font-size: var(--text-sm); color: var(--muted); margin-top: 2px; }

/* ─── Info Row ───────────────────────────────────── */
.info-row {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 0; border-bottom: 1px solid var(--border);
}
.info-row:last-child { border-bottom: none; }
.info-row-icon {
  width: 32px; height: 32px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  background: var(--accent-dim); color: var(--accent);
  flex-shrink: 0; font-size: 14px;
}
.info-row-label { font-size: var(--text-md); font-weight: 600; color: var(--accent); min-width: 90px; flex-shrink: 0; }
.info-row-desc { font-size: var(--text-md); color: var(--text-dim); line-height: 1.6; }

/* ─── Responsive ─────────────────────────────────── */
@media (max-width: 900px) {
  .extraction-grid { grid-template-columns: 1fr; }
  .agents-grid { grid-template-columns: repeat(2, 1fr); }
  .fields-panel { max-height: 50vh; }
}
@media (max-width: 600px) {
  .agents-grid { grid-template-columns: 1fr; }
  .modal { min-width: unset; }
}

/* ─── Batch Mode Chip ────────────────────────────── */
.batch-mode-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--accent-dim);
  border: 1px solid rgba(251,107,45,0.25);
  color: var(--accent);
  border-radius: 99px;
  padding: 4px 11px;
  font-size: var(--text-sm);
  font-weight: 600;
  vertical-align: middle;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

/* ─── Batch Progress Panel ───────────────────────── */
.batch-progress-panel {
  background: rgba(251,107,45,0.06);
  border: 1px solid rgba(251,107,45,0.18);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
}
.batch-progress-panel::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--grad-brand);
  animation: shimmer 2s linear infinite;
}

/* ─── Batch Stats Row ────────────────────────────── */
.batch-stats-row {
  display: flex;
  align-items: center;
  gap: 0;
  flex-wrap: wrap;
  gap: 16px;
}
.batch-stat-cell {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 6px 0;
}
.batch-stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* ─── Spin keyframe (for in-batch spinner) ───────── */
@keyframes spin {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* ─── Shimmer animation for progress panel header ── */
@keyframes shimmer {
  0%   { transform: translateX(-100%); opacity: 1; }
  50%  { opacity: 0.7; }
  100% { transform: translateX(100%); opacity: 1; }
}

/* ─── Threshold Slider (Settings page) ──────────── */
input[type='range'] {
  -webkit-appearance: none; appearance: none;
  width: 100%; height: 6px; border-radius: 4px;
  background: transparent; outline: none; cursor: pointer;
}
input[type='range']::-webkit-slider-thumb {
  -webkit-appearance: none; appearance: none;
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--accent); border: 2px solid var(--card);
  box-shadow: 0 0 0 3px var(--accent-dim), 0 2px 6px rgba(0,0,0,0.18);
  cursor: grab; transition: box-shadow 0.15s ease, transform 0.15s ease;
  margin-top: -6px;
}
input[type='range']::-webkit-slider-thumb:active {
  cursor: grabbing; transform: scale(1.15);
  box-shadow: 0 0 0 5px var(--accent-dim), 0 2px 12px rgba(251,107,45,0.3);
}
input[type='range']::-moz-range-thumb {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--accent); border: 2px solid var(--card);
  box-shadow: 0 0 0 3px var(--accent-dim); cursor: grab;
}
input[type='range']::-webkit-slider-runnable-track {
  height: 6px; border-radius: 4px;
}

/* ─── Signature Verification ────────────────────── */

/* Inline upload dropzone (compact, for inside KYC cards) */
.verify-dropzone {
  padding: 10px 14px;
  border: 1.5px dashed var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-sunken);
  text-align: center;
  cursor: pointer;
  transition: all var(--dur) var(--ease);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.verify-dropzone:hover, .verify-dropzone.dragover {
  border-color: #a855f7;
  background: rgba(168,85,247,0.04);
  box-shadow: 0 0 12px rgba(168,85,247,0.08);
}
.verify-dropzone .verify-drop-icon {
  width: 32px; height: 32px; border-radius: 50%;
  background: rgba(168,85,247,0.1);
  display: flex; align-items: center; justify-content: center;
  color: #a855f7;
  transition: all var(--dur) var(--ease);
}
.verify-dropzone:hover .verify-drop-icon {
  background: #a855f7;
  color: white;
  transform: scale(1.05);
}

/* Verdict Panel — glassmorphic card */
.verdict-panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-top: 12px;
  transition: all var(--dur-md) var(--ease);
}
.verdict-panel:hover {
  border-color: var(--border-hi);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
}

/* Verdict Header Banner */
.verdict-header {
  padding: 16px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.verdict-header.genuine {
  background: linear-gradient(135deg, rgba(16,185,129,0.08), rgba(16,185,129,0.02));
  border-bottom: 1px solid rgba(16,185,129,0.15);
}
.verdict-header.uncertain {
  background: linear-gradient(135deg, rgba(245,158,11,0.08), rgba(245,158,11,0.02));
  border-bottom: 1px solid rgba(245,158,11,0.15);
}
.verdict-header.forged {
  background: linear-gradient(135deg, rgba(239,68,68,0.08), rgba(239,68,68,0.02));
  border-bottom: 1px solid rgba(239,68,68,0.15);
}

/* Verdict Badge */
.verdict-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 99px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.verdict-badge.genuine {
  background: rgba(16,185,129,0.12);
  color: #059669;
  border: 1px solid rgba(16,185,129,0.25);
}
.verdict-badge.uncertain {
  background: rgba(245,158,11,0.12);
  color: #d97706;
  border: 1px solid rgba(245,158,11,0.25);
}
.verdict-badge.forged {
  background: rgba(239,68,68,0.12);
  color: #dc2626;
  border: 1px solid rgba(239,68,68,0.25);
}

/* Score Bar */
.score-bar-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 18px;
}
.score-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.score-bar-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  width: 100px;
  flex-shrink: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.score-bar-track {
  flex: 1;
  height: 8px;
  border-radius: 99px;
  background: var(--surface-sunken);
  overflow: hidden;
  position: relative;
}
.score-bar-fill {
  height: 100%;
  border-radius: 99px;
  transition: width 1s var(--ease);
  position: relative;
}
.score-bar-fill::after {
  content: '';
  position: absolute; right: 0; top: 0; bottom: 0;
  width: 16px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25));
}
.score-bar-fill.high {
  background: linear-gradient(90deg, #059669, #34d399);
}
.score-bar-fill.medium {
  background: linear-gradient(90deg, #d97706, #fbbf24);
}
.score-bar-fill.low {
  background: linear-gradient(90deg, #dc2626, #f87171);
}
.score-bar-value {
  font-size: 12px;
  font-weight: 700;
  width: 44px;
  text-align: right;
  flex-shrink: 0;
}

/* Analysis Accordion Row */
.analysis-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.analysis-row:last-child { border-bottom: none; }
.analysis-dimension {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
  width: 120px;
  flex-shrink: 0;
}
.analysis-score {
  font-size: 12px;
  font-weight: 700;
  width: 36px;
  text-align: center;
  flex-shrink: 0;
  border-radius: 4px;
  padding: 2px 4px;
}
.analysis-score.high { background: rgba(16,185,129,0.1); color: #059669; }
.analysis-score.medium { background: rgba(245,158,11,0.1); color: #d97706; }
.analysis-score.low { background: rgba(239,68,68,0.1); color: #dc2626; }
.analysis-observation {
  font-size: 11px;
  color: var(--muted);
  flex: 1;
  line-height: 1.4;
}

/* Authenticity Flags */
.flag-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
}
.flag-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.flag-indicator.safe {
  background: var(--success);
  box-shadow: 0 0 4px rgba(16,185,129,0.4);
}
.flag-indicator.danger {
  background: var(--danger);
  box-shadow: 0 0 4px rgba(239,68,68,0.4);
}
.flag-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
}

/* Recommendation Banner */
.recommendation-banner {
  padding: 10px 18px;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  letter-spacing: 0.02em;
}
.recommendation-banner.accept {
  background: rgba(16,185,129,0.06);
  color: #059669;
  border-top: 1px solid rgba(16,185,129,0.15);
}
.recommendation-banner.review {
  background: rgba(245,158,11,0.06);
  color: #d97706;
  border-top: 1px solid rgba(245,158,11,0.15);
}
.recommendation-banner.reject {
  background: rgba(239,68,68,0.06);
  color: #dc2626;
  border-top: 1px solid rgba(239,68,68,0.15);
}

/* Verification Loading Overlay */
.verification-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 28px 16px;
  text-align: center;
}
.verification-loading .verify-spinner {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 3px solid rgba(168,85,247,0.15);
  border-top-color: #a855f7;
  animation: spin 0.8s linear infinite;
}
.verification-loading .verify-text {
  font-size: 12px;
  font-weight: 600;
  color: #a855f7;
  letter-spacing: 0.02em;
}
.verification-loading .verify-subtext {
  font-size: 11px;
  color: var(--muted);
  max-width: 220px;
  line-height: 1.5;
}

/* Verifying border glow */
.kyc-card-verifying {
  border-color: rgba(168,85,247,0.4) !important;
  box-shadow: 0 0 20px rgba(168,85,247,0.12) !important;
  animation: pulse-purple 2s ease-in-out infinite;
}
@keyframes pulse-purple {
  0%, 100% { box-shadow: 0 0 20px rgba(168,85,247,0.12); }
  50% { box-shadow: 0 0 30px rgba(168,85,247,0.2); }
}

/* Reference image preview (small thumbnail) */
.ref-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-top: 6px;
}
.ref-preview img {
  width: 32px;
  height: 32px;
  object-fit: contain;
  border-radius: 3px;
  border: 1px solid var(--border);
}
.ref-preview .ref-name {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-dim);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ─── Face Verification Panel ─────────────────────── */

/* Signal badges (supports_same / supports_different / inconclusive) */
.face-signal-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 99px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  white-space: nowrap;
}
.face-signal-same {
  background: rgba(16,185,129,0.1);
  color: #059669;
  border: 1px solid rgba(16,185,129,0.2);
}
.face-signal-diff {
  background: rgba(239,68,68,0.1);
  color: #dc2626;
  border: 1px solid rgba(239,68,68,0.2);
}
.face-signal-inc {
  background: rgba(245,158,11,0.1);
  color: #d97706;
  border: 1px solid rgba(245,158,11,0.2);
}

/* Feature analysis blocks */
.face-feature-block {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.face-feature-block:last-child {
  border-bottom: none;
}
.face-feature-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.face-feature-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim);
}

/* Confidence badges (low / medium / high) */
.face-conf-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 99px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.face-conf-badge.high {
  background: rgba(16,185,129,0.1);
  color: #059669;
  border: 1px solid rgba(16,185,129,0.2);
}
.face-conf-badge.medium {
  background: rgba(245,158,11,0.1);
  color: #d97706;
  border: 1px solid rgba(245,158,11,0.2);
}
.face-conf-badge.low {
  background: rgba(239,68,68,0.1);
  color: #dc2626;
  border: 1px solid rgba(239,68,68,0.2);
}

/* Points lists (same / different) */
.face-points-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: flex-start;
  margin-bottom: 6px;
}
.face-points-label {
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  width: 100%;
  margin-bottom: 2px;
}
.face-points-list.same .face-points-label { color: #059669; }
.face-points-list.diff .face-points-label { color: #dc2626; }

.face-point {
  font-size: 10px;
  color: var(--text-dim);
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  line-height: 1.5;
}

/* Variability chips */
.face-variability-chip {
  font-size: 9px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: capitalize;
  white-space: nowrap;
}
.face-variability-chip.ok {
  background: rgba(16,185,129,0.08);
  color: #059669;
  border: 1px solid rgba(16,185,129,0.15);
}
.face-variability-chip.mild {
  background: rgba(245,158,11,0.08);
  color: #d97706;
  border: 1px solid rgba(245,158,11,0.15);
}
.face-variability-chip.sig {
  background: rgba(239,68,68,0.08);
  color: #dc2626;
  border: 1px solid rgba(239,68,68,0.15);
}

/* Age gap badge */
.face-age-gap-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(59,130,246,0.08);
  color: #3b82f6;
  border: 1px solid rgba(59,130,246,0.15);
  text-transform: capitalize;
}


/* ═══════════════════════════════════════════════════
   CLAIM PROCESS — Dashboard & Workflow Pages
   ═══════════════════════════════════════════════════ */

/* ─── Page Layout ─── */
.claim-page { max-width: 1400px; margin: 0 auto; }

.claim-page-header {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
}
.claim-page-title {
  font-size: var(--text-2xl); font-weight: 700; letter-spacing: -0.03em; color: var(--text);
}
.claim-page-sub {
  font-size: var(--text-md); color: var(--muted); margin-top: 4px; line-height: 1.5;
}

/* ─── Claim Stats Grid ─── */
.claim-stats-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
}
@media (max-width: 800px) { .claim-stats-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .claim-stats-grid { grid-template-columns: 1fr; } }

.claim-stat {
  display: flex; align-items: center; gap: 14px;
  padding: 16px 18px; position: relative; overflow: hidden;
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); cursor: default;
  box-shadow: var(--shadow-card);
  transition: all var(--dur-md) var(--ease);
}
.claim-stat::before {
  content: ''; position: absolute; top: 0; right: 0;
  width: 90px; height: 90px; border-radius: 50%;
  background: var(--accent-dim2); transform: translate(30px, -30px);
  transition: all var(--dur-md) var(--ease);
}
.claim-stat::after {
  content: ''; position: absolute; top: 0; left: 0; right: 0;
  height: 2px; background: var(--grad-brand); opacity: 0;
  transition: opacity var(--dur-md) var(--ease);
}
.claim-stat:hover {
  transform: translateY(-3px);
  border-color: rgba(251, 107, 45, 0.35);
  box-shadow: var(--glow-sm), var(--shadow-card);
}
.claim-stat:hover::before { transform: translate(20px, -20px) scale(1.3); }
.claim-stat:hover::after { opacity: 1; }

.claim-stat-icon {
  width: 42px; height: 42px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  position: relative; z-index: 1; flex-shrink: 0;
  border: 1px solid transparent;
}
.claim-stat-icon.accent  { background: var(--accent-dim); color: var(--accent); border-color: rgba(251,107,45,0.1); }
.claim-stat-icon.info    { background: var(--info-dim); color: var(--info); border-color: rgba(59,130,246,0.1); }
.claim-stat-icon.warn    { background: var(--warn-dim); color: var(--warn); border-color: rgba(245,158,11,0.1); }
.claim-stat-icon.success { background: var(--success-dim); color: var(--success); border-color: rgba(16,185,129,0.1); }

.claim-stat-value {
  font-size: var(--text-2xl); font-weight: 800; letter-spacing: -0.04em;
  color: var(--text); position: relative; z-index: 1;
  font-variant-numeric: tabular-nums;
}
.claim-stat-label {
  font-size: var(--text-sm); color: var(--text-dim); letter-spacing: 0.02em;
  position: relative; z-index: 1;
}

/* ─── Claim Card ─── */
.claim-card {
  background: var(--glass); border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-radius: var(--radius); overflow: hidden;
  box-shadow: var(--shadow-card); position: relative;
  transition: all var(--dur-md) var(--ease);
  cursor: default;
}
.claim-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0;
  height: 2px; background: var(--grad-brand); opacity: 0;
  transition: opacity var(--dur-md) var(--ease);
}
.claim-card:hover { transform: translateY(-3px); }
.claim-card:hover::before { opacity: 1; }

.claim-card.border-warn    { border-color: rgba(245,158,11,0.3); }
.claim-card.border-success { border-color: rgba(16,185,129,0.3); }
.claim-card.border-info    { border-color: rgba(59,130,246,0.3); }

.claim-card-main {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 20px; flex-wrap: wrap;
}
.claim-card-left {
  display: flex; align-items: flex-start; gap: 14px; flex: 1; min-width: 0;
}
.claim-card-avatar {
  width: 44px; height: 44px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: var(--grad-brand); color: white;
  box-shadow: 0 4px 16px rgba(251,107,45,0.3);
}
.claim-card-info { min-width: 0; flex: 1; }
.claim-card-name-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.claim-card-name { font-size: var(--text-lg); font-weight: 600; color: var(--text); }
.claim-card-id {
  font-size: var(--text-xs); font-weight: 500; font-family: monospace;
  background: var(--card-alt); border: 1px solid var(--border); border-radius: 6px;
  padding: 2px 7px; color: var(--muted);
}
.claim-card-meta {
  font-size: var(--text-sm); color: var(--muted); margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.claim-card-desc {
  font-size: var(--text-sm); color: var(--muted); margin-top: 3px;
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden;
}
.claim-card-right {
  display: flex; align-items: center; gap: 14px; flex-shrink: 0;
}
.claim-card-amount {
  text-align: right;
}
.claim-card-amount-value {
  font-size: var(--text-xl); font-weight: 600; letter-spacing: -0.02em;
  color: var(--text); font-variant-numeric: tabular-nums;
}
.claim-card-status {
  display: flex; align-items: center; justify-content: flex-end;
  gap: 5px; font-size: var(--text-sm); margin-top: 3px;
}
.claim-card-status.pending    { color: var(--muted); }
.claim-card-status.processing { color: var(--info); }
.claim-card-status.missing    { color: var(--warn); }
.claim-card-status.approved   { color: var(--success); }
.claim-card-status.rejected   { color: var(--danger); }

.claim-card-actions { display: flex; align-items: center; gap: 8px; }

/* Process CTA button with pulse */
.claim-btn-process {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 16px; border-radius: var(--radius-sm);
  background: var(--grad-brand); color: white; border: none;
  font-size: var(--text-md); font-weight: 600; cursor: pointer;
  white-space: nowrap; min-width: 100px; justify-content: center;
  transition: opacity var(--dur) var(--ease), transform var(--dur) var(--ease);
  animation: pulse-ring 2s ease-out infinite;
}
.claim-btn-process:hover { opacity: 0.9; transform: translateY(-1px); }

@keyframes pulse-ring {
  0%   { box-shadow: 0 0 0 0 rgba(251, 107, 45, 0.5); }
  70%  { box-shadow: 0 0 0 12px rgba(251, 107, 45, 0); }
  100% { box-shadow: 0 0 0 0 rgba(251, 107, 45, 0); }
}

/* ─── Priority Badge ─── */
.priority-badge {
  display: inline-flex; align-items: center; gap: 5px;
  border-radius: 99px; border: 1px solid; padding: 2px 9px;
  font-size: var(--text-xs); font-weight: 600;
}
.priority-badge .priority-dot { width: 6px; height: 6px; border-radius: 50%; }

.priority-badge.low     { color: var(--muted); border-color: var(--border); background: var(--card-alt); }
.priority-badge.low .priority-dot { background: var(--muted); }
.priority-badge.medium  { color: var(--info); border-color: rgba(59,130,246,0.3); background: var(--info-dim); }
.priority-badge.medium .priority-dot { background: var(--info); }
.priority-badge.high    { color: var(--warn); border-color: var(--warn-border); background: var(--warn-dim); }
.priority-badge.high .priority-dot { background: var(--warn); }
.priority-badge.urgent  { color: var(--danger); border-color: var(--danger-border); background: var(--danger-dim); }
.priority-badge.urgent .priority-dot { background: var(--danger); }

/* ─── Claim Expanded Documents ─── */
.claim-card-expand {
  border-top: 1px solid var(--border); background: var(--card-alt);
  padding: 20px; overflow: hidden;
  animation: slide-in 250ms var(--ease) both;
}
.claim-docs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 700px) { .claim-docs-grid { grid-template-columns: 1fr; } }

.claim-doc-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: var(--radius-sm);
  font-size: var(--text-md);
}
.claim-doc-item.present {
  border: 1px solid rgba(16,185,129,0.15); background: rgba(16,185,129,0.05);
}
.claim-doc-item.present .doc-status-icon { color: var(--success); }
.claim-doc-item.missing {
  border: 1px dashed rgba(245,158,11,0.3); background: rgba(245,158,11,0.05);
}
.claim-doc-item.missing .doc-name { color: var(--warn); }
.claim-doc-item.missing .doc-status-icon { color: var(--warn); }

.doc-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-status-icon { flex-shrink: 0; }

.claim-docs-verified {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; border-radius: var(--radius);
  border: 1px solid rgba(16,185,129,0.2); background: rgba(16,185,129,0.05);
}
.claim-docs-verified-title { font-size: var(--text-md); font-weight: 600; color: var(--success); }
.claim-docs-verified-sub { font-size: var(--text-sm); color: var(--muted); }

/* ─── Form Styles ─── */
.claim-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 500px) { .claim-form-grid { grid-template-columns: 1fr; } }

.claim-form-label {
  display: block; font-size: var(--text-sm); font-weight: 600;
  color: var(--text-dim); margin-bottom: 5px;
}
.claim-form-label .required { color: var(--danger); }

.claim-form-note {
  padding: 8px 12px; border-radius: var(--radius-sm);
  border: 1px solid rgba(59,130,246,0.2); background: rgba(59,130,246,0.05);
  font-size: var(--text-sm); color: var(--muted); margin-top: 8px;
}
.claim-form-note strong { color: var(--info); font-weight: 600; }


/* ═══════════════════════════════════════════════════
   CLAIM WORKFLOW — Pipeline Visualization Page
   ═══════════════════════════════════════════════════ */

/* ─── Workflow Status Bar ─── */
.wf-status-bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 14px; flex-wrap: wrap;
  padding: 16px 20px; border-radius: var(--radius);
  background: var(--glass); border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px); box-shadow: var(--shadow-card);
  animation: slide-in var(--dur) var(--ease) both;
}
.wf-status-bar.done { border-color: rgba(16,185,129,0.3); }

.wf-status-left { display: flex; align-items: center; gap: 14px; }
.wf-status-info-title { font-size: var(--text-md); font-weight: 600; display: flex; align-items: center; gap: 8px; }
.wf-status-info-sub { font-size: var(--text-sm); color: var(--muted); }

.wf-status-right { display: flex; align-items: center; gap: 14px; }

.wf-progress-bar {
  width: 128px; height: 8px; border-radius: 99px;
  background: var(--card-alt); overflow: hidden;
}
.wf-progress-fill {
  height: 100%; border-radius: 99px;
  background: var(--grad-brand);
  transition: width 0.4s var(--ease);
}
.wf-progress-fill.done { background: var(--success); }

.wf-progress-pct {
  font-size: var(--text-sm); font-family: monospace; color: var(--muted);
}
.wf-progress-pct.done { color: var(--success); }

/* ─── Workflow 3-Column Layout ─── */
.wf-columns {
  display: grid; grid-template-columns: minmax(0,320px) minmax(0,1fr) minmax(0,380px);
  gap: 16px;
  animation: slide-up var(--dur-md) var(--ease) 100ms both;
}
@media (max-width: 1100px) {
  .wf-columns { grid-template-columns: 1fr; }
}

/* ─── Workflow Timeline (Left Column) ─── */
.wf-timeline {
  background: var(--glass); border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px); border-radius: var(--radius);
  display: flex; flex-direction: column; height: 640px; overflow: hidden;
}
.wf-timeline-header {
  padding: 14px 16px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.wf-timeline-title { font-size: var(--text-md); font-weight: 600; }
.wf-timeline-sub { font-size: var(--text-sm); color: var(--muted); }
.wf-timeline-tag {
  font-size: var(--text-xs); font-family: monospace; letter-spacing: 0.06em;
  padding: 2px 8px; background: var(--card-alt); border: 1px solid var(--border);
  border-radius: 6px; color: var(--muted);
}

.wf-timeline-list {
  flex: 1; overflow-y: auto; padding: 12px 8px; position: relative;
}
.wf-timeline-line {
  position: absolute; left: 22px; top: 12px; bottom: 12px;
  width: 1px;
  background: linear-gradient(to bottom, var(--border), rgba(0,0,0,0));
}

.wf-step-btn {
  width: 100%; display: flex; align-items: flex-start; gap: 12px;
  padding: 8px; border-radius: var(--radius-sm);
  background: none; border: none; text-align: left;
  cursor: pointer; position: relative; color: inherit;
  transition: background var(--dur) var(--ease);
}
.wf-step-btn:hover { background: var(--card-alt); }
.wf-step-btn.active { background: var(--accent-dim); }
.wf-step-btn.active::before {
  content: ''; position: absolute; left: 0; top: 18%; bottom: 18%;
  width: 3px; border-radius: 0 2px 2px 0;
  background: var(--grad-brand);
  box-shadow: 0 0 10px rgba(251,107,45,0.4);
  animation: nav-indicator-in 240ms var(--ease-spring) both;
}

.wf-step-circle {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border: 1.5px solid var(--border); background: var(--card);
  position: relative; z-index: 1; margin-top: 2px;
}
.wf-step-circle.waiting  { border-color: var(--border); color: var(--muted); }
.wf-step-circle.running  { border-color: rgba(59,130,246,0.4); background: var(--info-dim); color: var(--info); }
.wf-step-circle.completed { border-color: rgba(16,185,129,0.4); background: var(--success-dim); color: var(--success); }

.wf-step-content { flex: 1; min-width: 0; }
.wf-step-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.wf-step-label { font-size: var(--text-md); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wf-step-metrics { display: flex; align-items: center; gap: 8px; flex-shrink: 0; font-size: var(--text-xs); color: var(--muted); }
.wf-step-conf {
  font-family: monospace; padding: 1px 5px; border-radius: 4px;
  background: rgba(16,185,129,0.1); color: var(--success);
}
.wf-step-dur { font-family: monospace; }
.wf-step-summary { font-size: var(--text-sm); color: var(--muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Expanded thought */
.wf-step-thought {
  margin: 6px 0 4px 40px; padding: 10px;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--card-alt); font-size: var(--text-sm);
  color: var(--muted); line-height: 1.6;
  animation: slide-in 200ms var(--ease) both;
}
.wf-step-thought-label {
  font-size: var(--text-xs); font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--accent); margin-bottom: 6px;
  display: flex; align-items: center; gap: 6px;
}
.wf-step-thought-text { color: var(--text-dim); display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }

.wf-step-reasoning { color: var(--info); display: flex; align-items: center; gap: 8px; }

/* ─── Workflow Pipeline Graph (Center Column) ─── */
.wf-pipeline {
  background: var(--glass); border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px); border-radius: var(--radius);
  display: flex; flex-direction: column; height: 640px; overflow: hidden;
}
.wf-pipeline-header {
  padding: 14px 16px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.wf-pipeline-title { font-size: var(--text-md); font-weight: 600; }
.wf-pipeline-sub { font-size: var(--text-sm); color: var(--muted); }

.wf-pipeline-legend {
  display: flex; gap: 6px; flex-wrap: wrap;
}
.wf-legend-item {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 7px; border-radius: 4px; font-size: var(--text-xs);
  border: 1px solid var(--border); background: var(--card-alt);
}
.wf-legend-dot { width: 6px; height: 6px; border-radius: 50%; }
.wf-legend-dot.running   { background: var(--info); }
.wf-legend-dot.completed { background: var(--success); }
.wf-legend-dot.waiting   { background: var(--muted); }

.wf-pipeline-body {
  flex: 1; overflow-y: auto; padding: 24px;
  display: flex; flex-direction: column; align-items: center; gap: 0;
}

/* ── Graph Canvas (ReactFlow-style 2-col grid) ── */
.wf-graph-canvas {
  flex: 1; position: relative; overflow: hidden;
  display: flex; flex-direction: column;
}
.wf-graph-dots {
  position: absolute; inset: 0; pointer-events: none;
}

.wf-graph-grid-wrap {
  position: relative; flex: 1; margin: 40px 32px;
  display: flex; flex-direction: column;
}
.wf-graph-edges {
  position: absolute; inset: 0; width: 100%; height: 100%;
  pointer-events: none; z-index: 1;
}
.wf-edge-animated {
  stroke-dasharray: 6 4;
  animation: dash 0.8s linear infinite;
}
@keyframes dash {
  to { stroke-dashoffset: -20; }
}

.wf-graph-grid {
  position: relative; z-index: 2;
  display: grid; grid-template-columns: 1fr 1fr;
  flex: 1; align-items: center; justify-items: center;
  gap: 0 40px;
}

/* Graph Node (replaces old wf-pipe-node) */
.wf-graph-node {
  min-width: 168px; padding: 10px 12px;
  border-radius: var(--radius); border: 1.5px solid var(--border);
  background: var(--card-alt); backdrop-filter: blur(8px);
  cursor: pointer; transition: all var(--dur) var(--ease); position: relative;
}
.wf-graph-node:hover { border-color: var(--border-hi); z-index: 10; }
.wf-graph-node.active { box-shadow: 0 0 0 2px rgba(251,107,45,0.4); z-index: 10; }
.wf-graph-node.waiting  { border-color: var(--border); }
.wf-graph-node.running  { border-color: rgba(59,130,246,0.5); background: rgba(59,130,246,0.05); }
.wf-graph-node.completed { border-color: rgba(16,185,129,0.4); background: rgba(16,185,129,0.05); }
.wf-graph-node.warning, .wf-graph-node.failed { border-color: var(--danger-border); background: var(--danger-dim); }

.wf-graph-node-head { display: flex; align-items: center; gap: 8px; }
.wf-graph-node-icon {
  width: 20px; height: 20px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); background: var(--card);
}
.wf-graph-node-icon.running  { border-color: rgba(59,130,246,0.4); color: var(--info); }
.wf-graph-node-icon.completed { border-color: rgba(16,185,129,0.4); color: var(--success); }
.wf-graph-node-icon.warning, .wf-graph-node-icon.failed { border-color: var(--danger-border); color: var(--danger); }
.wf-graph-node-icon.waiting  { color: var(--muted); }

.wf-graph-node-label { font-size: var(--text-md); font-weight: 600; }
.wf-graph-node-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; font-size: var(--text-xs); }
.wf-graph-node-state { font-weight: 600; }
.wf-graph-node-state.running { color: var(--info); }
.wf-graph-node-state.completed { color: var(--success); }
.wf-graph-node-state.warning, .wf-graph-node-state.failed { color: var(--danger); }
.wf-graph-node-state.waiting { color: var(--muted); }
.wf-graph-node-dur { font-family: monospace; color: var(--muted); }

/* Hover tooltip (appears to the right of the node) */
.wf-graph-tooltip {
  pointer-events: none; position: absolute;
  left: calc(100% + 12px); top: 0; z-index: 20;
  width: 220px; padding: 12px; border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--card);
  box-shadow: var(--shadow); font-size: var(--text-sm);
  opacity: 0; transform: translateX(-6px);
  transition: opacity 150ms var(--ease), transform 150ms var(--ease);
}
.wf-graph-node:hover .wf-graph-tooltip {
  opacity: 1; transform: translateX(0); pointer-events: auto;
}
/* Flip tooltip to left side for right-column nodes */
.wf-graph-node:nth-child(even) .wf-graph-tooltip {
  left: auto; right: calc(100% + 12px);
  transform: translateX(6px);
}
.wf-graph-node:nth-child(even):hover .wf-graph-tooltip {
  transform: translateX(0);
}
.wf-graph-tooltip-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
}

/* Pipeline Node (legacy — still used for shimmer bar) */
.wf-pipe-node {
  width: 260px; padding: 12px 14px;
  border-radius: var(--radius); border: 1.5px solid var(--border);
  background: var(--card-alt); backdrop-filter: blur(8px);
  cursor: pointer; transition: all var(--dur) var(--ease); position: relative;
}

/* Running shimmer bar */
.wf-pipe-node-shimmer {
  height: 2px; margin-top: 8px; border-radius: 99px; overflow: hidden;
  background: rgba(59,130,246,0.15);
}
.wf-pipe-node-shimmer-bar {
  height: 100%; width: 33%;
  background: linear-gradient(90deg, transparent, var(--info), transparent);
  background-size: 200% 100%;
  animation: shimmer-line 1.2s linear infinite;
}

/* ─── Agent Inspector (Right Column) ─── */
.wf-inspector {
  background: var(--glass); border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px); border-radius: var(--radius);
  display: flex; flex-direction: column; height: 640px; overflow: hidden;
}
.wf-inspector-header {
  padding: 14px 16px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.wf-inspector-title { font-size: var(--text-md); font-weight: 600; }
.wf-inspector-sub { font-size: var(--text-sm); color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Inspector tab bar */
.wf-inspector-tabs {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 8px; border-bottom: 1px solid var(--border);
}
.wf-inspector-tab {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 6px; font-size: var(--text-sm);
  background: none; border: none; cursor: pointer; color: var(--muted);
  transition: all var(--dur) var(--ease);
}
.wf-inspector-tab:hover { color: var(--text); }
.wf-inspector-tab.active { background: var(--accent-dim); color: var(--accent); }
.wf-inspector-tab.active-output { background: var(--card-alt); color: var(--text); }

.wf-inspector-actions { margin-left: auto; display: flex; gap: 4px; }

.wf-inspector-body {
  flex: 1; overflow-y: auto; padding: 16px;
}

/* Thought content */
.wf-thought-chain-label {
  font-size: var(--text-xs); font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--accent); margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}
.wf-thought-chain-box {
  padding: 16px; border-radius: var(--radius);
  border: 1px solid rgba(251,107,45,0.15); background: rgba(251,107,45,0.05);
}
.wf-thought-chain-text {
  font-size: var(--text-base); line-height: 1.8; color: var(--text-dim);
  white-space: pre-wrap;
}
.wf-thought-conf {
  display: inline-flex; align-items: center; gap: 8px;
  margin-top: 12px; padding: 6px 12px; border-radius: var(--radius-sm);
  border: 1px solid rgba(16,185,129,0.2); background: rgba(16,185,129,0.05);
  font-size: var(--text-sm);
}
.wf-thought-conf-value { font-family: monospace; font-weight: 600; color: var(--success); }

/* JSON output */
.wf-output-json {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: var(--text-sm); line-height: 1.7; color: var(--text-dim);
  white-space: pre-wrap; word-break: break-word;
}
.wf-output-json .json-key { color: var(--accent); }
.wf-output-json .json-string { color: #d4a745; }
.wf-output-json .json-number { color: var(--success); }
.wf-output-json .json-bool { color: var(--accent2); }

/* Metadata grid */
.wf-meta-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
}
.wf-meta-item {
  padding: 8px 10px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--card-alt);
}
.wf-meta-key { font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
.wf-meta-val { font-family: monospace; font-size: var(--text-sm); margin-top: 3px; }

/* Waiting / Running placeholders */
.wf-placeholder { display: flex; align-items: center; gap: 8px; font-size: var(--text-md); color: var(--muted); }
.wf-placeholder.reasoning { color: var(--info); font-weight: 500; }

.wf-skeleton-bars { margin-top: 12px; }
.wf-skeleton-bar {
  height: 8px; border-radius: 4px; background: var(--info-dim);
  animation: shimmer-line 1.5s linear infinite;
}
.wf-skeleton-bar:nth-child(2) { width: 60%; margin-top: 8px; opacity: 0.7; }
.wf-skeleton-bar:nth-child(3) { width: 80%; margin-top: 8px; opacity: 0.5; }


/* ═══════════════════════════════════════════════════
   COMPLETION SUMMARY
   ═══════════════════════════════════════════════════ */

.wf-completion {
  background: var(--glass); border: 1px solid var(--glass-border);
  backdrop-filter: blur(20px); border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow-card);
  animation: slide-up var(--dur-md) var(--ease) both;
}

.wf-completion-header {
  display: flex; align-items: center; gap: 14px;
  padding: 20px; border-bottom: 1px solid var(--border);
  position: relative; overflow: hidden;
}
.wf-completion-header::before {
  content: ''; position: absolute; inset: 0; opacity: 0.4;
  background: radial-gradient(400px circle at 0% 0%, rgba(16,185,129,0.18), transparent 50%);
  pointer-events: none;
}
.wf-completion-icon {
  width: 40px; height: 40px; border-radius: var(--radius);
  display: flex; align-items: center; justify-content: center;
  background: rgba(16,185,129,0.15); color: var(--success); flex-shrink: 0;
  position: relative; z-index: 1;
}
.wf-completion-title { font-size: var(--text-md); font-weight: 600; position: relative; z-index: 1; }
.wf-completion-sub { font-size: var(--text-sm); color: var(--muted); position: relative; z-index: 1; }
.wf-completion-actions { margin-left: auto; display: flex; gap: 8px; position: relative; z-index: 1; }

/* Stats cards row */
.wf-completion-stats {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;
  padding: 20px; border-bottom: 1px solid var(--border);
}
@media (max-width: 900px) { .wf-completion-stats { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 600px) { .wf-completion-stats { grid-template-columns: repeat(2, 1fr); } }

.wf-completion-stat {
  padding: 12px; border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--card-alt);
  position: relative; overflow: hidden; cursor: default;
  transition: transform var(--dur-md) var(--ease);
}
.wf-completion-stat:hover { transform: translateY(-3px); }
.wf-completion-stat::before {
  content: ''; position: absolute; top: 0; right: 0;
  width: 90px; height: 90px; border-radius: 50%;
  background: var(--accent-dim2); transform: translate(30px, -30px);
}
.wf-completion-stat::after {
  content: ''; position: absolute; top: 0; left: 0; right: 0;
  height: 2px; background: var(--grad-brand); opacity: 0;
  transition: opacity var(--dur-md) var(--ease);
}
.wf-completion-stat:hover::after { opacity: 1; }

.wf-completion-stat-label {
  font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--muted); position: relative; z-index: 1;
}
.wf-completion-stat-value {
  font-size: var(--text-2xl); font-weight: 800; letter-spacing: -0.04em;
  margin-top: 4px; position: relative; z-index: 1;
}
.wf-completion-stat-sub {
  font-size: var(--text-sm); color: var(--muted); position: relative; z-index: 1;
}

/* Pros / Cons */
.wf-proscons {
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
  padding: 20px; border-bottom: 1px solid var(--border);
}
@media (max-width: 800px) { .wf-proscons { grid-template-columns: 1fr; } }

.wf-proscons-title {
  font-size: var(--text-sm); font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.wf-proscons-title.pros { color: var(--success); }
.wf-proscons-title.cons { color: var(--warn); }

.wf-proscons-list { display: flex; flex-direction: column; gap: 8px; }
.wf-proscons-item {
  display: flex; gap: 10px; padding: 10px 12px; border-radius: var(--radius-sm);
  font-size: var(--text-base); line-height: 1.6;
}
.wf-proscons-item.pro {
  border: 1px solid rgba(16,185,129,0.15); background: rgba(16,185,129,0.05);
}
.wf-proscons-item.con {
  border: 1px solid rgba(245,158,11,0.15); background: rgba(245,158,11,0.05);
}
.wf-proscons-icon { flex-shrink: 0; margin-top: 2px; }

/* AI Suggestion + Decision */
.wf-decision-grid {
  display: grid; grid-template-columns: 2fr 1fr; gap: 20px; padding: 20px;
}
@media (max-width: 800px) { .wf-decision-grid { grid-template-columns: 1fr; } }

.wf-suggestion-title {
  font-size: var(--text-sm); font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--muted); margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.wf-suggestion-box {
  padding: 16px; border-radius: var(--radius);
  border: 1px solid rgba(251,107,45,0.15); background: rgba(251,107,45,0.05);
}
.wf-suggestion-rec {
  display: flex; align-items: center; gap: 8px;
  font-size: var(--text-md); font-weight: 700; color: var(--accent); margin-bottom: 12px;
}
.wf-suggestion-text {
  font-size: var(--text-base); line-height: 1.8; color: var(--text-dim);
}
.wf-suggestion-metrics {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 16px;
}
.wf-suggestion-metric {
  padding: 10px; text-align: center; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--card-alt);
}
.wf-suggestion-metric-label { font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
.wf-suggestion-metric-value { font-size: var(--text-md); font-weight: 700; margin-top: 4px; }

/* Final decision card */
.wf-final-decision {
  padding: 20px; text-align: center;
  border-radius: var(--radius);
  border: 1px solid rgba(16,185,129,0.3); background: rgba(16,185,129,0.05);
}
.wf-final-icon-wrap {
  position: relative; display: inline-flex; margin-bottom: 16px;
}
.wf-final-icon {
  width: 80px; height: 80px; border-radius: var(--radius);
  display: flex; align-items: center; justify-content: center;
  background: rgba(16,185,129,0.15); color: var(--success);
}
.wf-final-checkmark {
  position: absolute; top: -4px; right: -4px;
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--success); color: white;
  display: flex; align-items: center; justify-content: center;
}
.wf-final-verdict {
  font-size: var(--text-3xl); font-weight: 800; color: var(--success);
  letter-spacing: -0.03em;
}
.wf-final-verdict-sub { font-size: var(--text-sm); color: var(--muted); margin-top: 4px; }
.wf-final-confidence {
  display: inline-block; margin-top: 14px;
  padding: 6px 18px; border-radius: 99px;
  border: 1px solid rgba(16,185,129,0.3); background: rgba(16,185,129,0.1);
  font-family: monospace; font-size: var(--text-md); font-weight: 700; color: var(--success);
}

.wf-final-details {
  margin-top: 18px; text-align: left;
}
.wf-final-detail-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--card-alt);
  font-size: var(--text-sm); margin-bottom: 6px;
}
.wf-final-detail-row:last-child { margin-bottom: 0; }
.wf-final-detail-key { color: var(--muted); }
.wf-final-detail-val { font-weight: 600; font-family: monospace; }
.wf-final-detail-val.success { color: var(--success); }

.wf-final-exports { display: flex; gap: 8px; margin-top: 12px; }
.wf-final-exports .btn { flex: 1; }

/* Bulk Uploader Styles */
.bulk-upload-zone {
  border: 2px dashed rgba(251, 107, 45, 0.25);
  border-radius: var(--radius);
  background: rgba(251, 107, 45, 0.02);
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: all var(--dur-md) var(--ease);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  position: relative;
}
.bulk-upload-zone:hover, .bulk-upload-zone.drag-active {
  border-color: var(--accent);
  background: rgba(251, 107, 45, 0.06);
  transform: translateY(-1px);
}
.bulk-upload-icon {
  color: var(--accent);
  transition: transform var(--dur-md) var(--ease);
}
.bulk-upload-zone:hover .bulk-upload-icon {
  transform: translateY(-2px) scale(1.05);
}
.bulk-upload-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text);
}
.bulk-upload-sub {
  font-size: var(--text-sm);
  color: var(--muted);
  line-height: 1.4;
}
.bulk-file-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
  padding-right: 4px;
}
.bulk-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--card-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-size: var(--text-sm);
  animation: slide-in 200ms var(--ease) both;
}
.bulk-file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.bulk-file-name {
  color: var(--text);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.bulk-file-size {
  font-size: var(--text-xs);
  color: var(--muted);
  flex-shrink: 0;
}

/* ══════════════════════════════════════════════════
   MISTRAL SIGNATURE COMPONENTS
══════════════════════════════════════════════════ */

/* ─── Sunset Stripe Band ─────────────────────────
   THE brand recognizer. Sits at the foot of every page.
   Multi-stop gradient: orange → sunshine → yellow → cream
─────────────────────────────────────────────────── */
.sunset-stripe {
  width: 100%;
  height: 6px;
  background: var(--grad-sunset);
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}
.sunset-stripe::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%);
  animation: shimmer-stripe 3s ease-in-out infinite;
}
@keyframes shimmer-stripe {
  0%, 100% { transform: translateX(-100%); }
  50% { transform: translateX(100%); }
}

/* ─── Card Cream ─────────────────────────────────
   Warm cream-yellow feature card (Mistral signature surface)
─────────────────────────────────────────────────── */
.card-cream {
  background: var(--mistral-cream, #fff8e0);
  border: 1px solid var(--mistral-beige-deep, #e6d5a8);
  border-radius: var(--radius);
  padding: 24px 32px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-card);
  color: var(--text);
}
[data-theme="dark"] .card-cream {
  background: var(--card-hi);
  border-color: var(--border-hi);
}

/* ─── Dashboard Hero Header ──────────────────────
   Editorial page-top header strip, Mistral-style
─────────────────────────────────────────────────── */
.page-hero {
  background: linear-gradient(135deg, var(--mistral-cream, #fff8e0) 0%, #fffaeb 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px 32px;
  margin-bottom: 22px;
  position: relative;
  overflow: hidden;
}
[data-theme="dark"] .page-hero {
  background: linear-gradient(135deg, var(--card-hi) 0%, var(--card-alt) 100%);
}
.page-hero::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--grad-sunset);
}
.page-hero::after {
  content: '';
  position: absolute; bottom: 0; right: 0;
  width: 200px; height: 200px;
  background: radial-gradient(circle, var(--hero-radial-glow) 0%, transparent 70%);
  pointer-events: none;
}
.page-hero-eyebrow {
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 8px;
}
.page-hero-title {
  font-family: var(--font-display);
  font-size: var(--text-3xl);
  font-weight: 400;
  letter-spacing: -0.5px;
  line-height: 1.15;
  color: var(--text);
}
.page-hero-sub {
  font-size: var(--text-xl);
  color: var(--text-dim);
  margin-top: 6px;
  font-weight: 400;
  line-height: 1.5;
}

/* ─── Stat Display (editorial large number) ──────
   PP Editorial Old style: big number + label
─────────────────────────────────────────────────── */
.stat-display-value {
  font-family: var(--font-display);
  font-size: 48px;
  font-weight: 400;
  letter-spacing: -1px;
  line-height: 1.10;
  color: var(--text);
}
.stat-display-label {
  font-size: var(--text-md);
  color: var(--muted);
  font-weight: 500;
  margin-top: 4px;
}

/* ─── Badge Orange (Mistral primary badge) ───────── */
.badge-orange {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
.badge-cream {
  background: var(--mistral-cream-deep, #fff0c2);
  color: var(--text);
  border-color: var(--mistral-beige-deep, #e6d5a8);
}
[data-theme="dark"] .badge-cream {
  background: var(--card-hi);
  border-color: var(--border-hi);
}

/* ══════════════════════════════════════════════════
   DARK MODE — Hardcoded Color Overrides
   Ensures all inline/hardcoded colors are readable
   on the jet black background
══════════════════════════════════════════════════ */

/* Verdict badges */
[data-theme="dark"] .verdict-badge.genuine   { color: #34d399; }
[data-theme="dark"] .verdict-badge.uncertain { color: #fbbf24; }
[data-theme="dark"] .verdict-badge.forged    { color: #f87171; }

/* Analysis scores */
[data-theme="dark"] .analysis-score.high   { color: #34d399; background: rgba(52,211,153,0.12); }
[data-theme="dark"] .analysis-score.medium { color: #fbbf24; background: rgba(251,191,36,0.12); }
[data-theme="dark"] .analysis-score.low    { color: #f87171; background: rgba(248,113,113,0.12); }

/* Recommendation banners */
[data-theme="dark"] .recommendation-banner.accept { color: #34d399; }
[data-theme="dark"] .recommendation-banner.review { color: #fbbf24; }
[data-theme="dark"] .recommendation-banner.reject { color: #f87171; }

/* Face verification signals */
[data-theme="dark"] .face-signal-same   { color: #34d399; }
[data-theme="dark"] .face-signal-diff   { color: #f87171; }
[data-theme="dark"] .face-signal-inc    { color: #fbbf24; }
[data-theme="dark"] .face-conf-badge.high   { color: #34d399; }
[data-theme="dark"] .face-conf-badge.medium { color: #fbbf24; }
[data-theme="dark"] .face-conf-badge.low    { color: #f87171; }

/* Face variability chips */
[data-theme="dark"] .face-variability-chip.ok   { color: #34d399; }
[data-theme="dark"] .face-variability-chip.mild { color: #fbbf24; }
[data-theme="dark"] .face-variability-chip.sig  { color: #f87171; }

/* Face points labels */
[data-theme="dark"] .face-points-list.same .face-points-label { color: #34d399; }
[data-theme="dark"] .face-points-list.diff .face-points-label { color: #f87171; }

/* Age gap badge */
[data-theme="dark"] .face-age-gap-badge { color: #60a5fa; }

/* JSON syntax highlighting */
[data-theme="dark"] .wf-output-json .json-string { color: #fbbf24; }

/* Verification loading */
[data-theme="dark"] .verification-loading .verify-text { color: #c084fc; }

/* Decorative gradients & stripe overrides to keep theme solid dark */
[data-theme="dark"] .sunset-stripe {
  background: var(--border);
}
[data-theme="dark"] .sunset-stripe::after {
  animation: none;
  display: none;
}
[data-theme="dark"] .page-hero::before {
  background: var(--border-hi);
}
[data-theme="dark"] .card-accent::before {
  background: var(--border-hi);
}
[data-theme="dark"] .modal::before {
  background: var(--border-hi);
}
[data-theme="dark"] .stat-card::after {
  background: var(--border-hi);
}
[data-theme="dark"] .claim-stat::after {
  background: var(--border-hi);
}
[data-theme="dark"] .wf-completion-stat::after {
  background: var(--border-hi);
}
[data-theme="dark"] .claim-btn-process {
  background: var(--accent);
}
[data-theme="dark"] .progress-fill {
  background: var(--accent);
}
[data-theme="dark"] .wf-step-btn.active::before {
  background: var(--accent);
}
```

## `src/styles/animations.css`

```css
/* ─── Keyframes ─────────────────────────────────── */

@keyframes border-rotate {
  to { filter: hue-rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); box-shadow: 0 0 0 0 var(--pulse-glow-1); }
  50%       { opacity: 0.75; transform: scale(0.94); box-shadow: 0 0 0 6px var(--pulse-glow-2); }
}

@keyframes ping {
  0%   { transform: scale(1); opacity: 0.8; }
  100% { transform: scale(2.4); opacity: 0; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes shimmer {
  0%   { background-position: -600px 0; }
  100% { background-position: 600px 0; }
}

@keyframes shimmer-line {
  0%   { background-position: -200px 0; }
  100% { background-position: 200px 0; }
}

@keyframes slide-in {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes slide-right {
  from { opacity: 0; transform: translateX(-14px); }
  to   { opacity: 1; transform: translateX(0); }
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes toast-in {
  from { opacity: 0; transform: translateX(120%); }
  to   { opacity: 1; transform: translateX(0); }
}

@keyframes progress-fill {
  from { width: 0; }
}

@keyframes glow-pulse {
  0%, 100% { box-shadow: var(--glow-pulse-1); }
  50%       { box-shadow: var(--glow-pulse-2); }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-4px); }
}

@keyframes nav-indicator-in {
  from { transform: scaleY(0); opacity: 0; }
  to   { transform: scaleY(1); opacity: 1; }
}

/* Count-up — used for stat card values */
@keyframes count-pop {
  0%   { transform: scale(0.85); opacity: 0; }
  60%  { transform: scale(1.05); }
  100% { transform: scale(1);   opacity: 1; }
}

/* ─── Animation classes ─────────────────────────── */

.anim-slide-in    { animation: slide-in    var(--dur) var(--ease) both; }
.anim-slide-up    { animation: slide-up    var(--dur) var(--ease) both; }
.anim-fade-in     { animation: fade-in     var(--dur) var(--ease) both; }
.anim-slide-right { animation: slide-right var(--dur) var(--ease) both; }
.anim-count-pop   { animation: count-pop   var(--dur-md) var(--ease-spring) both; }

/* ─── Stagger delays ─────────────────────────────── */
.delay-1 { animation-delay: 60ms;  }
.delay-2 { animation-delay: 120ms; }
.delay-3 { animation-delay: 180ms; }
.delay-4 { animation-delay: 240ms; }
.delay-5 { animation-delay: 300ms; }
.delay-6 { animation-delay: 360ms; }

/* ─── Skeleton loading ──────────────────────────── */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--card)     0%,
    var(--card-alt) 50%,
    var(--card)     100%
  );
  background-size: 1200px 100%;
  animation: shimmer 1.8s infinite linear;
  border-radius: var(--radius-sm);
}

.spin, .spin-icon, .animate-spin {
  animation: spin 0.8s linear infinite !important;
  transform-origin: center !important;
  transform-box: fill-box !important;
  display: inline-block !important;
}

/* ─── Pulse dot (live indicator) ─────────────────── */
.pulse-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--success);
  position: relative;
  flex-shrink: 0;
}
.pulse-dot::after {
  content: '';
  position: absolute; inset: -2px;
  border-radius: 50%;
  background: var(--success);
  opacity: 0.4;
  animation: ping 2s ease-out infinite;
}

/* ─── Hover Micro-Interactions ────────────────────── */
.hover-scale {
  transition: transform var(--dur) var(--ease-spring);
}
.hover-scale:hover {
  transform: scale(1.03);
}

.hover-lift {
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
}
.hover-lift:hover {
  transform: translateY(-2px);
  box-shadow: var(--glow-sm);
}

/* ─── Reduced motion — Accessibility ─────────────── */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }

  .skeleton {
    animation: none;
    background: var(--card-alt);
  }

  .pulse-dot::after {
    animation: none;
    display: none;
  }

  .spin {
    animation: none;
  }
}
```


---

# State store, API client & hooks

## `src/store/AppStore.jsx`

```jsx
import { createContext, useContext, useReducer, useCallback } from 'react';

// ─── Initial State ───────────────────────────────
function lsGet(key, fallback) {
  try { const v = localStorage.getItem(key); return v !== null ? JSON.parse(v) : fallback; } catch { return fallback; }
}

const initialState = {
  documents: [],        // [{id, filename, status, doc_type, workflow_run_id}]
  activeDocId: null,    // currently viewed document id
  pollingIds: new Set(),
  toasts: [],
  loading: false,
  confidenceMode: (() => {
    try {
      return localStorage.getItem('idp-confidence-mode') || 'word';
    } catch {
      return 'word';
    }
  })(),
  // Confidence thresholds (user-configurable)
  fieldHighlightThreshold: lsGet('idp-field-highlight-threshold', 95), // % below which a field value is amber-highlighted
  autoApproveThreshold:    lsGet('idp-auto-approve-threshold', 80),    // % below which a doc enters review queue
  confHighThreshold:       lsGet('idp-conf-high-threshold', 90),       // % for green badge
  confMedThreshold:        lsGet('idp-conf-med-threshold', 70),        // % for amber badge (below → red)
};

// ─── Reducer ─────────────────────────────────────
function reducer(state, action) {
  switch (action.type) {
    case 'SET_DOCUMENTS':
      return { ...state, documents: action.payload };

    case 'ADD_DOCUMENT':
      return {
        ...state,
        documents: [action.payload, ...state.documents.filter((d) => d.id !== action.payload.id)],
      };

    case 'UPDATE_DOCUMENT': {
      const docs = state.documents.map((d) =>
        d.id === action.payload.id ? { ...d, ...action.payload } : d
      );
      // If the doc wasn't in the list yet, add it
      if (!docs.find((d) => d.id === action.payload.id)) {
        docs.unshift(action.payload);
      }
      return { ...state, documents: docs };
    }

    case 'REMOVE_DOCUMENT':
      return { ...state, documents: state.documents.filter((d) => d.id !== action.payload) };

    case 'SET_ACTIVE_DOC':
      return { ...state, activeDocId: action.payload };

    case 'ADD_POLLING':
      return { ...state, pollingIds: new Set([...state.pollingIds, action.payload]) };

    case 'REMOVE_POLLING': {
      const next = new Set(state.pollingIds);
      next.delete(action.payload);
      return { ...state, pollingIds: next };
    }

    case 'ADD_TOAST':
      return { ...state, toasts: [...state.toasts, action.payload] };

    case 'REMOVE_TOAST':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.payload) };

    case 'SET_LOADING':
      return { ...state, loading: action.payload };

    case 'SET_CONFIDENCE_MODE':
      try { localStorage.setItem('idp-confidence-mode', action.payload); } catch {}
      return { ...state, confidenceMode: action.payload };

    case 'SET_FIELD_HIGHLIGHT_THRESHOLD':
      try { localStorage.setItem('idp-field-highlight-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, fieldHighlightThreshold: action.payload };

    case 'SET_AUTO_APPROVE_THRESHOLD':
      try { localStorage.setItem('idp-auto-approve-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, autoApproveThreshold: action.payload };

    case 'SET_CONF_HIGH_THRESHOLD':
      try { localStorage.setItem('idp-conf-high-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, confHighThreshold: action.payload };

    case 'SET_CONF_MED_THRESHOLD':
      try { localStorage.setItem('idp-conf-med-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, confMedThreshold: action.payload };

    default:
      return state;
  }
}

// ─── Context ─────────────────────────────────────
const AppContext = createContext(null);

let toastId = 0;

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const setDocuments = useCallback((docs) => dispatch({ type: 'SET_DOCUMENTS', payload: docs }), []);
  const addDocument  = useCallback((doc)  => dispatch({ type: 'ADD_DOCUMENT',  payload: doc }),  []);
  const updateDocument = useCallback((doc) => dispatch({ type: 'UPDATE_DOCUMENT', payload: doc }), []);
  const removeDocument = useCallback((id)  => dispatch({ type: 'REMOVE_DOCUMENT', payload: id }),  []);
  const setActiveDoc = useCallback((id)   => dispatch({ type: 'SET_ACTIVE_DOC', payload: id }),   []);
  const addPolling   = useCallback((id)   => dispatch({ type: 'ADD_POLLING',   payload: id }),    []);
  const removePolling= useCallback((id)   => dispatch({ type: 'REMOVE_POLLING',payload: id }),    []);
  const setConfidenceMode           = useCallback((mode) => dispatch({ type: 'SET_CONFIDENCE_MODE',           payload: mode }), []);
  const setFieldHighlightThreshold  = useCallback((v)    => dispatch({ type: 'SET_FIELD_HIGHLIGHT_THRESHOLD', payload: v }),    []);
  const setAutoApproveThreshold     = useCallback((v)    => dispatch({ type: 'SET_AUTO_APPROVE_THRESHOLD',    payload: v }),    []);
  const setConfHighThreshold        = useCallback((v)    => dispatch({ type: 'SET_CONF_HIGH_THRESHOLD',       payload: v }),    []);
  const setConfMedThreshold         = useCallback((v)    => dispatch({ type: 'SET_CONF_MED_THRESHOLD',        payload: v }),    []);

  const toast = useCallback((msg, type = 'info', duration = 4000) => {
    const id = ++toastId;
    dispatch({ type: 'ADD_TOAST', payload: { id, msg, type } });
    setTimeout(() => dispatch({ type: 'REMOVE_TOAST', payload: id }), duration);
  }, []);

  const dismissToast = useCallback((id) => dispatch({ type: 'REMOVE_TOAST', payload: id }), []);

  // ─── Derived helpers ────────────────────────────
  const pendingDocs = state.documents.filter((d) => ['pending','pre_validating','processing','preprocessing','classifying','fraud_checking','extracting','validating'].includes(d.status));
  const reviewDocs  = state.documents.filter((d) => ['awaiting_review', 'duplicate'].includes(d.status));

  const completedDocs = state.documents.filter((d) => d.status === 'completed');

  return (
    <AppContext.Provider value={{
      ...state,
      pendingDocs,
      reviewDocs,
      completedDocs,
      setDocuments,
      addDocument,
      updateDocument,
      removeDocument,
      setActiveDoc,
      addPolling,
      removePolling,
      toast,
      dismissToast,
      setConfidenceMode,
      setFieldHighlightThreshold,
      setAutoApproveThreshold,
      setConfHighThreshold,
      setConfMedThreshold,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be inside AppProvider');
  return ctx;
}
```

## `src/api/client.js`

```js
import axios from 'axios';

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: BASE, timeout: 30000 });

// ─── Response interceptor: normalize errors ──────
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err?.response?.data?.detail ||
      err?.response?.data?.message ||
      err?.message ||
      'Unknown error';
    return Promise.reject(new Error(msg));
  }
);

// ─── Document APIs ───────────────────────────────

/**
 * Upload a document.
 * @param {File} file
 * @param {(pct: number) => void} onProgress
 * @returns {Promise<{document_id, filename, status, message, workflow_run_id}>}
 */
export async function uploadDocument(file, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/**
 * Batch upload — sends all files in a single multipart request to /upload/batch.
 * Server processes them concurrently and returns per-file results.
 * @param {File[]} files
 * @param {(pct: number) => void} onProgress  — overall upload progress 0-100
 * @returns {Promise<{ total, succeeded, failed, results: Array }>}
 */
export async function uploadDocumentsBatch(files, onProgress) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const { data } = await api.post('/upload/batch', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000, // 5 min — large batches can take a while
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/**
 * Get workflow status for a document.
 * @param {string} documentId
 * @returns {Promise<WorkflowStatusResponse>}
 */
export async function getStatus(documentId) {
  const { data } = await api.get(`/status/${documentId}`);
  return data;
}

/**
 * List documents (paginated).
 * @param {number} page
 * @param {number} limit
 */
export async function listDocuments(page = 1, limit = 50) {
  const pageNum = typeof page === 'number' ? page : 1;
  const limitNum = typeof limit === 'number' ? limit : 50;
  const { data } = await api.get('/documents', { params: { page: pageNum, limit: limitNum } });
  return data; // array
}

/**
 * Get full extracted data for a document.
 * @param {string} documentId
 */
export async function getExtractedData(documentId) {
  const { data } = await api.get(`/documents/${documentId}/extracted`);
  return data;
}

/**
 * Update extracted data for a document.
 * @param {string} documentId
 * @param {object} validatedData
 */
export async function updateExtractedData(documentId, validatedData) {
  const { data } = await api.put(`/documents/${documentId}/extracted`, { validated_data: validatedData });
  return data;
}

/**
 * Signal duplicate decision.
 * @param {string} workflowRunId
 * @param {boolean} override
 */
export async function resumeDuplicate(workflowRunId, override) {
  const { data } = await api.post(`/workflow/${workflowRunId}/resume/duplicate`, { override });
  return data;
}

/**
 * Signal human review decision.
 * @param {string} workflowRunId
 * @param {boolean} approved
 * @param {object|null} corrections
 * @param {string|null} rejectionReason
 */
export async function resumeReview(workflowRunId, approved, corrections = null, rejectionReason = null) {
  const { data } = await api.post(`/workflow/${workflowRunId}/resume/review`, {
    approved,
    corrections,
    rejection_reason: rejectionReason,
  });
  return data;
}

/**
 * Fetch all pipeline agents (live from Mistral API + static workflow agents).
 * @returns {Promise<Array>}
 */
export async function getAgents() {
  const { data } = await api.get('/agents');
  return data;
}

/**
 * Delete (soft) a document.
 * @param {string} documentId
 */
export async function deleteDocument(documentId) {
  const { data } = await api.delete(`/documents/${documentId}`);
  return data;
}

/**
 * Get the preview URL for a document.
 * @param {string} documentId
 * @returns {string}
 */
export function getDocumentFileUrl(documentId) {
  return `${BASE}/documents/${documentId}/file`;
}

/**
 * Get OCR bounding box blocks for field citation highlighting.
 * Only available for image documents (PNG/JPEG/WEBP) processed after this feature was added.
 * @param {string} documentId
 * @returns {Promise<{ blocks: Array, available: boolean }>}
 */
export async function getOcrBlocks(documentId) {
  const { data } = await api.get(`/documents/${documentId}/ocr-blocks`);
  return data;
}

/**
 * Get templates from backend
 * @returns {Promise<object>}
 */
export async function getTemplates() {
  const { data } = await api.get('/templates');
  return data;
}

/**
 * Save templates to backend
 * @param {object} templatesData
 * @returns {Promise<object>}
 */
export async function saveTemplates(templatesData) {
  const { data } = await api.put('/templates', templatesData);
  return data;
}

/**
 * Generate a template from a sample document.
 * @param {string} templateName
 * @param {File} file
 * @param {boolean} isKyc
 * @param {object|null} kycBoxes - Optional {signature: {x1,y1,x2,y2}, photo: {x1,y1,x2,y2}}
 * @returns {Promise<{success: boolean, template_name: string, fields: Array, is_kyc: boolean}>}
 */
export async function generateTemplateFromSample(templateName, file, isKyc = false, kycBoxes = null) {
  const form = new FormData();
  form.append('file', file);
  const params = { template_name: templateName, is_kyc: isKyc };
  if (kycBoxes) {
    params.kyc_boxes = JSON.stringify(kycBoxes);
  }
  const { data } = await api.post('/templates/generate', form, {
    params,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return data;
}

/**
 * Delete a template.
 * @param {string} templateName
 * @returns {Promise<object>}
 */
export async function deleteTemplate(templateName) {
  const { data } = await api.delete(`/templates/${templateName}`);
  return data;
}

/**
 * Get the URL for a cropped signature/photo image.
 * @param {string} documentId
 * @param {string} filename - e.g. "signature.png" or "photo.png"
 * @returns {string}
 */
export function getCropUrl(documentId, filename) {
  return `${BASE}/documents/${documentId}/crops/${filename}`;
}

/**
 * Verify a signature or photo against a reference image.
 * Runs the DINO + Mistral Vision + Judge pipeline.
 * @param {string} documentId
 * @param {File} referenceFile - The reference signature/photo to compare against
 * @param {'signature'|'photo'} verificationType
 * @returns {Promise<object>} Full verification result with verdict, scores, analysis
 */
export async function verifySignature(documentId, referenceFile, verificationType = 'signature') {
  const form = new FormData();
  form.append('file', referenceFile);
  const { data } = await api.post(
    `/documents/${documentId}/verify-signature`,
    form,
    {
      params: { verification_type: verificationType },
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000, // 2 min — ML inference + Mistral API calls
    }
  );
  return data;
}

/**
 * Get normalization settings.
 * @returns {Promise<object>}
 */
export async function getNormConfig() {
  const { data } = await api.get('/settings/normalization');
  return data;
}

/**
 * Save normalization settings.
 * @param {object} config
 * @returns {Promise<object>}
 */
export async function saveNormConfig(config) {
  const { data } = await api.put('/settings/normalization', config);
  return data;
}

/**
 * Get classification document types.
 * @returns {Promise<string[]>}
 */
export async function getClassificationConfig() {
  const { data } = await api.get('/settings/classification');
  return data;
}

/**
 * Save classification document types.
 * @param {string[]} docTypes
 * @returns {Promise<object>}
 */
export async function saveClassificationConfig(docTypes) {
  const { data } = await api.put('/settings/classification', docTypes);
  return data;
}


// ─── Claim Processing APIs ────────────────────────────────────────────────────

/**
 * Create a new claim record.
 * @param {{ claimant_name, claim_type, policy_number, description, priority, amount }} payload
 */
export async function createClaim(payload) {
  const { data } = await api.post('/claims', payload);
  return data;
}

/**
 * List all claims.
 * @returns {Promise<Array>}
 */
export async function listClaims() {
  const { data } = await api.get('/claims');
  return data;
}

/**
 * Get extraction status for all docs linked to a claim.
 * @param {string} claimId
 * @returns {Promise<{ claim_status, total_docs, completed_docs, failed_docs, ready_to_process, doc_statuses }>}
 */
export async function getClaimStatus(claimId) {
  const { data } = await api.get(`/claims/${claimId}/status`);
  return data;
}

/**
 * Trigger the claim processing workflow.
 * @param {string} claimId
 * @returns {Promise<{ claim_id, workflow_run_id, status }>}
 */
export async function runClaimWorkflow(claimId) {
  const { data } = await api.post(`/claims/${claimId}/run`);
  return data;
}

export async function rerunClaimWorkflow(claimId) {
  const { data } = await api.post(`/claims/${claimId}/rerun`);
  return data;
}

/**
 * Get the final claim report (after workflow completes).
 * @param {string} claimId
 * @returns {Promise<{ claim_id, claimant_name, overall_status, suggestion, agent_results, processed_at }>}
 */
export async function getClaimReport(claimId) {
  const { data } = await api.get(`/claims/${claimId}/report`);
  return data;
}

/**
 * Submit adjuster's accept/reject decision.
 * @param {string} claimId
 * @param {'approve'|'reject'} decision
 * @param {string} [notes]
 */
export async function submitClaimDecision(claimId, decision, notes = '') {
  const { data } = await api.post(`/claims/${claimId}/decision`, { decision, notes });
  return data;
}

/**
 * Permanently delete a claim and its document links.
 * @param {string} claimId
 */
export async function deleteClaim(claimId) {
  const { data } = await api.delete(`/claims/${claimId}`);
  return data;
}

/**
 * Upload a document as part of a claim — passes claim_id and doc_type as query params.
 * @param {string} claimId
 * @param {File} file
 * @param {string} docType  e.g. "medical_report"
 * @param {(pct: number) => void} onProgress
 */
export async function uploadClaimDocument(claimId, file, docType, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/upload', form, {
    params: { claim_id: claimId, doc_type: docType },
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

export default api;

```

## `src/hooks/useDocumentList.js`

```js
import { useCallback, useState } from 'react';
import { listDocuments } from '../api/client';
import { useApp } from '../store/AppStore';

/**
 * Hook to fetch the document list from the backend and sync to AppStore.
 */
export function useDocumentList() {
  const { setDocuments, toast } = useApp();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async (page = 1, limit = 100) => {
    // Guard against React synthetic event objects passed via onClick={refresh}
    const pageNum = typeof page === 'number' ? page : 1;
    const limitNum = typeof limit === 'number' ? limit : 100;
    setLoading(true);
    setError(null);
    try {
      const docs = await listDocuments(pageNum, limitNum);
      setDocuments(docs);
    } catch (err) {
      setError(err.message);
      toast('Failed to load documents: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [setDocuments, toast]);

  return { refresh, loading, error };
}
```

## `src/hooks/useDocumentPoller.js`

```js
import { useEffect, useRef } from 'react';
import { getStatus } from '../api/client';
import { useApp } from '../store/AppStore';

const TERMINAL_STATUSES = new Set(['completed', 'rejected', 'error', 'deleted']);
const POLL_INTERVAL = 2500; // ms

/**
 * Polls /status/{documentId} every 2.5s until a terminal status is reached.
 * Updates AppStore on every tick.
 */
export function useDocumentPoller(documentId) {
  const { updateDocument, addPolling, removePolling, toast } = useApp();
  const timerRef = useRef(null);
  const prevStatus = useRef(null);

  useEffect(() => {
    if (!documentId) return;

    let active = true;
    addPolling(documentId);

    const poll = async () => {
      try {
        const data = await getStatus(documentId);
        if (!active) return;

        // Map document_id to id so AppStore updates the correct item
        const payload = { ...data, id: data.document_id };
        updateDocument(payload);

        // Toast on status transitions
        if (prevStatus.current && prevStatus.current !== data.status) {
          if (data.status === 'completed') toast(`Document processed successfully!`, 'success');
          if (data.status === 'awaiting_review') toast(`Document needs human review.`, 'warn');
          if (data.status === 'rejected') toast(`Document rejected: ${data.message || 'See document for reason.'}`, 'error');
          if (data.status === 'error') toast(`Processing error: ${data.message}`, 'error');
        }
        prevStatus.current = data.status;

        if (!TERMINAL_STATUSES.has(data.status)) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL);
        } else {
          removePolling(documentId);
        }
      } catch (err) {
        if (!active) return;
        console.warn('Polling error for', documentId, err.message);
        timerRef.current = setTimeout(poll, POLL_INTERVAL * 2); // back-off
      }
    };

    poll();

    return () => {
      active = false;
      clearTimeout(timerRef.current);
      removePolling(documentId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);
}
```


---

# Layout components

## `src/components/layout/AppShell.jsx`

```jsx
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
```

## `src/components/layout/Sidebar.jsx`

```jsx
import { useState, useEffect, useCallback } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Upload, Cpu, FileSearch,
  CheckCircle, FileText, Bot, BarChart2,
  ChevronLeft, ChevronRight, Settings, FileCode,
  ClipboardList
} from 'lucide-react';
import { useApp } from '../../store/AppStore';

const navSections = [
  {
    label: 'Main',
    items: [
      { label: 'Dashboard',  icon: LayoutDashboard, to: '/'           },
      { label: 'Upload',     icon: Upload,          to: '/upload'     },
      { label: 'Processing', icon: Cpu,             to: '/processing' },
    ],
  },
  {
    label: 'Data',
    items: [
      { label: 'Extraction', icon: FileSearch,  to: '/extraction' },
      { label: 'Validation', icon: CheckCircle, to: '/validation' },
      { label: 'Documents',  icon: FileText,    to: '/documents'  },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { label: 'Agents',    icon: Bot,      to: '/agents'    },
      { label: 'Analytics', icon: BarChart2, to: '/analytics' },
      { label: 'Templates', icon: FileCode,  to: '/templates' },
    ],
  },
  {
    label: 'Claims',
    items: [
      { label: 'Claim Process', icon: ClipboardList, to: '/claim-process' },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'Settings', icon: Settings, to: '/settings' },
    ],
  },
];

export function Sidebar({ mobileOpen, onMobileClose }) {
  const { reviewDocs, pendingDocs } = useApp();
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebar-collapsed') === 'true'; }
    catch { return false; }
  });

  const toggleCollapse = useCallback(() => {
    setCollapsed((v) => {
      const next = !v;
      try { localStorage.setItem('sidebar-collapsed', String(next)); } catch {}
      return next;
    });
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    if (mobileOpen && onMobileClose) onMobileClose();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sidebarClass = [
    'sidebar',
    collapsed ? 'collapsed' : '',
    mobileOpen ? 'mobile-open' : '',
  ].filter(Boolean).join(' ');

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={onMobileClose} />
      )}

      <aside className={sidebarClass}>
        <div className="sidebar-content">
          {/* ── Logo ── */}
          <div className="logo">
            <div className="logo-mark">
              <div className="logo-icon">
                <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
                  <rect x="3" y="1" width="12" height="16" rx="2" fill="white" fillOpacity="0.15"/>
                  <rect x="3" y="1" width="12" height="16" rx="2" stroke="white" strokeOpacity="0.5" strokeWidth="1"/>
                  <line x1="5.5" y1="5" x2="12.5" y2="5" stroke="white" strokeOpacity="0.7" strokeWidth="1" strokeLinecap="round"/>
                  <line x1="5.5" y1="8" x2="12.5" y2="8" stroke="white" strokeOpacity="0.7" strokeWidth="1" strokeLinecap="round"/>
                  <line x1="5.5" y1="11" x2="10" y2="11" stroke="white" strokeOpacity="0.5" strokeWidth="1" strokeLinecap="round"/>
                  <circle cx="16" cy="16" r="5" fill="var(--accent3)" fillOpacity="0.9"/>
                  <path d="M13.5 16L15.2 17.7L18.5 14" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="logo-text-wrap">
                <div className="logo-text">Intelligent Document</div>
                <div className="logo-text" style={{ marginTop: 1 }}>Processing</div>
                <div className="logo-sub">IDP Platform · v2.0</div>
              </div>
            </div>
          </div>

          {/* ── Navigation ── */}
          {navSections.map((section) => (
            <div key={section.label} className="nav-section">
              <div className="nav-label">{section.label}</div>
              {section.items.map(({ label, icon: Icon, to }) => {
                const badge =
                  label === 'Validation' && reviewDocs.length > 0
                    ? reviewDocs.length
                    : label === 'Processing' && pendingDocs.length > 0
                    ? pendingDocs.length
                    : null;

                return (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    title={collapsed ? label : undefined}
                    className={({ isActive }) =>
                      `nav-item${isActive ? ' active' : ''}`
                    }
                    onClick={onMobileClose}
                  >
                    <Icon size={16} className="nav-icon" strokeWidth={1.75} />
                    <span className="nav-item-label">{label}</span>
                    {badge && <span className="nav-badge">{badge}</span>}
                  </NavLink>
                );
              })}
            </div>
          ))}

          {/* ── Footer ── */}
          <div className="sidebar-footer">
            <div className="agent-status">
              <div className="pulse-dot" />
              <div className="agent-status-text">
                <div style={{ fontSize: 'var(--text-md)', color: 'var(--text)', fontWeight: 600 }}>
                  10 Agents Active
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', marginTop: 1 }}>
                  All systems nominal
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Collapse toggle */}
        <button
          className="sidebar-collapse-btn"
          onClick={toggleCollapse}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed
            ? <ChevronRight size={12} />
            : <ChevronLeft size={12} />
          }
        </button>
      </aside>
    </>
  );
}
```

## `src/components/layout/TopBar.jsx`

```jsx
import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Sun, Moon, User, Menu, ArrowRight } from 'lucide-react';
import { useApp } from '../../store/AppStore';
import { useDocumentList } from '../../hooks/useDocumentList';

const PAGE_META = {
  '/':           { title: 'Dashboard',   sub: 'Overview & live stats' },
  '/upload':     { title: 'Upload',      sub: 'Add documents to the pipeline' },
  '/processing': { title: 'Processing',  sub: 'Live workflow orchestration' },
  '/extraction': { title: 'Extraction',  sub: 'AI-extracted structured data' },
  '/validation': { title: 'Validation',  sub: 'Human review queue' },
  '/documents':  { title: 'Documents',   sub: 'All processed files' },
  '/agents':     { title: 'Agents',      sub: 'Multi-agent system overview' },
  '/analytics':  { title: 'Analytics',   sub: 'Processing metrics & trends' },
  '/settings':   { title: 'Settings',    sub: 'Configure system preferences' },
};

// ── Dark mode helpers ─────────────────────────────
function getInitialTheme() {
  try {
    const stored = localStorage.getItem('idp-theme');
    if (stored) return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('idp-theme', theme); } catch {}
}

export function TopBar({ onMobileMenuToggle }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { reviewDocs } = useApp();
  const { loading } = useDocumentList();

  const meta = PAGE_META[pathname] || { title: 'IDP Platform', sub: '' };

  // ── Dark mode state ──
  const [theme, setTheme] = useState(getInitialTheme);
  useEffect(() => { applyTheme(theme); }, [theme]);
  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
  }, []);

  // ── Notification dropdown ──
  const [notifOpen, setNotifOpen] = useState(false);
  const notifRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const hasNotifs = reviewDocs.length > 0;

  return (
    <div className="topbar">
      <div className="topbar-left">
        {/* Hamburger — mobile only */}
        <button
          className="topbar-hamburger"
          onClick={onMobileMenuToggle}
          aria-label="Open navigation menu"
        >
          <Menu size={16} />
        </button>

        <div className="topbar-breadcrumb">
          <div className="topbar-title">{meta.title}</div>
          {meta.sub && <div className="topbar-sub">{meta.sub}</div>}
        </div>
      </div>

      <div className="topbar-right">
        {/* Loading indicator — only show when actually syncing */}
        {loading && (
          <span style={{
            fontSize: 'var(--text-sm)', color: 'var(--muted)',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span className="spin" style={{
              display: 'inline-block', width: 12, height: 12,
              border: '1.5px solid var(--border)', borderTopColor: 'var(--accent)',
              borderRadius: '50%',
            }} />
            Syncing
          </span>
        )}

        {/* Dark / Light toggle */}
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          id="topbar-theme-toggle"
        >
          {theme === 'dark'
            ? <Sun size={15} strokeWidth={1.75} />
            : <Moon size={15} strokeWidth={1.75} />
          }
        </button>

        {/* Notification bell */}
        <div className="notif-wrapper" ref={notifRef}>
          <button
            className="theme-toggle"
            style={{ position: 'relative' }}
            onClick={() => setNotifOpen((o) => !o)}
            id="topbar-notifications-btn"
            aria-label={`Notifications${hasNotifs ? ` — ${reviewDocs.length} pending` : ''}`}
            title={hasNotifs ? `${reviewDocs.length} document${reviewDocs.length > 1 ? 's' : ''} awaiting review` : 'No notifications'}
          >
            <Bell size={15} strokeWidth={1.75} />
            {hasNotifs && (
              <span style={{
                position: 'absolute', top: 6, right: 6,
                width: 7, height: 7, borderRadius: '50%',
                background: 'var(--warn)',
                boxShadow: '0 0 6px rgba(245,158,11,0.5)',
                border: '1.5px solid var(--surface)',
              }} />
            )}
          </button>

          {/* Dropdown */}
          {notifOpen && (
            <div className="notif-dropdown">
              <div className="notif-header">
                <span>Notifications</span>
                {hasNotifs && (
                  <span className="badge badge-yellow">{reviewDocs.length} pending</span>
                )}
              </div>
              {!hasNotifs ? (
                <div className="notif-empty">
                  <Bell size={20} style={{ opacity: 0.3, marginBottom: 6 }} />
                  <div>All clear — no pending reviews</div>
                </div>
              ) : (
                reviewDocs.slice(0, 5).map((doc) => (
                  <div
                    key={doc.id}
                    className="notif-item"
                    onClick={() => { navigate('/validation'); setNotifOpen(false); }}
                  >
                    <div className="notif-dot" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 'var(--text-md)', fontWeight: 500,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {doc.filename}
                      </div>
                      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 2 }}>
                        Awaiting review
                      </div>
                    </div>
                    <ArrowRight size={12} style={{ color: 'var(--muted)', flexShrink: 0 }} />
                  </div>
                ))
              )}
              {reviewDocs.length > 5 && (
                <div
                  style={{
                    padding: '8px 16px', fontSize: 'var(--text-sm)',
                    color: 'var(--accent)', textAlign: 'center', cursor: 'pointer',
                    borderTop: '1px solid var(--border)',
                  }}
                  onClick={() => { navigate('/validation'); setNotifOpen(false); }}
                >
                  View all {reviewDocs.length} →
                </div>
              )}
            </div>
          )}
        </div>

        {/* User avatar */}
        <div
          id="topbar-user-avatar"
          style={{
            width: 34, height: 34, borderRadius: '50%',
            background: 'var(--grad-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 14px rgba(250,82,15,0.25)',
            border: '2px solid rgba(250,82,15,0.20)',
            cursor: 'pointer',
            flexShrink: 0,
          }}
          title="User settings"
          aria-label="User menu"
        >
          <User size={16} color="white" strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

// Export theme initializer so it can be called on app load
export { applyTheme, getInitialTheme };
```


---

# UI components

## `src/components/ui/ConfidenceBar.jsx`

```jsx
export function ConfidenceBar({ label, value, color }) {
  const pct = Math.round((value || 0) * 100);
  const col =
    pct >= 90 ? 'var(--success)' :
    pct >= 70 ? 'var(--warn)' :
    'var(--danger)';
  const fillColor = color || col;

  return (
    <div className="conf-bar-row">
      <div className="conf-bar-label">
        <span>{label}</span>
        <span style={{ color: fillColor, fontWeight: 600 }}>{pct}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: pct + '%', background: fillColor }} />
      </div>
    </div>
  );
}
```

## `src/components/ui/DonutChart.jsx`

```jsx
import { useEffect, useRef } from 'react';
import { BarChart2 } from 'lucide-react';

const COLORS = ['#6366f1','#06b6d4','#10b981','#f59e0b','#8b5cf6','#ef4444','#3b82f6'];

export function DonutChart({ data = [] }) {
  const canvasRef = useRef(null);
  const total = data.reduce((s, d) => s + d.value, 0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !total) return;
    const ctx = canvas.getContext('2d');
    const cx = canvas.width / 2, cy = canvas.height / 2;
    const r = Math.min(cx, cy) - 6, hole = r * 0.58;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let start = -Math.PI / 2;

    data.forEach((d, i) => {
      const slice = (d.value / total) * 2 * Math.PI;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, start, start + slice);
      ctx.closePath();
      ctx.fillStyle = COLORS[i % COLORS.length];
      ctx.fill();
      start += slice;
    });

    // Cut hole
    ctx.beginPath();
    ctx.arc(cx, cy, hole, 0, 2 * Math.PI);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--card').trim() || '#151826';
    ctx.fill();

    // Center text
    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 16px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(total, cx, cy);
  }, [data, total]);

  if (!total) {
    return (
      <div className="empty-state" style={{ padding: '24px' }}>
        <BarChart2 className="empty-icon" size={36} />
        <div className="empty-sub">No data yet</div>
      </div>
    );
  }

  return (
    <div className="donut-wrap">
      <canvas ref={canvasRef} width={120} height={120} />
      <div className="donut-legend">
        {data.map((d, i) => (
          <div key={d.label} className="legend-item">
            <div className="legend-dot" style={{ background: COLORS[i % COLORS.length] }} />
            <span style={{ color: 'var(--text-dim)' }}>{d.label}</span>
            <span style={{ color: 'var(--muted)', marginLeft: 'auto', marginRight: 0 }}>
              {Math.round((d.value / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## `src/components/ui/Modal.jsx`

```jsx
import { X } from 'lucide-react';

export function Modal({ title, subtitle, onClose, children, footer, wide }) {
  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal${wide ? ' modal-wide' : ''}`}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div className="modal-title">{title}</div>
            {subtitle && <div className="modal-sub">{subtitle}</div>}
          </div>
          {onClose && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={onClose}
              style={{ padding: '4px 8px' }}
            >
              <X size={14} />
            </button>
          )}
        </div>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          {children}
        </div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
```

## `src/components/ui/PipelineSteps.jsx`

```jsx
import { Check, Cpu, Tag, FileSearch, CheckCircle, UserCheck, Package, Shield, Wand2 } from 'lucide-react';

const STEPS = [
  { key: 'intake', label: 'Ingestion', icon: Package },
  { key: 'pre_val', label: 'Quality Check', icon: Shield },
  { key: 'preprocess', label: 'Pre Processing', icon: Wand2 },
  { key: 'classify', label: 'Split & Classification', icon: Tag },
  { key: 'extract', label: 'Extraction', icon: FileSearch },
  { key: 'validate', label: 'Validation', icon: CheckCircle },
  { key: 'review', label: 'Human Review', icon: UserCheck },
  { key: 'output', label: 'Output', icon: Cpu },
];

/**
 * Maps backend status to which step is "running" and which are "done".
 */
function getStepState(status, idx) {
  const order = {
    pending: -1,
    processing: 0,  // intake step
    pre_validating: 1,  // pre-validate step
    preprocessing: 2,  // preprocess step (NEW)
    classifying: 3,  // was 2
    fraud_checking: 3,  // same as classifying (runs in parallel context)
    extracting: 4,  // was 3
    validating: 5,  // was 4
    awaiting_review: 6,  // was 5
    completed: 8,  // all done (8 steps total)
    rejected: -2,
    error: -2,
  };

  const active = order[status] ?? -1;
  if (active === 7) return 'done';
  if (idx < active) return 'done';
  if (idx === active) return 'running';
  return '';
}

export function PipelineSteps({ status }) {
  return (
    <div className="pipeline">
      {STEPS.map(({ key, label, icon: Icon }, idx) => {
        const state = getStepState(status, idx);
        return (
          <div key={key} className={`pipeline-step ${state}`}>
            <div className="step-circle">
              {state === 'done' ? (
                <Check size={15} />
              ) : (
                <Icon size={15} />
              )}
            </div>
            <div className="step-label">{label}</div>
          </div>
        );
      })}
    </div>
  );
}
```

## `src/components/ui/RegionSelector.jsx`

```jsx
import { useState, useRef, useCallback, useEffect } from 'react';
import { Edit2, Image, RotateCcw, MousePointer2 } from 'lucide-react';

/**
 * RegionSelector — Visual drag-to-select crop region picker.
 *
 * Props:
 *   imageUrl   — Object URL or data URL of the sample image
 *   regions    — { signature: {x1,y1,x2,y2}|null, photo: {x1,y1,x2,y2}|null } (percentages 0-100)
 *   onChange   — (regions) => void — called with updated percentage-based regions
 */
export function RegionSelector({ imageUrl, regions, onChange }) {
  const containerRef = useRef(null);
  const imgRef = useRef(null);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [activeMode, setActiveMode] = useState(null); // 'signature' | 'photo' | null
  const [drawing, setDrawing] = useState(false);
  const [startPt, setStartPt] = useState(null);
  const [currentPt, setCurrentPt] = useState(null);

  // Reset loaded state when image changes
  useEffect(() => {
    setImgLoaded(false);
  }, [imageUrl]);

  const MODE_CONFIG = {
    signature: {
      label: 'Signature',
      color: 'rgba(79, 110, 247, 0.25)',
      border: 'rgba(79, 110, 247, 0.8)',
      icon: Edit2,
      btnColor: 'var(--accent)',
      btnBg: 'var(--accent-dim)',
    },
    photo: {
      label: 'Photo',
      color: 'rgba(16, 185, 129, 0.25)',
      border: 'rgba(16, 185, 129, 0.8)',
      icon: Image,
      btnColor: '#10b981',
      btnBg: 'rgba(16, 185, 129, 0.1)',
    },
  };

  // Convert page-relative mouse coords to percentage of natural image dimensions
  const toPercent = useCallback((clientX, clientY) => {
    const img = imgRef.current;
    if (!img) return null;
    const rect = img.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    const pctX = Math.max(0, Math.min(100, (px / rect.width) * 100));
    const pctY = Math.max(0, Math.min(100, (py / rect.height) * 100));
    return { x: Math.round(pctX * 10) / 10, y: Math.round(pctY * 10) / 10 };
  }, []);

  const handleMouseDown = useCallback((e) => {
    if (!activeMode) return;
    e.preventDefault();
    const pt = toPercent(e.clientX, e.clientY);
    if (!pt) return;
    setDrawing(true);
    setStartPt(pt);
    setCurrentPt(pt);
  }, [activeMode, toPercent]);

  const handleMouseMove = useCallback((e) => {
    if (!drawing) return;
    e.preventDefault();
    const pt = toPercent(e.clientX, e.clientY);
    if (pt) setCurrentPt(pt);
  }, [drawing, toPercent]);

  const handleMouseUp = useCallback((e) => {
    if (!drawing || !startPt || !activeMode) {
      setDrawing(false);
      return;
    }
    e.preventDefault();
    const end = toPercent(e.clientX, e.clientY);
    if (!end) { setDrawing(false); return; }

    const x1 = Math.min(startPt.x, end.x);
    const y1 = Math.min(startPt.y, end.y);
    const x2 = Math.max(startPt.x, end.x);
    const y2 = Math.max(startPt.y, end.y);

    // Minimum size check (at least 2% in each dimension)
    if (x2 - x1 < 2 || y2 - y1 < 2) {
      setDrawing(false);
      setStartPt(null);
      setCurrentPt(null);
      return;
    }

    const newRegions = {
      ...regions,
      [activeMode]: { x1: Math.round(x1), y1: Math.round(y1), x2: Math.round(x2), y2: Math.round(y2) },
    };
    onChange(newRegions);
    setDrawing(false);
    setStartPt(null);
    setCurrentPt(null);
    setActiveMode(null); // Deactivate after drawing
  }, [drawing, startPt, activeMode, toPercent, regions, onChange]);

  // Also handle mouse leaving the image area
  const handleMouseLeave = useCallback(() => {
    if (drawing) {
      setDrawing(false);
      setStartPt(null);
      setCurrentPt(null);
    }
  }, [drawing]);

  const handleClearRegion = (mode) => {
    onChange({ ...regions, [mode]: null });
  };

  const handleClearAll = () => {
    onChange({ signature: null, photo: null });
  };

  // Render a region overlay (either saved or being drawn)
  const renderRegion = (mode, box, isDraft = false) => {
    if (!box) return null;
    const cfg = MODE_CONFIG[mode];
    return (
      <div
        key={mode + (isDraft ? '-draft' : '')}
        style={{
          position: 'absolute',
          left: `${box.x1}%`,
          top: `${box.y1}%`,
          width: `${box.x2 - box.x1}%`,
          height: `${box.y2 - box.y1}%`,
          background: cfg.color,
          border: `2px ${isDraft ? 'dashed' : 'solid'} ${cfg.border}`,
          borderRadius: 4,
          pointerEvents: 'none',
          zIndex: 2,
          transition: isDraft ? 'none' : 'all 0.15s ease',
        }}
      >
        <span style={{
          position: 'absolute',
          top: -20,
          left: 0,
          fontSize: 10,
          fontWeight: 700,
          color: cfg.border,
          background: 'rgba(0,0,0,0.7)',
          padding: '1px 6px',
          borderRadius: 3,
          whiteSpace: 'nowrap',
          letterSpacing: 0.5,
        }}>
          {cfg.label}
        </span>
      </div>
    );
  };

  // Draft box while drawing
  const draftBox = drawing && startPt && currentPt ? {
    x1: Math.min(startPt.x, currentPt.x),
    y1: Math.min(startPt.y, currentPt.y),
    x2: Math.max(startPt.x, currentPt.x),
    y2: Math.max(startPt.y, currentPt.y),
  } : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Mode Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginRight: 4 }}>
          Draw region:
        </span>
        {Object.entries(MODE_CONFIG).map(([mode, cfg]) => {
          const Icon = cfg.icon;
          const isActive = activeMode === mode;
          const hasRegion = regions[mode] != null;
          return (
            <div key={mode} style={{ display: 'flex', gap: 4 }}>
              <button
                type="button"
                onClick={() => setActiveMode(isActive ? null : mode)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  fontSize: 11, fontWeight: 600, padding: '5px 10px',
                  borderRadius: 6, border: `1.5px solid ${isActive ? cfg.border : 'var(--border)'}`,
                  background: isActive ? cfg.btnBg : 'transparent',
                  color: isActive ? cfg.btnColor : 'var(--text-dim)',
                  cursor: 'pointer', transition: 'all 0.15s ease',
                }}
              >
                <Icon size={12} />
                {cfg.label}
                {hasRegion && <span style={{ color: '#10b981', marginLeft: 2 }}>✓</span>}
              </button>
              {hasRegion && (
                <button
                  type="button"
                  onClick={() => handleClearRegion(mode)}
                  title={`Clear ${cfg.label}`}
                  style={{
                    display: 'inline-flex', alignItems: 'center',
                    fontSize: 10, padding: '3px 6px', borderRadius: 4,
                    border: '1px solid var(--border)', background: 'transparent',
                    color: 'var(--muted)', cursor: 'pointer',
                  }}
                >
                  ✕
                </button>
              )}
            </div>
          );
        })}

        <div style={{ flex: 1 }} />
        {(regions.signature || regions.photo) && (
          <button
            type="button"
            onClick={handleClearAll}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontSize: 10, fontWeight: 600, padding: '4px 8px',
              borderRadius: 4, border: '1px solid var(--border)',
              background: 'transparent', color: 'var(--muted)', cursor: 'pointer',
            }}
          >
            <RotateCcw size={10} /> Reset All
          </button>
        )}
      </div>

      {/* Active mode instruction */}
      {activeMode && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 12px', borderRadius: 6,
          background: MODE_CONFIG[activeMode].color,
          border: `1px solid ${MODE_CONFIG[activeMode].border}`,
          fontSize: 11, fontWeight: 600, color: MODE_CONFIG[activeMode].border,
        }}>
          <MousePointer2 size={12} />
          Click and drag on the image to select the <strong>{MODE_CONFIG[activeMode].label}</strong> region
        </div>
      )}

      {/* Image + Overlay Container */}
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          borderRadius: 'var(--radius)',
          overflow: 'hidden',
          border: activeMode ? `2px solid ${MODE_CONFIG[activeMode].border}` : '2px solid var(--border)',
          cursor: activeMode ? 'crosshair' : 'default',
          userSelect: 'none',
          transition: 'border-color 0.2s ease',
          background: 'var(--surface-sunken)',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      >
        <img
          ref={imgRef}
          src={imageUrl}
          alt="Sample document"
          onLoad={() => setImgLoaded(true)}
          draggable={false}
          style={{
            display: 'block',
            width: '100%',
            height: 'auto',
            maxHeight: 500,
            objectFit: 'contain',
            pointerEvents: 'none',
          }}
        />

        {/* Overlay for drawn regions */}
        {imgLoaded && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            pointerEvents: 'none',
          }}>
            {regions.signature && renderRegion('signature', regions.signature)}
            {regions.photo && renderRegion('photo', regions.photo)}
            {draftBox && activeMode && renderRegion(activeMode, draftBox, true)}
          </div>
        )}

        {/* Loading state */}
        {!imgLoaded && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 60, color: 'var(--muted)', fontSize: 12,
          }}>
            Loading image preview...
          </div>
        )}
      </div>

      {/* Coordinate summary */}
      {(regions.signature || regions.photo) && (
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
          fontSize: 10, color: 'var(--muted)',
        }}>
          {regions.signature && (
            <div style={{
              padding: '6px 10px', borderRadius: 4,
              background: 'rgba(79, 110, 247, 0.06)',
              border: '1px solid rgba(79, 110, 247, 0.15)',
            }}>
              <strong style={{ color: 'var(--accent)' }}>Signature:</strong>{' '}
              ({regions.signature.x1}%, {regions.signature.y1}%) → ({regions.signature.x2}%, {regions.signature.y2}%)
            </div>
          )}
          {regions.photo && (
            <div style={{
              padding: '6px 10px', borderRadius: 4,
              background: 'rgba(16, 185, 129, 0.06)',
              border: '1px solid rgba(16, 185, 129, 0.15)',
            }}>
              <strong style={{ color: '#10b981' }}>Photo:</strong>{' '}
              ({regions.photo.x1}%, {regions.photo.y1}%) → ({regions.photo.x2}%, {regions.photo.y2}%)
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

## `src/components/ui/StatCard.jsx`

```jsx
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const DELTA_ICONS = {
  up:      <TrendingUp  size={11} />,
  down:    <TrendingDown size={11} />,
  warn:    <TrendingDown size={11} />,
  neutral: <Minus       size={11} />,
};

/**
 * StatCard — premium metric card with Lucide icon support
 *
 * @param {ReactNode} icon        — Lucide icon component (e.g. <FileText size={18} />)
 * @param {string}    iconVariant — 'accent' | 'success' | 'warn' | 'danger' | 'info'
 * @param {string}    label       — metric label
 * @param {any}       value       — primary metric value
 * @param {string}    unit        — optional unit suffix (e.g. '%')
 * @param {string}    delta       — secondary descriptive text
 * @param {string}    deltaType   — 'up' | 'down' | 'warn' | 'neutral'
 */
export function StatCard({
  icon,
  iconVariant = 'accent',
  label,
  value,
  unit = '',
  delta,
  deltaType = 'neutral',
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${iconVariant}`}>
        {icon}
      </div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {delta && (
        <div className={`stat-delta ${deltaType}`}>
          {DELTA_ICONS[deltaType]}
          {delta}
        </div>
      )}
    </div>
  );
}
```

## `src/components/ui/StatusBadge.jsx`

```jsx
import {
  Upload, Bot, FileSearch, CheckCircle, AlertTriangle, Check, X, AlertCircle, Shield, Wand2
} from 'lucide-react';

const STATUS_MAP = {
  pending:          { label: 'Pending',          cls: 'badge-gray',   icon: null },
  pre_validating:   { label: 'Quality Check',    cls: 'badge-cyan',   icon: Shield },
  preprocessing:    { label: 'Pre Processing',   cls: 'badge-purple', icon: Wand2 },
  processing:       { label: 'Ingestion',        cls: 'badge-blue',   icon: Upload },
  classifying:      { label: 'Classification',   cls: 'badge-blue',   icon: Bot },
  fraud_checking:   { label: 'Fraud Checking',   cls: 'badge-blue',   icon: Shield },
  extracting:       { label: 'Extraction',       cls: 'badge-blue',   icon: FileSearch },

  validating:       { label: 'Validation',       cls: 'badge-blue',   icon: CheckCircle },
  awaiting_review:  { label: 'Human Review',     cls: 'badge-yellow', icon: AlertTriangle },
  duplicate:        { label: 'Duplicate',        cls: 'badge-yellow', icon: AlertTriangle },
  completed:        { label: 'Completed',        cls: 'badge-green',  icon: Check },
  rejected:         { label: 'Rejected',         cls: 'badge-red',    icon: X },
  failed:           { label: 'Failed',           cls: 'badge-red',    icon: AlertCircle },
  error:            { label: 'Error',            cls: 'badge-red',    icon: AlertCircle },
  deleted:          { label: 'Deleted',          cls: 'badge-gray',   icon: null },
};


export function StatusBadge({ status }) {
  const s = STATUS_MAP[status] || { label: status, cls: 'badge-gray', icon: null };
  const Icon = s.icon;
  return (
    <span className={`badge ${s.cls}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {Icon && <Icon size={11} strokeWidth={2.5} />}
      {s.label}
    </span>
  );
}
```

## `src/components/ui/ToastContainer.jsx`

```jsx
import { useApp } from '../../store/AppStore';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

const ICONS = {
  success: <CheckCircle size={16} color="var(--success)" />,
  error:   <AlertCircle size={16} color="var(--danger)" />,
  info:    <Info        size={16} color="var(--accent)" />,
  warn:    <AlertTriangle size={16} color="var(--warn)" />,
};

export function ToastContainer() {
  const { toasts, dismissToast } = useApp();

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`}>
          <span className="toast-icon">{ICONS[t.type] || ICONS.info}</span>
          <span className="toast-msg">{t.msg}</span>
          <button className="toast-close" onClick={() => dismissToast(t.id)}>
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}
```


---

# Pages

## `src/pages/claimData.js`

```js
/* ─── Claim Types ─── */
export const CLAIM_TYPES = [
  'Health Insurance',
  'Motor Insurance',
  'Life Insurance',
  'Travel Insurance',
  'Property Insurance',
  'Fire Insurance',
  'Marine Insurance',
];

export const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

export const DEFAULT_DOCUMENTS = [
  { name: 'Aadhaar Card', present: true },
  { name: 'PAN Card', present: true },
];

/* ─── Sample Claims ─── */
export const SAMPLE_CLAIMS = [
  {
    id: 'CLM-2026-001',
    claimantName: 'Priya S. Kapoor',
    claimType: 'Health Insurance',
    amount: 245000,
    dateSubmitted: '2026-07-08',
    priority: 'high',
    status: 'pending',
    policyNumber: 'HLT-9827-4501',
    description: 'Hospitalization claim for cardiac procedure at Apollo Hospital, Mumbai.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Hospital Discharge Summary', present: true },
      { name: 'Medical Bills', present: true },
      { name: 'Prescription Records', present: true },
    ],
  },
  {
    id: 'CLM-2026-002',
    claimantName: 'Rajesh M. Gupta',
    claimType: 'Motor Insurance',
    amount: 87500,
    dateSubmitted: '2026-07-07',
    priority: 'medium',
    status: 'pending',
    policyNumber: 'MTR-3341-7820',
    description: 'Vehicle damage claim due to road accident on NH-48, Pune.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: false },
      { name: 'FIR Copy', present: true },
      { name: 'Vehicle Registration', present: true },
      { name: 'Repair Estimate', present: false },
    ],
  },
  {
    id: 'CLM-2026-003',
    claimantName: 'Ananya R. Sharma',
    claimType: 'Life Insurance',
    amount: 1500000,
    dateSubmitted: '2026-07-06',
    priority: 'urgent',
    status: 'pending',
    policyNumber: 'LIF-7752-0093',
    description: "Death benefit claim — policyholder's nominee filing for term life payout.",
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Death Certificate', present: true },
      { name: 'Nominee ID Proof', present: true },
      { name: 'Policy Document', present: true },
      { name: 'Bank Account Proof', present: true },
    ],
  },
  {
    id: 'CLM-2026-004',
    claimantName: 'Vikram D. Patel',
    claimType: 'Health Insurance',
    amount: 62000,
    dateSubmitted: '2026-07-05',
    priority: 'low',
    status: 'pending',
    policyNumber: 'HLT-4420-8816',
    description: 'OPD reimbursement claim for dental surgery at Max Healthcare.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: false },
      { name: 'Hospital Bills', present: true },
      { name: 'Prescription Records', present: false },
      { name: "Doctor's Referral Letter", present: false },
    ],
  },
  {
    id: 'CLM-2026-005',
    claimantName: 'Meera K. Joshi',
    claimType: 'Travel Insurance',
    amount: 180000,
    dateSubmitted: '2026-07-04',
    priority: 'medium',
    status: 'pending',
    policyNumber: 'TRV-6618-2234',
    description: 'Medical emergency during international trip to Thailand — hospitalization reimbursement.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'Passport Copy', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Hospital Bills (Foreign)', present: true },
      { name: 'Travel Itinerary', present: true },
      { name: 'Currency Exchange Receipts', present: false },
    ],
  },
  {
    id: 'CLM-2026-006',
    claimantName: 'Arjun B. Nair',
    claimType: 'Property Insurance',
    amount: 520000,
    dateSubmitted: '2026-07-03',
    priority: 'high',
    status: 'pending',
    policyNumber: 'PRP-1190-5567',
    description: 'Fire damage claim for commercial property in Kochi industrial area.',
    documents: [
      { name: 'Aadhaar Card', present: true },
      { name: 'PAN Card', present: true },
      { name: 'Fire Brigade Report', present: true },
      { name: 'Property Valuation Report', present: true },
      { name: 'Insurance Policy Copy', present: true },
      { name: 'Photographs of Damage', present: true },
    ],
  },
];

/* ─── Workflow Steps ─── */
export const INITIAL_STEPS = [
  {
    id: 'case-setup',
    label: 'Claim Case Setup',
    summary: 'Initializes claim case file, verifies policy validity, and loads claimant profile.',
    outputKind: 'json',
    agentThought:
      "I need to first verify that the policy number is valid and active. Let me cross-reference the claimant's details with our policyholder database. I'm checking the policy inception date, premium payment history, and coverage limits. The policy HLT-9827-4501 is active with premiums paid through July 2026. The claimant Priya S. Kapoor matches the policyholder on record. Coverage type is comprehensive health with a sum insured of ₹10,00,000. No prior claims in the last 12 months. Waiting period of 30 days has been satisfied. I'll now set up the case file and proceed to validation.",
    output: {
      case_id: 'CLM-2026-001',
      policy_number: 'HLT-9827-4501',
      policy_status: 'active',
      claimant: 'Priya S. Kapoor',
      claim_type: 'Health Insurance — Hospitalization',
      sum_insured: 1000000,
      claim_amount: 245000,
      premium_status: 'paid_up',
      waiting_period: 'satisfied',
      prior_claims_12m: 0,
      documents_received: 5,
    },
  },
  {
    id: 'integrity-validator',
    label: 'Claim Integrity Validator',
    summary: 'Validates document authenticity, cross-references data, and detects anomalies.',
    outputKind: 'json',
    agentThought:
      "Starting integrity validation. I'll examine each submitted document for authenticity markers. The Aadhaar Card shows valid QR code pattern and UIDAI format — no signs of tampering. PAN Card format matches Income Tax Department standards with correct checksum. Hospital discharge summary has official Apollo Hospital letterhead with registration number verified against hospital registry. Medical bills contain sequential invoice numbers consistent with Apollo Hospital's billing system. Prescription records bear valid MCI registration numbers for the attending physicians. Cross-referencing claimant identity: name and date of birth match across all documents. Address on Aadhaar aligns with policy records. No duplicate claim submissions detected in the system. Document timestamps are chronologically consistent — admission date precedes discharge, prescriptions dated during hospitalization period. Overall integrity assessment: PASS with high confidence.",
    output: {
      overall_integrity: 'PASS',
      document_verification: {
        aadhaar_card: { authentic: true, tamper_score: 0.01 },
        pan_card: { authentic: true, tamper_score: 0.02 },
        discharge_summary: { authentic: true, tamper_score: 0.03 },
        medical_bills: { authentic: true, tamper_score: 0.01 },
        prescriptions: { authentic: true, tamper_score: 0.02 },
      },
      identity_cross_match: true,
      duplicate_claim_check: 'no_duplicates',
      chronological_consistency: true,
      anomaly_flags: [],
    },
  },
  {
    id: 'medical-validator',
    label: 'Medical Validator',
    summary: 'Validates medical diagnosis, treatment protocols, and clinical necessity.',
    outputKind: 'json',
    agentThought:
      "Analyzing the medical documentation for clinical validity. The discharge summary indicates a diagnosis of acute coronary syndrome (ACS) — ICD-10 code I21.9. The patient presented with chest pain and elevated troponin levels, which is consistent with the diagnosis. Treatment involved percutaneous coronary intervention (PCI) with a drug-eluting stent placement — this is the standard of care for this condition. The 4-day hospitalization duration (July 4-8, 2026) is within normal range for PCI procedures. Medications prescribed post-discharge include dual antiplatelet therapy (Aspirin + Clopidogrel), statin, and beta-blocker — all consistent with ACC/AHA guidelines for post-ACS management. The attending cardiologist Dr. R. Mehta has MCI registration MH-12847 which I've verified as valid. ICU stay of 2 days post-procedure is clinically appropriate. Lab work shows improving cardiac markers during hospitalization. No red flags for unnecessary procedures or extended stay. Medical necessity: CONFIRMED.",
    output: {
      diagnosis: 'Acute Coronary Syndrome (I21.9)',
      procedure: 'Percutaneous Coronary Intervention (PCI) with DES',
      clinical_necessity: 'confirmed',
      treatment_guideline_compliance: 'ACC/AHA compliant',
      hospitalization_duration: '4 days (appropriate)',
      icu_days: 2,
      attending_physician: 'Dr. R. Mehta (MCI: MH-12847)',
      physician_verified: true,
      prescribed_medications: ['Aspirin', 'Clopidogrel', 'Atorvastatin', 'Metoprolol'],
      lab_trend: 'improving cardiac markers',
      medical_necessity_score: 0.96,
    },
  },
  {
    id: 'treatment-validator',
    label: 'Treatment Validator',
    summary: 'Validates treatment costs, procedure codes, and billing accuracy.',
    outputKind: 'json',
    agentThought:
      "Now I'll validate the financial aspects of the treatment. The total claim amount is ₹2,45,000. Breaking it down: Room charges (₹8,000/day × 4 days = ₹32,000) — this is within the policy's room rent limit of ₹10,000/day. ICU charges (₹15,000/day × 2 days = ₹30,000) — within network hospital ICU rates. PCI procedure with drug-eluting stent: ₹1,20,000 — I'm cross-referencing with the NPPA-capped stent price and Apollo Hospital's standard procedure rate. The stent cost is within the government-mandated ceiling price. Investigation charges (Echo, Angiography, Blood work): ₹28,000 — consistent with standard diagnostic pricing. Medication charges: ₹15,000 — aligns with prescribed drugs and hospital pharmacy rates. Surgeon and anesthesiologist fees: ₹20,000 — within CGHS/NABH benchmark rates. No billing anomalies detected — all procedure codes map correctly to the treatments documented. The sub-limits under the policy are not breached. One minor observation: the consumables charge of ₹12,000 is slightly above average but within acceptable variance (15%). Billing validation: PASS.",
    output: {
      total_claimed: 245000,
      breakdown: {
        room_charges: 32000,
        icu_charges: 30000,
        procedure_stent: 120000,
        diagnostics: 28000,
        medications: 15000,
        surgeon_fees: 20000,
      },
      room_rent_within_limit: true,
      stent_price_compliance: 'within NPPA ceiling',
      procedure_code_match: true,
      billing_anomalies: 0,
      cost_benchmark: 'within_range',
      consumables_variance: '15% above avg (acceptable)',
      sub_limit_breach: false,
      billing_validation: 'PASS',
    },
  },
  {
    id: 'disability-mgmt',
    label: 'Disability Management',
    summary: 'Assesses post-treatment disability, recovery timeline, and rehabilitation needs.',
    outputKind: 'json',
    agentThought:
      'Evaluating post-treatment disability and recovery trajectory. Based on the discharge summary and post-operative notes, the patient underwent successful PCI with good angiographic result — TIMI 3 flow achieved. Expected recovery timeline: The patient should be able to resume light activities within 1-2 weeks and return to normal work within 4-6 weeks. Cardiac rehabilitation is recommended — Phase I (in-hospital) was completed, Phase II (outpatient supervised exercise) should begin 2 weeks post-discharge. No permanent disability is anticipated from this procedure — ejection fraction on discharge echo was 52% (mildly reduced but expected to improve with medical therapy). The patient will need cardiac follow-up at 1 month, 3 months, and 6 months. Dual antiplatelet therapy should continue for minimum 12 months. No occupational restrictions beyond avoiding heavy physical exertion for 6 weeks. This is a temporary disability case with full recovery expected. No additional disability benefits applicable under the current policy terms. Recovery prognosis: FAVORABLE.',
    output: {
      disability_type: 'temporary',
      recovery_timeline: '4-6 weeks to full activity',
      permanent_disability: false,
      ejection_fraction: '52% (mildly reduced, improving)',
      cardiac_rehab: 'Phase II recommended',
      work_restriction: '6 weeks — no heavy exertion',
      follow_up_schedule: ['1 month', '3 months', '6 months'],
      antiplatelet_duration: '12 months minimum',
      prognosis: 'favorable',
      disability_benefit_applicable: false,
      recovery_score: 0.88,
    },
  },
  {
    id: 'litigation-validator',
    label: 'Litigation Validator',
    summary: 'Assesses legal risk, policy exclusions, regulatory compliance, and fraud indicators.',
    outputKind: 'json',
    agentThought:
      "Conducting litigation risk assessment and regulatory compliance check. First, checking policy exclusions: Pre-existing disease clause — the claimant's policy has completed the 4-year waiting period for pre-existing conditions, so even if coronary artery disease was pre-existing, it's now covered. The policy does not have any specific cardiac exclusion riders. Checking for moral hazard: No pattern of frequent claims, no history of claim disputes, and the claimant has been with the insurer for 6 years with consistent premium payments. IRDAI compliance check: The claim is within the timeline (filed within 24 hours of discharge as required), all mandatory documents are submitted, and the hospital is within the approved network. Third-party liability assessment: This is a medical event, not an accident, so no third-party recovery applies. Anti-fraud screening: Cross-referencing with the Insurance Information Bureau (IIB) — no fraud flags on the claimant, no suspicious patterns with the hospital or physician. Legal risk assessment: Very low. The claim is straightforward with complete documentation, valid medical necessity, and no exclusion triggers. Recommendation: No legal hold required, standard processing pathway appropriate. Litigation risk: LOW.",
    output: {
      pre_existing_clause: 'cleared (4-year waiting satisfied)',
      policy_exclusions_triggered: [],
      moral_hazard_indicators: 'none',
      irdai_compliance: 'fully_compliant',
      claim_filing_timeline: 'within 24 hours',
      third_party_liability: 'not_applicable',
      iib_fraud_flags: 0,
      legal_hold_required: false,
      regulatory_risk: 'low',
      litigation_risk_score: 0.05,
      recommendation: 'standard processing — no legal review needed',
    },
  },
];

export const STEP_DURATIONS = {
  'case-setup': 1200,
  'integrity-validator': 2200,
  'medical-validator': 2800,
  'treatment-validator': 2400,
  'disability-mgmt': 2000,
  'litigation-validator': 1800,
};

export function stepDuration(id) {
  return STEP_DURATIONS[id] ?? 1500;
}

/* ─── Completion Summary Data ─── */
export const PROS = [
  'Policy is active with continuous premium payments for 6 years — strong policyholder history',
  'All 5 submitted documents pass authenticity checks with near-zero tamper scores',
  'Medical diagnosis (ACS) is well-documented with supporting lab results and imaging',
  'Treatment follows ACC/AHA clinical guidelines — PCI with DES is standard of care',
  'Billing amounts are within NPPA ceilings and CGHS/NABH benchmark rates',
  'No prior claims in 12 months — no pattern of excessive utilization',
  'Pre-existing disease waiting period fully satisfied (4+ years)',
  'Hospital is within approved network — no out-of-network complications',
  'No fraud indicators flagged by IIB or internal anomaly detection',
  'Claim filed within 24 hours of discharge — full IRDAI timeline compliance',
];

export const CONS = [
  'Consumables charges are 15% above average (₹12,000) — within tolerance but notable',
  'Ejection fraction at 52% indicates mildly reduced cardiac function post-procedure',
  'Patient will require ongoing cardiac medication for minimum 12 months — future claim risk',
  'Single coronary event may indicate underlying cardiovascular disease — potential for recurrence',
];
```

## `src/pages/Dashboard.jsx`

```jsx
import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, ArrowRight, FileText, Target, Clock, AlertCircle,
  CheckCircle2, Loader2, Activity
} from 'lucide-react';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatCard } from '../components/ui/StatCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { DonutChart } from '../components/ui/DonutChart';
import { PipelineSteps } from '../components/ui/PipelineSteps';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';

// Status → activity dot color
const STATUS_COLORS = {
  completed:       'var(--success)',
  awaiting_review: 'var(--warn)',
  error:           'var(--danger)',
  pre_validating:  '#0891b2',
  preprocessing:   'var(--accent2)',
  processing:      'var(--accent)',
  classifying:     'var(--accent)',
  extracting:      'var(--accent)',
  validating:      'var(--accent)',
  pending:         'var(--muted)',
  rejected:        'var(--danger)',
  failed:          'var(--danger)',
};

const STATUS_LABELS = {
  completed:       'Completed',
  awaiting_review: 'Human Review',
  error:           'Error',
  pre_validating:  'Quality Check',
  preprocessing:   'Pre Processing',
  processing:      'Ingestion',
  classifying:     'Classification',
  extracting:      'Extraction',
  validating:      'Validation',
  pending:         'Queued',
  rejected:        'Rejected',
  failed:          'Failed',
};

export function Dashboard() {
  const { documents, reviewDocs, pendingDocs, completedDocs } = useApp();
  const { refresh, loading } = useDocumentList();
  const navigate = useNavigate();

  useEffect(() => { refresh(); }, []);

  // Auto-refresh every 10s
  useEffect(() => {
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, [refresh]);

  // ── Computed stats ──────────────────────────────
  const totalCount  = documents.length;
  const errorCount  = documents.filter((d) => d.status === 'error').length;
  const successRate = totalCount > 0
    ? Math.round((completedDocs.length / totalCount) * 100)
    : 0;

  // Document type distribution for donut
  const typeData = useMemo(() => {
    const map = {};
    documents.forEach((d) => {
      if (d.doc_type) map[d.doc_type] = (map[d.doc_type] || 0) + 1;
    });
    return Object.entries(map).map(([label, value]) => ({ label, value }));
  }, [documents]);

  // Most recent active doc for pipeline display
  const activeDoc = pendingDocs[0] || completedDocs[0];

  // Processing status breakdown
  const confBars = [
    { label: 'Completed',   value: completedDocs.length / Math.max(totalCount, 1) },
    { label: 'In Review',   value: reviewDocs.length   / Math.max(totalCount, 1) },
    { label: 'Processing',  value: pendingDocs.length  / Math.max(totalCount, 1) },
    { label: 'Errors',      value: errorCount          / Math.max(totalCount, 1) },
  ];

  // Recent activity feed (last 8 docs sorted by most recent)
  const recentDocs = useMemo(() =>
    [...documents].slice(0, 8),
  [documents]);

  return (
    <div className="page">
      {/* ── Mistral-style editorial hero header ── */}
      <div className="page-hero">
        <div className="page-hero-eyebrow">IDP Platform · v2.0</div>
        <div className="page-hero-title">
          {loading ? 'Loading…' : `${totalCount.toLocaleString()} document${totalCount !== 1 ? 's' : ''} processed`}
        </div>
        <div className="page-hero-sub">
          {successRate}% success · {reviewDocs.length} pending review · {errorCount > 0 ? `${errorCount} errors` : 'No errors'}
        </div>
      </div>

      {/* ── Stat Cards ── */}
      <div className="stats-row">
        <StatCard
          icon={<FileText size={18} />}
          iconVariant="accent"
          label="Total Documents"
          value={loading ? '—' : totalCount.toLocaleString()}
          delta={pendingDocs.length > 0 ? `${pendingDocs.length} in pipeline` : 'Queue empty'}
          deltaType={pendingDocs.length > 0 ? 'warn' : 'neutral'}
        />
        <StatCard
          icon={<Target size={18} />}
          iconVariant="success"
          label="Success Rate"
          value={loading ? '—' : successRate}
          unit="%"
          delta={`${completedDocs.length} completed`}
          deltaType="up"
        />
        <StatCard
          icon={<Clock size={18} />}
          iconVariant="warn"
          label="Pending Review"
          value={loading ? '—' : reviewDocs.length}
          delta={reviewDocs.length > 0 ? 'Action required' : 'All clear'}
          deltaType={reviewDocs.length > 0 ? 'warn' : 'up'}
        />
        <StatCard
          icon={<AlertCircle size={18} />}
          iconVariant={errorCount > 0 ? 'danger' : 'success'}
          label="Errors"
          value={loading ? '—' : errorCount}
          delta={errorCount > 0 ? 'Needs attention' : 'No errors'}
          deltaType={errorCount > 0 ? 'down' : 'up'}
        />
      </div>

      {/* ── Recent Docs + Chart ── */}
      <div className="grid-2">
        {/* Recent documents table */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Recent Documents</div>
              <div className="card-sub">Latest processing queue</div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/documents')}>
              View All <ArrowRight size={12} />
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon-wrap">
                <FileText size={28} />
              </div>
              <div className="empty-title">No documents yet</div>
              <div className="empty-sub">Upload a document to get started with the AI pipeline</div>
              <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/upload')}>
                <Upload size={13} /> Upload Document
              </button>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {recentDocs.map((doc) => (
                    <tr
                      key={doc.id}
                      onClick={() => navigate('/extraction', { state: { docId: doc.id } })}
                    >
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <FileText size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                          <span style={{ fontSize: 'var(--text-md)' }}>{doc.filename}</span>
                        </div>
                      </td>
                      <td>
                        {doc.doc_type ? (
                          <span className="badge badge-cyan">{doc.doc_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                        ) : (
                          <span style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>—</span>
                        )}
                      </td>
                      <td><StatusBadge status={doc.status} /></td>
                      <td style={{ width: 32 }}>
                        <ArrowRight size={13} className="row-arrow" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Donut chart */}
          <div className="card-data card" style={{ marginBottom: 0 }}>
            <div className="card-header">
              <div>
                <div className="card-title">Document Types</div>
                <div className="card-sub">Distribution across all docs</div>
              </div>
            </div>
            <DonutChart data={typeData} />
          </div>
        </div>
      </div>

      {/* ── Active Pipeline ── */}
      {activeDoc && (
        <div className="card card-accent" style={{ marginTop: 16 }}>
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Activity size={15} style={{ color: 'var(--accent)' }} />
                Active Pipeline
              </div>
              <div className="card-sub">
                Processing: <strong style={{ color: 'var(--accent)' }}>{activeDoc.filename}</strong>
              </div>
            </div>
            <div className="chip">
              Live <span className="pulse-dot" style={{ width: 6, height: 6, marginLeft: 6, display: 'inline-block' }} />
            </div>
          </div>
          <PipelineSteps status={activeDoc.status} />
        </div>
      )}

      {/* ── Status breakdown + Activity feed ── */}
      <div className="grid-2" style={{ marginTop: activeDoc ? 0 : 16 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Processing Status Breakdown</div>
          </div>
          {confBars.map((b) => (
            <ConfidenceBar key={b.label} label={b.label} value={b.value} />
          ))}
        </div>

        {/* Recent Activity Feed */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Recent Activity</div>
            <div className="card-sub" style={{ marginTop: 0 }}>{recentDocs.length} documents</div>
          </div>

          {documents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)', fontSize: 'var(--text-md)' }}>
              No activity yet
            </div>
          ) : (
            <div className="activity-feed">
              {recentDocs.slice(0, 6).map((doc) => (
                <div
                  key={doc.id}
                  className="activity-item"
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate('/extraction', { state: { docId: doc.id } })}
                >
                  <div
                    className="activity-dot"
                    style={{ background: STATUS_COLORS[doc.status] || 'var(--muted)' }}
                  />
                  <div className="activity-content">
                    <div className="activity-title">{doc.filename}</div>
                    <div className="activity-meta">
                      {STATUS_LABELS[doc.status] || doc.status}
                      {doc.doc_type && ` · ${doc.doc_type}`}
                    </div>
                  </div>
                  <ArrowRight size={12} style={{ color: 'var(--muted)', flexShrink: 0 }} />
                </div>
              ))}
            </div>
          )}

          {/* Quick action if pending reviews */}
          {reviewDocs.length > 0 && (
            <button
              className="btn btn-ghost"
              style={{
                width: '100%', marginTop: 12,
                borderColor: 'var(--warn)', color: 'var(--warn)',
              }}
              onClick={() => navigate('/validation')}
            >
              <Clock size={13} />
              Review {reviewDocs.length} Pending Document{reviewDocs.length > 1 ? 's' : ''}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
```

## `src/pages/Upload.jsx`

```jsx
import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud, X, FileText, Image, File,
  CheckCircle2, ScanSearch, Brain, ShieldCheck, UserCheck, Share2,
  XCircle, Layers, RefreshCw, AlertTriangle, Zap,
} from 'lucide-react';
import { uploadDocumentsBatch } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentPoller } from '../hooks/useDocumentPoller';

// ─── Constants ────────────────────────────────────────────────────────────────
const ALLOWED = {
  'application/pdf': { ext: 'PDF', icon: FileText, color: '#ef4444' },
  'image/jpeg':      { ext: 'JPG', icon: Image,    color: '#f59e0b' },
  'image/png':       { ext: 'PNG', icon: Image,    color: '#10b981' },
  'image/webp':      { ext: 'WEBP', icon: Image,   color: '#06b6d4' },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                     { ext: 'DOCX', icon: File,    color: '#3b82f6' },
};
const MAX_BATCH = 20;

// ─── QueueItem ────────────────────────────────────────────────────────────────
function QueueItem({ item, onRemove, locked }) {
  const meta   = ALLOWED[item.file.type] || {};
  const Icon   = meta.icon || File;
  const isDone    = item.status === 'done';
  const isError   = item.status === 'error';
  const isUploading = item.status === 'uploading';

  const thumbStyle = isDone
    ? { background: 'var(--success-dim)', borderColor: 'var(--success-border)' }
    : isError
    ? { background: 'var(--danger-dim)', borderColor: 'var(--danger-border)' }
    : isUploading
    ? { background: 'var(--accent-dim)', borderColor: 'rgba(79,110,247,0.3)' }
    : {};

  const iconColor = isDone ? 'var(--success)'
    : isError      ? 'var(--danger)'
    : isUploading  ? 'var(--accent)'
    : (meta.color  || 'var(--accent)');

  return (
    <div
      className="doc-card"
      style={
        isDone  ? { borderColor: 'var(--success-border)', background: 'rgba(16,185,129,0.03)' }
        : isError ? { borderColor: 'var(--danger-border)', background: 'rgba(239,68,68,0.03)' }
        : {}
      }
    >
      {/* Thumb */}
      <div className="doc-thumb" style={thumbStyle}>
        <Icon size={18} color={iconColor} />
      </div>

      {/* Info */}
      <div className="doc-info">
        <div className="doc-name">{item.file.name}</div>
        <div className="doc-meta">
          {(item.file.size / 1024).toFixed(0)} KB
          {meta.ext && <span style={{ marginLeft: 6, opacity: 0.7 }}>· {meta.ext}</span>}
          {isError && (
            <span style={{ color: 'var(--danger)', marginLeft: 8 }}>
              <AlertTriangle size={10} style={{ display: 'inline', marginRight: 3 }} />
              {item.error}
            </span>
          )}
        </div>
      </div>

      {/* Status + remove */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
        {item.status === 'ready' && (
          <span className="badge badge-gray">Ready</span>
        )}
        {isUploading && (
          <span className="badge badge-blue" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block', width: 10, height: 10,
                border: '1.5px solid rgba(37,99,235,0.3)', borderTopColor: '#2563eb',
                borderRadius: '50%', animation: 'spin 0.8s linear infinite',
              }}
            />
            In Batch
          </span>
        )}
        {isDone && (
          <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <CheckCircle2 size={11} />
            Submitted
          </span>
        )}
        {isError && <span className="badge badge-red">Failed</span>}

        {!locked && item.status !== 'uploading' && (
          <button
            onClick={() => onRemove(item.id)}
            title="Remove"
            style={{
              background: 'none', border: 'none',
              color: 'var(--muted)', cursor: 'pointer', padding: 4,
              borderRadius: 4, lineHeight: 0,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--danger)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
          >
            <X size={13} />
          </button>
        )}
      </div>
    </div>
  );
}

// ─── DocPoller — mounts one poller per successfully uploaded doc id ─────────
function DocPoller({ docId }) {
  useDocumentPoller(docId);
  return null;
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function Upload() {
  const [isDragover, setIsDragover]     = useState(false);
  const [queue, setQueue]               = useState([]);
  const [uploading, setUploading]       = useState(false);
  const [batchProgress, setBatchProgress] = useState(0);
  const [batchResult, setBatchResult]   = useState(null);
  const [uploadedIds, setUploadedIds]   = useState([]);

  const fileInputRef = useRef(null);
  const itemIdRef    = useRef(0);
  const { addDocument, toast } = useApp();
  const navigate = useNavigate();

  // ── File queue management ──────────────────────────────────────────────────
  const addFiles = useCallback((files) => {
    const newItems = Array.from(files)
      .filter((f) => {
        if (!ALLOWED[f.type]) {
          toast(`Unsupported type: ${f.name}`, 'warn');
          return false;
        }
        return true;
      })
      .map((f) => ({
        id:       ++itemIdRef.current,
        file:     f,
        status:   'ready',
        error:    null,
        documentId: null,
      }));

    setQueue((q) => {
      const combined = [...q, ...newItems];
      if (combined.length > MAX_BATCH) {
        toast(`Batch limit is ${MAX_BATCH} files. Extra files ignored.`, 'warn');
        return combined.slice(0, MAX_BATCH);
      }
      return combined;
    });
  }, [toast]);

  const removeItem = (id) => setQueue((q) => q.filter((i) => i.id !== id));
  const clearAll   = () => { if (!uploading) { setQueue([]); setBatchResult(null); } };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragover(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };
  const handleFileChange = (e) => {
    if (e.target.files.length) addFiles(e.target.files);
    // Reset input so same file can be re-added after removal
    e.target.value = '';
  };

  // ── Retry failed items ─────────────────────────────────────────────────────
  const retryFailed = () => {
    setQueue((q) => q.map((i) =>
      i.status === 'error' ? { ...i, status: 'ready', error: null } : i
    ));
    setBatchResult(null);
  };

  // ── Batch upload ───────────────────────────────────────────────────────────
  const processBatch = async () => {
    const ready = queue.filter((i) => i.status === 'ready');
    if (!ready.length) return;

    const readyIds = new Set(ready.map((r) => r.id));

    setUploading(true);
    setBatchProgress(0);
    setBatchResult(null);

    // Mark all ready items as uploading
    setQueue((q) => q.map((i) =>
      readyIds.has(i.id) ? { ...i, status: 'uploading' } : i
    ));

    try {
      const files  = ready.map((i) => i.file);
      const result = await uploadDocumentsBatch(files, (pct) => setBatchProgress(pct));

      setBatchResult(result);

      // Map queue-item IDs back to results by positional index
      const idToResult = {};
      ready.forEach((item, idx) => { idToResult[item.id] = result.results[idx]; });

      setQueue((q) => q.map((item) => {
        if (!readyIds.has(item.id)) return item;
        const r = idToResult[item.id];
        if (r?.success) return { ...item, status: 'done', documentId: r.document_id };
        return { ...item, status: 'error', error: r?.error || 'Server error' };
      }));

      // Register successful docs in global store + start pollers
      const successful = result.results.filter((r) => r.success);
      successful.forEach((r) => {
        addDocument({
          id:              r.document_id,
          filename:        r.filename,
          status:          r.status,
          workflow_run_id: r.workflow_run_id,
        });
      });
      setUploadedIds((ids) => [...ids, ...successful.map((r) => r.document_id)]);

      if (result.succeeded > 0)
        toast(`${result.succeeded} file${result.succeeded > 1 ? 's' : ''} submitted to AI pipeline!`, 'success');
      if (result.failed > 0)
        toast(`${result.failed} file${result.failed > 1 ? 's' : ''} failed to upload`, 'warn');

    } catch (err) {
      setQueue((q) => q.map((i) =>
        readyIds.has(i.id) ? { ...i, status: 'error', error: err.message } : i
      ));
      toast(`Batch upload failed: ${err.message}`, 'error');
    }

    setUploading(false);
  };

  // ── Derived counts ─────────────────────────────────────────────────────────
  const readyCount     = queue.filter((i) => i.status === 'ready').length;
  const failedCount    = queue.filter((i) => i.status === 'error').length;
  const doneCount      = queue.filter((i) => i.status === 'done').length;
  const uploadingCount = queue.filter((i) => i.status === 'uploading').length;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="page">
      {/* Mount one status-poller per successfully uploaded doc */}
      {uploadedIds.map((id) => <DocPoller key={id} docId={id} />)}

      <div style={{ maxWidth: 780, margin: '0 auto' }}>

        {/* ── Upload Zone ── */}
        <div className={isDragover ? 'animated-border-active' : ''} style={{ marginBottom: 24 }}>
          <div
            className={`upload-zone ${isDragover ? 'dragover' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setIsDragover(true); }}
            onDragLeave={() => setIsDragover(false)}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            {/* Glowing Icon Circle with Outer Dashed Spinner */}
            <div className="upload-icon-circle">
              <UploadCloud size={32} strokeWidth={1.5} style={{ transform: isDragover ? 'scale(1.1) translateY(-2px)' : 'none', transition: 'all 0.3s ease' }} />
            </div>

            <h3 className="upload-main-heading">
              Drag &amp; drop documents here or <span className="upload-accent-text">browse files</span>
            </h3>

            <p className="upload-sub-description">
              Upload documents to start the automated AI ingestion pipeline. Your files will be classified, structured data extracted, and formulas validated in parallel.
            </p>

            {/* Redesigned File Type Chips */}
            <div className="upload-types-grid" style={{ marginBottom: 24 }}>
              {[
                { name: 'PDF', icon: FileText, color: '#ef4444' },
                { name: 'DOCX', icon: File, color: '#3b82f6' },
                { name: 'PNG', icon: Image, color: '#10b981' },
                { name: 'JPG', icon: Image, color: '#f59e0b' },
                { name: 'WEBP', icon: Image, color: '#06b6d4' },
              ].map((t) => {
                const Icon = t.icon;
                return (
                  <span key={t.name} className="upload-type-badge">
                    <Icon size={12} style={{ color: t.color }} />
                    {t.name}
                  </span>
                );
              })}
            </div>

            {/* Ingestion Pipeline Strip Info badge */}
            <div className="upload-batch-strip">
              <Layers size={13} />
              <span>Batch Ingestion Mode (Up to {MAX_BATCH} files)</span>
              <span style={{ opacity: 0.3 }}>•</span>
              <Zap size={12} />
              <span>Concurrently Processed via Mistral AI</span>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.png,.jpg,.jpeg,.webp"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
          </div>
        </div>

        {/* ── Upload Queue ── */}
        {queue.length > 0 && (
          <div className="card" style={{ marginBottom: 20 }}>

            {/* Queue header */}
            <div className="card-header">
              <div>
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Layers size={15} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                  Upload Queue
                  <span className="batch-mode-chip" style={{ fontSize: 10, padding: '2px 8px' }}>Batch</span>
                </div>
                <div className="card-sub" style={{ marginTop: 4 }}>
                  {queue.length} file{queue.length !== 1 ? 's' : ''}
                  {doneCount > 0      && <span style={{ color: 'var(--success)', marginLeft: 6 }}>· {doneCount} done</span>}
                  {uploadingCount > 0 && <span style={{ color: 'var(--accent)',  marginLeft: 6 }}>· {uploadingCount} uploading</span>}
                  {readyCount > 0     && <span style={{ color: 'var(--muted)',   marginLeft: 6 }}>· {readyCount} ready</span>}
                  {failedCount > 0    && <span style={{ color: 'var(--danger)',  marginLeft: 6 }}>· {failedCount} failed</span>}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                {failedCount > 0 && !uploading && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={retryFailed}
                    style={{ color: 'var(--warn)', borderColor: 'var(--warn-border)' }}
                  >
                    <RefreshCw size={12} /> Retry {failedCount} Failed
                  </button>
                )}
                {!uploading && (
                  <button className="btn btn-ghost btn-sm" onClick={clearAll}>
                    Clear All
                  </button>
                )}
              </div>
            </div>

            {/* Batch overall progress — shown while uploading */}
            {uploading && (
              <div className="batch-progress-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>
                    Uploading {uploadingCount} file{uploadingCount !== 1 ? 's' : ''} as one batch…
                  </span>
                  <span style={{ fontSize: 'var(--text-lg)', fontWeight: 800, color: 'var(--accent)', letterSpacing: '-0.02em' }}>
                    {batchProgress}%
                  </span>
                </div>

                {/* Progress bar */}
                <div className="progress-bar" style={{ height: 8 }}>
                  <div
                    className="progress-fill"
                    style={{ width: `${batchProgress}%`, transition: 'width 0.4s ease' }}
                  />
                </div>

                {/* Server-side note */}
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-sm)', color: 'var(--muted)' }}>
                  <span style={{
                    display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
                    background: 'var(--accent)', animation: 'pulse 1.5s ease-in-out infinite',
                  }} />
                  Server is processing all files concurrently with Mistral AI Workflows
                </div>
              </div>
            )}

            {/* File list */}
            <div style={{ marginTop: uploading ? 8 : 0 }}>
              {queue.map((item) => (
                <QueueItem
                  key={item.id}
                  item={item}
                  onRemove={removeItem}
                  locked={uploading}
                />
              ))}
            </div>

            {/* Action footer */}
            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button
                id="batch-upload-btn"
                className="btn btn-primary"
                style={{ flex: 1, fontSize: 'var(--text-md)' }}
                onClick={processBatch}
                disabled={uploading || readyCount === 0}
              >
                {uploading ? (
                  <>
                    <span style={{
                      display: 'inline-block', width: 14, height: 14,
                      border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white',
                      borderRadius: '50%', animation: 'spin 0.8s linear infinite',
                    }} />
                    Uploading Batch…
                  </>
                ) : (
                  <>
                    <Layers size={14} />
                    Send {readyCount} File{readyCount !== 1 ? 's' : ''} as Batch to AI Pipeline
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ── Batch Result Card ── */}
        {batchResult && (
          <div
            className="card"
            style={{
              marginBottom: 20,
              borderColor: batchResult.failed === 0 ? 'var(--success-border)' : 'var(--warn-border)',
              background: batchResult.failed === 0
                ? 'rgba(16,185,129,0.04)'
                : 'rgba(245,158,11,0.04)',
            }}
          >
            {/* Label */}
            <div style={{
              fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.09em', color: 'var(--muted)', marginBottom: 16,
            }}>
              Batch Result
            </div>

            {/* Stats row */}
            <div className="batch-stats-row">
              {/* Succeeded */}
              <div className="batch-stat-cell">
                <div className="batch-stat-icon" style={{ background: 'var(--success-dim)', color: 'var(--success)' }}>
                  <CheckCircle2 size={22} />
                </div>
                <div>
                  <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, color: 'var(--success)', letterSpacing: '-0.04em', lineHeight: 1 }}>
                    {batchResult.succeeded}
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 3 }}>Submitted</div>
                </div>
              </div>

              {/* Divider */}
              <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch', margin: '0 8px' }} />

              {/* Failed */}
              <div className="batch-stat-cell">
                <div className="batch-stat-icon" style={{
                  background: batchResult.failed > 0 ? 'var(--danger-dim)' : 'var(--card-alt)',
                  color: batchResult.failed > 0 ? 'var(--danger)' : 'var(--muted)',
                }}>
                  <XCircle size={22} />
                </div>
                <div>
                  <div style={{
                    fontSize: 'var(--text-3xl)', fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1,
                    color: batchResult.failed > 0 ? 'var(--danger)' : 'var(--muted)',
                  }}>
                    {batchResult.failed}
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 3 }}>Failed</div>
                </div>
              </div>

              {/* Divider */}
              <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch', margin: '0 8px' }} />

              {/* Total */}
              <div className="batch-stat-cell">
                <div className="batch-stat-icon" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>
                  <Layers size={22} />
                </div>
                <div>
                  <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1 }}>
                    {batchResult.total}
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 3 }}>Total Files</div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' }}>
              {batchResult.succeeded > 0 && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate('/processing')}>
                  View Processing →
                </button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => navigate('/')}>
                Back to Dashboard
              </button>
              {batchResult.failed > 0 && (
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={retryFailed}
                  style={{ color: 'var(--warn)', borderColor: 'var(--warn-border)' }}
                >
                  <RefreshCw size={12} />
                  Retry {batchResult.failed} Failed File{batchResult.failed > 1 ? 's' : ''}
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Pipeline Info Card (shown only when queue is empty) ── */}
        {queue.length === 0 && (
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">AI Processing Pipeline</div>
                <div className="card-sub">
                  8-step automated workflow · All batch files run through each stage in parallel
                </div>
              </div>
              <span className="batch-mode-chip">
                <Zap size={11} /> Parallel
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {[
                { icon: <CheckCircle2 size={15} />, label: 'Ingestion',     desc: 'Duplicate detection via SHA-256 & initial validation' },
                { icon: <ShieldCheck size={15} />,  label: 'Quality Check',   desc: 'Verification of document readability, layout alignment, and security constraints' },
                { icon: <Brain size={15} />,        label: 'Pre Processing',  desc: 'Automatic image enhancement, deskewing, and formatting conversion' },
                { icon: <Layers size={15} />,       label: 'Classification',  desc: 'AI determines document type and selects extraction schema automatically' },
                { icon: <ScanSearch size={15} />,   label: 'Extraction',      desc: 'Mistral OCR + structured field extraction per document type' },
                { icon: <ShieldCheck size={15} />,  label: 'Validation',      desc: 'Math cross-checks, date logic, and custom schema validation' },
                { icon: <UserCheck size={15} />,    label: 'Human Review',    desc: 'Human approval required when extraction confidence is low' },
                { icon: <Share2 size={15} />,       label: 'Output',          desc: 'Structured JSON persisted & ready for downstream export' },
              ].map(({ icon, label, desc }) => (
                <div key={label} className="info-row">
                  <div className="info-row-icon">{icon}</div>
                  <div className="info-row-label">{label}</div>
                  <div className="info-row-desc">{desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
```

## `src/pages/Documents.jsx`

```jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, RefreshCw, ChevronLeft, ChevronRight, Folder, FileText, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { deleteDocument, listDocuments } from '../api/client';
import { useApp } from '../store/AppStore';
import { StatusBadge } from '../components/ui/StatusBadge';

const STATUS_FILTERS = ['all', 'pending', 'processing', 'awaiting_review', 'completed', 'rejected', 'failed', 'error'];

const STATUS_FILTER_LABELS = {
  all:             'All',
  pending:         'Pending',
  processing:      'Ingestion',
  awaiting_review: 'Human Review',
  completed:       'Completed',
  rejected:        'Rejected',
  failed:          'Failed',
  error:           'Error',
};

/** Renders a rejection/failure reason with expand/collapse if the text is long */
function ExpandableReason({ reason }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = reason.length > 80;
  return (
    <div style={{
      marginTop: 5, padding: '5px 8px',
      background: 'var(--danger-dim, rgba(239,68,68,0.08))',
      border: '1px solid var(--danger-border, rgba(239,68,68,0.2))',
      borderRadius: 6, maxWidth: 340,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 5 }}>
        <AlertCircle size={12} style={{ color: 'var(--danger)', marginTop: 2, flexShrink: 0 }} />
        <span style={{ fontSize: 11, color: 'var(--danger)', lineHeight: 1.4, flex: 1 }}>
          {isLong && !expanded ? reason.slice(0, 80) + '…' : reason}
        </span>
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            marginTop: 4, marginLeft: 17,
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--danger)', fontSize: 10, display: 'flex', alignItems: 'center', gap: 2,
            opacity: 0.75, padding: 0,
          }}
        >
          {expanded ? <><ChevronUp size={10} /> Show less</> : <><ChevronDown size={10} /> Show more</>}
        </button>
      )}
    </div>
  );
}


export function Documents() {
  const { documents, setDocuments, removeDocument, toast } = useApp();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const navigate = useNavigate();
  const LIMIT = 20;

  const load = async (p = 1) => {
    setLoading(true);
    try {
      const docs = await listDocuments(p, LIMIT);
      setDocuments(docs);
    } catch (err) {
      toast('Error loading documents: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const filtered = filter === 'all' ? documents : documents.filter((d) => d.status === filter);

  const handleDelete = async (doc) => {
    if (!confirm(`Delete "${doc.filename}"?`)) return;
    setDeleting(doc.id);
    try {
      await deleteDocument(doc.id);
      removeDocument(doc.id);
      toast(`"${doc.filename}" deleted.`, 'info');
    } catch (err) {
      toast('Delete failed: ' + err.message, 'error');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">All Documents</div>
            <div className="card-sub">{filtered.length} document{filtered.length !== 1 ? 's' : ''}</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => load(page)} disabled={loading}>
              <RefreshCw size={12} className={loading ? 'spin' : ''} /> Refresh
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => navigate('/upload')}>
              + Upload
            </button>
          </div>
        </div>

        {/* Filter Bar */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              className={`btn btn-ghost btn-sm`}
              style={filter === s ? { borderColor: 'var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' } : {}}
              onClick={() => setFilter(s)}
            >
              {STATUS_FILTER_LABELS[s] || s}
              {s !== 'all' && (
                <span style={{ marginLeft: 4, opacity: 0.6 }}>
                  ({documents.filter((d) => d.status === s).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">
            <Folder className="empty-icon" size={36} />
            <div className="empty-title">No documents</div>
            <div className="empty-sub">
              {filter !== 'all' ? `No documents with status "${STATUS_FILTER_LABELS[filter] || filter}".` : 'Upload a document to get started.'}
            </div>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>ID</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
                      <span
                        className="doc-filename-link"
                        onClick={() => navigate('/extraction')}
                      >
                        {doc.filename}
                      </span>
                    </td>
                    <td>
                      {doc.doc_type
                        ? <span className="badge badge-cyan">{doc.doc_type}</span>
                        : null}
                    </td>
                    <td style={{ whiteSpace: 'normal', overflow: 'visible' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                        <StatusBadge status={doc.status} />
                        {['rejected', 'failed', 'error'].includes(doc.status) && doc.message && (
                          <ExpandableReason reason={doc.message} />
                        )}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--muted)' }}>
                        {doc.id.slice(0, 8)}…
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        style={{ padding: '4px 8px' }}
                        onClick={() => handleDelete(doc)}
                        disabled={deleting === doc.id}
                      >
                        {deleting === doc.id
                          ? <span className="spin" style={{ width: 12, height: 12, border: '2px solid rgba(239,68,68,0.3)', borderTopColor: 'var(--danger)', borderRadius: '50%', display: 'inline-block' }} />
                          : <Trash2 size={12} />
                        }
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, fontSize: 12, color: 'var(--muted)' }}>
          <span>Page {page}</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1 || loading}>
              <ChevronLeft size={13} />
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setPage((p) => p + 1)} disabled={documents.length < LIMIT || loading}>
              <ChevronRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

## `src/pages/Processing.jsx`

```jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Cpu, CheckCircle, ListTodo, FileText, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { useDocumentPoller } from '../hooks/useDocumentPoller';
import { StatusBadge } from '../components/ui/StatusBadge';
import { PipelineSteps } from '../components/ui/PipelineSteps';

/** Renders a rejection/failure reason with expand/collapse if the text is long */
function ExpandableReason({ reason }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = reason.length > 80;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      marginTop: 4, padding: '4px 7px',
      background: 'rgba(239,68,68,0.08)',
      border: '1px solid rgba(239,68,68,0.2)',
      borderRadius: 5,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 5 }}>
        <AlertCircle size={11} style={{ color: 'var(--danger)', marginTop: 1, flexShrink: 0 }} />
        <span style={{ fontSize: 10, color: 'var(--danger)', lineHeight: 1.4, flex: 1 }}>
          {isLong && !expanded ? reason.slice(0, 80) + '…' : reason}
        </span>
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            marginTop: 3, marginLeft: 16,
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--danger)', fontSize: 9, display: 'flex', alignItems: 'center', gap: 2,
            opacity: 0.75, padding: 0,
          }}
        >
          {expanded ? <><ChevronUp size={9} /> Show less</> : <><ChevronDown size={9} /> Show more</>}
        </button>
      )}
    </div>
  );
}

// Renders one poller per active doc
function PollersRenderer({ ids }) {
  return ids.map((id) => <SinglePoller key={id} docId={id} />);
}
function SinglePoller({ docId }) {
  useDocumentPoller(docId);
  return null;
}

export function Processing() {
  const { documents, pendingDocs } = useApp();
  const { refresh, loading } = useDocumentList();
  const navigate = useNavigate();

  useEffect(() => { refresh(); }, []);

  // Most recently active doc for the live pipeline display
  const featured = pendingDocs[0];

  return (
    <div className="page">
      {/* Activate pollers for all pending docs */}
      <PollersRenderer ids={pendingDocs.map((d) => d.id)} />

      {/* Live Pipeline for featured doc */}
      {featured ? (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Cpu size={16} style={{ color: 'var(--accent)' }} />
                Live Processing Pipeline
              </div>
              <div className="card-sub">
                Processing: <strong style={{ color: 'var(--accent)' }}>{featured.filename}</strong>
              </div>
            </div>
            <div className="chip" style={{ gap: 6 }}>
              <span className="pulse-dot" style={{ width: 6, height: 6 }} />
              Live
            </div>
          </div>
          <PipelineSteps status={featured.status} />
        </div>
      ) : (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon-wrap" style={{ color: 'var(--success)', background: 'var(--success-dim)', border: '1px solid var(--success-border)' }}>
              <CheckCircle size={32} />
            </div>
            <div className="empty-title">No active processing</div>
            <div className="empty-sub">All documents have been processed or the queue is empty.</div>
            <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => navigate('/upload')}>
              Upload Documents
            </button>
          </div>
        </div>
      )}

      {/* Processing Queue Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ListTodo size={16} style={{ color: 'var(--accent)' }} />
            Processing Queue
          </div>
          <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>
            <RefreshCw size={12} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>

        {pendingDocs.length === 0 ? (
          <div className="empty-state" style={{ padding: '24px' }}>
            <div className="empty-sub">No documents currently in the processing pipeline.</div>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Workflow Run</th>
                </tr>
              </thead>
              <tbody>
                {pendingDocs.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
                      <span style={{ fontSize: 12 }}>{doc.filename}</span>
                    </td>
                    <td>
                      {doc.doc_type
                        ? <span className="badge badge-cyan">{doc.doc_type}</span>
                        : <span style={{ color: 'var(--muted)', fontSize: 11 }}>Classifying…</span>}
                    </td>
                    <td><StatusBadge status={doc.status} /></td>
                    <td>
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'monospace' }}>
                        {doc.workflow_run_id?.slice(0, 16) || '—'}…
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* All Documents Mini Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">All Documents</div>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/documents')}>
            Full List →
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th><th>Type</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {documents.slice(0, 10).map((doc) => (
                <tr key={doc.id} style={{ cursor: 'pointer' }} onClick={() => navigate('/extraction')}>
                  <td>
                    <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
                    <span style={{ fontSize: 12 }}>{doc.filename}</span>
                  </td>
                  <td>
                    {doc.doc_type
                      ? <span className="badge badge-cyan">{doc.doc_type}</span>
                      : <span style={{ color: 'var(--muted)', fontSize: 11 }}>—</span>}
                  </td>
                  <td style={{ whiteSpace: 'normal', overflow: 'visible' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                      <StatusBadge status={doc.status} />
                      {['rejected', 'failed', 'error'].includes(doc.status) && doc.message && (
                        <ExpandableReason reason={doc.message} />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
```

## `src/pages/Extraction.jsx`

```jsx
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Copy, Download, ChevronDown, ChevronRight, Maximize2, ExternalLink, FileText, FileSearch, CheckCircle2, AlertTriangle, Edit2, Check, X, Trash2, Plus, ShieldCheck, UserCircle2, PenTool, ZoomIn, Upload, RotateCcw, Shield, Eye, Fingerprint, Users } from 'lucide-react';
import { getExtractedData, getDocumentFileUrl, updateExtractedData, getTemplates, verifySignature, getOcrBlocks } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';

function isNullOrEmpty(v) {
  if (v === null || v === undefined) return true;
  if (typeof v === 'string') {
    const trimmed = v.trim().toLowerCase();
    return trimmed === '' || trimmed === 'null' || trimmed === 'none';
  }
  return false;
}

function parseTableData(value, key) {
  if (value === null || value === undefined) return null;
  let parsed = value;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        parsed = JSON.parse(trimmed);
      } catch (e) {
        return null;
      }
    } else {
      return null;
    }
  }

  if (Array.isArray(parsed)) {
    if (parsed.length === 0) {
      return parsed;
    }
    if (parsed.every(item => item !== null && typeof item === 'object' && !Array.isArray(item))) {
      return parsed;
    }
  }
  return null;
}

function parseArrayOfText(value) {
  if (value === null || value === undefined) return null;
  let parsed = value;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        parsed = JSON.parse(trimmed);
      } catch (e) {
        return null;
      }
    } else {
      return null;
    }
  }

  if (Array.isArray(parsed)) {
    if (parsed.length === 0) {
      return parsed;
    }
    if (parsed.every(item => item !== null && typeof item !== 'object')) {
      return parsed.map(String);
    }
  }
  return null;
}

const getTableHeaders = (items) => {
  const keysSet = new Set();
  items.forEach(item => {
    if (item && typeof item === 'object') {
      Object.keys(item).forEach(key => keysSet.add(key));
    }
  });
  return Array.from(keysSet);
};

/** Recursively collect all leaf numbers from a nested confidence structure and average them. */
function flattenConfidence(conf) {
  if (conf == null) return null;
  if (typeof conf === 'number') return conf;
  const nums = [];
  const collect = (node) => {
    if (typeof node === 'number') {
      nums.push(node);
    } else if (Array.isArray(node)) {
      node.forEach(collect);
    } else if (node && typeof node === 'object') {
      Object.values(node).forEach(collect);
    }
  };
  collect(conf);
  if (nums.length === 0) return null;
  return nums.reduce((s, n) => s + n, 0) / nums.length;
}

const getDefaultHeaders = (key) => {
  const k = (key || '').toLowerCase();
  if (k.includes('item')) {
    return ['description', 'quantity', 'unit_price', 'total'];
  }
  if (k.includes('transaction')) {
    return ['date', 'description', 'debit', 'credit', 'balance'];
  }
  return ['description', 'quantity', 'unit_price', 'total'];
};

function FieldRow({ label, fieldKey, value, isEditing, onChange, conf, confHighThreshold = 90, confMedThreshold = 70, fieldHighlightThreshold = 95, rawVal, onFieldHover }) {
  const [newInputVal, setNewInputVal] = useState('');
  // conf may be a nested structure for table/array fields — flatten to a single average number
  const resolvedConf = flattenConfidence(conf);
  const pct = resolvedConf != null ? Math.round(resolvedConf * 100) : null;
  const confClass = pct == null ? '' : pct >= confHighThreshold ? 'conf-high' : pct >= confMedThreshold ? 'conf-med' : 'conf-low';
  const confColor = pct == null ? '' : pct >= confHighThreshold ? 'var(--success)' : pct >= confMedThreshold ? 'var(--warn)' : 'var(--danger)';

  const tableData = parseTableData(value, fieldKey);
  const stringArray = parseArrayOfText(value);

  if (tableData) {
    let headers = getTableHeaders(tableData);
    if (headers.length === 0) {
      headers = getDefaultHeaders(fieldKey);
    }

    const handleCellChange = (rowIndex, key, cellValue) => {
      const updatedData = tableData.map((row, rIdx) => {
        if (rIdx === rowIndex) {
          const originalValue = row[key];
          let typedValue = cellValue;
          if (typeof originalValue === 'number') {
            const parsedNum = Number(cellValue);
            if (!isNaN(parsedNum)) {
              typedValue = parsedNum;
            }
          }
          return { ...row, [key]: typedValue };
        }
        return row;
      });

      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updatedData));
      } else {
        onChange(fieldKey, updatedData);
      }
    };

    const handleAddRow = () => {
      const newRow = {};
      headers.forEach(h => {
        newRow[h] = h === 'description' || h === 'date' ? '' : 0;
      });
      const updatedData = [...tableData, newRow];
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updatedData));
      } else {
        onChange(fieldKey, updatedData);
      }
    };

    const handleDeleteRow = (rowIndex) => {
      const updatedData = tableData.filter((_, rIdx) => rIdx !== rowIndex);
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updatedData));
      } else {
        onChange(fieldKey, updatedData);
      }
    };

    return (
      <div
        className="field-row-table-container"
        style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 0', borderBottom: '1px solid var(--border)', cursor: onFieldHover ? 'crosshair' : 'default' }}
        onMouseEnter={() => onFieldHover?.(fieldKey)}
        onMouseLeave={() => onFieldHover?.(null)}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="field-key" style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-dim)' }}>{label}</div>
          {!isEditing && pct != null && (
            <div className="field-conf" style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 'var(--text-sm)' }}>
              <div className={`conf-dot ${confClass}`} />
              <span style={{ color: confColor }}>{pct}%</span>
            </div>
          )}
        </div>

        <div className="table-wrap" style={{
          background: 'var(--surface-sunken)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          overflowX: 'auto',
          marginTop: 4
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--card-alt)' }}>
                {headers.map(h => (
                  <th key={h} style={{
                    padding: '8px 12px',
                    fontSize: 11,
                    fontWeight: 700,
                    textAlign: 'left',
                    borderBottom: '1px solid var(--border)',
                    textTransform: 'uppercase',
                    color: 'var(--muted)'
                  }}>
                    {h.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </th>
                ))}
                {isEditing && (
                  <th style={{
                    padding: '8px 12px',
                    fontSize: 11,
                    fontWeight: 700,
                    textAlign: 'center',
                    borderBottom: '1px solid var(--border)',
                    textTransform: 'uppercase',
                    color: 'var(--muted)',
                    width: 50
                  }}>
                    Actions
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {tableData.length === 0 ? (
                <tr>
                  <td colSpan={headers.length + (isEditing ? 1 : 0)} style={{ padding: '16px', textAlign: 'center', color: 'var(--muted)', fontStyle: 'italic' }}>
                    No items in table. Click "Add Row" below to add one.
                  </td>
                </tr>
              ) : (
                tableData.map((row, rIdx) => (
                  <tr key={rIdx} style={{ borderBottom: rIdx === tableData.length - 1 ? 'none' : '1px solid var(--border)', cursor: 'default' }}>
                    {headers.map(h => {
                      const cellVal = row[h];
                      return (
                        <td key={h} style={{ padding: '8px 12px', verticalAlign: 'middle', maxWidth: 'none', overflow: 'visible', whiteSpace: 'normal' }}>
                          {isEditing ? (
                            <input
                              type="text"
                              className="styled-input"
                              value={isNullOrEmpty(cellVal) ? '' : cellVal}
                              onChange={(e) => handleCellChange(rIdx, h, e.target.value)}
                              style={{
                                width: '100%',
                                padding: '4px 8px',
                                fontSize: 12,
                                background: 'var(--card-alt)',
                                border: '1px solid var(--border)',
                                borderRadius: 4
                              }}
                            />
                          ) : (
                            isNullOrEmpty(cellVal) ? '' : String(cellVal)
                          )}
                        </td>
                      );
                    })}
                    {isEditing && (
                      <td style={{ padding: '8px 12px', textAlign: 'center', verticalAlign: 'middle' }}>
                        <button
                          type="button"
                          onClick={() => handleDeleteRow(rIdx)}
                          className="btn btn-icon btn-danger btn-sm"
                          style={{ padding: 4, borderRadius: 4, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
                          title="Delete row"
                        >
                          <Trash2 size={12} />
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {isEditing && (
          <button
            type="button"
            onClick={handleAddRow}
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 4, display: 'inline-flex', alignItems: 'center', gap: 6, width: 'fit-content' }}
          >
            <Plus size={13} /> Add Row
          </button>
        )}
      </div>
    );
  }

  if (stringArray) {
    const handleAddArrayItem = () => {
      if (!newInputVal.trim()) return;
      const updated = [...stringArray, newInputVal.trim()];
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updated));
      } else {
        onChange(fieldKey, updated);
      }
      setNewInputVal('');
    };

    const handleRemoveArrayItem = (index) => {
      const updated = stringArray.filter((_, i) => i !== index);
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updated));
      } else {
        onChange(fieldKey, updated);
      }
    };

    return (
      <div
        className="field-row-array-container"
        style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 0', borderBottom: '1px solid var(--border)', cursor: onFieldHover ? 'crosshair' : 'default' }}
        onMouseEnter={() => onFieldHover?.(fieldKey)}
        onMouseLeave={() => onFieldHover?.(null)}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="field-key" style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-dim)' }}>{label}</div>
          {!isEditing && pct != null && (
            <div className="field-conf" style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 'var(--text-sm)' }}>
              <div className={`conf-dot ${confClass}`} />
              <span style={{ color: confColor }}>{pct}%</span>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
          {stringArray.length === 0 ? (
            <span style={{ color: 'var(--muted)', fontStyle: 'italic', fontSize: 12 }}>No items</span>
          ) : (
            stringArray.map((item, idx) => (
              <span key={idx} style={{
                background: 'var(--surface-sunken)',
                color: 'var(--text)',
                padding: '4px 10px',
                borderRadius: '16px',
                border: '1px solid var(--border)',
                fontSize: 12,
                fontWeight: 500,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6
              }}>
                {item}
                {isEditing && (
                  <button
                    type="button"
                    onClick={() => handleRemoveArrayItem(idx)}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--muted)',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 0
                    }}
                  >
                    <X size={12} />
                  </button>
                )}
              </span>
            ))
          )}
        </div>

        {isEditing && (
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            <input
              type="text"
              placeholder="Add item..."
              value={newInputVal}
              onChange={(e) => setNewInputVal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddArrayItem();
                }
              }}
              style={{
                flexGrow: 1,
                padding: '4px 8px',
                fontSize: 12,
                background: 'var(--card-alt)',
                border: '1px solid var(--border)',
                borderRadius: 4
              }}
            />
            <button
              type="button"
              onClick={handleAddArrayItem}
              className="btn btn-ghost btn-sm"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, height: 26, padding: '0 8px' }}
            >
              <Plus size={12} /> Add
            </button>
          </div>
        )}
      </div>
    );
  }

  const rawIsNull = isNullOrEmpty(rawVal);
  const valIsNull = isNullOrEmpty(value);

  const hasRawDiff = !rawIsNull && typeof rawVal !== 'object' && String(rawVal).trim() !== String(value ?? '').trim();

  return (
    <div
      className="field-row"
      style={{ display: 'flex', alignItems: 'center', minHeight: 32, cursor: onFieldHover ? 'crosshair' : 'default' }}
      onMouseEnter={() => onFieldHover?.(fieldKey)}
      onMouseLeave={() => onFieldHover?.(null)}
    >
      <div className="field-key" style={{ width: '40%', flexShrink: 0 }}>{label}</div>
      <div className="field-val" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {isEditing ? (
          <input
            type="text"
            className="styled-input"
            value={valIsNull ? '' : value}
            onChange={(e) => onChange(fieldKey, e.target.value)}
            style={{ width: '100%', padding: '4px 8px', fontSize: 13, background: 'var(--card-alt)' }}
          />
        ) : (
          (valIsNull && !hasRawDiff) ? '' :
            (() => {
              const displayVal = hasRawDiff ? rawVal : value;
              const renderedText = isNullOrEmpty(displayVal) ?
                '' :
                (typeof displayVal === 'object' ?
                  <code style={{ fontSize: 11, background: 'transparent', color: 'inherit' }}>{JSON.stringify(displayVal)}</code> :
                  String(displayVal));

              if (!isEditing && pct != null && pct < fieldHighlightThreshold) {
                return (
                  <span style={{
                    background: 'rgba(245, 158, 11, 0.12)',
                    color: 'var(--warn)',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    fontWeight: 500,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6
                  }}>
                    {renderedText}
                  </span>
                );
              }
              return renderedText;
            })()
        )}
        {hasRawDiff && (
          <span style={{ fontSize: 11, color: 'var(--text-dim)', fontStyle: 'italic', marginTop: 2 }}>
            {isEditing ? `Original (OCR): "${rawIsNull ? '' : String(rawVal)}"` : `normalised: "${valIsNull ? '' : String(value)}"`}
          </span>
        )}
      </div>
      {!isEditing && pct != null && (
        <div className="field-conf" style={{ flexShrink: 0, marginLeft: 8 }}>
          <div className={`conf-dot ${confClass}`} />
          <span style={{ color: confColor }}>{pct}%</span>
        </div>
      )}
    </div>
  );
}

function FieldGroup({ title, children }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="field-group">
      <div
        className="field-group-title"
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {title}
      </div>
      {open && children}
    </div>
  );
}

// Keys that hold KYC image data — excluded from regular field rendering
const KYC_IMAGE_KEYS = new Set(['signature_image', 'photo_image', 'signature_detected', 'photo_detected']);


/** Score classification helper */
function getScoreClass(score, max = 100) {
  const pct = max === 1 ? score * 100 : score;
  if (pct >= 75) return 'high';
  if (pct >= 55) return 'medium';
  return 'low';
}

/** Score bar sub-component */
function ScoreBar({ label, value, max = 100, suffix = '' }) {
  const pct = max === 1 ? (value * 100) : (value / max * 100);
  const displayVal = max === 1 ? value.toFixed(4) : Math.round(value);
  const cls = getScoreClass(value, max);
  return (
    <div className="score-bar-row">
      <div className="score-bar-label">{label}</div>
      <div className="score-bar-track">
        <div className={`score-bar-fill ${cls}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <div className="score-bar-value" style={{ color: cls === 'high' ? '#059669' : cls === 'medium' ? '#d97706' : '#dc2626' }}>
        {displayVal}{suffix}
      </div>
    </div>
  );
}

/** Analysis dimension row */
function AnalysisRow({ name, data }) {
  if (!data) return null;
  const score = data.score ?? 0;
  const cls = getScoreClass(score);
  return (
    <div className="analysis-row">
      <div className="analysis-dimension">{name}</div>
      <div className={`analysis-score ${cls}`}>{score}</div>
      <div className="analysis-observation">{data.observation || '—'}</div>
    </div>
  );
}

/** Authenticity flag row */
function FlagRow({ label, flagged }) {
  return (
    <div className="flag-row">
      <div className={`flag-indicator ${flagged ? 'danger' : 'safe'}`} />
      <div className="flag-label">{label}{flagged ? ' — Detected' : ' — Clear'}</div>
    </div>
  );
}

/** Full verdict panel for signature/photo verification results */
function SignatureVerdictPanel({ result, verificationType, onReset }) {
  if (!result) return null;

  const judge = result.judge || {};
  const dino = result.dino || {};
  const vision = result.mistral_vision || {};
  const scores = judge.scores || {};
  const verdict = (judge.verdict || result.verdict || 'unknown').toLowerCase();
  const confidence = judge.confidence ?? 0;
  const recommendation = judge.recommendation || '';
  const summary = judge.summary || '';

  const verdictIcon = verdict === 'genuine' ? <CheckCircle2 size={16} /> : verdict === 'uncertain' ? <AlertTriangle size={16} /> : <Shield size={16} />;
  const verdictLabel = verdict === 'genuine' ? 'GENUINE' : verdict === 'uncertain' ? 'UNCERTAIN' : 'FORGED';

  const recClass = recommendation.toLowerCase().includes('accept') ? 'accept'
    : recommendation.toLowerCase().includes('review') ? 'review' : 'reject';
  const recIcon = recClass === 'accept' ? <CheckCircle2 size={12} /> : recClass === 'review' ? <Eye size={12} /> : <Shield size={12} />;

  const [showStructural, setShowStructural] = useState(false);
  const [showSpatial, setShowSpatial] = useState(false);
  const [showFlags, setShowFlags] = useState(false);
  const [showUnique, setShowUnique] = useState(false);

  const structural = judge.structural_analysis || vision.structural_analysis || {};
  const spatial = judge.spatial_analysis || vision.spatial_analysis || {};
  const flags = judge.authenticity_flags || vision.authenticity_flags || {};
  const unique = judge.unique_features || vision.unique_features || {};

  return (
    <div className="verdict-panel">
      {/* Header with verdict badge */}
      <div className={`verdict-header ${verdict}`}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className={`verdict-badge ${verdict}`}>
            {verdictIcon} {verdictLabel}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            Confidence: <strong style={{ color: 'var(--text)' }}>{confidence}%</strong>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Fingerprint size={10} />
            {verificationType === 'signature' ? 'Signature' : 'Photo'} Verification
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onReset} style={{ fontSize: 10, padding: '2px 8px', gap: 3 }}>
            <RotateCcw size={10} /> Reset
          </button>
        </div>
      </div>

      {/* Score Breakdown */}
      <div className="score-bar-container">
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 2 }}>Score Breakdown</div>
        <ScoreBar label="DINOv2" value={scores.embedding_cosine_score ?? dino.score ?? 0} max={1} />
        <ScoreBar label="LLM Visual" value={scores.llm_visual_score ?? vision.llm_visual_score ?? 0} max={100} />
        <ScoreBar label="Combined" value={scores.combined_weighted_score ?? 0} max={100} />
        {(scores.penalties_applied != null && scores.penalties_applied > 0) && (
          <div style={{ fontSize: 10, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
            <AlertTriangle size={10} />
            {scores.penalties_applied} point penalty applied
            {scores.penalty_reasons?.length > 0 && ` (${scores.penalty_reasons.join(', ')})`}
          </div>
        )}
      </div>

      {/* Structural Analysis Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowStructural(s => !s)}
        >
          {showStructural ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Structural Analysis (5 dimensions)
        </div>
        {showStructural && (
          <div style={{ padding: '0 18px 12px' }}>
            <AnalysisRow name="Stroke Flow" data={structural.stroke_flow} />
            <AnalysisRow name="Stroke Thickness" data={structural.stroke_thickness} />
            <AnalysisRow name="Loop Morphology" data={structural.loop_morphology} />
            <AnalysisRow name="Connectivity" data={structural.connectivity_pattern} />
            <AnalysisRow name="Entry/Exit" data={structural.entry_exit_strokes} />
          </div>
        )}
      </div>

      {/* Spatial Analysis Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowSpatial(s => !s)}
        >
          {showSpatial ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Spatial Analysis (4 dimensions)
        </div>
        {showSpatial && (
          <div style={{ padding: '0 18px 12px' }}>
            <AnalysisRow name="Slant Angle" data={spatial.slant_angle} />
            <AnalysisRow name="Baseline" data={spatial.baseline_alignment} />
            <AnalysisRow name="Proportions" data={spatial.proportions} />
            <AnalysisRow name="Spacing" data={spatial.spacing} />
          </div>
        )}
      </div>

      {/* Authenticity Flags Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowFlags(s => !s)}
        >
          {showFlags ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Authenticity Flags
        </div>
        {showFlags && (
          <div style={{ padding: '0 18px 12px' }}>
            <FlagRow label="Tremor / Shakiness" flagged={flags.tremor_detected} />
            <FlagRow label="Retouching" flagged={flags.retouching_detected} />
            <FlagRow label="Hesitation Marks" flagged={flags.hesitation_marks} />
            <FlagRow label="Unnatural Slowness" flagged={flags.unnatural_slowness} />
            <FlagRow label="Pen Lift Mismatch" flagged={flags.pen_lift_mismatch} />
            {flags.flag_details && (
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6, fontStyle: 'italic', lineHeight: 1.5 }}>
                {flags.flag_details}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Unique Features Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowUnique(s => !s)}
        >
          {showUnique ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Unique Features
        </div>
        {showUnique && (
          <div style={{ padding: '0 18px 12px' }}>
            <div className="flag-row">
              <div className={`flag-indicator ${unique.idiosyncratic_marks_present ? 'safe' : 'danger'}`} />
              <div className="flag-label">Idiosyncratic marks {unique.idiosyncratic_marks_present ? 'present' : 'not found'}</div>
            </div>
            {unique.idiosyncratic_marks_present && (
              <div className="flag-row">
                <div className={`flag-indicator ${unique.marks_match ? 'safe' : 'danger'}`} />
                <div className="flag-label">Marks {unique.marks_match ? 'match' : 'do not match'}</div>
              </div>
            )}
            {unique.details && (
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6, fontStyle: 'italic', lineHeight: 1.5 }}>
                {unique.details}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Summary */}
      {summary && (
        <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.6, fontStyle: 'italic' }}>
          {summary}
        </div>
      )}

      {/* Override notice */}
      {judge.override_applied && (
        <div style={{ padding: '8px 18px', borderTop: '1px solid var(--border)', fontSize: 10, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(239,68,68,0.03)' }}>
          <AlertTriangle size={10} />
          Override applied: {judge.override_reason}
        </div>
      )}

      {/* Recommendation */}
      {recommendation && (
        <div className={`recommendation-banner ${recClass}`}>
          {recIcon} {recommendation}
        </div>
      )}
    </div>
  );
}

/** Full verdict panel for face/photo verification results (multi-agent pipeline) */
function FaceVerdictPanel({ result, onReset }) {
  if (!result) return null;

  const mod1 = result.module1 || {};
  const mod2 = result.module2 || {};
  const mod3 = result.module3 || {};
  const outputCode = result.output_code;
  const verdict = (result.verdict || 'needs_review').toLowerCase();
  const verdictLabel = result.verdict_label || 'NEEDS REVIEW';

  const verdictIcon = verdict === 'same_person' ? <CheckCircle2 size={16} /> : verdict === 'different_person' ? <Shield size={16} /> : <AlertTriangle size={16} />;
  const verdictClass = verdict === 'same_person' ? 'genuine' : verdict === 'different_person' ? 'forged' : 'uncertain';

  const [showMod1, setShowMod1] = useState(false);
  const [showMod2, setShowMod2] = useState(false);
  const [showMod3, setShowMod3] = useState(false);

  const getSignalBadge = (signal) => {
    if (!signal) return null;
    const cls = signal === 'supports_same' ? 'face-signal-same' : signal === 'supports_different' ? 'face-signal-diff' : 'face-signal-inc';
    const label = signal === 'supports_same' ? 'Supports Same' : signal === 'supports_different' ? 'Supports Different' : 'Inconclusive';
    return <span className={`face-signal-badge ${cls}`}>{label}</span>;
  };

  const renderFeaturePoints = (label, same, diff, confidence) => (
    <div className="face-feature-block">
      <div className="face-feature-header">
        <span className="face-feature-name">{label}</span>
        {confidence && <span className={`face-conf-badge ${confidence}`}>{confidence}</span>}
      </div>
      {same && same.length > 0 && (
        <div className="face-points-list same">
          <span className="face-points-label">✓ Similar:</span>
          {same.map((p, i) => <span key={i} className="face-point">{p}</span>)}
        </div>
      )}
      {diff && diff.length > 0 && (
        <div className="face-points-list diff">
          <span className="face-points-label">✗ Different:</span>
          {diff.map((p, i) => <span key={i} className="face-point">{p}</span>)}
        </div>
      )}
    </div>
  );

  return (
    <div className="verdict-panel" style={{ marginTop: 12 }}>
      {/* Header */}
      <div className={`verdict-header ${verdictClass}`}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className={`verdict-badge ${verdictClass}`}>
            {verdictIcon} {verdictLabel}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            Score: <strong style={{ color: 'var(--text)' }}>{outputCode}/5</strong>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Users size={10} /> Face Verification
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onReset} style={{ fontSize: 10, padding: '2px 8px', gap: 3 }}>
            <RotateCcw size={10} /> Reset
          </button>
        </div>
      </div>

      {/* Module Signals Overview */}
      <div style={{ padding: '12px 18px', display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>Agent Signals</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>M1: {getSignalBadge(mod1.signal)}</span>
          <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>M2: {getSignalBadge(mod2.signal)}</span>
          <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>M3: {getSignalBadge(mod3.signal)}</span>
        </div>
      </div>

      {/* Module 1 — Morphology Part 1 */}
      <div style={{ borderBottom: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowMod1(s => !s)}
        >
          {showMod1 ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Module 1 — Face Geometry / Eyes / Nose
          <span style={{ marginLeft: 'auto' }}>{getSignalBadge(mod1.signal)}</span>
        </div>
        {showMod1 && (
          <div style={{ padding: '0 18px 12px' }}>
            {mod1.features?.facial_geometry && renderFeaturePoints('Facial Geometry', mod1.features.facial_geometry.same_points, mod1.features.facial_geometry.different_points, mod1.features.facial_geometry.confidence)}
            {mod1.features?.eyes && renderFeaturePoints('Eyes', mod1.features.eyes.same_points, mod1.features.eyes.different_points, mod1.features.eyes.confidence)}
            {mod1.features?.nose && renderFeaturePoints('Nose', mod1.features.nose.same_points, mod1.features.nose.different_points, mod1.features.nose.confidence)}
            {mod1.asymmetry && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Asymmetry</span></div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                  <div>Image A: {mod1.asymmetry.image_a || '—'}</div>
                  <div>Image B: {mod1.asymmetry.image_b || '—'}</div>
                  <div>Match: <strong>{mod1.asymmetry.match || '—'}</strong></div>
                </div>
              </div>
            )}
            {mod1.anchor_features && mod1.anchor_features.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
                <strong>Anchor features:</strong> {mod1.anchor_features.join(', ')}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Module 2 — Morphology Part 2 */}
      <div style={{ borderBottom: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowMod2(s => !s)}
        >
          {showMod2 ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Module 2 — Mouth / Ears / Jaw / Secondary
          <span style={{ marginLeft: 'auto' }}>{getSignalBadge(mod2.signal)}</span>
        </div>
        {showMod2 && (
          <div style={{ padding: '0 18px 12px' }}>
            {mod2.features?.mouth_lips && renderFeaturePoints('Mouth & Lips', mod2.features.mouth_lips.same_points, mod2.features.mouth_lips.different_points, mod2.features.mouth_lips.confidence)}
            {mod2.features?.ears && renderFeaturePoints('Ears', mod2.features.ears.same_points, mod2.features.ears.different_points, mod2.features.ears.confidence)}
            {mod2.features?.jaw_chin_secondary && renderFeaturePoints('Jaw / Chin / Secondary', mod2.features.jaw_chin_secondary.same_points, mod2.features.jaw_chin_secondary.different_points, mod2.features.jaw_chin_secondary.confidence)}
            {mod2.variability_factors && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Variability Factors</span></div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4 }}>
                  {Object.entries(mod2.variability_factors).map(([k, v]) => (
                    <span key={k} className={`face-variability-chip ${v === 'none' ? 'ok' : v === 'mild' ? 'mild' : 'sig'}`}>
                      {k.replace(/_/g, ' ')}: {v}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Module 3 — Age Variation */}
      <div style={{ borderBottom: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowMod3(s => !s)}
        >
          {showMod3 ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Module 3 — Age Variation Analysis
          <span style={{ marginLeft: 'auto' }}>{getSignalBadge(mod3.signal)}</span>
        </div>
        {showMod3 && (
          <div style={{ padding: '0 18px 12px' }}>
            {mod3.estimated_age_gap && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Estimated Age Gap</span></div>
                <span className="face-age-gap-badge">{(mod3.estimated_age_gap || '').replace(/_/g, ' ')}</span>
                {mod3.age_cues_used && mod3.age_cues_used.length > 0 && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>Cues: {mod3.age_cues_used.join(', ')}</div>
                )}
              </div>
            )}
            {mod3.stable_features && (
              <div className="face-feature-block">
                <div className="face-feature-header">
                  <span className="face-feature-name">Stable Features (Bone-Anchored)</span>
                  {mod3.stable_features.confidence && <span className={`face-conf-badge ${mod3.stable_features.confidence}`}>{mod3.stable_features.confidence}</span>}
                </div>
                {mod3.stable_features.consistent && mod3.stable_features.consistent.length > 0 && (
                  <div className="face-points-list same">
                    <span className="face-points-label">✓ Consistent:</span>
                    {mod3.stable_features.consistent.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
                {mod3.stable_features.inconsistent && mod3.stable_features.inconsistent.length > 0 && (
                  <div className="face-points-list diff">
                    <span className="face-points-label">✗ Inconsistent:</span>
                    {mod3.stable_features.inconsistent.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
              </div>
            )}
            {mod3.soft_tissue_differences && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Soft Tissue Differences</span></div>
                {mod3.soft_tissue_differences.age_explained && mod3.soft_tissue_differences.age_explained.length > 0 && (
                  <div className="face-points-list same">
                    <span className="face-points-label">Age-explained:</span>
                    {mod3.soft_tissue_differences.age_explained.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
                {mod3.soft_tissue_differences.biologically_inconsistent && mod3.soft_tissue_differences.biologically_inconsistent.length > 0 && (
                  <div className="face-points-list diff">
                    <span className="face-points-label">⚠ Biologically inconsistent:</span>
                    {mod3.soft_tissue_differences.biologically_inconsistent.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
              </div>
            )}
            {mod3.non_age_explained_differences && mod3.non_age_explained_differences.length > 0 && (
              <div style={{ padding: '8px 0', fontSize: 11, color: 'var(--danger)', display: 'flex', alignItems: 'flex-start', gap: 4 }}>
                <AlertTriangle size={11} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>Non-age-explained differences: {mod3.non_age_explained_differences.join(', ')}</span>
              </div>
            )}
            {mod3.aging_trajectory && (
              <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-dim)' }}>
                Aging trajectory: <strong>{mod3.aging_trajectory}</strong>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recommendation */}
      {outputCode && (
        <div className={`recommendation-banner ${outputCode === 5 ? 'accept' : outputCode === 3 ? 'review' : 'reject'}`}>
          {outputCode === 5 ? <CheckCircle2 size={12} /> : outputCode === 3 ? <Eye size={12} /> : <Shield size={12} />}
          {outputCode === 5 ? 'Accept — Same Person' : outputCode === 3 ? 'Manual Review Required' : 'Reject — Different Person'}
        </div>
      )}
    </div>
  );
}

function renderFields(data, isEditing, editedData, onChange, confidences = {}, confidenceMode = 'word', confHighThreshold = 90, confMedThreshold = 70, fieldHighlightThreshold = 95, fieldThresholds = {}, rawFields = {}, onFieldHover = null) {
  if (!data || typeof data !== 'object') return null;
  const groups = {};
  const renderSource = isEditing ? editedData : data;
  Object.entries(renderSource).forEach(([k, v]) => {
    // Skip KYC image fields — they are rendered separately in the Identity Verification section
    if (KYC_IMAGE_KEYS.has(k)) return;
    const group = k.startsWith('vendor') ? 'Vendor' :
      k.startsWith('bill') || k.startsWith('line') ? 'Billing' :
        ['subtotal', 'tax', 'total_amount', 'currency'].includes(k) ? 'Financial' :
          ['due_date', 'invoice_date', 'invoice_number', 'payment_terms'].includes(k) ? 'Header' :
            'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push([k, v]);
  });

  return Object.entries(groups).map(([group, fields]) => (
    <FieldGroup key={group} title={group}>
      {fields.map(([k, v]) => (
        <FieldRow
          key={k}
          label={k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          fieldKey={k}
          value={v}
          rawVal={rawFields?.[k]}
          isEditing={isEditing}
          onChange={onChange}
          conf={(confidenceMode === 'word' || confidenceMode === 'both') ? confidences[k] : null}
          confHighThreshold={confHighThreshold}
          confMedThreshold={confMedThreshold}
          fieldHighlightThreshold={fieldThresholds[k] ?? fieldHighlightThreshold}
          onFieldHover={onFieldHover}
        />
      ))}
    </FieldGroup>
  ));
}


/** KYC Image Card — glassmorphic card for displaying cropped signature/photo */
function KycImageCard({ label, icon: Icon, base64Data, detected, accentColor, verificationType, documentId, verificationResult, onVerify, isVerifying }) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [refFile, setRefFile] = useState(null);
  const [refPreview, setRefPreview] = useState(null);
  const fileInputRef = React.useRef(null);

  const handleDownload = () => {
    if (!base64Data) return;
    const a = document.createElement('a');
    a.href = `data:image/png;base64,${base64Data}`;
    a.download = `${label.toLowerCase().replace(/\s+/g, '_')}.png`;
    a.click();
  };

  const handleFileSelect = (file) => {
    if (!file || !file.type.startsWith('image/')) return;
    setRefFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setRefPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    handleFileSelect(file);
  };

  const handleVerifyClick = () => {
    if (refFile && onVerify) {
      onVerify(refFile, verificationType);
    }
  };

  const handleReset = () => {
    setRefFile(null);
    setRefPreview(null);
    setShowUpload(false);
  };

  if (!detected || !base64Data) {
    return (
      <div style={{
        flex: 1,
        minWidth: 200,
        padding: '20px 16px',
        borderRadius: 'var(--radius)',
        border: '1.5px dashed var(--border)',
        background: 'var(--surface-sunken)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        textAlign: 'center',
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: '50%',
          background: 'rgba(107,114,128,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Icon size={20} style={{ color: 'var(--muted)', opacity: 0.6 }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>{label}</span>
        <span style={{
          fontSize: 10, color: 'var(--warn)',
          background: 'rgba(245,158,11,0.08)',
          border: '1px solid rgba(245,158,11,0.2)',
          padding: '2px 8px', borderRadius: 99,
          display: 'inline-flex', alignItems: 'center', gap: 4
        }}>
          <AlertTriangle size={10} /> Not Detected
        </span>
      </div>
    );
  }

  const isPhotoType = verificationType === 'photo';

  return (
    <>
      <div className={isVerifying ? 'kyc-card-verifying' : ''} style={{
        flex: 1,
        minWidth: 200,
        padding: 0,
        borderRadius: 'var(--radius)',
        border: `1.5px solid ${accentColor}25`,
        background: `linear-gradient(135deg, ${accentColor}08, ${accentColor}03)`,
        backdropFilter: 'blur(12px)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
      }}
        onMouseEnter={(e) => {
          if (!isVerifying) {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = `0 8px 24px ${accentColor}15`;
          }
        }}
        onMouseLeave={(e) => {
          if (!isVerifying) {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }
        }}
      >
        {/* Header */}
        <div style={{
          padding: '8px 12px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: `1px solid ${accentColor}15`,
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: accentColor, display: 'flex', alignItems: 'center', gap: 5, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            <Icon size={12} /> {label}
          </span>
          <span style={{
            fontSize: 9, fontWeight: 600,
            color: 'var(--success)',
            background: 'rgba(16,185,129,0.08)',
            border: '1px solid rgba(16,185,129,0.2)',
            padding: '1px 6px', borderRadius: 99,
            display: 'inline-flex', alignItems: 'center', gap: 3
          }}>
            <CheckCircle2 size={8} /> Detected
          </span>
        </div>

        {/* Image */}
        <div
          style={{
            padding: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 100,
            cursor: 'pointer',
            position: 'relative',
          }}
          onClick={() => setLightboxOpen(true)}
          title="Click to expand"
        >
          <img
            src={`data:image/png;base64,${base64Data}`}
            alt={label}
            style={{
              maxWidth: '100%',
              maxHeight: 140,
              objectFit: 'contain',
              borderRadius: 4,
              border: '1px solid var(--border)',
            }}
          />
          <div style={{
            position: 'absolute', bottom: 16, right: 16,
            background: 'rgba(0,0,0,0.5)', color: '#fff',
            borderRadius: '50%', width: 24, height: 24,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: 0.7, transition: 'opacity 0.2s',
          }}>
            <ZoomIn size={12} />
          </div>
        </div>

        {/* Verification Loading State */}
        {isVerifying && (
          <div className="verification-loading">
            <div className="verify-spinner" />
            <div className="verify-text">Analyzing {verificationType}...</div>
            <div className="verify-subtext">{verificationType === 'photo' ? 'Running 3 forensic face analysis agents in parallel' : 'Running DINOv2 embeddings and Mistral Vision forensic analysis'}</div>
          </div>
        )}

        {/* Upload area (when verify mode is active and not currently verifying) */}
        {showUpload && !isVerifying && !verificationResult && (
          <div style={{ padding: '0 12px 8px' }}>
            <div
              className={`verify-dropzone ${dragOver ? 'dragover' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="verify-drop-icon">
                <Upload size={14} />
              </div>
              <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)' }}>
                Drop reference {verificationType} or click to browse
              </span>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => handleFileSelect(e.target.files?.[0])}
              />
            </div>

            {/* Reference preview */}
            {refPreview && (
              <div className="ref-preview">
                <img src={refPreview} alt="Reference" />
                <span className="ref-name">{refFile?.name}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); setRefFile(null); setRefPreview(null); }}
                  style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 0, display: 'flex' }}
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 6, marginTop: 8, justifyContent: 'flex-end' }}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={(e) => { e.stopPropagation(); handleReset(); }}
                style={{ fontSize: 10, padding: '2px 8px' }}
              >
                Cancel
              </button>
              {isPhotoType ? (
                <button
                  className="btn btn-primary btn-sm"
                  disabled={!refFile}
                  onClick={(e) => { e.stopPropagation(); handleVerifyClick(); }}
                  style={{ fontSize: 10, padding: '2px 10px', gap: 4, background: '#3b82f6', borderColor: '#3b82f6' }}
                >
                  <Users size={10} /> Run Face Verification
                </button>
              ) : (
                <button
                  className="btn btn-primary btn-sm"
                  disabled={!refFile}
                  onClick={(e) => { e.stopPropagation(); handleVerifyClick(); }}
                  style={{ fontSize: 10, padding: '2px 10px', gap: 4, background: '#a855f7', borderColor: '#a855f7' }}
                >
                  <Fingerprint size={10} /> Run Verification
                </button>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{
          padding: '6px 12px 8px',
          display: 'flex', gap: 6, justifyContent: 'flex-end',
          borderTop: `1px solid ${accentColor}10`,
        }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleDownload}
            style={{ fontSize: 10, padding: '2px 8px', gap: 4 }}
          >
            <Download size={10} /> Download
          </button>
          {!verificationResult && !showUpload && !isVerifying && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowUpload(true)}
              style={{ fontSize: 10, padding: '2px 8px', gap: 4, color: '#a855f7', borderColor: 'rgba(168,85,247,0.25)' }}
            >
              <Fingerprint size={10} /> Verify
            </button>
          )}
          {verificationResult && (
            <span style={{
              fontSize: 9, fontWeight: 600,
              padding: '2px 8px', borderRadius: 99,
              display: 'inline-flex', alignItems: 'center', gap: 3,
              ...(['genuine', 'same_person'].includes(verificationResult.verdict)
                ? { color: '#059669', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }
                : ['uncertain', 'needs_review'].includes(verificationResult.verdict)
                  ? { color: '#d97706', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }
                  : { color: '#dc2626', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' })
            }}>
              {['genuine', 'same_person'].includes(verificationResult.verdict) ? <CheckCircle2 size={8} /> : ['uncertain', 'needs_review'].includes(verificationResult.verdict) ? <AlertTriangle size={8} /> : <Shield size={8} />}
              {(verificationResult.verdict || 'unknown').toUpperCase()}
            </span>
          )}
        </div>
      </div>

      {/* Lightbox modal */}
      {lightboxOpen && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 1100,
            background: 'rgba(8,11,20,0.92)', backdropFilter: 'blur(20px)',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            animation: 'fade-in 150ms ease',
            cursor: 'pointer',
          }}
          onClick={() => setLightboxOpen(false)}
        >
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            position: 'absolute', top: 20, right: 20,
          }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={(e) => { e.stopPropagation(); handleDownload(); }}
              style={{ color: '#fff', borderColor: 'rgba(255,255,255,0.2)', fontSize: 11, gap: 5 }}
            >
              <Download size={12} /> Download
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setLightboxOpen(false)}
              style={{ color: '#fff', borderColor: 'rgba(255,255,255,0.2)', fontSize: 11 }}
            >
              ✕ Close
            </button>
          </div>
          <div style={{
            fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.7)',
            marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <Icon size={14} /> {label}
          </div>
          <img
            src={`data:image/png;base64,${base64Data}`}
            alt={label}
            style={{
              maxWidth: '90vw', maxHeight: '80vh',
              objectFit: 'contain', borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.1)',
              boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}

/** Inline document viewer — PDF / image / fallback */
function DocumentViewer({ fileUrl, filename, ext, ocrBlocks = [], highlightFieldKey = null, extractedData = null, rawFields = null }) {
  // ── All hooks must be at the top — no exceptions (Rules of Hooks) ──
  const imgRef    = useRef(null);
  const canvasRef = useRef(null);

  // Strip markdown formatting from block content before substring matching
  const stripMarkdown = (text) =>
    (text || '').replace(/\*\*/g, '').replace(/[_*#\[\]()!`]/g, '').toLowerCase().trim();

  // Helper to extract primitive match strings (needles) for any value type (string, number, boolean, array, table)
  const getValueNeedles = (val, rawVal, key) => {
    const needles = new Set();
    const addPrimitive = (v) => {
      if (v === null || v === undefined || v === '') return;
      if (typeof v === 'boolean') {
        // Boolean fields won't literally say "true" or "false" on document. Match keyword instead.
        const kLower = key.toLowerCase();
        if (kLower.includes('signature') || kLower.includes('sign')) {
          needles.add('signature');
          needles.add('sign');
        } else if (kLower.includes('photo') || kLower.includes('picture')) {
          needles.add('photo');
          needles.add('photograph');
        }
        return;
      }
      const str = String(v).trim();
      if (str.length >= 2) {
        needles.add(str.toLowerCase());
        // Handle common date formatting variations: YYYY-MM-DD -> DD/MM/YYYY
        const dateMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (dateMatch) {
          const [_, y, m, d] = dateMatch;
          needles.add(`${d}/${m}/${y}`);
          needles.add(`${d}-${m}-${y}`);
          needles.add(`${d}.${m}.${y}`);
        }
      }
    };

    const processValue = (value) => {
      if (Array.isArray(value)) {
        value.forEach(item => {
          if (item && typeof item === 'object') {
            Object.values(item).forEach(addPrimitive);
          } else {
            addPrimitive(item);
          }
        });
      } else if (value && typeof value === 'object') {
        Object.values(value).forEach(addPrimitive);
      } else {
        addPrimitive(value);
      }
    };

    // 1. Process rawVal first (matches OCR blocks exactly)
    if (rawVal !== undefined && rawVal !== null) {
      processValue(rawVal);
    }
    // 2. Fallback / add normalized value primitives
    if (val !== undefined && val !== null) {
      processValue(val);
    }

    return Array.from(needles);
  };

  // Find blocks whose stripped content contains any of the value needles.
  // Guards inside handle the fileUrl/data-not-ready cases — safe to run unconditionally.
  const matchingBlocks = useMemo(() => {
    if (!fileUrl || !highlightFieldKey || !ocrBlocks.length) return [];
    const val = extractedData?.[highlightFieldKey];
    const rawVal = rawFields?.[highlightFieldKey];
    const needles = getValueNeedles(val, rawVal, highlightFieldKey);
    if (!needles.length) return [];
    return ocrBlocks.filter(b => b.type !== 'image' && needles.some(needle => stripMarkdown(b.content).includes(needle)));
  }, [fileUrl, highlightFieldKey, extractedData, rawFields, ocrBlocks]);

  // Sync canvas dimensions to match the rendered <img>
  const syncCanvas = () => {
    const img    = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas) return;
    canvas.width  = img.clientWidth;
    canvas.height = img.clientHeight;
  };

  // Draw highlight rectangles whenever matching blocks change.
  // Guards inside handle the refs-not-ready / no-matches cases safely.
  useEffect(() => {
    const canvas = canvasRef.current;
    const img    = imgRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!matchingBlocks.length) return;

    // Scale: OCR pixel space → rendered img size
    const pageW  = matchingBlocks[0]?.page_width  || img.naturalWidth  || img.clientWidth  || 1;
    const pageH  = matchingBlocks[0]?.page_height || img.naturalHeight || img.clientHeight || 1;
    const scaleX = img.clientWidth  / pageW;
    const scaleY = img.clientHeight / pageH;

    matchingBlocks.forEach(block => {
      const x = block.top_left_x     * scaleX;
      const y = block.top_left_y     * scaleY;
      const w = (block.bottom_right_x - block.top_left_x) * scaleX;
      const h = (block.bottom_right_y - block.top_left_y) * scaleY;
      // Filled highlight
      ctx.fillStyle = 'rgba(99, 179, 237, 0.25)';
      ctx.fillRect(x, y, w, h);
      // Crisp border
      ctx.strokeStyle = 'rgba(66, 153, 225, 0.9)';
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);
    });
  }, [matchingBlocks]);

  // ── Early return AFTER all hooks ──
  if (!fileUrl) return null;

  if (ext === 'pdf') {
    return (
      <object
        data={`${fileUrl}#toolbar=1&navpanes=0&view=FitH`}
        type="application/pdf"
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
      >
        {/* Fallback iframe */}
        <iframe
          src={`${fileUrl}#toolbar=1&navpanes=0`}
          style={{ width: '100%', height: '100%', border: 'none' }}
          title={filename}
        />
        {/* Last-resort text fallback */}
        <div style={{ padding: 24, textAlign: 'center' }}>
          <p style={{ color: 'var(--muted)', marginBottom: 12 }}>
            Your browser cannot display PDFs inline.
          </p>
          <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">
            Open PDF
          </a>
        </div>
      </object>
    );
  }

  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
    return (
      <div style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--surface)',
        padding: 16,
      }}>
        <img
          ref={imgRef}
          src={fileUrl}
          alt={filename}
          onLoad={syncCanvas}
          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 6, display: 'block' }}
        />
        {/* Canvas overlay for citation bbox highlights — sits on top of img, pointer-events:none so it doesn't block interaction */}
        <canvas
          ref={canvasRef}
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
          }}
        />
      </div>
    );
  }

  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--surface)', padding: 24, textAlign: 'center',
    }}>
      <div className="empty-icon-wrap">
        <FileText size={32} />
      </div>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6, color: 'var(--text)' }}>{filename}</div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 20 }}>
        Preview not supported for .{ext} files in-browser.
      </div>
      <a href={fileUrl} download={filename} className="btn btn-ghost btn-sm" style={{ border: '1px solid var(--border)' }}>
        Download File
      </a>
    </div>
  );
}


function getAverageWordConfidence(extracted) {
  const confidences = extracted?.raw_extracted?.field_confidences;
  if (!confidences || typeof confidences !== 'object') return 0;

  const flatConfidences = [];
  const traverse = (obj) => {
    if (typeof obj === 'number') {
      flatConfidences.push(obj);
    } else if (Array.isArray(obj)) {
      obj.forEach(item => traverse(item));
    } else if (obj && typeof obj === 'object') {
      Object.values(obj).forEach(val => traverse(val));
    }
  };
  traverse(confidences);

  if (flatConfidences.length === 0) return 0;
  return flatConfidences.reduce((sum, val) => sum + val, 0) / flatConfidences.length;
}

export function Extraction() {
  const { completedDocs, confidenceMode, fieldHighlightThreshold, autoApproveThreshold, confHighThreshold, confMedThreshold } = useApp();
  const { refresh } = useDocumentList();
  const [activeId, setActiveId] = useState(null);
  const [extracted, setExtracted] = useState(null);
  const [loadingEx, setLoadingEx] = useState(false);
  const [error, setError] = useState(null);
  const [viewerExpanded, setViewerExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedData, setEditedData] = useState({});
  const [saving, setSaving] = useState(false);
  const [templates, setTemplates] = useState({});
  const [sigVerifying, setSigVerifying] = useState(false);
  const [sigResult, setSigResult] = useState(null);
  const [photoVerifying, setPhotoVerifying] = useState(false);
  const [photoResult, setPhotoResult] = useState(null);
  // Field citation highlighting state
  const [ocrBlocks, setOcrBlocks] = useState([]);
  const [hoveredField, setHoveredField] = useState(null);
  const { toast } = useApp();
  const navigate = useNavigate();

  useEffect(() => {
    getTemplates()
      .then(data => setTemplates(data || {}))
      .catch(err => console.error('Failed to load templates:', err));
  }, []);

  const wordConf = extracted ? getAverageWordConfidence(extracted) : 0;
  const pageConf = extracted ? (extracted.confidence_score ?? 0) : 0;

  const displayConfidence = extracted
    ? (confidenceMode === 'page'
      ? pageConf
      : confidenceMode === 'word'
        ? wordConf
        : Math.min(wordConf, pageConf))
    : 0;

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (completedDocs.length > 0 && !activeId) {
      setActiveId(completedDocs[0].id);
    }
  }, [completedDocs, activeId]);

  useEffect(() => {
    if (!activeId) return;
    setLoadingEx(true); setError(null); setExtracted(null); setIsEditing(false); setEditedData({});
    setOcrBlocks([]); setHoveredField(null); // reset citation state on doc switch
    getExtractedData(activeId)
      .then((data) => {
        setExtracted(data);
        if (data?.validated_data) {
          setEditedData(data.validated_data);
        }
        // Load persisted verification results — only show if they contain a valid verdict
        const sigData = data?.signature_verification;
        setSigResult(sigData && sigData.verdict ? sigData : null);
        
        const photoData = data?.photo_verification;
        setPhotoResult(photoData && photoData.verdict ? photoData : null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingEx(false));
    // Fetch OCR blocks for field citation highlighting (non-fatal)
    getOcrBlocks(activeId)
      .then(d => setOcrBlocks(d.available ? d.blocks : []))
      .catch(() => setOcrBlocks([]));
  }, [activeId]);

  const copyJSON = () => {
    if (extracted) {
      navigator.clipboard.writeText(JSON.stringify(extracted.validated_data, null, 2));
    }
  };

  const handleFieldChange = (key, val) => {
    setEditedData((prev) => ({
      ...prev,
      [key]: val,
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateExtractedData(activeId, editedData);
      toast('Extracted data updated successfully ✓', 'success');
      const data = await getExtractedData(activeId);
      setExtracted(data);
      if (data?.validated_data) {
        setEditedData(data.validated_data);
      }
      setIsEditing(false);
    } catch (err) {
      toast('Failed to save changes: ' + err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (extracted?.validated_data) {
      setEditedData(extracted.validated_data);
    }
    setIsEditing(false);
  };

  const handleVerify = async (file, type) => {
    if (!activeId) return;
    const setVerifying = type === 'signature' ? setSigVerifying : setPhotoVerifying;
    const setResult = type === 'signature' ? setSigResult : setPhotoResult;
    setVerifying(true);
    try {
      const result = await verifySignature(activeId, file, type);
      setResult(result);
      toast(`${type === 'signature' ? 'Signature' : 'Photo'} verification complete: ${(result.verdict || 'unknown').toUpperCase()}`,
        result.verdict === 'genuine' ? 'success' : result.verdict === 'uncertain' ? 'warn' : 'error'
      );
    } catch (err) {
      toast(`Verification failed: ${err.message}`, 'error');
    } finally {
      setVerifying(false);
    }
  };

  const handleResetVerification = (type) => {
    if (type === 'signature') {
      setSigResult(null);
    } else {
      setPhotoResult(null);
    }
  };

  const activeDoc = completedDocs.find((d) => d.id === activeId);

  const fieldThresholds = useMemo(() => {
    const map = {};
    if (activeDoc?.doc_type) {
      const docTypeKey = activeDoc.doc_type.toLowerCase().replace(/\s+/g, '_');
      const raw = templates[docTypeKey];
      // Handle both old (list) and new ({fields, is_kyc}) formats
      const fields = Array.isArray(raw) ? raw : (raw?.fields || []);
      fields.forEach(f => {
        if (f.confidence_threshold !== undefined && f.confidence_threshold !== null) {
          map[f.key] = f.confidence_threshold;
        }
      });
    }
    return map;
  }, [templates, activeDoc?.doc_type]);

  const fileUrl = activeId ? getDocumentFileUrl(activeId) : '';
  const ext = activeDoc?.filename?.split('.').pop()?.toLowerCase() ?? '';

  if (completedDocs.length === 0) {
    return (
      <div className="page">
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon-wrap">
              <FileSearch size={32} />
            </div>
            <div className="empty-title">No completed documents</div>
            <div className="empty-sub">Upload and process a document to see extracted data here.</div>
            <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => navigate('/upload')}>
              Upload Document
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      {/* Document Tabs */}
      <div className="tabs">
        {completedDocs.slice(0, 8).map((doc) => (
          <div
            key={doc.id}
            className={`tab ${activeId === doc.id ? 'active' : ''}`}
            onClick={() => setActiveId(doc.id)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <FileText size={13} />
            {doc.filename.length > 24 ? doc.filename.slice(0, 24) + '…' : doc.filename}
          </div>
        ))}
      </div>

      {/* ── Full-screen overlay viewer ── */}
      {viewerExpanded && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(8,11,20,0.90)', backdropFilter: 'blur(16px)',
            display: 'flex', flexDirection: 'column',
            animation: 'fade-in 150ms ease',
          }}
          onClick={(e) => e.target === e.currentTarget && setViewerExpanded(false)}
        >
          {/* Header bar */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 20px', borderBottom: '1px solid var(--border)',
            background: 'var(--card)', flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontWeight: 700, fontSize: 14, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <FileText size={15} />
                {activeDoc?.filename}
              </span>
              {activeDoc?.doc_type && <span className="badge badge-cyan">{activeDoc.doc_type}</span>}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">
                <ExternalLink size={13} /> Open in new tab
              </a>
              <button className="btn btn-ghost btn-sm" onClick={() => setViewerExpanded(false)}>✕ Close</button>
            </div>
          </div>
          {/* Full viewer body */}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <DocumentViewer
              fileUrl={fileUrl}
              filename={activeDoc?.filename ?? ''}
              ext={ext}
              ocrBlocks={ocrBlocks}
              highlightFieldKey={hoveredField}
              extractedData={extracted?.validated_data}
              rawFields={extracted?.raw_extracted?.raw_fields}
            />
          </div>
        </div>
      )}

      {/* ── Side-by-side split layout ── */}
      <div className="extraction-grid" style={{ alignItems: 'start' }}>

        {/* ── LEFT: Sticky document viewer panel ── */}
        <div
          className="doc-preview"
          style={{
            position: 'sticky',
            top: 16,
            padding: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            height: 'min(82vh, 720px)',
          }}
        >
          {/* Panel header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '11px 14px', borderBottom: '1px solid var(--border)',
            flexShrink: 0, background: 'var(--card)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Source Document
              </span>
              {activeDoc?.doc_type && <span className="badge badge-cyan">{activeDoc.doc_type}</span>}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                id="extraction-viewer-expand"
                className="btn btn-ghost btn-sm"
                title="Expand to fullscreen"
                onClick={() => setViewerExpanded(true)}
                style={{ fontSize: 11, padding: '3px 9px', gap: 5 }}
              >
                <Maximize2 size={12} /> Expand
              </button>
              <a
                href={fileUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 11, padding: '3px 9px', gap: 5 }}
              >
                <ExternalLink size={12} /> New tab
              </a>
            </div>
          </div>

          {/* Embedded viewer */}
          <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
            <DocumentViewer
              fileUrl={fileUrl}
              filename={activeDoc?.filename ?? ''}
              ext={ext}
              ocrBlocks={ocrBlocks}
              highlightFieldKey={hoveredField}
              extractedData={extracted?.validated_data}
              rawFields={extracted?.raw_extracted?.raw_fields}
            />
          </div>

          {/* Confidence banner pinned to bottom */}
          {extracted && (
            <div style={{
              padding: '9px 14px', flexShrink: 0,
              borderTop: '1px solid var(--border)',
              background: displayConfidence >= autoApproveThreshold / 100
                ? 'rgba(16,185,129,0.06)'
                : 'rgba(245,158,11,0.06)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{
                fontSize: 12, fontWeight: 600,
                color: displayConfidence >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
              }}>
                {displayConfidence >= autoApproveThreshold / 100 ? (
                  <>
                    <CheckCircle2 size={13} />
                    High Confidence
                  </>
                ) : (
                  <>
                    <AlertTriangle size={13} />
                    Review Recommended
                  </>
                )}
              </span>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                {confidenceMode === 'word' && (
                  <>
                    Word Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(wordConf * 100)}%</strong>
                  </>
                )}
                {confidenceMode === 'page' && (
                  <>
                    Page Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(pageConf * 100)}%</strong>
                  </>
                )}
                {confidenceMode === 'both' && (
                  <>
                    Word Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(wordConf * 100)}%</strong> · Page Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(pageConf * 100)}%</strong>
                  </>
                )}
                {extracted.reviewer_corrections && Object.keys(extracted.reviewer_corrections).length > 0 && (
                  <span style={{ marginLeft: 8, color: 'var(--accent)' }}>
                    · {Object.keys(extracted.reviewer_corrections).length} corrected
                  </span>
                )}
              </span>
            </div>
          )}
        </div>

        {/* ── RIGHT: Extracted fields panel (scrollable) ── */}
        <div className="fields-panel">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Extracted Data</div>
              {extracted && (
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                  {confidenceMode === 'word' && (
                    <>
                      Word Confidence: <span style={{ color: wordConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(wordConf * 100)}%</span>
                    </>
                  )}
                  {confidenceMode === 'page' && (
                    <>
                      Page Confidence: <span style={{ color: pageConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(pageConf * 100)}%</span>
                    </>
                  )}
                  {confidenceMode === 'both' && (
                    <>
                      Word: <span style={{ color: wordConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(wordConf * 100)}%</span> · Page: <span style={{ color: pageConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(pageConf * 100)}%</span>
                    </>
                  )}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {isEditing ? (
                <>
                  <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Check size={12} /> Save
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={handleCancel} disabled={saving} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <X size={12} /> Cancel
                  </button>
                </>
              ) : (
                <>
                  <button className="btn btn-ghost btn-sm" onClick={() => setIsEditing(true)} disabled={!extracted} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Edit2 size={12} /> Edit Fields
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={copyJSON} disabled={!extracted} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Copy size={12} /> Copy JSON
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={!extracted}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(extracted?.validated_data, null, 2)], { type: 'application/json' });
                      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
                      a.download = `${activeDoc?.filename?.replace(/\.[^.]+$/, '') || 'extracted'}.json`;
                      a.click();
                    }}
                  >
                    <Download size={12} /> Export
                  </button>
                </>
              )}
            </div>
          </div>

          {loadingEx && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[100, 80, 90, 70, 85].map((w, i) => (
                <div key={i} className="skeleton" style={{ height: 32, width: `${w}%` }} />
              ))}
            </div>
          )}

          {error && (
            <div style={{ color: 'var(--danger)', fontSize: 13, padding: 12, background: 'rgba(239,68,68,0.08)', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          {extracted && !loadingEx && (
            <>
              {/* ── Identity Verification Section (KYC signature/photo) ── */}
              {extracted.validated_data && (
                extracted.validated_data.signature_image || extracted.validated_data.photo_image ||
                extracted.validated_data.signature_detected !== undefined || extracted.validated_data.photo_detected !== undefined
              ) && (
                  <FieldGroup title="Identity Verification">
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      marginBottom: 10, padding: '6px 0',
                    }}>
                      <ShieldCheck size={14} style={{ color: 'var(--accent)' }} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)' }}>
                        KYC Document — Signature & Photo Extraction
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      <KycImageCard
                        label="Signature"
                        icon={PenTool}
                        base64Data={extracted.validated_data.signature_image}
                        detected={extracted.validated_data.signature_detected}
                        accentColor="#7c3aed"
                        verificationType="signature"
                        documentId={activeId}
                        verificationResult={sigResult}
                        onVerify={handleVerify}
                        isVerifying={sigVerifying}
                      />
                      <KycImageCard
                        label="Photo"
                        icon={UserCircle2}
                        base64Data={extracted.validated_data.photo_image}
                        detected={extracted.validated_data.photo_detected}
                        accentColor="#3b82f6"
                        verificationType="photo"
                        documentId={activeId}
                        verificationResult={photoResult}
                        onVerify={handleVerify}
                        isVerifying={photoVerifying}
                      />
                    </div>

                    {/* Signature Verification Verdict Panel */}
                    {sigResult && (
                      <SignatureVerdictPanel
                        result={sigResult}
                        verificationType="signature"
                        onReset={() => handleResetVerification('signature')}
                      />
                    )}

                    {/* Photo Verification Verdict Panel (Face multi-agent pipeline) */}
                    {photoResult && (
                      <FaceVerdictPanel
                        result={photoResult}
                        onReset={() => handleResetVerification('photo')}
                      />
                    )}
                  </FieldGroup>
                )}

              {extracted.validated_data ? (
                renderFields(extracted.validated_data, isEditing, editedData, handleFieldChange, extracted.raw_extracted?.field_confidences || {}, confidenceMode, confHighThreshold, confMedThreshold, fieldHighlightThreshold, fieldThresholds, extracted.raw_extracted?.raw_fields || {}, ocrBlocks.length ? setHoveredField : null)
              ) : (
                <div className="empty-state" style={{ padding: 24 }}>
                  <div className="empty-sub">No structured data extracted yet.</div>
                </div>
              )}

              {/* Raw extraction */}
              {extracted.raw_extracted && (
                <FieldGroup title="Raw Extraction (OCR)">
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace', padding: 10, background: 'var(--surface)', borderRadius: 6, overflow: 'auto', maxHeight: 180 }}>
                    <pre>{typeof extracted.raw_extracted === 'string' ? extracted.raw_extracted : JSON.stringify(extracted.raw_extracted, null, 2)}</pre>
                  </div>
                </FieldGroup>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

## `src/pages/Validation.jsx`

```jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Edit3, RefreshCw, AlertTriangle, FileText, X, Plus } from 'lucide-react';
import { resumeReview, resumeDuplicate, getExtractedData } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Modal } from '../components/ui/Modal';

function parseArrayOfText(value) {
  if (value === null || value === undefined) return null;
  let parsed = value;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        parsed = JSON.parse(trimmed);
      } catch (e) {
        return null;
      }
    } else {
      return null;
    }
  }
  
  if (Array.isArray(parsed)) {
    if (parsed.length === 0) {
      return parsed;
    }
    if (parsed.every(item => item !== null && typeof item !== 'object')) {
      return parsed.map(String);
    }
  }
  return null;
}

/**
 * Inline field-level corrections editor.
 * Renders extracted fields as styled inputs so reviewers can correct
 * individual values instead of hand-editing raw JSON.
 */
function InlineCorrectionsEditor({ validatedData, onChange }) {
  const [edits, setEdits] = useState(() => {
    // Initialise with current values so the reviewer sees pre-filled inputs
    const init = {};
    if (validatedData && typeof validatedData === 'object') {
      Object.entries(validatedData).forEach(([k, v]) => {
        const arr = parseArrayOfText(v);
        if (arr) {
          init[k] = arr;
        } else if (v != null && typeof v !== 'object') {
          init[k] = String(v);
        }
      });
    }
    return init;
  });

  // Track which keys have been changed from the original
  const [changed, setChanged] = useState(new Set());

  const handleChange = (key, newVal) => {
    const original = validatedData?.[key];
    const isChanged = Array.isArray(newVal)
      ? JSON.stringify(parseArrayOfText(original) || []) !== JSON.stringify(newVal)
      : String(original) !== newVal;

    setChanged((prev) => {
      const next = new Set(prev);
      isChanged ? next.add(key) : next.delete(key);
      return next;
    });

    const next = { ...edits, [key]: newVal };
    setEdits(next);

    // Re-derive corrections from the changed set after this update
    const finalChanged = new Set(changed);
    isChanged ? finalChanged.add(key) : finalChanged.delete(key);
    const finalCorrections = {};
    finalChanged.forEach((k) => {
      let valToSend = next[k];
      if (Array.isArray(valToSend)) {
        const origVal = validatedData?.[k];
        if (typeof origVal === 'string') {
          valToSend = JSON.stringify(valToSend);
        }
      }
      finalCorrections[k] = valToSend;
    });
    onChange(finalCorrections);
  };

  if (!validatedData || typeof validatedData !== 'object') {
    return (
      <div style={{ fontSize: 13, color: 'var(--muted)', padding: '12px 0' }}>
        No extracted fields available to edit.
      </div>
    );
  }

  const primitiveEntries = Object.entries(validatedData).filter(
    ([, v]) => v != null && typeof v !== 'object' && parseArrayOfText(v) === null
  );
  const textArrayEntries = Object.entries(validatedData).filter(
    ([, v]) => v != null && parseArrayOfText(v) !== null
  );
  const objectEntries = Object.entries(validatedData).filter(
    ([, v]) => v != null && typeof v === 'object' && parseArrayOfText(v) === null
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {changed.size > 0 && (
        <div style={{
          fontSize: 12, color: 'var(--accent)', fontWeight: 600,
          padding: '6px 10px', background: 'var(--accent-dim)',
          borderRadius: 6, border: '1px solid rgba(79,110,247,0.2)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
        }}>
          <Edit3 size={13} />
          {changed.size} field{changed.size !== 1 ? 's' : ''} modified
        </div>
      )}

      {primitiveEntries.map(([key, originalVal]) => {
        const isModified = changed.has(key);
        return (
          <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{
              fontSize: 11, fontWeight: 600, color: isModified ? 'var(--accent)' : 'var(--muted)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
              {key.replace(/_/g, ' ')}
              {isModified && (
                <span style={{
                  fontSize: 10, background: 'var(--accent)', color: 'white',
                  borderRadius: 99, padding: '1px 6px',
                }}>modified</span>
              )}
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id={`correction-field-${key}`}
                type="text"
                className="styled-input"
                value={(edits[key] === 'null' || edits[key] === 'NULL') ? '' : (edits[key] ?? '')}
                onChange={(e) => handleChange(key, e.target.value)}
                placeholder={originalVal == null || originalVal === 'null' || originalVal === 'NULL' ? '' : String(originalVal)}
                style={{
                  borderColor: isModified ? 'var(--accent)' : undefined,
                  boxShadow: isModified ? '0 0 0 3px var(--accent-dim)' : undefined,
                  paddingRight: isModified ? 70 : undefined,
                  transition: 'all 0.2s ease',
                }}
              />
              {isModified && (
                <button
                  type="button"
                  onClick={() => handleChange(key, String(originalVal))}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    fontSize: 10, color: 'var(--muted)', background: 'var(--card-alt)',
                    border: '1px solid var(--border)', borderRadius: 4,
                    padding: '2px 7px', cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  title="Reset to original"
                >
                  ↩ reset
                </button>
              )}
            </div>
            {isModified && (
              <div style={{ fontSize: 11, color: 'var(--muted)', paddingLeft: 2 }}>
                Original: <span style={{ fontFamily: 'monospace', color: 'var(--text-dim)' }}>{originalVal == null || originalVal === 'null' || originalVal === 'NULL' ? '' : String(originalVal)}</span>
              </div>
            )}
          </div>
        );
      })}

      {textArrayEntries.map(([key, originalVal]) => {
        const isModified = changed.has(key);
        const currentArray = edits[key] || [];

        const handleAdd = (val) => {
          if (!val.trim()) return;
          handleChange(key, [...currentArray, val.trim()]);
        };

        const handleRemove = (idxToRemove) => {
          handleChange(key, currentArray.filter((_, i) => i !== idxToRemove));
        };

        return (
          <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{
              fontSize: 11, fontWeight: 600, color: isModified ? 'var(--accent)' : 'var(--muted)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
              {key.replace(/_/g, ' ')}
              {isModified && (
                <span style={{
                  fontSize: 10, background: 'var(--accent)', color: 'white',
                  borderRadius: 99, padding: '1px 6px',
                }}>modified</span>
              )}
            </label>
            
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 4, background: 'var(--surface)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
              {currentArray.length === 0 ? (
                <span style={{ color: 'var(--muted)', fontStyle: 'italic', fontSize: 12 }}>No items</span>
              ) : (
                currentArray.map((item, idx) => (
                  <span key={idx} style={{
                    background: 'var(--card-alt)',
                    color: 'var(--text)',
                    padding: '3px 8px',
                    borderRadius: '12px',
                    border: '1px solid var(--border)',
                    fontSize: 11,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4
                  }}>
                    {item}
                    <button
                      type="button"
                      onClick={() => handleRemove(idx)}
                      style={{
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--muted)',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: 0
                      }}
                    >
                      <X size={10} />
                    </button>
                  </span>
                ))
              )}
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="text"
                placeholder="Add item..."
                id={`add-input-${key}`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAdd(e.target.value);
                    e.target.value = '';
                  }
                }}
                style={{
                  flexGrow: 1,
                  padding: '6px 10px',
                  fontSize: 12,
                  background: 'var(--card-alt)',
                  border: '1px solid var(--border)',
                  borderRadius: 4
                }}
              />
              <button
                type="button"
                onClick={() => {
                  const input = document.getElementById(`add-input-${key}`);
                  if (input) {
                    handleAdd(input.value);
                    input.value = '';
                  }
                }}
                className="btn btn-ghost btn-sm"
                style={{ height: 30, padding: '0 10px', fontSize: 11 }}
              >
                <Plus size={11} /> Add
              </button>
            </div>
            
            {isModified && (
              <div style={{ fontSize: 11, color: 'var(--muted)', paddingLeft: 2, marginTop: 2 }}>
                Original: <span style={{ fontFamily: 'monospace', color: 'var(--text-dim)' }}>
                  {JSON.stringify(parseArrayOfText(originalVal))}
                </span>
              </div>
            )}
          </div>
        );
      })}

      {objectEntries.length > 0 && (
        <div style={{
          fontSize: 11, color: 'var(--muted)', padding: '8px 10px',
          background: 'var(--surface)', borderRadius: 6,
          border: '1px solid var(--border)',
        }}>
          <strong>Note:</strong> Complex/nested fields (
          {objectEntries.map(([k]) => <code key={k} style={{ margin: '0 3px' }}>{k}</code>)}
          ) cannot be edited inline and are passed through unchanged.
        </div>
      )}
    </div>
  );
}

function ReviewCard({ doc, onAction }) {
  const [extracted, setExtracted] = useState(null);
  const [showEdit, setShowEdit] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [corrections, setCorrections] = useState({});
  const [loading, setLoading] = useState(false);
  const { toast } = useApp();

  useEffect(() => {
    getExtractedData(doc.id)
      .then(setExtracted)
      .catch(() => {});
  }, [doc.id]);

  const score = extracted?.confidence_score;
  const scoreColor = score == null ? 'var(--muted)' : score >= 0.8 ? 'var(--success)' : 'var(--warn)';

  const handle = async (approved, corr = null, reason = null) => {
    setLoading(true);
    try {
      await resumeReview(doc.workflow_run_id, approved, corr, reason);
      onAction(doc.id, approved ? 'approved' : 'rejected');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    } finally {
      setLoading(false);
      setShowEdit(false);
      setShowRejectConfirm(false);
      setRejectionReason('');
    }
  };

  const handleDuplicate = async (override) => {
    setLoading(true);
    try {
      await resumeDuplicate(doc.workflow_run_id, override);
      onAction(doc.id, override ? 'override' : 'rejected');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    } finally {
      setLoading(false);
      setRejectionReason('');
    }
  };

  const isDuplicateWait = doc.message?.toLowerCase().includes('duplicate');

  const handleSaveAndApprove = () => {
    // Pass corrections only if any fields were changed
    handle(true, Object.keys(corrections).length > 0 ? corrections : null);
  };

  const handleConfirmReject = () => {
    if (isDuplicateWait) {
      handleDuplicate(false);
    } else {
      handle(false, null, rejectionReason.trim() || null);
    }
  };

  return (
    <>
      <div className="card" style={{ borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.03)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
              <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
              {doc.filename}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <StatusBadge status={doc.status} />
              {doc.doc_type && <span className="badge badge-cyan">{doc.doc_type}</span>}
              {score != null && (
                <span className="badge badge-yellow">
                  Confidence: <strong style={{ color: scoreColor }}>{Math.round(score * 100)}%</strong>
                </span>
              )}
            </div>
          </div>
          {doc.message && (
            <span style={{ fontSize: 11, color: 'var(--warn)', maxWidth: 200, textAlign: 'right' }}>
              ⚠ {doc.message}
            </span>
          )}
        </div>

        {/* Extracted fields summary */}
        {extracted?.validated_data && (
          <div style={{ background: 'var(--surface)', borderRadius: 8, padding: 12, marginBottom: 14, fontSize: 12 }}>
            <div style={{ color: 'var(--muted)', marginBottom: 8, fontWeight: 600, fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Extracted Fields
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {Object.entries(extracted.validated_data)
                .filter(([k, v]) => {
                  if (v == null || v === 'null' || v === 'NULL') return false;
                  if (typeof v !== 'object') return true;
                  return parseArrayOfText(v) !== null;
                })
                .slice(0, 8)
                .map(([k, v]) => {
                  const arr = parseArrayOfText(v);
                  const displayVal = arr ? arr.join(', ') : String(v);
                  return (
                    <div key={k}>
                      <span style={{ color: 'var(--muted)' }}>{k.replace(/_/g, ' ')}: </span>
                      <span style={{ color: 'var(--text)', fontWeight: 500 }} title={displayVal}>
                        {displayVal.length > 30 ? displayVal.slice(0, 27) + '...' : displayVal}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          {isDuplicateWait ? (
            <>
              <button className="btn btn-primary" onClick={() => handleDuplicate(true)} disabled={loading}>
                <CheckCircle size={14} /> Override Duplicate
              </button>
              <button className="btn btn-danger" onClick={() => setShowRejectConfirm(true)} disabled={loading}>
                <XCircle size={14} /> Reject
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-success" onClick={() => handle(true)} disabled={loading}>
                <CheckCircle size={14} /> Approve
              </button>
              <button className="btn btn-danger" onClick={() => setShowRejectConfirm(true)} disabled={loading}>
                <XCircle size={14} /> Reject
              </button>
              <button className="btn btn-ghost" onClick={() => { setCorrections({}); setShowEdit(true); }} disabled={loading}>
                <Edit3 size={14} /> Edit &amp; Approve
              </button>
            </>
          )}
        </div>
      </div>

      {/* Reject confirmation modal */}
      {showRejectConfirm && (
        <Modal
          title="Reject Document?"
          subtitle={`This will stop processing for "${doc.filename}". This cannot be undone.`}
          onClose={() => { setShowRejectConfirm(false); setRejectionReason(''); }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => { setShowRejectConfirm(false); setRejectionReason(''); }}>Cancel</button>
              <button
                className="btn btn-danger"
                onClick={handleConfirmReject}
                disabled={loading}
              >
                <XCircle size={14} /> Confirm Reject
              </button>
            </>
          }
        >
          <div style={{
            display: 'flex', gap: 12, alignItems: 'flex-start',
            padding: '12px 14px',
            background: 'var(--danger-dim)', border: '1px solid var(--danger-border)',
            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-md)',
            marginBottom: 12,
          }}>
            <AlertTriangle size={16} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 1 }} />
            <span style={{ color: 'var(--danger)' }}>Rejecting stops the workflow and marks this document as failed.</span>
          </div>
          {!isDuplicateWait && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Rejection Reason <span style={{ color: 'var(--muted)', fontWeight: 400, textTransform: 'none' }}>(optional)</span>
              </label>
              <textarea
                id="rejection-reason-input"
                rows={3}
                placeholder="e.g. Poor document quality, missing fields, suspected fraud…"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '8px 10px',
                  fontSize: 12,
                  background: 'var(--card-alt)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  color: 'var(--text)',
                  resize: 'vertical',
                  lineHeight: 1.5,
                  fontFamily: 'inherit',
                  outline: 'none',
                }}
                onFocus={(e) => { e.target.style.borderColor = 'var(--danger)'; e.target.style.boxShadow = '0 0 0 3px var(--danger-dim)'; }}
                onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none'; }}
              />
            </div>
          )}
        </Modal>
      )}

      {/* ── Feature 21: Inline edit modal with individual field inputs ── */}
      {showEdit && (
        <Modal
          title="Edit &amp; Approve"
          subtitle={`Correct extracted fields for ${doc.filename} — only changed values are submitted.`}
          onClose={() => setShowEdit(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowEdit(false)}>Cancel</button>
              <button
                id="corrections-save-btn"
                className="btn btn-primary"
                onClick={handleSaveAndApprove}
                disabled={loading}
              >
                {Object.keys(corrections).length > 0
                  ? `Save ${Object.keys(corrections).length} Correction${Object.keys(corrections).length !== 1 ? 's' : ''} & Approve`
                  : 'Approve without changes'}
              </button>
            </>
          }
        >
          <InlineCorrectionsEditor
            validatedData={extracted?.validated_data}
            onChange={setCorrections}
          />
        </Modal>
      )}
    </>
  );
}

const RULES = [
  { label: 'Confidence threshold triggers review', badge: '< 80%', variant: 'badge-green' },
  { label: 'Math cross-check on financial docs',   badge: 'Enabled', variant: 'badge-green' },
  { label: 'Date format normalization (ISO 8601)', badge: 'Enabled', variant: 'badge-green' },
  { label: 'Duplicate detection (SHA-256 hash)',   badge: 'Enabled', variant: 'badge-green' },
];

export function Validation() {
  const { reviewDocs, updateDocument, toast } = useApp();
  const { refresh, loading } = useDocumentList();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(new Set());

  useEffect(() => { refresh(); }, []);

  const handleAction = (docId, action) => {
    setDismissed((d) => new Set([...d, docId]));
    const newStatus = action === 'approved' ? 'completed' : 
                      action === 'override' ? 'processing' : 'rejected';
    updateDocument({ id: docId, status: newStatus });
    toast(
      action === 'approved' ? 'Document approved ✓' :
      action === 'override' ? 'Duplicate overridden, processing continues' :
      'Document rejected',
      action === 'rejected' ? 'warn' : 'success'
    );
  };

  const visible = reviewDocs.filter((d) => !dismissed.has(d.id));

  return (
    <div className="page">
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <div>
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertTriangle size={16} style={{ color: 'var(--warn)' }} />
                  Pending Human Review
                </div>
                <div className="card-sub">{visible.length} document{visible.length !== 1 ? 's' : ''} awaiting decision</div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>
                <RefreshCw size={12} className={loading ? 'spin' : ''} />
              </button>
            </div>
          </div>

          {visible.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <div className="empty-icon-wrap" style={{ color: 'var(--success)', background: 'var(--success-dim)', border: '1px solid var(--success-border)' }}>
                  <CheckCircle size={32} />
                </div>
                <div className="empty-title">All clear!</div>
                <div className="empty-sub">No documents are currently awaiting review.</div>
                <button className="btn btn-ghost btn-sm" style={{ marginTop: 14 }} onClick={() => navigate('/documents')}>
                  View All Documents
                </button>
              </div>
            </div>
          ) : (
            visible.map((doc) => (
              <ReviewCard key={doc.id} doc={doc} onAction={handleAction} />
            ))
          )}
        </div>

        <div>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>Validation Rules</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
              {RULES.map((r) => (
                <div key={r.label} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 12px', background: 'var(--surface)', borderRadius: 8,
                }}>
                  <span>{r.label}</span>
                  <span className={`badge ${r.variant}`}>{r.badge}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>How Review Works</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7 }}>
              <p style={{ marginBottom: 8 }}>Documents are automatically approved if confidence ≥ 80%. Otherwise, they enter this review queue.</p>
              <p style={{ marginBottom: 8 }}><strong>Approve</strong> — signals the workflow to finalize and store extracted data.</p>
              <p style={{ marginBottom: 8 }}><strong>Edit &amp; Approve</strong> — opens an inline field editor. Each extracted field appears as a styled input — just change what's wrong and the corrections are tracked automatically. No manual JSON required.</p>
              <p><strong>Reject</strong> — marks the document as rejected and stops processing.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

## `src/pages/ClaimProcess.jsx`

```jsx
import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ClipboardList, FileSearch, Plus, Sparkles, TrendingUp, Clock,
  AlertTriangle, CheckCircle, User, Trash2, ChevronDown, ChevronUp,
  Play, Loader2, FileText, ShieldCheck, ShieldOff, X, Upload, UploadCloud,
} from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { CLAIM_TYPES, PRIORITY_OPTIONS } from './claimData';
import {
  createClaim, listClaims, getClaimStatus, runClaimWorkflow, uploadClaimDocument, deleteClaim,
} from '../api/client';

/* ─── Helpers ─── */
function formatCurrency(amount) {
  if (!amount) return '—';
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
}
function formatCompactCurrency(amount) {
  if (!amount) return '₹0';
  if (amount >= 1_000_000) return `₹${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `₹${(amount / 1_000).toFixed(0)}K`;
  return `₹${amount}`;
}
function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* ─── Status config ─── */
const statusConfig = {
  creating:   { label: 'Creating Request…', icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  extracting: { label: 'Extracting Docs…',  icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  ready:      { label: 'Ready to Process',  icon: <CheckCircle size={14} />,              cls: 'approved'   },
  processing: { label: 'Processing…',       icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_integrity: { label: 'Processing… (Integrity)', icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_medical:   { label: 'Processing… (Medical)',   icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_treatment: { label: 'Processing… (Treatment)', icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_disability:{ label: 'Processing… (Disability)',icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_litigation:{ label: 'Processing… (Litigation)',icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  generating_report:  { label: 'Processing… (Report)',    icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  completed:  { label: 'Report Ready',      icon: <FileText size={14} />,                 cls: 'pending'    },
  approved:   { label: 'Approved',          icon: <ShieldCheck size={14} />,              cls: 'approved'   },
  rejected:   { label: 'Rejected',          icon: <X size={14} />,                        cls: 'rejected'   },
  failed:     { label: 'Failed',            icon: <AlertTriangle size={14} />,            cls: 'missing'    },
};

const borderMap = {
  ready:      'border-success',
  processing: 'border-info',
  failed:     'border-warn',
};



/* ─── Main component ─── */
export function ClaimProcess() {
  const navigate = useNavigate();
  const [claims, setClaims]       = useState([]);
  const [loading, setLoading]     = useState(true);
  const [loadError, setLoadError] = useState('');
  const [expandedId, setExpanded] = useState(null);
  const [dialogOpen, setDialog]   = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [deletingId, setDeletingId] = useState(null);

  /* Form state */
  const [fName, setFName]         = useState('');
  const [fPriority, setFPriority] = useState('medium');
  const [fDesc, setFDesc]         = useState('');
  const [fFiles, setFFiles]       = useState([]);
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef(null);

  /* Per-claim doc status cache for expanded card */
  const [docStatuses, setDocStatuses]     = useState({});
  const [uploadingDocKey, setUploadingDocKey] = useState(null);

  const pollRef = useRef(null);

  /* ── Load claims from API ─────────────────────────────────────── */
  const loadClaims = useCallback(async () => {
    try {
      setLoadError('');
      const data = await listClaims();
      setClaims(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to load claims:', e);
      setLoadError(e.message || 'Failed to load claims');
    } finally {
      setLoading(false);
    }
  }, []);

  /* ── Direct Upload handler for required/extra docs ─────────────── */
  const handleDirectUpload = useCallback(async (claimId, files, docType) => {
    if (!files) return;
    const fileList = Array.isArray(files) ? files : [files];
    if (fileList.length === 0) return;
    const key = `${claimId}_${docType || 'general'}`;
    setUploadingDocKey(key);
    try {
      for (const file of fileList) {
        await uploadClaimDocument(claimId, file, docType);
      }
      const data = await getClaimStatus(claimId);
      setDocStatuses(prev => ({ ...prev, [claimId]: data }));
      await loadClaims();
    } catch (e) {
      alert(`Failed to upload document: ${e.message}`);
    } finally {
      setUploadingDocKey(null);
    }
  }, [loadClaims]);

  useEffect(() => {
    loadClaims();
  }, [loadClaims]);

  /* ── Poll active claims every 6s ─────────────────────────────── */
  useEffect(() => {
    const ACTIVE = ['creating', 'extracting', 'processing'];
    const hasActive = claims.some(c => ACTIVE.includes(c.status));
    if (hasActive) {
      pollRef.current = setInterval(loadClaims, 6000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [claims, loadClaims]);

  /* ── Fetch doc statuses for expanded claim ───────────────────── */
  useEffect(() => {
    if (!expandedId) return;
    const fetchDocStatus = async () => {
      try {
        const data = await getClaimStatus(expandedId);
        setDocStatuses(prev => ({ ...prev, [expandedId]: data }));
      } catch (e) {
        console.error('Failed to fetch doc status:', e);
      }
    };
    fetchDocStatus();
    const interval = setInterval(fetchDocStatus, 5000);
    return () => clearInterval(interval);
  }, [expandedId]);

  const resetForm = useCallback(() => {
    setFName(''); setFPriority('medium');
    setFDesc(''); setFFiles([]);
    setSubmitError('');
  }, []);

  const handleToggle = useCallback((id) => setExpanded(prev => prev === id ? null : id), []);

  /* ── Process: trigger workflow ───────────────────────────────── */
  const handleProcess = useCallback(async (claimId) => {
    try {
      await runClaimWorkflow(claimId);
      navigate(`/claim-workflow?claim_id=${claimId}`);
    } catch (e) {
      alert(`Failed to start workflow: ${e.message}`);
    }
  }, [navigate]);

  /* ── View report (already completed) ────────────────────────── */
  const handleViewReport = useCallback((claimId) => {
    navigate(`/claim-workflow?claim_id=${claimId}&view_report=1`);
  }, [navigate]);

  /* ── Delete claim ─────────────────────────────────────────────── */
  const handleDelete = useCallback(async (claimId, claimantName) => {
    if (!window.confirm(`Delete claim for "${claimantName}"? This cannot be undone.`)) return;
    setDeletingId(claimId);
    try {
      await deleteClaim(claimId);
      setClaims(prev => prev.filter(c => c.claim_id !== claimId));
      if (expandedId === claimId) setExpanded(null);
    } catch (e) {
      alert(`Failed to delete claim: ${e.message}`);
    } finally {
      setDeletingId(null);
    }
  }, [expandedId]);

  /* ── Bulk file upload helpers ─────────────────────────────────── */
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFFiles(prev => [...prev, ...newFiles]);
    }
  }, []);

  const handleFileSelect = useCallback((e) => {
    if (e.target.files && e.target.files[0]) {
      const newFiles = Array.from(e.target.files);
      setFFiles(prev => [...prev, ...newFiles]);
    }
  }, []);

  const removeFile = useCallback((idxToRemove) => {
    setFFiles(prev => prev.filter((_, i) => i !== idxToRemove));
  }, []);

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  /* ── Create claim + upload docs ──────────────────────────────── */
  const handleCreate = useCallback(async () => {
    if (!fName.trim() || fFiles.length === 0) return;
    setSubmitting(true);
    setSubmitError('');

    try {
      // 1. Create claim record
      const claimData = await createClaim({
        claimant_name: fName.trim(),
        claim_type: 'unknown',
        policy_number: 'unknown',
        description: fDesc.trim() || undefined,
        priority: fPriority,
        amount: 0,
      });

      const claimId = claimData.claim_id;

      // 2. Upload each doc sequentially
      for (const file of fFiles) {
        try {
          await uploadClaimDocument(claimId, file, undefined);
        } catch (uploadErr) {
          console.error(`Failed to upload ${file.name}:`, uploadErr);
        }
      }

      // 3. Refresh list and close modal
      await loadClaims();
      resetForm();
      setDialog(false);
    } catch (e) {
      setSubmitError(e.message || 'Failed to create claim. Check backend connection.');
    } finally {
      setSubmitting(false);
    }
  }, [fName, fDesc, fPriority, fFiles, loadClaims, resetForm]);

  const isFormValid = fName.trim() && fFiles.length > 0;

  /* ── Stats ────────────────────────────────────────────────────── */
  const pendingCount  = claims.filter(c => ['creating', 'extracting', 'ready'].includes(c.status)).length;
  const activeCount   = claims.filter(c => c.status === 'processing').length;
  const totalAmount   = claims.reduce((s, c) => s + (c.amount || 0), 0);

  return (
    <div className="claim-page">
      {/* Header */}
      <div className="claim-page-header" style={{ marginBottom: 20 }}>
        <div>
          <div className="chip" style={{ marginBottom: 6 }}>
            <Sparkles size={12} /> Claims Dashboard
          </div>
          <div className="claim-page-title">
            Claim Approval <span className="grad">Requests</span>
          </div>
          <div className="claim-page-sub">
            Create a claim, upload documents, and run the AI validation pipeline.
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setDialog(true)}>
          <Plus size={14} /> Create New Request
        </button>
      </div>

      {/* Stats */}
      <div className="claim-stats-grid anim-slide-in" style={{ marginBottom: 20 }}>
        <div className="claim-stat">
          <div className="claim-stat-icon accent"><ClipboardList size={16} /></div>
          <div>
            <div className="claim-stat-value">{claims.length}</div>
            <div className="claim-stat-label">Total Claims</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon info"><Clock size={16} /></div>
          <div>
            <div className="claim-stat-value">{pendingCount}</div>
            <div className="claim-stat-label">Pending / Ready</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon warn"><AlertTriangle size={16} /></div>
          <div>
            <div className="claim-stat-value">{activeCount}</div>
            <div className="claim-stat-label">Processing</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon success"><TrendingUp size={16} /></div>
          <div>
            <div className="claim-stat-value">{formatCompactCurrency(totalAmount)}</div>
            <div className="claim-stat-label">Total Value</div>
          </div>
        </div>
      </div>

      {/* List header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <FileSearch size={14} color="var(--muted)" />
        <span style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>
          All Requests ({claims.length})
        </span>
      </div>

      {/* Claim list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {loading ? (
          <div className="card-glass" style={{ textAlign: 'center', padding: '56px 24px' }}>
            <Loader2 size={24} className="spin" style={{ margin: '0 auto 12px', display: 'block', color: 'var(--accent)' }} />
            <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>Loading claims…</div>
          </div>
        ) : loadError ? (
          <div className="card-glass" style={{ textAlign: 'center', padding: '56px 24px' }}>
            <AlertTriangle size={24} style={{ margin: '0 auto 12px', display: 'block', color: 'var(--warn)' }} />
            <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>{loadError}</div>
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={loadClaims}>Retry</button>
          </div>
        ) : claims.length === 0 ? (
          <div className="card-glass" style={{ textAlign: 'center', padding: '56px 24px' }}>
            <div className="empty-icon-wrap"><ClipboardList size={24} /></div>
            <div className="empty-title">No claim requests</div>
            <div className="empty-sub">Click "Create New Request" to add your first claim.</div>
          </div>
        ) : (
          claims.map((claim, i) => {
            const status   = statusConfig[claim.status] || statusConfig.failed;
            const border   = borderMap[claim.status] || '';
            const expanded = expandedId === claim.id || expandedId === claim.claim_id;
            const cid      = claim.claim_id;
            const docStatus = docStatuses[cid];

            return (
              <div
                key={cid}
                className={`claim-card ${border} anim-slide-in`}
                style={{ animationDelay: `${i * 40}ms` }}
              >
                {/* Main row */}
                <div className="claim-card-main">
                  <div className="claim-card-left">
                    <div className="claim-card-avatar"><User size={18} /></div>
                    <div className="claim-card-info">
                      <div className="claim-card-name-row">
                        <span className="claim-card-name">{claim.claimant_name}</span>
                        <span className="claim-card-id">{cid}</span>
                        {claim.priority && (
                          <span className={`priority-badge ${claim.priority}`}>
                            <span className="priority-dot" />
                            {claim.priority.charAt(0).toUpperCase() + claim.priority.slice(1)}
                          </span>
                        )}
                      </div>
                      <div className="claim-card-meta">
                        {claim.claim_type} · Policy {claim.policy_number} · {formatDate(claim.submitted_at)}
                      </div>
                      {claim.description && (
                        <div className="claim-card-desc">{claim.description}</div>
                      )}
                    </div>
                  </div>

                  <div className="claim-card-right">
                    <div className="claim-card-amount">
                      <div className="claim-card-amount-value">{formatCurrency(claim.amount)}</div>
                      <div className={`claim-card-status ${status.cls}`}>
                        {status.icon} {status.label}
                      </div>
                    </div>
                    <div className="claim-card-actions">
                      <button className="btn btn-ghost btn-icon btn-sm" title="Toggle" onClick={() => handleToggle(cid)}>
                        {(expandedId === cid) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>

                      {/* Delete button */}
                      <button
                        className="btn btn-ghost btn-icon btn-sm"
                        title="Delete claim"
                        disabled={deletingId === cid}
                        onClick={(e) => { e.stopPropagation(); handleDelete(cid, claim.claimant_name); }}
                        style={{ color: 'var(--error, #dc2626)' }}
                      >
                        {deletingId === cid ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
                      </button>

                      {/* Process button — only when ready */}
                      {claim.status === 'ready' && (
                        <button className="claim-btn-process" onClick={() => handleProcess(cid)}>
                          <Play size={14} /> Process
                        </button>
                      )}

                      {/* Spinner while extracting/creating/processing */}
                      {['creating', 'extracting', 'processing'].includes(claim.status) && (
                        <button className="btn btn-ghost btn-sm" disabled>
                          <Loader2 size={14} className="spin" />
                          {claim.status === 'processing' ? 'Processing' : 'Extracting'}
                        </button>
                      )}

                      {/* View report for completed/approved/rejected */}
                      {['completed', 'approved', 'rejected'].includes(claim.status) && (
                        <button className="claim-btn-process" style={{ background: 'var(--surface-2)', color: 'var(--text)' }} onClick={() => handleViewReport(cid)}>
                          <FileText size={14} /> View Report
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded doc panel with Warning Banner Above & 2 Columns Below */}
                {expandedId === cid && (
                  <div className="claim-card-expand">
                    {/* Top Header Bar */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                      <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
                        Claim Requirements ({docStatus?.claim_type || claim.claim_type || 'General'})
                      </div>
                      <div style={{ display: 'flex', gap: 10 }}>
                        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--success)', background: 'rgba(16,185,129,0.15)', padding: '3px 10px', borderRadius: 6 }}>
                          {docStatus?.required_docs?.filter(d => d.is_completed)?.length || 0} Completed
                        </span>
                        {docStatus?.missing_required_count > 0 ? (
                          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: '#f59e0b', background: 'rgba(245,158,11,0.15)', padding: '3px 10px', borderRadius: 6 }}>
                            {docStatus.missing_required_count} Pending
                          </span>
                        ) : (
                          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--success)', background: 'rgba(16,185,129,0.15)', padding: '3px 10px', borderRadius: 6 }}>
                            All Complete
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Warning / Status Banner (ABOVE COLUMNS) */}
                    <div style={{ marginBottom: 18 }}>
                      {docStatus?.ready_to_process ? (
                        <div className="claim-docs-verified" style={{ padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <ShieldCheck size={22} color="var(--success)" />
                            <div>
                              <div className="claim-docs-verified-title">All required documents uploaded & extracted</div>
                              <div className="claim-docs-verified-sub" style={{ marginTop: 2 }}>Ready for automated AI claim verification pipeline.</div>
                            </div>
                          </div>
                          <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                            <UploadCloud size={14} /> Upload Extra Document(s)
                            <input
                              type="file"
                              multiple
                              style={{ display: 'none' }}
                              onChange={(e) => {
                                if (e.target.files && e.target.files.length > 0) {
                                  handleDirectUpload(cid, Array.from(e.target.files), 'general');
                                }
                              }}
                            />
                          </label>
                        </div>
                      ) : (
                        <div className="claim-docs-verified" style={{ background: 'rgba(245,158,11,0.08)', borderColor: 'rgba(245,158,11,0.3)', padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <AlertTriangle size={22} color="#f59e0b" />
                            <div>
                              <div className="claim-docs-verified-title" style={{ color: '#f59e0b' }}>
                                {docStatus?.missing_required_count || 0} Compulsory Document(s) Pending Upload
                              </div>
                              <div className="claim-docs-verified-sub" style={{ marginTop: 2 }}>
                                Please upload all pending compulsory documents below to enable AI claim evaluation.
                              </div>
                            </div>
                          </div>
                          <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', flexShrink: 0 }}>
                            <UploadCloud size={14} /> Upload Extra Document(s)
                            <input
                              type="file"
                              multiple
                              style={{ display: 'none' }}
                              onChange={(e) => {
                                if (e.target.files && e.target.files.length > 0) {
                                  handleDirectUpload(cid, Array.from(e.target.files), 'general');
                                }
                              }}
                            />
                          </label>
                        </div>
                      )}
                    </div>

                    {/* 2 Main Columns */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                      
                      {/* COLUMN 1: COMPLETED DOCUMENTS */}
                      <div style={{ background: 'var(--surface)', padding: 14, borderRadius: 10, border: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                          <CheckCircle size={16} color="var(--success)" />
                          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text)' }}>
                            Completed Documents ({docStatus?.required_docs?.filter(d => d.is_completed)?.length || 0})
                          </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {docStatus?.required_docs?.filter(d => d.is_completed).length > 0 ? (
                            docStatus.required_docs.filter(d => d.is_completed).map((req, idx) => (
                              <div key={idx} className="claim-doc-item present" style={{ justifyContent: 'space-between', padding: '10px 12px' }}>
                                <div style={{ minWidth: 0 }}>
                                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text)' }}>
                                    {req.label}
                                  </div>
                                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {req.filename}
                                  </div>
                                </div>
                                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--success)', background: 'rgba(16,185,129,0.12)', padding: '3px 8px', borderRadius: 6, flexShrink: 0 }}>
                                  Extracted
                                </span>
                              </div>
                            ))
                          ) : (
                            <div style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)', padding: '12px 0', textAlign: 'center' }}>
                              No completed documents uploaded yet.
                            </div>
                          )}
                        </div>
                      </div>

                      {/* COLUMN 2: PENDING DOCUMENTS */}
                      <div style={{ background: 'var(--surface)', padding: 14, borderRadius: 10, border: '1px solid rgba(245,158,11,0.25)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                          <AlertTriangle size={16} color="#f59e0b" />
                          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text)' }}>
                            Pending Documents ({docStatus?.required_docs?.filter(d => !d.is_completed)?.length || 0})
                          </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {docStatus?.required_docs?.filter(d => !d.is_completed).length > 0 ? (
                            docStatus.required_docs.filter(d => !d.is_completed).map((req, idx) => {
                              const uploadKey = `${cid}_${req.doc_type}`;
                              const isUploading = uploadingDocKey === uploadKey;
                              return (
                                <div key={idx} className="claim-doc-item missing" style={{ justifyContent: 'space-between', padding: '10px 12px' }}>
                                  <div style={{ minWidth: 0 }}>
                                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text)' }}>
                                      {req.label} <span style={{ color: '#dc2626' }}>*</span>
                                    </div>
                                    {req.is_uploaded ? (
                                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        Uploaded: {req.filename}
                                      </div>
                                    ) : (
                                      <div style={{ fontSize: 'var(--text-xs)', color: '#f59e0b', fontWeight: 500 }}>
                                        Not uploaded yet
                                      </div>
                                    )}
                                  </div>

                                  {req.is_uploaded ? (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--accent)', background: 'rgba(6,192,219,0.12)', padding: '4px 10px', borderRadius: 6, flexShrink: 0 }}>
                                      <Loader2 size={13} className="spin" /> Processing…
                                    </span>
                                  ) : (
                                    <label style={{ cursor: isUploading ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--accent)', background: 'rgba(6,192,219,0.1)', padding: '5px 12px', borderRadius: 6, border: '1px solid rgba(6,192,219,0.3)', flexShrink: 0 }}>
                                      {isUploading ? <Loader2 size={13} className="spin" /> : <Upload size={13} />}
                                      {isUploading ? 'Uploading…' : 'Upload'}
                                      <input
                                        type="file"
                                        multiple
                                        style={{ display: 'none' }}
                                        disabled={isUploading}
                                        onChange={(e) => {
                                          if (e.target.files && e.target.files.length > 0) {
                                            handleDirectUpload(cid, Array.from(e.target.files), req.doc_type);
                                          }
                                        }}
                                      />
                                    </label>
                                  )}
                                </div>
                              );
                            })
                          ) : (
                            <div style={{ color: 'var(--success)', fontSize: 'var(--text-xs)', padding: '12px 0', textAlign: 'center', fontWeight: 600 }}>
                              🎉 All required documents uploaded!
                            </div>
                          )}
                        </div>
                      </div>

                    </div>

                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', fontSize: 'var(--text-sm)', color: 'var(--muted)', padding: '32px 0 16px' }}>
        Atlas · Document Intelligence · Claim Processing
      </div>

      {/* Create Dialog */}
      {dialogOpen && (
        <Modal
          title="Create New Claim Request"
          subtitle="Fill in claim details and upload all documents. Document classification is performed automatically during processing."
          onClose={() => { setDialog(false); resetForm(); }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => { setDialog(false); resetForm(); }} disabled={submitting}>Cancel</button>
              <button className="btn btn-primary" disabled={!isFormValid || submitting} onClick={handleCreate}>
                {submitting ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
                {submitting ? 'Creating…' : 'Create & Upload'}
              </button>
            </>
          }
        >
          {/* Claimant + Priority */}
          <div className="claim-form-grid">
            <div>
              <label className="claim-form-label">Claimant Name <span className="required">*</span></label>
              <input className="styled-input" placeholder="e.g. Priya S. Kapoor" value={fName} onChange={e => setFName(e.target.value)} />
            </div>
            <div>
              <label className="claim-form-label">Priority</label>
              <select className="styled-select" value={fPriority} onChange={e => setFPriority(e.target.value)}>
                {PRIORITY_OPTIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
          </div>

          {/* Description */}
          <div style={{ marginTop: 14 }}>
            <label className="claim-form-label">Description</label>
            <textarea 
              className="styled-input" 
              placeholder="Brief description of claim details, incident, or remarks…" 
              value={fDesc} 
              onChange={e => setFDesc(e.target.value)}
              style={{ minHeight: 80, resize: 'vertical', width: '100%', fontFamily: 'inherit' }}
            />
          </div>

          {/* Bulk Document upload section */}
          <div style={{ marginTop: 20 }}>
            <label className="claim-form-label" style={{ marginBottom: 10, display: 'block' }}>
              Documents <span className="required">*</span>
              <span style={{ fontWeight: 400, color: 'var(--muted)', marginLeft: 6 }}>(upload all files at once)</span>
            </label>
            
            <div 
              className={`bulk-upload-zone ${dragActive ? 'drag-active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud className="bulk-upload-icon" size={28} />
              <div className="bulk-upload-title">Drag & drop your files here or <span style={{ color: 'var(--accent)', textDecoration: 'underline' }}>browse</span></div>
              <div className="bulk-upload-sub">Supports PDF, JPG, PNG, WEBP, DOCX up to 10MB</div>
              <input 
                type="file" 
                ref={fileInputRef} 
                style={{ display: 'none' }} 
                multiple 
                onChange={handleFileSelect} 
                accept=".pdf,.jpg,.jpeg,.png,.webp,.docx" 
              />
            </div>

            {fFiles.length > 0 && (
              <div className="bulk-file-list">
                {fFiles.map((file, i) => (
                  <div key={i} className="bulk-file-item">
                    <div className="bulk-file-info">
                      <FileText size={14} color="var(--accent)" />
                      <span className="bulk-file-name" title={file.name}>{file.name}</span>
                      <span className="bulk-file-size">({formatFileSize(file.size)})</span>
                    </div>
                    <button 
                      className="btn btn-ghost btn-icon btn-sm" 
                      onClick={(e) => { e.stopPropagation(); removeFile(i); }} 
                      title="Remove file"
                      type="button"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {submitError && (
            <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--error-dim, rgba(220,38,38,0.1))', border: '1px solid var(--error, #dc2626)', borderRadius: 8, color: 'var(--error, #dc2626)', fontSize: 'var(--text-sm)' }}>
              {submitError}
            </div>
          )}

          <div className="claim-form-note" style={{ marginTop: 16 }}>
            <strong>Note:</strong> Documents are automatically classified (e.g. claim form, policy document, medical report) and synced during processing.
          </div>
        </Modal>
      )}
    </div>
  );
}
```

## `src/pages/ClaimWorkflow.jsx`

```jsx
import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, CheckCircle, ChevronDown, Download, Loader2, RotateCcw,
  Circle, AlertTriangle, X as XIcon, Brain, Copy, FileOutput, Sparkles,
  ThumbsUp, ThumbsDown, ShieldCheck, ShieldOff, Scale, Gavel, FileText, FileCode, ClipboardList,
} from 'lucide-react';
import { INITIAL_STEPS, stepDuration } from './claimData';
import { runClaimWorkflow, rerunClaimWorkflow, getClaimStatus, getClaimReport, submitClaimDecision } from '../api/client';

/* ─── JSON syntax highlighter ─── */
function highlightJson(json) {
  return json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/(\".*?\")(\s*:)/g, '<span class="json-key">$1</span>$2')
    .replace(/:\s*(\".*?\")/g, ': <span class="json-string">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span class="json-bool">$1</span>')
    .replace(/:\s*(-?\d+(?:\.\d+)?)/g, ': <span class="json-number">$1</span>');
}

/* ─── State icon ─── */
function StateIcon({ state, size = 14 }) {
  if (state === 'running')   return <Loader2 size={size} className="spin" />;
  if (state === 'completed') return <CheckCircle size={size} />;
  if (state === 'warning')   return <AlertTriangle size={size} />;
  if (state === 'failed')    return <XIcon size={size} />;
  return <Circle size={size} />;
}

/* ─── Status label for overall_status ─── */
function OverallStatusBadge({ status }) {
  if (!status) return null;
  const s = status.toUpperCase();
  if (s === 'APPROVE') return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 14px', borderRadius: 8, background: 'var(--success-dim)', color: 'var(--success)', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
      <ShieldCheck size={14} /> APPROVE
    </div>
  );
  if (s === 'REJECT') return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 14px', borderRadius: 8, background: 'rgba(220,38,38,0.12)', color: '#dc2626', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
      <ShieldOff size={14} /> REJECT
    </div>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 14px', borderRadius: 8, background: 'var(--warn-dim)', color: 'var(--warn)', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
      <Scale size={14} /> REVIEW BEFORE APPROVAL
    </div>
  );
}

/* ─── Agent result card ─── */
function AgentResultCard({ name, result }) {
  const [open, setOpen] = useState(false);
  const status = result?.status || 'UNKNOWN';
  const color = status === 'PASS' ? 'var(--success)' : status === 'FAIL' ? '#dc2626' : status === 'FLAG' ? 'var(--warn)' : 'var(--muted)';

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', marginBottom: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: 'var(--surface)', border: 'none', cursor: 'pointer', color: 'var(--text)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color, background: `${color}18`, padding: '2px 8px', borderRadius: 4 }}>{status}</span>
        </div>
        <ChevronDown size={14} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms', color: 'var(--muted)' }} />
      </button>
      {open && (
        <div style={{ padding: '12px 14px', background: 'var(--surface-2)', borderTop: '1px solid var(--border)' }}>
          {result?.overall_reason && (
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginBottom: 10 }}>{result.overall_reason}</div>
          )}
          {result?.checks?.map((check, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6 }}>
              <span style={{
                fontSize: 'var(--text-xs)', fontWeight: 700, flexShrink: 0, marginTop: 1,
                color: check.result === 'PASS' ? 'var(--success)' : check.result === 'FAIL' ? '#dc2626' : 'var(--warn)'
              }}>
                {check.result}
              </span>
              <div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>{check.name}</div>
                {check.explanation && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', marginTop: 2 }}>{check.explanation}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Structured output view for the Output tab ─── */
function AgentOutputView({ output, state }) {
  if (state === 'waiting') {
    return <div className="wf-placeholder"><FileOutput size={16} /> Output will appear when this step completes…</div>;
  }
  if (state === 'running') {
    return (
      <div>
        <div className="wf-placeholder reasoning"><Loader2 size={16} className="spin" /> Agent is running checks…</div>
        <div className="wf-skeleton-bars" style={{ marginTop: 16, padding: 16, borderRadius: 'var(--radius)', border: '1px solid rgba(59,130,246,0.2)', background: 'rgba(59,130,246,0.05)' }}>
          <div className="wf-skeleton-bar" style={{ width: '60%' }} />
          <div className="wf-skeleton-bar" />
          <div className="wf-skeleton-bar" style={{ width: '80%' }} />
        </div>
      </div>
    );
  }
  if (!output) return <div className="wf-placeholder">No output available.</div>;

  const status = output.status || 'UNKNOWN';
  const statusColor =
    status === 'PASS'  ? 'var(--success)' :
    status === 'FAIL'  ? '#dc2626' :
    status === 'FLAG'  ? 'var(--warn)' :
    status === 'ERROR' ? '#dc2626' : 'var(--muted)';
  const statusBg = `${statusColor}18`;

  const checkColor = r =>
    r === 'PASS'  ? 'var(--success)' :
    r === 'FAIL'  ? '#dc2626' :
    r === 'FLAG'  ? 'var(--warn)' : 'var(--muted)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Status banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 8, background: statusBg, border: `1px solid ${statusColor}30` }}>
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text)' }}>
          {output.agent || 'Agent'}
        </div>
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: statusColor, background: `${statusColor}22`, padding: '3px 10px', borderRadius: 6, letterSpacing: '0.04em' }}>
          {status}
        </span>
      </div>

      {/* Checks list */}
      {output.checks?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {output.checks.map((check, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '9px 12px', borderRadius: 8, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
              <span style={{ flexShrink: 0, marginTop: 1, fontSize: 'var(--text-xs)', fontWeight: 700, color: checkColor(check.result), background: `${checkColor(check.result)}18`, padding: '2px 7px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                {check.result || '—'}
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text)', marginBottom: check.explanation ? 3 : 0 }}>{check.name}</div>
                {check.explanation && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', lineHeight: 1.5 }}>{check.explanation}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Overall reason */}
      {output.overall_reason && (
        <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 'var(--text-sm)', color: 'var(--muted)', lineHeight: 1.6 }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 6 }}>Overall Reason</div>
          {output.overall_reason}
        </div>
      )}
    </div>
  );
}

/* ─── The CLAIM STEP definitions (maps to 5 agents + generate step) ─── */
const CLAIM_STEPS = [
  {
    id: 'integrity', label: 'Claim Integrity',
    summary: 'Validates completeness, dates, policy, duplicates',
    description: 'Checking required fields, verifying date logic, confirming the policy was active on the incident date, and scanning for duplicate submissions.',
  },
  {
    id: 'medical', label: 'Medical Check',
    summary: 'Validates diagnosis, ICD code, provider, documentation',
    description: 'Validating the diagnosis description, verifying the ICD code format, confirming provider credentials, and checking for supporting medical documentation.',
  },
  {
    id: 'treatment', label: 'Treatment Review',
    summary: 'Validates treatment-diagnosis alignment and billing',
    description: 'Confirming treatment matches the diagnosed condition, reviewing procedure codes, and checking for billing anomalies or over-billing patterns.',
  },
  {
    id: 'disability', label: 'Disability Check',
    summary: 'Validates certificate, severity, limitations',
    description: 'Verifying the disability certificate is present and valid, assessing severity classification, and confirming reported functional limitations are consistent.',
  },
  {
    id: 'litigation', label: 'Litigation Scan',
    summary: 'Detects attorney involvement and fraud indicators',
    description: 'Scanning for attorney representation, cross-referencing prior claim history for fraud patterns, and flagging any legal hold indicators.',
  },
  {
    id: 'report', label: 'Report Generation',
    summary: 'Generates final suggestion and overall decision',
    description: 'Synthesising all agent results into a final recommendation and overall approval decision.',
  },
];

export function ClaimWorkflow() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const claimId    = searchParams.get('claim_id');
  const viewReport = searchParams.get('view_report') === '1';

  const [steps, setSteps]     = useState(() => CLAIM_STEPS.map(s => ({ ...s, state: 'waiting', duration: undefined })));
  const [running, setRunning] = useState(false);
  const [done, setDone]       = useState(false);
  const [active, setActive]   = useState(CLAIM_STEPS[0].id);
  const [openSteps, setOpen]  = useState({});
  const [tab, setTab]         = useState('thought');
  const [report, setReport]   = useState(null);
  const [claimStatus, setClaimStatus] = useState(null);
  const [error, setError]     = useState(null);
  const [decisionSent, setDecisionSent] = useState(false);
  const [decisionResult, setDecisionResult] = useState(null);
  const startedRef             = useRef(false);
  const pollRef                = useRef(null);      // holds setInterval id
  const pollFnRef              = useRef(null);      // stable ref to latest pollStatus

  /* ── Map backend claim status → step states ─── */
  const mapStatusToSteps = useCallback((status, agentResults) => {
    // Keys must match what the backend stores in agent_results
    const order = ['claim_integrity', 'medical', 'treatment', 'disability', 'litigation', 'report'];
    const processingSteps = ['checking_integrity', 'checking_medical', 'checking_treatment', 'checking_disability', 'checking_litigation', 'generating_report'];

    const isCompleted = status === 'completed' || status === 'approved' || status === 'rejected';
    const currentIdx = processingSteps.indexOf(status);

    setSteps(prev => prev.map((s, idx) => {
      const agentKey = order[idx];

      if (agentResults && agentResults[agentKey]) {
        // Agent completed — use real data
        const result = agentResults[agentKey];
        const agentStatus = result.status;
        return {
          ...s,
          state: agentStatus === 'ERROR' ? 'failed' : agentStatus === 'FAIL' ? 'warning' : 'completed',
          agentThought: result.overall_reason || '',
          output: result,
          outputKind: 'json',
          confidence: agentStatus === 'PASS' ? 0.97 : 0.7,
        };
      } else if (isCompleted) {
        // Workflow done but no agent result for this step (e.g. 'report' step) — mark completed
        return { ...s, state: 'completed' };
      } else if (currentIdx >= 0 && idx === currentIdx) {
        return { ...s, state: 'running' };
      } else if (currentIdx >= 0 && idx < currentIdx) {
        return { ...s, state: 'completed' };
      }
      return { ...s, state: 'waiting' };
    }));
  }, []);

  /* ── Poll claim status ─── */
  // Defined once; pollFnRef keeps the latest version stable so setInterval never goes stale.
  const pollStatus = useCallback(async () => {
    if (!claimId) return;
    try {
      const statusData = await getClaimStatus(claimId);
      setClaimStatus(statusData);

      const cs = statusData.claim_status;

      if (cs === 'completed' || cs === 'approved' || cs === 'rejected') {
        clearInterval(pollRef.current);
        setRunning(false);
        setDone(true);

        // Restore adjuster decision from DB status so refresh doesn't reset it
        if (cs === 'approved' || cs === 'rejected') {
          setDecisionResult(cs);
          setDecisionSent(true);
        }

        try {
          const reportData = await getClaimReport(claimId);
          setReport(reportData);
          setSteps(prev => prev.map(s => ({ ...s, state: 'completed' })));
          if (reportData.agent_results) {
            mapStatusToSteps('completed', reportData.agent_results);
          }
        } catch (e) {
          console.error('Failed to load report:', e);
        }
      } else if (cs === 'processing' || cs.startsWith('checking_') || cs === 'generating_report') {
        setRunning(true);
        mapStatusToSteps(cs, statusData.agent_results || null);
      } else if (cs === 'failed') {
        clearInterval(pollRef.current);
        setRunning(false);
        setError('Claim workflow failed. Please try again.');
      }
    } catch (e) {
      console.error('Poll error:', e);
    }
  }, [claimId, mapStatusToSteps]);

  // Keep the ref in sync so the interval always calls the latest closure.
  pollFnRef.current = pollStatus;

  const startPolling = useCallback(() => {
    clearInterval(pollRef.current);
    // Use ref so the interval callback is always fresh — avoids stale closure / self-cancel
    pollRef.current = setInterval(() => pollFnRef.current(), 4000);
    pollFnRef.current(); // immediate first tick
  }, []);

  /* ── On mount: check current status first, then start / resume / load ─── */
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    if (!claimId) {
      setError('No claim ID provided. Go back and select a claim.');
      return;
    }

    if (viewReport) {
      // Explicit report view — load report and status in parallel
      setDone(true);
      Promise.all([getClaimReport(claimId), getClaimStatus(claimId)])
        .then(([r, statusData]) => {
          setReport(r);
          // Restore adjuster decision so buttons don't reappear on refresh
          const cs = statusData.claim_status;
          if (cs === 'approved' || cs === 'rejected') {
            setDecisionResult(cs);
            setDecisionSent(true);
          }
          if (r.agent_results) {
            setSteps(prev => prev.map((s, idx) => {
              const key = ['integrity', 'medical', 'treatment', 'disability', 'litigation', 'report'][idx];
              const result = r.agent_results[key];
              if (!result) return { ...s, state: 'completed' };
              return {
                ...s,
                state: result.status === 'ERROR' ? 'failed' : result.status === 'FAIL' ? 'warning' : 'completed',
                agentThought: result.overall_reason || '',
                output: result,
                outputKind: 'json',
                confidence: 0.95,
              };
            }));
          }
        })
        .catch(e => setError(`Failed to load report: ${e.message}`));
      return;
    }

    // Always check current status first — handles refresh mid-flight cleanly
    getClaimStatus(claimId).then(statusData => {
      const cs = statusData.claim_status;

      if (cs === 'completed' || cs === 'approved' || cs === 'rejected') {
        // Restore adjuster decision immediately — don't wait for pollStatus chain
        if (cs === 'approved' || cs === 'rejected') {
          setDecisionResult(cs);
          setDecisionSent(true);
        }
        // Load report
        pollFnRef.current();
      } else if (cs === 'processing' || cs.startsWith('checking_') || cs === 'generating_report') {
        // Already running (e.g. after a refresh) — resume polling, don't re-POST /run
        setRunning(true);
        mapStatusToSteps(cs, null);
        startPolling();
      } else {
        // Not started yet — fire the workflow then poll
        setRunning(true);
        runClaimWorkflow(claimId)
          .catch(() => { /* 409 or other — still poll below */ })
          .finally(() => startPolling());
      }
    }).catch(() => {
      // Status fetch failed — fall back to starting workflow
      setRunning(true);
      runClaimWorkflow(claimId)
        .catch(() => {})
        .finally(() => startPolling());
    });

    return () => clearInterval(pollRef.current);
  }, [claimId, viewReport]); // pollStatus intentionally omitted — use pollFnRef to stay stable

  /* ── Auto-scroll on done ─── */
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => document.getElementById('completion-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 400);
    return () => clearTimeout(t);
  }, [done]);

  const restart = useCallback(() => navigate('/claim-process'), [navigate]);

  const rerun = useCallback(() => {
    if (!claimId) return;
    clearInterval(pollRef.current);
    setSteps(CLAIM_STEPS.map(s => ({ ...s, state: 'waiting', duration: undefined })));
    setRunning(true);
    setDone(false);
    setReport(null);
    setError(null);
    setDecisionSent(false);
    setDecisionResult(null);
    setActive(CLAIM_STEPS[0].id);
    rerunClaimWorkflow(claimId)
      .catch((e) => setError(`Failed to rerun: ${e?.response?.data?.detail || e.message}`))
      .finally(() => startPolling());
  }, [claimId, startPolling]);

  const handleDecision = useCallback(async (decision) => {
    if (!claimId || decisionSent) return;
    setDecisionSent(true);
    try {
      const result = await submitClaimDecision(claimId, decision);
      setDecisionResult(result.decision);
    } catch (e) {
      alert(`Failed to submit decision: ${e.message}`);
      setDecisionSent(false);
    }
  }, [claimId, decisionSent]);

  const completedCount  = steps.filter(s => s.state === 'completed').length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);
  const currentStep     = steps.find(s => s.id === active) || steps[0];
  const isJson          = currentStep.outputKind === 'json';
  const jsonContent     = currentStep.state === 'waiting' ? '// Waiting…' : isJson ? JSON.stringify(currentStep.output, null, 2) : String(currentStep.output ?? '');
  const thoughtText     = currentStep.agentThought ?? '';

  if (error) {
    return (
      <div className="claim-page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 16 }}>
        <AlertTriangle size={32} color="var(--warn)" />
        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>Workflow Error</div>
        <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>{error}</div>
        <button className="btn btn-primary" onClick={restart}><ArrowLeft size={14} /> Back to Claims</button>
      </div>
    );
  }

  return (
    <div className="claim-page">
      {/* Status bar */}
      <div className={`wf-status-bar${done ? ' done' : ''}`} style={{ marginBottom: 20 }}>
        <div className="wf-status-left">
          <button className="btn btn-ghost btn-sm" onClick={restart}>
            <ArrowLeft size={14} /> Back
          </button>
          <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
          <div>
            <div className="wf-status-info-title">
              {running ? <><Loader2 size={14} className="spin" style={{ color: 'var(--info)' }} /> Claim analysis in progress…</> :
               done    ? <><CheckCircle size={14} style={{ color: 'var(--success)' }} /> <span style={{ color: 'var(--success)' }}>Claim analysis completed</span></> :
                         'Initializing workflow…'}
            </div>
            <div className="wf-status-info-sub">
              {claimId} · {completedCount}/{steps.length} agents complete
            </div>
          </div>
        </div>
        <div className="wf-status-right">
          <div className="wf-progress-bar">
            <div className={`wf-progress-fill${done ? ' done' : ''}`} style={{ width: `${progressPercent}%` }} />
          </div>
          <span className={`wf-progress-pct${done ? ' done' : ''}`}>{progressPercent}%</span>
          {done && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 8 }}>
              <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
              <button className="btn btn-ghost btn-sm" onClick={() => document.getElementById('completion-summary')?.scrollIntoView({ behavior: 'smooth' })}>
                <ChevronDown size={14} /> View results
              </button>
              <button className="btn btn-ghost btn-sm" onClick={rerun} title="Rerun workflow">
                <RotateCcw size={14} /> Rerun
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Three panel layout */}
      <div style={{ display: 'flex', gap: 20, flex: 1, padding: 20, minHeight: 0 }}>
        {/* ── Left Sidebar: Stepper (HIDDEN) ── 
        <div className="wf-sidebar">
          <div className="wf-timeline-header">
            <div>
              <div className="wf-timeline-title">AI execution timeline</div>
              <div className="wf-timeline-sub">5 validation agents + report</div>
            </div>
            <span className="wf-timeline-tag">{claimId || 'claim'}</span>
          </div>
          <div className="wf-timeline-list">
            <div className="wf-timeline-line" />
            {steps.map(s => {
              const isOpen   = openSteps[s.id] ?? s.state === 'running';
              const isActive = active === s.id;
              return (
                <div key={s.id}>
                  <button
                    className={`wf-step-btn${isActive ? ' active' : ''}`}
                    onClick={() => { setActive(s.id); setOpen(o => ({ ...o, [s.id]: !isOpen })); }}
                  >
                    <div className={`wf-step-circle ${s.state}`}><StateIcon state={s.state} size={14} /></div>
                    <div className="wf-step-content">
                      <div className="wf-step-top">
                        <div className="wf-step-label">{s.label}</div>
                        <div className="wf-step-metrics">
                          {s.output?.status && s.state === 'completed' && (
                            <span className="wf-step-conf" style={{
                              color: s.output.status === 'PASS' ? 'var(--success)' : s.output.status === 'FAIL' ? '#dc2626' : 'var(--warn)'
                            }}>{s.output.status}</span>
                          )}
                          <ChevronDown size={12} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }} />
                        </div>
                      </div>
                      <div className="wf-step-summary">{s.summary}</div>
                    </div>
                  </button>
                  {isOpen && s.state !== 'waiting' && (
                    <div className="wf-step-thought">
                      {s.state === 'running' ? (
                        <div className="wf-step-reasoning"><Loader2 size={12} className="spin" /> Agent is running checks…</div>
                      ) : (
                        <>
                          <div className="wf-step-thought-label"><Brain size={12} /> Agent Result</div>
                          <div className="wf-step-thought-text">{thoughtText || s.summary}</div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        */}

        {/* ── Pipeline Graph ── */}
        <div className="wf-pipeline" style={{ flex: 1 }}>
          <div className="wf-pipeline-header">
            <div>
              <div className="wf-pipeline-title">Workflow graph</div>
              <div className="wf-pipeline-sub">Live execution across {steps.length} nodes</div>
            </div>
            <div className="wf-pipeline-legend">
              {['running', 'completed', 'waiting'].map(s => (
                <span key={s} className="wf-legend-item">
                  <span className={`wf-legend-dot ${s}`} /> {s.charAt(0).toUpperCase() + s.slice(1)}
                </span>
              ))}
            </div>
          </div>
          <div className="wf-graph-canvas">
            <svg className="wf-graph-dots" width="100%" height="100%">
              <defs>
                <pattern id="dotPattern" x="0" y="0" width="18" height="18" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="1" fill="var(--border)" opacity="0.4" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#dotPattern)" />
            </svg>
            <div className="wf-graph-grid-wrap">
              <svg className="wf-graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none">
                {steps.slice(0, -1).map((s, i) => {
                  const next = steps[i + 1];
                  const cols = 2, rows = Math.ceil(steps.length / cols);
                  const cx = col => col === 0 ? 25 : 75;
                  const rowH = 100 / rows;
                  const cy = row => row * rowH + rowH / 2;
                  const sCol = i % cols, sRow = Math.floor(i / cols);
                  const tCol = (i + 1) % cols, tRow = Math.floor((i + 1) / cols);
                  let sx = cx(sCol);
                  let sy = cy(sRow);
                  let tx = cx(tCol);
                  let ty = cy(tRow);
                  
                  if (sRow === tRow) {
                    // Horizontal connection
                    sx += 14;
                    tx -= 14;
                  } else {
                    // Vertical/Diagonal connection
                    sy += 6;
                    ty -= 6;
                  }

                  const finished = ['completed', 'warning', 'failed'];
                  const isComplete = finished.includes(s.state) && finished.includes(next.state);
                  
                  let d = '';
                  if (sRow === tRow) {
                    d = `M ${sx} ${sy} L ${tx} ${ty}`;
                  } else {
                    const midY = (sy + ty) / 2;
                    d = `M ${sx} ${sy} C ${sx} ${midY}, ${tx} ${midY}, ${tx} ${ty}`;
                  }
                  return (
                    <path key={`${s.id}->${next.id}`} d={d} fill="none"
                      stroke={isComplete ? 'var(--success)' : 'var(--border)'}
                      strokeWidth={isComplete ? 2 : 1.25}
                      vectorEffect="non-scaling-stroke"
                    />
                  );
                })}
              </svg>
              <div className="wf-graph-grid">
                {steps.map(s => {
                  const isActive = active === s.id;
                  return (
                    <div key={s.id} className={`wf-graph-node ${s.state}${isActive ? ' active' : ''}`} onClick={() => setActive(s.id)}>
                      <div className="wf-graph-node-head">
                        <div className={`wf-graph-node-icon ${s.state}`}><StateIcon state={s.state} size={12} /></div>
                        <div className="wf-graph-node-label">{s.label}</div>
                      </div>
                      <div className="wf-graph-node-foot">
                        <span className={`wf-graph-node-state ${s.state}`}>
                          {s.state === 'waiting' ? 'Waiting' : s.state === 'running' ? 'Running' : s.output?.status || 'Done'}
                        </span>
                        <span className="wf-graph-node-dur">{s.output?.status || '—'}</span>
                      </div>
                      {s.state === 'running' && (
                        <div className="wf-pipe-node-shimmer"><div className="wf-pipe-node-shimmer-bar" /></div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* ── Agent Inspector ── */}
        <div className="wf-inspector" style={{ flex: 1 }}>
          <div className="wf-inspector-header">
            <div style={{ minWidth: 0 }}>
              <div className="wf-inspector-title">Agent Inspector</div>
              <div className="wf-inspector-sub">{currentStep.label} · {currentStep.state === 'running' ? 'running…' : currentStep.state}</div>
            </div>
            <select className="styled-select" value={currentStep.id} onChange={e => setActive(e.target.value)} style={{ width: 170, fontSize: 'var(--text-sm)', padding: '5px 8px' }}>
              {steps.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
          <div className="wf-inspector-tabs">
            {[
              { key: 'thought', icon: <Brain size={12} />, label: 'Agent Thought' },
              { key: 'output',  icon: <FileOutput size={12} />, label: 'Output' },
              { key: 'meta',    icon: <Sparkles size={12} />, label: 'Metadata' },
            ].map(t => (
              <button key={t.key} className={`wf-inspector-tab${tab === t.key ? (t.key === 'thought' ? ' active' : ' active-output') : ''}`} onClick={() => setTab(t.key)}>
                {t.icon} {t.label}
              </button>
            ))}
            <div className="wf-inspector-actions">
              <button className="btn btn-ghost btn-icon btn-sm" title="Copy" onClick={() => navigator.clipboard?.writeText(tab === 'thought' ? thoughtText : jsonContent)}>
                <Copy size={14} />
              </button>
            </div>
          </div>
          <div className="wf-inspector-body">
            {tab === 'thought' && (
              currentStep.state === 'waiting' ? (
                <div className="wf-placeholder"><Brain size={16} /> Agent will reason when this step starts…</div>
              ) : currentStep.state === 'running' ? (
                <div>
                  {/* Description of what this agent checks — shown while running */}
                  <div className="wf-thought-chain-label"><ClipboardList size={14} /> What this agent checks</div>
                  <div className="wf-thought-chain-box" style={{ marginBottom: 16 }}>
                    <div className="wf-thought-chain-text">{currentStep.description}</div>
                  </div>
                  <div className="wf-placeholder reasoning"><Loader2 size={16} className="spin" /> Agent is reasoning…</div>
                  <div className="wf-skeleton-bars" style={{ marginTop: 16, padding: 16, borderRadius: 'var(--radius)', border: '1px solid rgba(59,130,246,0.2)', background: 'rgba(59,130,246,0.05)' }}>
                    <div className="wf-skeleton-bar" style={{ width: '75%' }} />
                    <div className="wf-skeleton-bar" />
                    <div className="wf-skeleton-bar" />
                  </div>
                </div>
              ) : (
                <div>
                  {/* Agent reasoning on top */}
                  <div className="wf-thought-chain-label"><Brain size={14} /> Agent Reasoning</div>
                  <div className="wf-thought-chain-box" style={{ marginBottom: 16 }}>
                    <div className="wf-thought-chain-text">{thoughtText || 'No thought available.'}</div>
                  </div>
                  {/* Description of checks below, secondary */}
                  <div className="wf-thought-chain-label" style={{ color: 'var(--muted)' }}><ClipboardList size={14} /> Checks performed</div>
                  <div className="wf-thought-chain-box">
                    <div className="wf-thought-chain-text" style={{ color: 'var(--muted)' }}>{currentStep.description}</div>
                  </div>
                </div>
              )
            )}
            {tab === 'output' && (
              <AgentOutputView output={currentStep.output} state={currentStep.state} />
            )}
            {tab === 'meta' && (
              <div className="wf-meta-grid">
                {[
                  ['Agent', currentStep.label],
                  ['State', currentStep.state],
                  ['Status', currentStep.output?.status || '—'],
                  ['Claim ID', claimId || '—'],
                  ['Model', 'mistral-large-latest'],
                  ['Mode', 'autonomous'],
                ].map(([k, v]) => (
                  <div key={k} className="wf-meta-item">
                    <div className="wf-meta-key">{k}</div>
                    <div className="wf-meta-val">{v}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Completion Summary with real report ── */}
      {done && report && (
        <div id="completion-summary" className="wf-completion" style={{ marginBottom: 20 }}>
          {/* Header */}
          <div className="wf-completion-header">
            <div className="wf-completion-icon"><CheckCircle size={20} /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="wf-completion-title">Claim Analysis Complete</div>
              <div className="wf-completion-sub">
                {report.claim_id} · {report.claimant_name} · {report.processed_at ? new Date(report.processed_at).toLocaleString('en-IN') : ''}
              </div>
            </div>
            <div className="wf-completion-actions">
              <OverallStatusBadge status={report.overall_status} />
              <button className="btn btn-ghost btn-sm" onClick={restart}><RotateCcw size={14} /> Back to Claims</button>
            </div>
          </div>

          {/* Agent results accordion */}
          <div style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 12 }}>
              Agent Results
            </div>
            {Object.entries(report.agent_results || {}).map(([key, result]) => (
              <AgentResultCard key={key} name={key} result={result} />
            ))}
          </div>

          {/* AI Suggestion + Decision */}
          <div className="wf-decision-grid" style={{ padding: '0 20px 20px' }}>
            <div>
              <div className="wf-suggestion-title"><Brain size={14} style={{ color: 'var(--accent)' }} /> AI Suggestion</div>
              <div className="wf-suggestion-box">
                <div className="wf-suggestion-rec"><Sparkles size={16} /> Recommendation: {report.overall_status}</div>
                <p className="wf-suggestion-text">
                  {report.suggestion || 'No suggestion available.'}
                </p>
              </div>
            </div>

            <div>
              <div className="wf-suggestion-title"><Gavel size={14} style={{ color: 'var(--success)' }} /> Adjuster Decision</div>
              <div className="wf-final-decision">
                {decisionResult ? (
                  <>
                    <div className="wf-final-icon-wrap">
                      <div className="wf-final-icon" style={decisionResult === 'rejected' ? { background: 'rgba(220,38,38,0.12)', color: '#dc2626' } : {}}>
                        {decisionResult === 'approved' ? <ShieldCheck size={40} /> : <ShieldOff size={40} />}
                      </div>
                    </div>
                    <div className="wf-final-verdict" style={{ color: decisionResult === 'rejected' ? '#dc2626' : undefined }}>
                      {decisionResult.toUpperCase()}
                    </div>
                    <div className="wf-final-verdict-sub">Decision recorded successfully</div>
                  </>
                ) : (
                  <>
                    <div style={{ marginBottom: 16, color: 'var(--muted)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>
                      Review the AI suggestion and make your decision.
                    </div>
                    <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                      <button
                        className="btn btn-primary"
                        disabled={decisionSent}
                        onClick={() => handleDecision('approve')}
                        style={{ background: 'var(--success)', borderColor: 'var(--success)' }}
                      >
                        <ShieldCheck size={14} /> Accept Claim
                      </button>
                      <button
                        className="btn btn-ghost"
                        disabled={decisionSent}
                        onClick={() => handleDecision('reject')}
                        style={{ color: '#dc2626', borderColor: '#dc2626' }}
                      >
                        <ShieldOff size={14} /> Reject Claim
                      </button>
                    </div>
                    <div style={{ marginTop: 16, color: 'var(--muted)', fontSize: 'var(--text-xs)', textAlign: 'center' }}>
                      Claim: {report.claim_id} · {report.claimant_name}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading state before report */}
      {done && !report && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Loader2 size={24} className="spin" style={{ color: 'var(--accent)', margin: '0 auto 12px', display: 'block' }} />
          <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>Loading report…</div>
        </div>
      )}

      {/* Footer */}
      <div style={{ textAlign: 'center', fontSize: 'var(--text-sm)', color: 'var(--muted)', padding: '32px 0 16px' }}>
        Atlas · Document Intelligence · Claim Processing
      </div>
    </div>
  );
}
```

## `src/pages/Settings.jsx`

```jsx
import { useState, useEffect } from 'react';
import { useApp } from '../store/AppStore';
import { getNormConfig, saveNormConfig, getClassificationConfig, saveClassificationConfig } from '../api/client';
import {
  Settings as SettingsIcon, SlidersHorizontal, BarChart3,
  CheckCircle2, Circle, ChevronRight, Zap, Eye, ShieldCheck,
  Palette, Info, RotateCcw, Save, Tag, Trash2, Plus,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────────
   Sidebar nav items
───────────────────────────────────────────────────────────── */
const NAV = [
  { id: 'confidence',  label: 'Confidence Scores',  icon: BarChart3,        desc: 'Granularity & display mode' },
  { id: 'thresholds',  label: 'Thresholds',         icon: SlidersHorizontal, desc: 'Highlight & approval limits' },
  { id: 'normalization', label: 'Normalization Format', icon: Palette,      desc: 'Date, number & name rules' },
  { id: 'classification', label: 'Classification Types', icon: Tag,          desc: 'Supported document types' },
];

/* ─────────────────────────────────────────────────────────────
   Tiny helper: section header
───────────────────────────────────────────────────────────── */
function SectionHeader({ icon: Icon, label, desc, color = 'var(--accent)' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 28 }}>
      <div style={{
        width: 42, height: 42, borderRadius: 10, flexShrink: 0,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 22%, transparent)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color,
      }}>
        <Icon size={18} />
      </div>
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.2px' }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{desc}</div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Confidence mode toggle card
───────────────────────────────────────────────────────────── */
function ModeCard({ active, icon: Icon, title, subtitle, onClick, accentColor = 'var(--accent)' }) {
  return (
    <button
      onClick={onClick}
      style={{
        all: 'unset', width: '100%', cursor: 'pointer',
        display: 'flex', alignItems: 'flex-start', gap: 14,
        padding: '16px 18px', borderRadius: 10,
        border: active ? `1.5px solid ${accentColor}` : '1.5px solid var(--border)',
        background: active ? `color-mix(in srgb, ${accentColor} 7%, var(--card-alt))` : 'var(--card-alt)',
        transition: 'all 0.18s ease',
        boxSizing: 'border-box',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {active && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: `linear-gradient(90deg, ${accentColor}, color-mix(in srgb, ${accentColor} 40%, transparent))`,
        }} />
      )}
      <div style={{
        width: 36, height: 36, borderRadius: 8, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: active ? `color-mix(in srgb, ${accentColor} 14%, transparent)` : 'var(--surface)',
        border: `1px solid ${active ? `color-mix(in srgb, ${accentColor} 25%, transparent)` : 'var(--border)'}`,
        color: active ? accentColor : 'var(--muted)',
        transition: 'all 0.18s ease',
      }}>
        <Icon size={16} />
      </div>
      <div style={{ flex: 1, textAlign: 'left' }}>
        <div style={{
          fontWeight: 600, fontSize: 13,
          color: active ? accentColor : 'var(--text)',
          marginBottom: 4, transition: 'color 0.18s ease',
        }}>{title}</div>
        <div style={{ fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.55 }}>{subtitle}</div>
      </div>
      <div style={{ marginTop: 2, flexShrink: 0 }}>
        {active
          ? <CheckCircle2 size={17} color={accentColor} />
          : <Circle size={17} color="var(--muted)" />}
      </div>
    </button>
  );
}

/* ─────────────────────────────────────────────────────────────
   Professional threshold slider
───────────────────────────────────────────────────────────── */
function ThresholdControl({ label, description, value, onChange, min = 50, max = 100, accentColor, icon: Icon, presets }) {
  const pct = ((value - min) / (max - min)) * 100;
  const ac = accentColor || 'var(--accent)';

  return (
    <div style={{
      background: 'var(--card-alt)', borderRadius: 10,
      border: '1px solid var(--border)', overflow: 'hidden',
    }}>
      {/* Header row */}
      <div style={{ padding: '14px 18px 12px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
        {Icon && (
          <div style={{
            width: 28, height: 28, borderRadius: 6, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: `color-mix(in srgb, ${ac} 12%, transparent)`,
            color: ac,
          }}>
            <Icon size={13} />
          </div>
        )}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{label}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1, lineHeight: 1.4 }}>{description}</div>
        </div>
        {/* Live value badge */}
        <div style={{
          fontSize: 18, fontWeight: 800, letterSpacing: '-0.5px',
          color: ac, minWidth: 48, textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {value}<span style={{ fontSize: 11, fontWeight: 600, opacity: 0.7 }}>%</span>
        </div>
      </div>

      {/* Slider body */}
      <div style={{ padding: '14px 18px 16px' }}>
        {/* Custom slider track */}
        <div style={{ position: 'relative', height: 8, borderRadius: 99, background: 'var(--border)', marginBottom: 10 }}>
          {/* Fill */}
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0,
            width: `${pct}%`, borderRadius: 99,
            background: `linear-gradient(90deg, color-mix(in srgb, ${ac} 60%, var(--border)), ${ac})`,
            transition: 'width 0.05s',
          }} />
          {/* Invisible native input on top */}
          <input
            type="range"
            min={min}
            max={max}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            style={{
              position: 'absolute', inset: '-6px 0',
              width: '100%', height: 'calc(100% + 12px)',
              opacity: 0, cursor: 'pointer', margin: 0,
              WebkitAppearance: 'none',
            }}
          />
          {/* Thumb indicator */}
          <div style={{
            position: 'absolute', top: '50%',
            left: `calc(${pct}% - 9px)`,
            transform: 'translateY(-50%)',
            width: 18, height: 18, borderRadius: '50%',
            background: ac, border: '2.5px solid var(--card)',
            boxShadow: `0 0 0 3px color-mix(in srgb, ${ac} 25%, transparent), 0 2px 6px rgba(0,0,0,0.15)`,
            pointerEvents: 'none',
            transition: 'left 0.05s',
          }} />
        </div>

        {/* Min / Max labels */}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: presets ? 12 : 0 }}>
          <span>{min}%</span>
          <span>{max}%</span>
        </div>

        {/* Preset chips */}
        {presets && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, color: 'var(--muted)', alignSelf: 'center', marginRight: 2 }}>Quick:</span>
            {presets.map((p) => (
              <button
                key={p}
                onClick={() => onChange(p)}
                style={{
                  all: 'unset', cursor: 'pointer',
                  fontSize: 10, fontWeight: 600, padding: '2px 9px',
                  borderRadius: 99,
                  background: value === p ? `color-mix(in srgb, ${ac} 15%, transparent)` : 'var(--surface)',
                  border: `1px solid ${value === p ? ac : 'var(--border)'}`,
                  color: value === p ? ac : 'var(--text-dim)',
                  transition: 'all 0.15s ease',
                }}
              >
                {p}%
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Info callout
───────────────────────────────────────────────────────────── */
function InfoCallout({ children }) {
  return (
    <div style={{
      display: 'flex', gap: 10, alignItems: 'flex-start',
      background: 'color-mix(in srgb, var(--accent) 6%, var(--card-alt))',
      border: '1px solid color-mix(in srgb, var(--accent) 15%, transparent)',
      borderRadius: 8, padding: '10px 14px', marginBottom: 20,
    }}>
      <Info size={13} color="var(--accent)" style={{ marginTop: 1, flexShrink: 0 }} />
      <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6, margin: 0 }}>{children}</p>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   CONFIDENCE SCORES SECTION
───────────────────────────────────────────────────────────── */
function ConfidenceSection({ confidenceMode, setConfidenceMode, toast }) {
  const isWord = confidenceMode === 'word' || confidenceMode === 'both';
  const isPage = confidenceMode === 'page' || confidenceMode === 'both';

  const toggleWord = () => {
    if (isWord && !isPage) { toast('At least one type must be active.', 'error'); return; }
    const next = isWord ? 'page' : 'both';
    setConfidenceMode(next);
    toast(`Granularity: ${next === 'both' ? 'Word + Page' : 'Page-wise'} ✓`, 'success');
  };

  const togglePage = () => {
    if (isPage && !isWord) { toast('At least one type must be active.', 'error'); return; }
    const next = isPage ? 'word' : 'both';
    setConfidenceMode(next);
    toast(`Granularity: ${next === 'both' ? 'Word + Page' : 'Word-wise'} ✓`, 'success');
  };

  return (
    <div>
      <SectionHeader icon={BarChart3} label="Confidence Score Granularity" desc="Choose how confidence is computed and displayed on the Extraction page" />

      <InfoCallout>
        You can enable one or both confidence modes simultaneously. Word-wise gives field-level detail; Page-wise shows the OCR structural accuracy from Mistral.
      </InfoCallout>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <ModeCard
          active={isWord}
          icon={Eye}
          title="Word-wise Confidence"
          subtitle="Field-level confidence scores per extracted value (e.g., Vendor Name, Total Amount). Overall score = average of all field confidences."
          onClick={toggleWord}
          accentColor="var(--accent)"
        />
        <ModeCard
          active={isPage}
          icon={BarChart3}
          title="Page-wise Confidence"
          subtitle="Average page-level OCR confidence from Mistral. Hides field variation badges — gives a clean structural accuracy view."
          onClick={togglePage}
          accentColor="var(--accent2)"
        />
      </div>

      {/* Active mode summary pill */}
      <div style={{
        marginTop: 16, display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderRadius: 8,
        background: 'var(--surface)', border: '1px solid var(--border)',
      }}>
        <Zap size={12} color="var(--accent)" />
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>Active mode:</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>
          {confidenceMode === 'both' ? 'Word-wise + Page-wise'
            : confidenceMode === 'word' ? 'Word-wise only'
            : 'Page-wise only'}
        </span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   THRESHOLDS SECTION
───────────────────────────────────────────────────────────── */
function ThresholdsSection({
  fieldHighlightThreshold, setFieldHighlightThreshold,
  autoApproveThreshold,    setAutoApproveThreshold,
  confHighThreshold,       setConfHighThreshold,
  confMedThreshold,        setConfMedThreshold,
  toast,
}) {
  const handleHigh = (v) => {
    if (v <= confMedThreshold) { toast('High threshold must exceed the Medium threshold.', 'error'); return; }
    setConfHighThreshold(v);
    toast(`High badge threshold → ${v}% ✓`, 'success');
  };
  const handleMed = (v) => {
    if (v >= confHighThreshold) { toast('Medium threshold must be below the High threshold.', 'error'); return; }
    setConfMedThreshold(v);
    toast(`Medium badge threshold → ${v}% ✓`, 'success');
  };

  return (
    <div>
      <SectionHeader icon={SlidersHorizontal} label="Confidence Thresholds" desc="Fine-tune when fields are flagged, highlighted, or auto-approved" />

      {/* Sub-group: Review & Highlighting */}
      <div style={{ marginBottom: 24 }}>
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color: 'var(--muted)', marginBottom: 12, paddingLeft: 2,
        }}>
          Review & Highlighting
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <ThresholdControl
            label="Auto-Approve Threshold"
            description="Documents at or above this confidence are automatically approved. Below this → human review queue."
            value={autoApproveThreshold}
            onChange={(v) => { setAutoApproveThreshold(v); toast(`Auto-approve → ${v}% ✓`, 'success'); }}
            min={50} max={100}
            accentColor="var(--success)"
            icon={ShieldCheck}
            presets={[70, 75, 80, 85, 90]}
          />
          <ThresholdControl
            label="Field Value Highlight"
            description="Fields whose word-level confidence falls below this are highlighted amber in the Extraction panel."
            value={fieldHighlightThreshold}
            onChange={(v) => { setFieldHighlightThreshold(v); toast(`Field highlight → ${v}% ✓`, 'success'); }}
            min={50} max={100}
            accentColor="var(--warn)"
            icon={Eye}
            presets={[80, 85, 90, 95, 100]}
          />
        </div>
      </div>

      {/* Sub-group: Badge Colors */}
      <div>
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color: 'var(--muted)', marginBottom: 12, paddingLeft: 2,
        }}>
          Field Badge Colors
        </div>

        {/* Color legend */}
        <div style={{
          display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap',
        }}>
          {[
            { label: 'High (green)', color: 'var(--success)', range: `≥ ${confHighThreshold}%` },
            { label: 'Medium (amber)', color: 'var(--warn)', range: `${confMedThreshold}%–${confHighThreshold - 1}%` },
            { label: 'Low (red)', color: 'var(--danger)', range: `< ${confMedThreshold}%` },
          ].map(({ label, color, range }) => (
            <div key={label} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 10px', borderRadius: 99,
              background: 'var(--card-alt)', border: '1px solid var(--border)',
              fontSize: 11, color: 'var(--text-dim)',
            }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block', boxShadow: `0 0 5px ${color}` }} />
              <span>{label}:</span>
              <span style={{ fontWeight: 600, color: 'var(--text)' }}>{range}</span>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <ThresholdControl
            label="High Confidence (Green) Threshold"
            description={`Fields at or above this value display a green badge. Must stay above Medium (${confMedThreshold}%).`}
            value={confHighThreshold}
            onChange={handleHigh}
            min={Math.min(confMedThreshold + 1, 99)} max={100}
            accentColor="var(--success)"
            icon={CheckCircle2}
            presets={[85, 90, 95]}
          />
          <ThresholdControl
            label="Medium Confidence (Amber) Threshold"
            description={`Fields between this and High (${confHighThreshold}%) show amber. Below this → red badge.`}
            value={confMedThreshold}
            onChange={handleMed}
            min={50} max={Math.max(confHighThreshold - 1, 51)}
            accentColor="var(--warn)"
            icon={Palette}
            presets={[60, 65, 70, 75]}
          />
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   NORMALIZATION FORMAT SECTION
───────────────────────────────────────────────────────────── */
function NormalizationSection({ toast }) {
  const [config, setConfig] = useState({
    date_format: 'YYYY-MM-DD',
    number_format: 'float',
    name_casing: 'Title Case',
    name_sequence: 'Firstname Lastname',
    custom_rules: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getNormConfig();
        if (active) {
          setConfig(data);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          toast(err.message || 'Failed to load normalization settings', 'error');
          setLoading(false);
        }
      }
    }
    load();
    return () => { active = false; };
  }, [toast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveNormConfig(config);
      toast('Normalization settings saved successfully ✓', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setConfig({
      date_format: 'YYYY-MM-DD',
      number_format: 'float',
      name_casing: 'Title Case',
      name_sequence: 'Firstname Lastname',
      custom_rules: '',
    });
    toast('Form reset to default presets (remember to save) ✓', 'info');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: 'var(--muted)' }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Loading settings from backend...</div>
      </div>
    );
  }

  // Build the live preview content dynamically based on current UI state
  const datePreview = config.date_format === 'keep'
    ? "Keep the date in its original raw string format as extracted."
    : `Normalize to ${config.date_format} format (e.g. '25 June 2026' -> '${config.date_format === 'YYYY-MM-DD' ? '2026-06-25' : config.date_format === 'MM/DD/YYYY' ? '06/25/2026' : '25/06/2026'}'). If invalid or missing, keep empty.`;

  const numPreview = config.number_format === 'float'
    ? "Convert to float/integer numbers (e.g. '$1,250.50' -> 1250.5). Strip any currency symbols."
    : config.number_format === 'integer'
    ? "Convert to integer numbers (e.g. '$1,250.50' -> 1250). Strip decimals and currency symbols."
    : "Keep numbers as strings (e.g. '$1,250.50' -> '$1,250.50').";

  const casingPreview = config.name_casing === 'Title Case'
    ? "Normalize spelling and standardize to Title Case."
    : config.name_casing === 'UPPERCASE'
    ? "Normalize spelling and convert to UPPERCASE."
    : "Keep name/address casing exactly as it is written in the document.";

  const seqPreview = config.name_sequence === 'Firstname Lastname'
    ? "Format person names as 'Firstname Lastname' (e.g. 'John Doe')."
    : config.name_sequence === 'Firstname Middlename Lastname'
    ? "Format person names as 'Firstname Middlename Lastname' (e.g. 'John Albert Doe'). If no middle name exists, omit it."
    : config.name_sequence === 'Lastname Firstname'
    ? "Format person names as 'Lastname Firstname' (e.g. 'Doe John')."
    : config.name_sequence === 'Lastname, Firstname Middlename'
    ? "Format person names as 'Lastname, Firstname Middlename' (e.g. 'Doe, John Albert')."
    : config.name_sequence === 'Title Firstname Lastname'
    ? "Format person names as 'Title Firstname Lastname' (e.g. 'Mr. John Doe'). If no title is in the document, omit it."
    : config.name_sequence === 'Title Firstname Middlename Lastname'
    ? "Format person names as 'Title Firstname Middlename Lastname' (e.g. 'Mr. John Albert Doe'). If no title/middle name is in the document, omit them."
    : "Keep the original order of names exactly as written in the document.";

  const livePromptSnippet = 
    `Your final response MUST be a JSON object containing EXACTLY these two keys:\n` +
    `1. 'raw_extracted': A JSON object containing the raw field values exactly as returned by the OCR tool (without formatting/cleaning).\n` +
    `2. 'normalized_extracted': A JSON object containing the normalized/cleaned field values. Apply standard formatting rules:\n` +
    `   - Dates: ${datePreview}\n` +
    `   - Amounts/Numbers: ${numPreview}\n` +
    `   - Names & Addresses: ${casingPreview}\n` +
    `   - Name Structure: ${seqPreview}\n` +
    (config.custom_rules ? config.custom_rules.split('\n').map(l => `   ${l}`).join('\n') : '');

  return (
    <div>
      <SectionHeader icon={Palette} label="Normalization Format Settings" desc="Control how extracted values are cleaned, formatted, and standardized" />

      <InfoCallout>
        These rules tell the general extractor agent how to format normalized fields. Changes are applied at runtime.
      </InfoCallout>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        
        {/* Date Format Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Date Field Format
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            {[
              { id: 'YYYY-MM-DD', label: 'ISO Format (YYYY-MM-DD)', desc: 'e.g. 2026-06-25' },
              { id: 'MM/DD/YYYY', label: 'US Format (MM/DD/YYYY)', desc: 'e.g. 06/25/2026' },
              { id: 'DD/MM/YYYY', label: 'EU Format (DD/MM/YYYY)', desc: 'e.g. 25/06/2026' },
              { id: 'keep', label: 'Keep Raw Text', desc: 'As written in document' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, date_format: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.date_format === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.date_format === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.date_format === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Number/Amount Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Number/Amount Formatting
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            {[
              { id: 'float', label: 'Decimal (Float)', desc: '1250.50' },
              { id: 'integer', label: 'Integer', desc: '1250' },
              { id: 'string', label: 'Raw String', desc: '"$1,250.50"' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, number_format: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.number_format === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.number_format === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.number_format === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Name Casing Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Name & Address Casing
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            {[
              { id: 'Title Case', label: 'Title Case', desc: 'John Doe' },
              { id: 'UPPERCASE', label: 'UPPERCASE', desc: 'JOHN DOE' },
              { id: 'keep', label: 'Keep Raw', desc: 'As-is' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, name_casing: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.name_casing === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.name_casing === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.name_casing === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Name Sequence/Structure Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Name Formatting Structure
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            {[
              { id: 'Firstname Lastname', label: 'First Last', desc: 'e.g. John Doe' },
              { id: 'Firstname Middlename Lastname', label: 'First Middle Last', desc: 'e.g. John Albert Doe' },
              { id: 'Lastname Firstname', label: 'Last First', desc: 'e.g. Doe John' },
              { id: 'Lastname, Firstname Middlename', label: 'Last, First Middle', desc: 'e.g. Doe, John Albert' },
              { id: 'Title Firstname Lastname', label: 'Title First Last', desc: 'e.g. Mr. John Doe' },
              { id: 'Title Firstname Middlename Lastname', label: 'Title First Middle Last', desc: 'e.g. Mr. John Albert Doe' },
              { id: 'keep', label: 'Keep Raw Order', desc: 'Original sequence' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, name_sequence: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.name_sequence === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.name_sequence === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.name_sequence === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Normalization Rules Textarea */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
              Custom Formatting Rules
            </label>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Appended to extractor instructions</span>
          </div>
          <textarea
            value={config.custom_rules}
            onChange={(e) => setConfig(prev => ({ ...prev, custom_rules: e.target.value }))}
            placeholder="- Phone numbers: standard format as +XX XXXXX XXXXX&#10;- Convert all country names to ISO 3166-1 alpha-3 code (e.g. 'United States' -> 'USA')"
            style={{
              width: '100%', height: 100, boxSizing: 'border-box',
              background: 'var(--card-alt)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '12px 14px', color: 'var(--text)',
              fontSize: 12.5, fontFamily: 'monospace', lineHeight: 1.5,
              resize: 'vertical', outline: 'none',
              transition: 'border-color 0.15s ease'
            }}
            onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
          />
        </div>

        {/* Live Prompt Preview */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 8, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Live Prompt Preview
          </label>
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 8, padding: 16, overflowX: 'auto',
            fontFamily: 'monospace', fontSize: 11, color: 'var(--text-dim)',
            lineHeight: 1.55, whiteSpace: 'pre-wrap'
          }}>
            {livePromptSnippet}
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
          <button
            onClick={handleReset}
            style={{
              all: 'unset', cursor: 'pointer',
              padding: '8px 16px', borderRadius: 8,
              border: '1px solid var(--border)',
              fontSize: 12.5, fontWeight: 600, color: 'var(--text-dim)',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--card-alt)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            Reset Presets
          </button>
          
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              all: 'unset', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '8px 18px', borderRadius: 8,
              background: 'var(--accent)',
              fontSize: 12.5, fontWeight: 600, color: 'white',
              opacity: saving ? 0.7 : 1,
              transition: 'all 0.15s ease',
              boxShadow: '0 2px 6px rgba(79,110,247,0.2)'
            }}
            onMouseEnter={e => { if(!saving) e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 90%, black)'; }}
            onMouseLeave={e => { if(!saving) e.currentTarget.style.background = 'var(--accent)'; }}
          >
            <Save size={14} />
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>

      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   CLASSIFICATION DOCUMENT TYPES SECTION
   ───────────────────────────────────────────────────────────── */
function ClassificationSection({ toast }) {
  const [docTypes, setDocTypes] = useState([]);
  const [newType, setNewType] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getClassificationConfig();
        if (active) {
          setDocTypes(data);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          toast(err.message || 'Failed to load classification settings', 'error');
          setLoading(false);
        }
      }
    }
    load();
    return () => { active = false; };
  }, [toast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveClassificationConfig(docTypes);
      toast('Classification document types saved successfully ✓', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleAddType = () => {
    const trimmed = newType.trim().toLowerCase().replace(/\s+/g, '_');
    if (!trimmed) return;
    if (docTypes.includes(trimmed)) {
      toast('This document type already exists', 'warning');
      return;
    }
    setDocTypes(prev => [...prev, trimmed]);
    setNewType('');
  };

  const handleRemoveType = (typeToRemove) => {
    setDocTypes(prev => prev.filter(t => t !== typeToRemove));
  };

  const handleReset = () => {
    setDocTypes([
      "invoice", "pan_card", "claim_form", "policy_document", 
      "id_proof", "medical_report", "lab_reports", 
      "prescription_records", "bills_invoices", 
      "disability_certificate", "legal_letter"
    ]);
    toast('Reset to default classification types (remember to save) ✓', 'info');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: 'var(--muted)' }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Loading classification settings...</div>
      </div>
    );
  }

  return (
    <div>
      <SectionHeader icon={Tag} label="Classification Document Types" desc="Configure which document types the AI classifier should recognize" />

      <InfoCallout>
        Adding a document type enables the Classifier Agent to identify it. 
        Note that you will also need to configure corresponding extraction rules on the Templates page.
      </InfoCallout>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 10 }}>
        
        {/* Add new type form */}
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            type="text"
            placeholder="e.g. utility_bill, driver_license"
            value={newType}
            onChange={(e) => setNewType(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddType(); }}
            style={{
              flex: 1,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '10px 14px',
              fontSize: 13,
              color: 'var(--text)',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
          <button
            onClick={handleAddType}
            style={{
              all: 'unset', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '10px 18px', borderRadius: 8,
              background: 'var(--accent)',
              fontSize: 12.5, fontWeight: 600, color: 'white',
              transition: 'all 0.15s ease',
              boxShadow: '0 2px 6px rgba(79,110,247,0.2)'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 90%, black)'}
            onMouseLeave={e => e.currentTarget.style.background = 'var(--accent)'}
          >
            <Plus size={14} />
            Add Type
          </button>
        </div>

        {/* Current list of types */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Currently Supported Types ({docTypes.length})
          </label>
          {docTypes.length === 0 ? (
            <div style={{ padding: '24px 18px', border: '1px dashed var(--border)', borderRadius: 10, textAlign: 'center', color: 'var(--muted)', fontSize: 12.5 }}>
              No document types configured. The classifier will fail unless you add at least one type.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {docTypes.map((type) => {
                // Generate a pretty display name
                const displayName = type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                return (
                  <div
                    key={type}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 14px', borderRadius: 8,
                      background: 'var(--card-alt)', border: '1px solid var(--border)',
                    }}
                  >
                    <div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{displayName}</span>
                      <span style={{ fontSize: 10.5, color: 'var(--muted)', marginLeft: 10, fontFamily: 'monospace', background: 'var(--surface)', padding: '2px 6px', borderRadius: 4 }}>
                        {type}
                      </span>
                    </div>
                    <button
                      onClick={() => handleRemoveType(type)}
                      style={{
                        all: 'unset', cursor: 'pointer',
                        width: 28, height: 28, borderRadius: 6,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'var(--muted)',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'color-mix(in srgb, var(--danger) 10%, transparent)'; e.currentTarget.style.color = 'var(--danger)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--muted)'; }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          borderTop: '1px solid var(--border)', paddingTop: 20, marginTop: 10
        }}>
          <button
            onClick={handleReset}
            style={{
              all: 'unset', cursor: 'pointer',
              fontSize: 11.5, fontWeight: 600, color: 'var(--text-dim)',
              padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)',
              background: 'transparent',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--card-alt)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            Reset Presets
          </button>
          
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              all: 'unset', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '8px 18px', borderRadius: 8,
              background: 'var(--accent)',
              fontSize: 12.5, fontWeight: 600, color: 'white',
              opacity: saving ? 0.7 : 1,
              transition: 'all 0.15s ease',
              boxShadow: '0 2px 6px rgba(79,110,247,0.2)'
            }}
            onMouseEnter={e => { if(!saving) e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 90%, black)'; }}
            onMouseLeave={e => { if(!saving) e.currentTarget.style.background = 'var(--accent)'; }}
          >
            <Save size={14} />
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>

      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   MAIN SETTINGS COMPONENT
───────────────────────────────────────────────────────────── */
export function Settings() {
  const [activeNav, setActiveNav] = useState('confidence');

  const {
    confidenceMode, setConfidenceMode,
    fieldHighlightThreshold, setFieldHighlightThreshold,
    autoApproveThreshold,    setAutoApproveThreshold,
    confHighThreshold,       setConfHighThreshold,
    confMedThreshold,        setConfMedThreshold,
    toast,
  } = useApp();

  const DEFAULTS = {
    confidenceMode: 'word',
    fieldHighlightThreshold: 95,
    autoApproveThreshold: 80,
    confHighThreshold: 90,
    confMedThreshold: 70,
  };

  const handleReset = () => {
    setConfidenceMode(DEFAULTS.confidenceMode);
    setFieldHighlightThreshold(DEFAULTS.fieldHighlightThreshold);
    setAutoApproveThreshold(DEFAULTS.autoApproveThreshold);
    setConfHighThreshold(DEFAULTS.confHighThreshold);
    setConfMedThreshold(DEFAULTS.confMedThreshold);
    toast('All settings reset to defaults ✓', 'success');
  };

  return (
    <div className="page" style={{ maxWidth: 900, margin: '0 auto' }}>

      {/* ── Page Header ───────────────────────────────── */}
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <div style={{
              width: 34, height: 34, borderRadius: 9,
              background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)',
            }}>
              <SettingsIcon size={16} />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.5px', color: 'var(--text)' }}>
              Settings
            </h1>
          </div>
          <p style={{ fontSize: 13, color: 'var(--muted)', marginLeft: 44 }}>
            Configure extraction behaviour, confidence display, and approval thresholds.
          </p>
        </div>
        <button
          onClick={handleReset}
          title="Reset all to defaults"
          style={{
            all: 'unset', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--card-alt)',
            fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--danger-border)'; e.currentTarget.style.color = 'var(--danger)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-dim)'; }}
        >
          <RotateCcw size={12} />
          Reset defaults
        </button>
      </div>

      {/* ── Layout: sidebar + content ─────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '210px 1fr', gap: 16, alignItems: 'start' }}>

        {/* ── Left sidebar nav ───────────────────────── */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 12, padding: 8, boxShadow: 'var(--shadow-card)',
          position: 'sticky', top: 16,
        }}>
          <div style={{ padding: '8px 10px 10px', borderBottom: '1px solid var(--border)', marginBottom: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)' }}>
              Preferences
            </span>
          </div>
          {NAV.map(({ id, label, icon: Icon, desc }) => {
            const active = activeNav === id;
            return (
              <button
                key={id}
                onClick={() => setActiveNav(id)}
                style={{
                  all: 'unset', cursor: 'pointer', width: '100%', boxSizing: 'border-box',
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 10px', borderRadius: 8, marginBottom: 2,
                  background: active ? 'var(--accent-dim)' : 'transparent',
                  border: `1px solid ${active ? 'rgba(79,110,247,0.2)' : 'transparent'}`,
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--card-alt)'; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{
                  width: 28, height: 28, borderRadius: 6, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: active ? 'var(--accent)' : 'var(--surface)',
                  border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                  color: active ? 'white' : 'var(--muted)',
                  transition: 'all 0.15s ease',
                }}>
                  <Icon size={13} />
                </div>
                <div style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: active ? 'var(--accent)' : 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {desc}
                  </div>
                </div>
                {active && <ChevronRight size={11} color="var(--accent)" style={{ flexShrink: 0 }} />}
              </button>
            );
          })}
        </div>

        {/* ── Right content panel ─────────────────────── */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 12, padding: 28, boxShadow: 'var(--shadow-card)',
          minHeight: 420,
        }}>
          {activeNav === 'confidence' && (
            <ConfidenceSection
              confidenceMode={confidenceMode}
              setConfidenceMode={setConfidenceMode}
              toast={toast}
            />
          )}
          {activeNav === 'thresholds' && (
            <ThresholdsSection
              fieldHighlightThreshold={fieldHighlightThreshold}
              setFieldHighlightThreshold={setFieldHighlightThreshold}
              autoApproveThreshold={autoApproveThreshold}
              setAutoApproveThreshold={setAutoApproveThreshold}
              confHighThreshold={confHighThreshold}
              setConfHighThreshold={setConfHighThreshold}
              confMedThreshold={confMedThreshold}
              setConfMedThreshold={setConfMedThreshold}
              toast={toast}
            />
          )}
          {activeNav === 'normalization' && (
            <NormalizationSection
              toast={toast}
            />
          )}
          {activeNav === 'classification' && (
            <ClassificationSection
              toast={toast}
            />
          )}
        </div>
      </div>
    </div>
  );
}
```

## `src/pages/Templates.jsx`

```jsx
import { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  FileCode, Plus, RotateCcw, Edit2, Trash2, Calendar, 
  Type, Hash, ToggleLeft, List, Table, Check, X, Search, 
  AlertCircle, CheckCircle2, ChevronRight, Image, ShieldCheck,
  Crop
} from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { RegionSelector } from '../components/ui/RegionSelector';
import { useApp } from '../store/AppStore';
import { getTemplates, saveTemplates, generateTemplateFromSample, deleteTemplate } from '../api/client';

const DEFAULT_TEMPLATES = {};

const TYPE_ICONS = {
  'Text': Type,
  'Number': Hash,
  'Date': Calendar,
  'Boolean': ToggleLeft,
  'Array of Text': List,
  'Array of Objects': Table,
  'Image': Image
};

export function Templates() {
  const { toast, fieldHighlightThreshold } = useApp();
  const [activeTab, setActiveTab] = useState('');
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingField, setEditingField] = useState(null); // null means adding a new field
  const [formData, setFormData] = useState({
    key: '',
    label: '',
    type: 'Text',
    required: false,
    description: '',
    confidence_threshold: ''
  });

  const [createTemplateModalOpen, setCreateTemplateModalOpen] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [isKycTemplate, setIsKycTemplate] = useState(false);
  const [sampleFile, setSampleFile] = useState(null);
  const [generatingTemplate, setGeneratingTemplate] = useState(false);
  const [createKycRegions, setCreateKycRegions] = useState({ signature: null, photo: null });

  // Preview URL for the sample file (only for images)
  const samplePreviewUrl = useMemo(() => {
    if (!sampleFile) return null;
    const imageTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    if (imageTypes.includes(sampleFile.type)) {
      return URL.createObjectURL(sampleFile);
    }
    return null;
  }, [sampleFile]);

  // Cleanup preview URL on unmount or change
  useEffect(() => {
    return () => {
      if (samplePreviewUrl) URL.revokeObjectURL(samplePreviewUrl);
    };
  }, [samplePreviewUrl]);

  useEffect(() => {
    getTemplates()
      .then(data => {
        const loadedTemplates = data || DEFAULT_TEMPLATES;
        setTemplates(loadedTemplates);
        const keys = Object.keys(loadedTemplates);
        if (keys.length > 0) {
          if (!activeTab || !loadedTemplates[activeTab]) {
            setActiveTab(keys[0]);
          }
        } else {
          setActiveTab('');
        }
      })
      .catch(err => {
        toast('Failed to load templates: ' + err.message, 'error');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [toast, activeTab]);

  const currentFields = useMemo(() => {
    const t = templates[activeTab];
    if (!t) return [];
    // Handle both old (list) and new ({fields, is_kyc}) formats
    if (Array.isArray(t)) return t;
    return t.fields || [];
  }, [templates, activeTab]);

  const isActiveKyc = useMemo(() => {
    const t = templates[activeTab];
    if (!t || Array.isArray(t)) return false;
    return t.is_kyc === true;
  }, [templates, activeTab]);



  const filteredFields = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return currentFields;
    return currentFields.filter(f => 
      f.key.toLowerCase().includes(q) || 
      f.label.toLowerCase().includes(q) || 
      f.description.toLowerCase().includes(q)
    );
  }, [currentFields, searchQuery]);

  const requiredCount = useMemo(() => {
    return currentFields.filter(f => f.required).length;
  }, [currentFields]);

  const handleOpenAddModal = () => {
    setEditingField(null);
    setFormData({
      key: '',
      label: '',
      type: 'Text',
      required: false,
      description: '',
      confidence_threshold: ''
    });
    setModalOpen(true);
  };

  const handleOpenEditModal = (field) => {
    setEditingField(field);
    setFormData({
      key: field.key,
      label: field.label,
      type: field.type,
      required: field.required,
      description: field.description || '',
      confidence_threshold: field.confidence_threshold !== undefined && field.confidence_threshold !== null ? field.confidence_threshold : ''
    });
    setModalOpen(true);
  };

  const handleDeleteField = async (fieldKey) => {
    if (window.confirm(`Are you sure you want to delete the field "${fieldKey}"?`)) {
      const updatedList = currentFields.filter(f => f.key !== fieldKey);
      // Preserve template metadata (is_kyc flag) when updating fields
      const existingTemplate = templates[activeTab];
      const templateMeta = (existingTemplate && !Array.isArray(existingTemplate)) ? existingTemplate : {};
      const updatedTemplates = { ...templates, [activeTab]: { ...templateMeta, fields: updatedList } };
      
      try {
        setTemplates(updatedTemplates);
        await saveTemplates(updatedTemplates);
        toast(`Field "${fieldKey}" deleted successfully ✓`, 'info');
      } catch (err) {
        toast(`Failed to delete field: ${err.message}`, 'error');
      }
    }
  };

  const handleDeleteTemplate = async () => {
    if (!activeTab) return;
    if (window.confirm(`Are you sure you want to delete the entire "${activeTab.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}" template? This cannot be undone.`)) {
      try {
        await deleteTemplate(activeTab);
        toast(`Template deleted successfully ✓`, 'info');
        const data = await getTemplates();
        const loadedTemplates = data || {};
        setTemplates(loadedTemplates);
        const keys = Object.keys(loadedTemplates);
        if (keys.length > 0) {
          setActiveTab(keys[0]);
        } else {
          setActiveTab('');
        }
      } catch (err) {
        toast(`Failed to delete template: ${err.message}`, 'error');
      }
    }
  };



  const handleGenerateTemplate = async (e) => {
    e.preventDefault();
    if (!newTemplateName.trim()) {
      alert('Template Name is required');
      return;
    }
    if (!sampleFile) {
      alert('Please select a sample document file');
      return;
    }
    
    setGeneratingTemplate(true);
    try {
      // Build kyc_boxes from drawn regions (only non-null entries)
      let kycBoxesToSend = null;
      if (isKycTemplate && (createKycRegions.signature || createKycRegions.photo)) {
        kycBoxesToSend = {};
        if (createKycRegions.signature) kycBoxesToSend.signature = createKycRegions.signature;
        if (createKycRegions.photo) kycBoxesToSend.photo = createKycRegions.photo;
      }

      const res = await generateTemplateFromSample(newTemplateName, sampleFile, isKycTemplate, kycBoxesToSend);
      toast(`Template "${res.template_name}" generated successfully ✓`, 'success');
      const updated = await getTemplates();
      setTemplates(updated || {});
      setActiveTab(res.template_name);
      setCreateTemplateModalOpen(false);
      setNewTemplateName('');
      setIsKycTemplate(false);
      setSampleFile(null);
      setCreateKycRegions({ signature: null, photo: null });
    } catch (err) {
      toast(`Failed to generate template: ${err.message}`, 'error');
    } finally {
      setGeneratingTemplate(false);
    }
  };

  const handleSaveField = async (e) => {
    e.preventDefault();
    const key = formData.key.trim().toLowerCase().replace(/\s+/g, '_');
    
    if (!key) {
      alert('Field Key is required');
      return;
    }

    if (!formData.label.trim()) {
      alert('Field Label is required');
      return;
    }

    // Validate snake_case key pattern
    if (!/^[a-z0-9_]+$/.test(key)) {
      alert('Field Key must only contain lowercase letters, numbers, and underscores');
      return;
    }

    // Check uniqueness if adding new OR renaming
    const isNew = !editingField;
    const isRename = editingField && editingField.key !== key;
    if (isNew || isRename) {
      const exists = currentFields.some(f => f.key === key);
      if (exists) {
        alert(`A field with key "${key}" already exists in this template.`);
        return;
      }
    }

    const fieldObj = {
      key,
      label: formData.label.trim(),
      type: formData.type,
      required: formData.required,
      description: formData.description.trim(),
      confidence_threshold: formData.confidence_threshold !== '' ? Number(formData.confidence_threshold) : null
    };

    let updatedList;
    if (isNew) {
      updatedList = [...currentFields, fieldObj];
    } else {
      updatedList = currentFields.map(f => f.key === editingField.key ? fieldObj : f);
    }
    // Preserve template metadata (is_kyc flag) when updating fields
    const existingTemplate = templates[activeTab];
    const templateMeta = (existingTemplate && !Array.isArray(existingTemplate)) ? existingTemplate : {};
    const updatedTemplates = { ...templates, [activeTab]: { ...templateMeta, fields: updatedList } };

    try {
      setTemplates(updatedTemplates);
      await saveTemplates(updatedTemplates);
      setModalOpen(false);
      toast(`Field "${key}" ${isNew ? 'added' : 'updated'} successfully ✓`, 'success');
    } catch (err) {
      toast(`Failed to save field: ${err.message}`, 'error');
    }
  };

  if (loading) {
    return (
      <div className="page anim-slide-in" style={{ padding: '20px 0' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="skeleton" style={{ height: 40, width: '40%' }} />
          <div className="skeleton" style={{ height: 20, width: '60%' }} />
          <div className="skeleton" style={{ height: 260, width: '100%', marginTop: 20 }} />
        </div>
      </div>
    );
  }

  const templateKeys = Object.keys(templates);

  return (
    <div className="page anim-slide-in">
      {/* ── Page Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, maxWidth: 660, margin: 0 }}>
            Configure target fields for standard Document Processing workflows. Adding or editing fields here dictates which elements the underlying extraction agents look for.
          </p>
          
          {templateKeys.length > 0 && (
            <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--accent)', background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.2)', borderRadius: 99, padding: '3px 10px' }}>
                <FileCode size={10} /> {currentFields.length} Total Fields
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--success)', background: 'var(--success-dim)', border: '1px solid var(--success-border)', borderRadius: 99, padding: '3px 10px' }}>
                <CheckCircle2 size={10} /> {requiredCount} Required Fields
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-dim)', background: 'var(--card-alt)', border: '1px solid var(--border)', borderRadius: 99, padding: '3px 10px' }}>
                {currentFields.length - requiredCount} Optional Fields
              </span>
            </div>
          )}
        </div>

        {/* Global actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button 
            className="btn btn-primary btn-sm" 
            onClick={() => setCreateTemplateModalOpen(true)}
            id="templates-create-template-btn"
          >
            <Plus size={12} /> Create Template
          </button>
        </div>
      </div>

      {templateKeys.length === 0 ? (
        <div className="card" style={{ padding: '64px 24px', textAlign: 'center', marginTop: 20 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, maxWidth: 480, margin: '0 auto' }}>
            <div style={{
              background: 'rgba(79, 110, 247, 0.1)',
              color: 'var(--accent)',
              padding: 20,
              borderRadius: '50%',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 8
            }}>
              <FileCode size={40} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text)' }}>No Templates Configured</h3>
            <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
              You don't have any document templates set up yet. Upload a sample document to automatically generate a template schema for your document type.
            </p>
            <button 
              className="btn btn-primary" 
              style={{ marginTop: 8 }}
              onClick={() => setCreateTemplateModalOpen(true)}
            >
              <Plus size={14} style={{ marginRight: 6 }} /> Create Template from Sample
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* ── Document Type Tabs ── */}
          <div className="tabs">
            {templateKeys.map((key) => {
            const tpl = templates[key];
            const kycFlag = tpl && !Array.isArray(tpl) && tpl.is_kyc;
            return (
              <div 
                key={key}
                className={`tab ${activeTab === key ? 'active' : ''}`}
                onClick={() => { setActiveTab(key); setSearchQuery(''); }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                {kycFlag && <ShieldCheck size={12} style={{ color: 'var(--accent)' }} />}
                {key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                {kycFlag && (
                  <span style={{
                    fontSize: 9, fontWeight: 700, color: 'var(--accent)',
                    background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.25)',
                    padding: '1px 5px', borderRadius: 4, marginLeft: 2
                  }}>KYC</span>
                )}
              </div>
            );
          })}
          </div>

          {/* ── Search Bar & Filter Strip ── */}
          <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexGrow: 1, minWidth: 240 }}>
              <Search size={14} style={{ color: 'var(--muted)' }} />
              <input 
                type="text" 
                placeholder="Filter fields by name, key, or description..."
                className="styled-input" 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ border: 'none', background: 'transparent', padding: 0, fontSize: 13, width: '100%' }}
              />
              {searchQuery && (
                <button 
                  className="btn btn-ghost btn-sm" 
                  onClick={() => setSearchQuery('')}
                  style={{ padding: '2px 6px', border: 'none', background: 'transparent' }}
                >
                  <X size={12} />
                </button>
              )}
            </div>
            
            {/* Template specific actions aligned next to the search */}
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              {activeTab && (
                <button 
                  className="btn btn-danger btn-sm" 
                  onClick={handleDeleteTemplate}
                  title="Delete active template"
                  id="templates-delete-template-btn"
                >
                  <Trash2 size={12} /> Delete Template
                </button>
              )}
              {activeTab && (
                <button 
                  className="btn btn-primary btn-sm" 
                  onClick={handleOpenAddModal}
                  id="templates-add-field-btn"
                >
                  <Plus size={12} /> Add Field
                </button>
              )}
            </div>
          </div>

          {/* ── Fields Table Card ── */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="table-wrap" style={{ maxHeight: 'calc(100vh - 280px)', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--card-alt)' }}>
                    <th style={{ padding: '12px 16px', width: '20%', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Field Name / Key</th>
                    <th style={{ padding: '12px 16px', width: '12%', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Type</th>
                    <th style={{ padding: '12px 16px', width: '33%', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Description</th>
                    <th style={{ padding: '12px 16px', width: '15%', textAlign: 'center', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Highlight Threshold</th>
                    <th style={{ padding: '12px 16px', width: '10%', textAlign: 'center', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Required</th>
                    <th style={{ padding: '12px 16px', width: '10%', textAlign: 'right', position: 'sticky', top: 0, zIndex: 10, background: 'var(--card-alt)' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFields.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--muted)' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                          <AlertCircle size={24} style={{ opacity: 0.5 }} />
                          <span>No fields match the search query</span>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredFields.map((field, idx) => {
                      const TypeIcon = TYPE_ICONS[field.type] || Type;
                      return (
                        <tr key={field.key} style={{ cursor: 'default' }}>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>
                              {field.label}
                            </div>
                            <code style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--surface-sunken)', padding: '2px 5px', borderRadius: 4, marginTop: 4, display: 'inline-block', fontFamily: 'monospace' }}>
                              {field.key}
                            </code>
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                            <span style={{ 
                              display: 'inline-flex', 
                              alignItems: 'center', 
                              gap: 6, 
                              fontSize: 11, 
                              fontWeight: 500,
                              color: 'var(--text-dim)',
                              background: 'var(--card-alt)',
                              border: '1px solid var(--border)',
                              padding: '3px 8px',
                              borderRadius: 6
                            }}>
                              <TypeIcon size={11} style={{ color: 'var(--accent)' }} />
                              {field.type}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', color: 'var(--text-dim)', fontSize: 12, lineHeight: 1.5, whiteSpace: 'normal', maxBreakWord: 'break-all' }}>
                            {field.description || <span style={{ fontStyle: 'italic', color: 'var(--muted)' }}>No description provided.</span>}
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', textAlign: 'center' }}>
                            {field.confidence_threshold !== undefined && field.confidence_threshold !== null ? (
                              <span style={{ fontWeight: 600, color: 'var(--warn)' }}>{field.confidence_threshold}%</span>
                            ) : (
                              <span style={{ color: 'var(--muted)', fontSize: 11 }}>{fieldHighlightThreshold}% (Default)</span>
                            )}
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', textAlign: 'center' }}>
                            {field.required ? (
                              <span className="badge badge-green" style={{ fontSize: 9 }}>Yes</span>
                            ) : (
                              <span className="badge badge-gray" style={{ fontSize: 9, opacity: 0.6 }}>No</span>
                            )}
                          </td>
                          <td style={{ padding: '12px 16px', verticalAlign: 'top', textAlign: 'right' }}>
                            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                              <button 
                                className="btn btn-ghost btn-sm" 
                                style={{ padding: 4 }}
                                onClick={() => handleOpenEditModal(field)}
                                title="Edit Field"
                              >
                                <Edit2 size={11} />
                              </button>
                              <button 
                                className="btn btn-danger btn-sm" 
                                style={{ padding: 4 }}
                                onClick={() => handleDeleteField(field.key)}
                                title="Delete Field"
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>


        </>
      )}

      {/* ── Edit/Add Field Modal ── */}
      {modalOpen && (
        <Modal
          title={editingField ? 'Edit Extraction Field' : 'Add Extraction Field'}
          subtitle={editingField ? `Modify parameters for ${editingField.key}` : 'Configure a new target field for this document schema'}
          onClose={() => setModalOpen(false)}
          footer={
            <div style={{ display: 'flex', gap: 8, width: '100%', justifyContent: 'flex-end' }}>
              <button 
                type="button" 
                className="btn btn-ghost btn-sm"
                onClick={() => setModalOpen(false)}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                form="field-form"
                className="btn btn-primary btn-sm"
              >
                Save Field
              </button>
            </div>
          }
        >
          <form id="field-form" onSubmit={handleSaveField} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Field Key */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Field Key (Database Identifier) <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <input
                type="text"
                className="styled-input"
                value={formData.key}
                disabled={!!editingField} // Disable renaming database key once created to preserve system map references
                placeholder="e.g. tax_registration_number"
                onChange={(e) => setFormData(prev => ({ ...prev, key: e.target.value }))}
                required
              />
              <span style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
                Must be snake_case (lowercase letters, numbers, underscores only). {editingField && 'Key cannot be renamed.'}
              </span>
            </div>

            {/* Field Label */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Display Label <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <input
                type="text"
                className="styled-input"
                value={formData.label}
                placeholder="e.g. Tax Registration Number"
                onChange={(e) => setFormData(prev => ({ ...prev, label: e.target.value }))}
                required
              />
            </div>

            {/* Data Type */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Data Type <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <select
                className="styled-select"
                value={formData.type}
                onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
              >
                <option value="Text">Text</option>
                <option value="Number">Number</option>
                <option value="Date">Date</option>
                <option value="Boolean">Boolean</option>
                <option value="Array of Text">Array of Text</option>
                <option value="Array of Objects">Array of Objects</option>
              </select>
            </div>

            {/* Description */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Description / Context Hint
              </label>
              <textarea
                className="styled-input"
                value={formData.description}
                placeholder="Explain what the extractor agent should look for..."
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                style={{ minHeight: 60, resize: 'vertical' }}
              />
            </div>

            {/* Custom Confidence Threshold */}
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Custom Highlight Threshold (%)
              </label>
              <input
                type="number"
                min="0"
                max="100"
                className="styled-input"
                value={formData.confidence_threshold}
                placeholder={`Leave blank to use default (${fieldHighlightThreshold}%)`}
                onChange={(e) => setFormData(prev => ({ ...prev, confidence_threshold: e.target.value }))}
              />
              <span style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
                Highlight this field if its extraction confidence falls below this value.
              </span>
            </div>

            {/* Required Toggle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
              <input
                type="checkbox"
                id="required-checkbox"
                checked={formData.required}
                onChange={(e) => setFormData(prev => ({ ...prev, required: e.target.checked }))}
                style={{ width: 14, height: 14, accentColor: 'var(--accent)', cursor: 'pointer' }}
              />
              <label htmlFor="required-checkbox" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', cursor: 'pointer' }}>
                Required Field (validations fail if missing)
              </label>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Create Template Modal ── */}
      {createTemplateModalOpen && (
        <Modal
          title="Create Template from Sample Document"
          subtitle="Upload a sample document and the AI will analyze its layout and fields to generate a template."
          onClose={() => !generatingTemplate && setCreateTemplateModalOpen(false)}
          wide={isKycTemplate && !!samplePreviewUrl}
          footer={
            <div style={{ display: 'flex', gap: 8, width: '100%', justifyContent: 'flex-end' }}>
              <button 
                type="button" 
                className="btn btn-ghost btn-sm"
                onClick={() => setCreateTemplateModalOpen(false)}
                disabled={generatingTemplate}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                form="generate-template-form"
                className="btn btn-primary btn-sm"
                disabled={generatingTemplate}
              >
                {generatingTemplate ? (
                  <>
                    <span className="spinner" style={{ marginRight: 6 }} />
                    Generating Schema...
                  </>
                ) : 'Generate Template'}
              </button>
            </div>
          }
        >
          <form id="generate-template-form" onSubmit={handleGenerateTemplate} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Template / Document Type Name <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <input
                type="text"
                className="styled-input"
                value={newTemplateName}
                placeholder="e.g. Purchase Order, Utility Bill, Invoice"
                onChange={(e) => setNewTemplateName(e.target.value)}
                required
                disabled={generatingTemplate}
              />
              <span style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
                This name will be used to identify and classify documents of this type.
              </span>
            </div>

            {/* KYC Document Toggle */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
              background: isKycTemplate ? 'rgba(79, 110, 247, 0.08)' : 'var(--surface-sunken)',
              border: isKycTemplate ? '1.5px solid rgba(79, 110, 247, 0.3)' : '1px solid var(--border)',
              borderRadius: 'var(--radius)', cursor: 'pointer',
              transition: 'all 0.2s ease'
            }} onClick={() => !generatingTemplate && setIsKycTemplate(prev => !prev)}>
              <input
                type="checkbox"
                id="kyc-toggle"
                checked={isKycTemplate}
                onChange={(e) => setIsKycTemplate(e.target.checked)}
                disabled={generatingTemplate}
                style={{ width: 16, height: 16, accentColor: 'var(--accent)', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <label htmlFor="kyc-toggle" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ShieldCheck size={14} style={{ color: 'var(--accent)' }} />
                  KYC Identity Document
                </label>
                <span style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2, display: 'block' }}>
                  Enable signature and photo extraction from identity cards (Aadhaar, PAN, etc.)
                </span>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                Upload Sample Document <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <div 
                style={{
                  border: '1.5px dashed var(--border)',
                  borderRadius: 'var(--radius)',
                  padding: '24px 16px',
                  textAlign: 'center',
                  background: 'var(--surface-sunken)',
                  cursor: 'pointer',
                  position: 'relative'
                }}
                onClick={() => !generatingTemplate && document.getElementById('sample-file-input').click()}
              >
                <input
                  id="sample-file-input"
                  type="file"
                  accept=".pdf,.docx,.png,.jpg,.jpeg,.webp"
                  onChange={(e) => {
                    if (e.target.files.length) {
                      setSampleFile(e.target.files[0]);
                    }
                  }}
                  style={{ display: 'none' }}
                  disabled={generatingTemplate}
                />
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Plus size={24} />
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                    {sampleFile ? sampleFile.name : 'Select sample file...'}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {sampleFile ? `${(sampleFile.size / 1024).toFixed(0)} KB` : 'Accepts PDF, DOCX, PNG, JPG up to 10MB'}
                  </span>
                </div>
              </div>
            </div>

            {/* Visual Region Selector — shown when KYC + image file */}
            {isKycTemplate && samplePreviewUrl && (
              <div style={{
                padding: 16, borderRadius: 'var(--radius)',
                background: 'rgba(79, 110, 247, 0.04)',
                border: '1px solid rgba(79, 110, 247, 0.15)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                  <Crop size={14} style={{ color: 'var(--accent)' }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>Select Extraction Regions</span>
                  <span style={{
                    fontSize: 9, fontWeight: 700, color: 'var(--accent)',
                    background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.25)',
                    padding: '1px 5px', borderRadius: 4,
                  }}>Optional</span>
                </div>
                <p style={{ fontSize: 11, color: 'var(--muted)', margin: '0 0 10px 0', lineHeight: 1.5 }}>
                  Draw rectangles on the sample image to define where the signature and photo are located. These coordinates will be used for precise extraction.
                </p>
                <RegionSelector
                  imageUrl={samplePreviewUrl}
                  regions={createKycRegions}
                  onChange={setCreateKycRegions}
                />
              </div>
            )}

            {/* PDF notice */}
            {isKycTemplate && sampleFile && !samplePreviewUrl && (
              <div style={{
                padding: '10px 14px', borderRadius: 'var(--radius)',
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.2)',
                fontSize: 11, color: 'var(--warn)', lineHeight: 1.5,
              }}>
                <strong>Note:</strong> Visual region selection is available for image files (PNG, JPG, WEBP). For PDFs, you can set extraction coordinates manually after the template is created.
              </div>
            )}
          </form>
        </Modal>
      )}
    </div>
  );
}
```

## `src/pages/Agents.jsx`

```jsx
import { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, ExternalLink, Cpu, Zap, AlertTriangle,
  Upload, Bot, FileSearch, CheckCircle, FileText, UserCheck, GitBranch, Shield
} from 'lucide-react';
import { getAgents } from '../api/client';

const AGENT_ICON_MAP = {
  intake: Upload,
  pre_validator: Shield,
  preprocessing: Cpu,
  classifier: Bot,
  extractor: FileSearch,
  invoice_extractor: FileSearch,
  contract_extractor: FileSearch,
  kyc_extractor: FileSearch,
  medical_extractor: FileSearch,
  bank_extractor: FileSearch,
  others_extractor: FileSearch,
  fraud_checker: Shield,
  validator: CheckCircle,
  auto_verifier: UserCheck,
  reviewer: UserCheck,
  output: FileText,
};

// ─── Skeleton card shown while loading ───────────────────────────────────────
function AgentSkeleton() {
  return (
    <div className="card agent-card" style={{ border: '1px solid var(--border)' }}>
      <div className="skeleton" style={{ width: 44, height: 44, borderRadius: 8, marginBottom: 14 }} />
      <div className="skeleton" style={{ width: '60%', height: 14, marginBottom: 8 }} />
      <div className="skeleton" style={{ width: '40%', height: 11, marginBottom: 12 }} />
      <div className="skeleton" style={{ width: '100%', height: 11, marginBottom: 6 }} />
      <div className="skeleton" style={{ width: '80%', height: 11, marginBottom: 14 }} />
      <div style={{ display: 'flex', gap: 5 }}>
        <div className="skeleton" style={{ width: 60, height: 20, borderRadius: 99 }} />
        <div className="skeleton" style={{ width: 50, height: 20, borderRadius: 99 }} />
        <div className="skeleton" style={{ width: 70, height: 20, borderRadius: 99 }} />
      </div>
    </div>
  );
}

// ─── Source badge: indicates if agent is live from Mistral or a workflow activity ─
function SourceBadge({ source }) {
  if (source === 'mistral') {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 10, fontWeight: 600, padding: '2px 7px',
        borderRadius: 99, border: '1px solid rgba(79,110,247,0.35)',
        background: 'rgba(79,110,247,0.08)', color: 'var(--accent)',
        marginBottom: 8,
      }}>
        <Zap size={9} /> Mistral Agent
      </span>
    );
  }
  if (source === 'mistral_fallback') {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 10, fontWeight: 600, padding: '2px 7px',
        borderRadius: 99, border: '1px solid rgba(245,158,11,0.35)',
        background: 'rgba(245,158,11,0.08)', color: 'var(--warn)',
        marginBottom: 8,
      }}>
        <AlertTriangle size={9} /> Mistral Agent (offline)
      </span>
    );
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 10, fontWeight: 600, padding: '2px 7px',
      borderRadius: 99, border: '1px solid var(--border)',
      background: 'var(--surface)', color: 'var(--text-dim)',
      marginBottom: 8,
    }}>
      <Cpu size={9} /> Workflow Activity
    </span>
  );
}

// ─── Single Agent Card ────────────────────────────────────────────────────────
function AgentCard({ agent, index }) {
  // Determine card class based on agent source
  const sourceClass =
    agent.source === 'mistral'          ? 'mistral-live' :
    agent.source === 'mistral_fallback' ? 'mistral-offline' :
    'workflow-activity';

  return (
    <div
      className={`card agent-card ${sourceClass} anim-slide-in`}
      style={{
        borderColor: agent.border,
        animationDelay: `${index * 60}ms`,
      }}
    >
      {/* Step badge */}
      <div style={{
        position: 'absolute', top: 12, right: 12,
        fontSize: 10, fontWeight: 700, color: 'var(--muted)',
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 99, padding: '2px 7px',
      }}>
        Step {agent.step}
      </div>

      {/* Avatar */}
      <div
        className="agent-avatar"
        style={{ background: agent.color, border: `1px solid ${agent.border}`, display: 'flex', alignItems: 'center', justify: 'center' }}
      >
        {(() => {
          const IconComponent = AGENT_ICON_MAP[agent.key] || Bot;
          return <IconComponent size={20} style={{ color: agent.border }} />;
        })()}
      </div>

      {/* Source badge */}
      <SourceBadge source={agent.source} />

      {/* Name & role */}
      <div className="agent-name">{agent.name}</div>
      <div className="agent-role">{agent.role}</div>

      {/* Description */}
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 10, lineHeight: 1.6 }}>
        {agent.description}
      </div>

      {/* Model chip */}
      {agent.model && (
        <div style={{
          fontSize: 10, color: 'var(--muted)',
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '3px 8px', marginBottom: 10,
          display: 'inline-block', fontFamily: 'monospace',
        }}>
          {agent.model}
        </div>
      )}

      {/* Agent ID with external link */}
      {agent.agent_id && (
        <div style={{
          fontSize: 10, color: 'var(--muted)', marginBottom: 10,
          display: 'flex', alignItems: 'center', gap: 5,
        }}>
          <span style={{ fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>
            {agent.agent_id}
          </span>
          <a
            href={`https://console.mistral.ai/build/playground?agentId=${agent.agent_id}&from=agents`}
            target="_blank"
            rel="noopener noreferrer"
            title="Open in Mistral Studio"
            style={{ color: 'var(--accent)', flexShrink: 0 }}
          >
            <ExternalLink size={10} />
          </a>
        </div>
      )}

      {/* Tools / Internal Functions */}
      <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
          <Cpu size={10} style={{ color: agent.border }} /> Running Functions
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {(agent.tools || []).map((t) => (
            <div key={t} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--card-alt)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '4px 8px', fontSize: 11, fontFamily: 'monospace',
              color: 'var(--text-dim)', wordBreak: 'break-all'
            }}>
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>λ</span>
              <span>{t.includes('(') ? t : `${t}()`}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Pipeline Collaboration Graph ───────────────────────────────────────────
const StepArrow = () => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: 28, flexShrink: 0 }}>
    <div style={{ width: 1.5, flex: 1, background: 'var(--border)' }} />
    <svg width="9" height="5" viewBox="0 0 9 5" style={{ display: 'block' }}>
      <polygon points="0,0 9,0 4.5,5" fill="var(--border)" />
    </svg>
  </div>
);

function PipelineGraph({ agents }) {
  const intakeAgent = agents.find(a => a.key === 'intake');
  const preValidatorAgent = agents.find(a => a.key === 'pre_validator');
  const preprocessingAgent = agents.find(a => a.key === 'preprocessing');
  const classifierAgent = agents.find(a => a.key === 'classifier');
  const fraudCheckerAgent = agents.find(a => a.key === 'fraud_checker');
  const validatorAgent = agents.find(a => a.key === 'validator');
  const autoVerifierAgent = agents.find(a => a.key === 'auto_verifier');
  const reviewerAgent = agents.find(a => a.key === 'reviewer');
  const outputAgent = agents.find(a => a.key === 'output');
  const extractors = agents.filter(a => a.key.includes('extractor'));

  // Ordered pipeline: 10 steps sequentially mapping the backend-v4 architecture.
  const steps = [
    { type: 'node', agent: intakeAgent, step: 1 },
    { type: 'node', agent: preValidatorAgent, step: 2 },
    { type: 'node', agent: preprocessingAgent, step: 2.5, conditional: true, label: "Enabled in config" },
    { type: 'node', agent: classifierAgent, step: 3 },
    { type: 'node', agent: fraudCheckerAgent, step: 3.5, conditional: true, label: "KYC Only" },
    { type: 'extractors',                     step: 4 },
    { type: 'node', agent: validatorAgent, step: 5 },
    { type: 'node', agent: autoVerifierAgent, step: 5.5, conditional: true, label: "KYC Only" },
    { type: 'node', agent: reviewerAgent, step: 6 },
    { type: 'node', agent: outputAgent, step: 7 },
  ];

  // Filter steps to only include those where the agent data exists in backend response (robust fallback)
  const activeSteps = steps.filter(s => {
    if (s.type === 'extractors') return extractors.length > 0;
    if (s.type === 'node') return !!s.agent;
    return false;
  });

  return (
    <div style={{ padding: '20px 28px 28px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {activeSteps.map((s, i) => {
        const isLast = i === activeSteps.length - 1;

        const StepBadge = ({ n }) => (
          <span style={{
            fontSize: 10, fontWeight: 600, color: 'var(--muted)',
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 99, padding: '1px 8px', whiteSpace: 'nowrap', flexShrink: 0,
          }}>Step {n}</span>
        );

        return (
          <div key={i} style={{ width: '100%', maxWidth: 560, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>

            {/* ── Regular node card ── */}
            {s.type === 'node' && s.agent && (
              <div style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 12,
                padding: '11px 16px', borderRadius: 10,
                background: s.agent.color,
                border: `1.5px solid ${s.agent.border}`,
              }}>
                <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
                  {(() => {
                    const IconComponent = AGENT_ICON_MAP[s.agent.key] || Bot;
                    return <IconComponent size={20} style={{ color: s.agent.border }} />;
                  })()}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', lineHeight: 1.3 }}>
                    {s.agent.name.replace(' Agent', '')}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                    {s.agent.role}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                  {s.conditional && (
                    <span style={{
                      fontSize: 9, fontWeight: 600, color: 'var(--muted)',
                      background: 'var(--surface)', border: '1px solid var(--border)',
                      borderRadius: 4, padding: '2px 6px', whiteSpace: 'nowrap',
                    }}>{s.label}</span>
                  )}
                  {s.agent.key === 'reviewer' && (
                    <span style={{
                      fontSize: 10, fontWeight: 600, color: 'var(--warn)',
                      background: 'rgba(245,158,11,0.10)',
                      border: '1px solid rgba(245,158,11,0.35)',
                      borderRadius: 99, padding: '1px 8px', whiteSpace: 'nowrap',
                    }}>‖ Human Review</span>
                  )}
                  <StepBadge n={s.step} />
                </div>
              </div>
            )}

            {/* ── Extractor group card ── */}
            {s.type === 'extractors' && (
              <div style={{
                width: '100%', borderRadius: 10,
                border: '1.5px dashed var(--border)',
                background: 'rgba(79,110,247,0.03)',
                padding: '11px 16px',
              }}>
                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
                    <FileSearch size={20} style={{ color: 'var(--accent)' }} />
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', lineHeight: 1.3 }}>Extractor</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                      Conditional — one activates per document type
                    </div>
                  </div>
                  <StepBadge n={s.step} />
                </div>
                {/* Type chips */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {extractors.map(e => (
                    <span key={e.key} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '4px 11px', borderRadius: 99,
                      background: e.color, border: `1px solid ${e.border}`,
                      fontSize: 11, fontWeight: 600, color: e.border,
                    }}>
                      {(() => {
                        const IconComponent = AGENT_ICON_MAP[e.key] || FileSearch;
                        return <IconComponent size={12} />;
                      })()}
                      {e.name.replace(' Agent', '').replace(' Extractor', '')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {!isLast && <StepArrow />}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main Agents Page ─────────────────────────────────────────────────────────
export function Agents() {
  const [agents, setAgents]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [lastFetched, setLastFetched] = useState(null);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAgents();
      setAgents(data);
      setLastFetched(new Date());
    } catch (err) {
      setError(err.message || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  // Counts
  const mistralCount  = agents.filter((a) => a.source === 'mistral').length;
  const workflowCount = agents.filter((a) => a.source === 'workflow').length;
  const offlineCount  = agents.filter((a) => a.source === 'mistral_fallback').length;

  return (
    <div className="page">

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, maxWidth: 620, margin: 0 }}>
            This IDP platform uses a <strong style={{ color: 'var(--text)' }}>multi-agent pipeline</strong> powered by
            the Mistral Workflow SDK. Specialized agents collaborate in sequence — each with defined roles, tools,
            and decision authority — to process documents from intake to structured output.
          </p>

          {/* Live counts */}
          {!loading && agents.length > 0 && (
            <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--accent)', background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.2)', borderRadius: 99, padding: '3px 10px' }}>
                <Zap size={10} /> {mistralCount} Mistral Agent{mistralCount !== 1 ? 's' : ''}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-dim)', background: 'var(--card-alt)', border: '1px solid var(--border)', borderRadius: 99, padding: '3px 10px' }}>
                <Cpu size={10} /> {workflowCount} Workflow Activit{workflowCount !== 1 ? 'ies' : 'y'}
              </span>
              {offlineCount > 0 && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--warn)', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 99, padding: '3px 10px' }}>
                  <AlertTriangle size={10} /> {offlineCount} Offline
                </span>
              )}
              {lastFetched && (
                <span style={{ fontSize: 10, color: 'var(--muted)', alignSelf: 'center' }}>
                  Updated {lastFetched.toLocaleTimeString()}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Refresh button */}
        <button
          className="btn btn-ghost btn-sm"
          onClick={fetchAgents}
          disabled={loading}
          id="agents-refresh-btn"
        >
          <RefreshCw size={12} className={loading ? 'spin' : ''} />
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div style={{
          background: 'var(--danger-dim)', border: '1px solid rgba(240,64,96,0.3)',
          borderRadius: 'var(--radius)', padding: '12px 16px', marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 13,
        }}>
          <AlertTriangle size={15} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <div>
            <strong style={{ color: 'var(--danger)' }}>Failed to load agents from backend</strong>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{error}</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={fetchAgents} style={{ marginLeft: 'auto' }}>
            Retry
          </button>
        </div>
      )}

      {/* ── Agent Cards Grid ── */}
      <div className="agents-grid">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => <AgentSkeleton key={i} />)
          : agents.map((agent, i) => (
              <AgentCard key={agent.key} agent={agent} index={i} />
            ))
        }
      </div>

      {/* ── Pipeline Graph ── */}
      {!loading && agents.length > 0 && (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <GitBranch size={16} style={{ color: 'var(--accent)' }} />
                Agent Collaboration Graph
              </div>
              <div className="card-sub">Vertical pipeline · conditional fan-out at extraction phase · human review gate</div>
            </div>
          </div>
          <PipelineGraph agents={agents} />
        </div>
      )}
    </div>
  );
}
```

## `src/pages/Analytics.jsx`

```jsx
import { useEffect, useMemo } from 'react';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatCard } from '../components/ui/StatCard';
import { DonutChart } from '../components/ui/DonutChart';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';
import { FileText, CheckCircle2, XCircle, Loader2, BarChart2 } from 'lucide-react';

function BarChart({ data }) {
  if (!data || data.length === 0) return <div className="empty-state" style={{ padding: 24 }}><div className="empty-sub">No data yet</div></div>;
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120, paddingTop: 8 }}>
      {data.map(({ label, value }) => (
        <div key={label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, height: '100%', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>{value}</span>
          <div style={{
            width: '100%', background: 'var(--accent)',
            height: `${(value / max) * 85}%`, minHeight: value > 0 ? 4 : 0,
            borderRadius: '4px 4px 0 0', opacity: 0.8,
            transition: 'height 0.5s ease',
          }} />
          <span style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'center', lineHeight: 1.2 }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

export function Analytics() {
  const { documents } = useApp();
  const { refresh, loading } = useDocumentList();

  useEffect(() => { refresh(); }, []);

  const total = documents.length;
  const completed = documents.filter((d) => d.status === 'completed').length;
  const rejected  = documents.filter((d) => d.status === 'rejected').length;
  const errors    = documents.filter((d) => d.status === 'error').length;
  const pending   = documents.filter((d) => ['pending','processing'].includes(d.status)).length;
  const inReview  = documents.filter((d) => d.status === 'awaiting_review').length;

  const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;
  const rejectionRate = total > 0 ? Math.round((rejected / total) * 100) : 0;

  // Doc type donut
  const typeData = useMemo(() => {
    const map = {};
    documents.forEach((d) => {
      if (d.doc_type) map[d.doc_type] = (map[d.doc_type] || 0) + 1;
    });
    return Object.entries(map).map(([label, value]) => ({ label, value }));
  }, [documents]);

  // Status bar chart
  const statusBars = [
    { label: 'Completed', value: completed },
    { label: 'In Review', value: inReview },
    { label: 'Processing', value: pending },
    { label: 'Rejected', value: rejected },
    { label: 'Errors', value: errors },
  ];

  // Status breakdown bars
  const breakdownBars = [
    { label: 'Success Rate',    value: successRate / 100 },
    { label: 'Rejection Rate',  value: rejectionRate / 100 },
    { label: 'Review Rate',     value: total > 0 ? inReview / total : 0 },
    { label: 'Error Rate',      value: total > 0 ? errors / total : 0 },
  ];

  return (
    <div className="page">
      <div className="stats-row">
        <StatCard icon={<FileText size={18} />}    iconVariant="accent"                     label="Total Documents" value={total.toLocaleString()} delta="All time" deltaType="neutral" />
        <StatCard icon={<CheckCircle2 size={18} />} iconVariant="success"                    label="Success Rate"    value={successRate} unit="%" delta={`${completed} completed`} deltaType="up" />
        <StatCard icon={<XCircle size={18} />}      iconVariant={rejectionRate > 10 ? 'danger' : 'success'} label="Rejection Rate" value={rejectionRate} unit="%" delta={`${rejected} rejected`} deltaType={rejectionRate > 10 ? 'down' : 'up'} />
        <StatCard icon={<Loader2 size={18} />}      iconVariant={inReview > 0 ? 'warn' : 'accent'}            label="In Pipeline"    value={pending + inReview} delta={inReview > 0 ? `${inReview} awaiting review` : 'Nothing pending'} deltaType={inReview > 0 ? 'warn' : 'up'} />
      </div>

      <div className="grid-2">
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Document Types</div>
            <div className="card-sub">Distribution by type</div>
          </div>
          <DonutChart data={typeData} />
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Status Distribution</div>
            <div className="card-sub">Count by processing status</div>
          </div>
          <BarChart data={statusBars} />
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div className="card-title">Performance Breakdown</div>
        </div>
        {breakdownBars.map((b) => (
          <ConfidenceBar key={b.label} label={b.label} value={b.value} />
        ))}
      </div>

      {total === 0 && (
        <div className="card">
          <div className="empty-state">
            <BarChart2 className="empty-icon" size={36} />
            <div className="empty-title">No analytics yet</div>
            <div className="empty-sub">Upload and process documents to see metrics here.</div>
          </div>
        </div>
      )}
    </div>
  );
}
```


---

# Static assets (`public/`)

## `public/icons.svg`

```html
<svg xmlns="http://www.w3.org/2000/svg">
  <symbol id="bluesky-icon" viewBox="0 0 16 17">
    <g clip-path="url(#bluesky-clip)"><path fill="#08060d" d="M7.75 7.735c-.693-1.348-2.58-3.86-4.334-5.097-1.68-1.187-2.32-.981-2.74-.79C.188 2.065.1 2.812.1 3.251s.241 3.602.398 4.13c.52 1.744 2.367 2.333 4.07 2.145-2.495.37-4.71 1.278-1.805 4.512 3.196 3.309 4.38-.71 4.987-2.746.608 2.036 1.307 5.91 4.93 2.746 2.72-2.746.747-4.143-1.747-4.512 1.702.189 3.55-.4 4.07-2.145.156-.528.397-3.691.397-4.13s-.088-1.186-.575-1.406c-.42-.19-1.06-.395-2.741.79-1.755 1.24-3.64 3.752-4.334 5.099"/></g>
    <defs><clipPath id="bluesky-clip"><path fill="#fff" d="M.1.85h15.3v15.3H.1z"/></clipPath></defs>
  </symbol>
  <symbol id="discord-icon" viewBox="0 0 20 19">
    <path fill="#08060d" d="M16.224 3.768a14.5 14.5 0 0 0-3.67-1.153c-.158.286-.343.67-.47.976a13.5 13.5 0 0 0-4.067 0c-.128-.306-.317-.69-.476-.976A14.4 14.4 0 0 0 3.868 3.77C1.546 7.28.916 10.703 1.231 14.077a14.7 14.7 0 0 0 4.5 2.306q.545-.748.965-1.587a9.5 9.5 0 0 1-1.518-.74q.191-.14.372-.293c2.927 1.369 6.107 1.369 8.999 0q.183.152.372.294-.723.437-1.52.74.418.838.963 1.588a14.6 14.6 0 0 0 4.504-2.308c.37-3.911-.63-7.302-2.644-10.309m-9.13 8.234c-.878 0-1.599-.82-1.599-1.82 0-.998.705-1.82 1.6-1.82.894 0 1.614.82 1.599 1.82.001 1-.705 1.82-1.6 1.82m5.91 0c-.878 0-1.599-.82-1.599-1.82 0-.998.705-1.82 1.6-1.82.893 0 1.614.82 1.599 1.82 0 1-.706 1.82-1.6 1.82"/>
  </symbol>
  <symbol id="documentation-icon" viewBox="0 0 21 20">
    <path fill="none" stroke="#aa3bff" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.35" d="m15.5 13.333 1.533 1.322c.645.555.967.833.967 1.178s-.322.623-.967 1.179L15.5 18.333m-3.333-5-1.534 1.322c-.644.555-.966.833-.966 1.178s.322.623.966 1.179l1.534 1.321"/>
    <path fill="none" stroke="#aa3bff" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.35" d="M17.167 10.836v-4.32c0-1.41 0-2.117-.224-2.68-.359-.906-1.118-1.621-2.08-1.96-.599-.21-1.349-.21-2.848-.21-2.623 0-3.935 0-4.983.369-1.684.591-3.013 1.842-3.641 3.428C3 6.449 3 7.684 3 10.154v2.122c0 2.558 0 3.838.706 4.726q.306.383.713.671c.76.536 1.79.64 3.581.66"/>
    <path fill="none" stroke="#aa3bff" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.35" d="M3 10a2.78 2.78 0 0 1 2.778-2.778c.555 0 1.209.097 1.748-.047.48-.129.854-.503.982-.982.145-.54.048-1.194.048-1.749a2.78 2.78 0 0 1 2.777-2.777"/>
  </symbol>
  <symbol id="github-icon" viewBox="0 0 19 19">
    <path fill="#08060d" fill-rule="evenodd" d="M9.356 1.85C5.05 1.85 1.57 5.356 1.57 9.694a7.84 7.84 0 0 0 5.324 7.44c.387.079.528-.168.528-.376 0-.182-.013-.805-.013-1.454-2.165.467-2.616-.935-2.616-.935-.349-.91-.864-1.143-.864-1.143-.71-.48.051-.48.051-.48.787.051 1.2.805 1.2.805.695 1.194 1.817.857 2.268.649.064-.507.27-.857.49-1.052-1.728-.182-3.545-.857-3.545-3.87 0-.857.31-1.558.8-2.104-.078-.195-.349-1 .077-2.078 0 0 .657-.208 2.14.805a7.5 7.5 0 0 1 1.946-.26c.657 0 1.328.092 1.946.26 1.483-1.013 2.14-.805 2.14-.805.426 1.078.155 1.883.078 2.078.502.546.799 1.247.799 2.104 0 3.013-1.818 3.675-3.558 3.87.284.247.528.714.528 1.454 0 1.052-.012 1.896-.012 2.156 0 .208.142.455.528.377a7.84 7.84 0 0 0 5.324-7.441c.013-4.338-3.48-7.844-7.773-7.844" clip-rule="evenodd"/>
  </symbol>
  <symbol id="social-icon" viewBox="0 0 20 20">
    <path fill="none" stroke="#aa3bff" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.35" d="M12.5 6.667a4.167 4.167 0 1 0-8.334 0 4.167 4.167 0 0 0 8.334 0"/>
    <path fill="none" stroke="#aa3bff" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.35" d="M2.5 16.667a5.833 5.833 0 0 1 8.75-5.053m3.837.474.513 1.035c.07.144.257.282.414.309l.93.155c.596.1.736.536.307.965l-.723.73a.64.64 0 0 0-.152.531l.207.903c.164.715-.213.991-.84.618l-.872-.52a.63.63 0 0 0-.577 0l-.872.52c-.624.373-1.003.094-.84-.618l.207-.903a.64.64 0 0 0-.152-.532l-.723-.729c-.426-.43-.289-.864.306-.964l.93-.156a.64.64 0 0 0 .412-.31l.513-1.034c.28-.562.735-.562 1.012 0"/>
  </symbol>
  <symbol id="x-icon" viewBox="0 0 19 19">
    <path fill="#08060d" fill-rule="evenodd" d="M1.893 1.98c.052.072 1.245 1.769 2.653 3.77l2.892 4.114c.183.261.333.48.333.486s-.068.089-.152.183l-.522.593-.765.867-3.597 4.087c-.375.426-.734.834-.798.905a1 1 0 0 0-.118.148c0 .01.236.017.664.017h.663l.729-.83c.4-.457.796-.906.879-.999a692 692 0 0 0 1.794-2.038c.034-.037.301-.34.594-.675l.551-.624.345-.392a7 7 0 0 1 .34-.374c.006 0 .93 1.306 2.052 2.903l2.084 2.965.045.063h2.275c1.87 0 2.273-.003 2.266-.021-.008-.02-1.098-1.572-3.894-5.547-2.013-2.862-2.28-3.246-2.273-3.266.008-.019.282-.332 2.085-2.38l2-2.274 1.567-1.782c.022-.028-.016-.03-.65-.03h-.674l-.3.342a871 871 0 0 1-1.782 2.025c-.067.075-.405.458-.75.852a100 100 0 0 1-.803.91c-.148.172-.299.344-.99 1.127-.304.343-.32.358-.345.327-.015-.019-.904-1.282-1.976-2.808L6.365 1.85H1.8zm1.782.91 8.078 11.294c.772 1.08 1.413 1.973 1.425 1.984.016.017.241.02 1.05.017l1.03-.004-2.694-3.766L7.796 5.75 5.722 2.852l-1.039-.004-1.039-.004z" clip-rule="evenodd"/>
  </symbol>
</svg>
```

## `public/favicon.svg`

```html
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="46" fill="none" viewBox="0 0 48 46"><path fill="#863bff" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" style="fill:#863bff;fill:color(display-p3 .5252 .23 1);fill-opacity:1"/><mask id="a" width="48" height="46" x="0" y="0" maskUnits="userSpaceOnUse" style="mask-type:alpha"><path fill="#000" d="M25.842 44.938c-.664.844-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.183c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.498 0-3.579-1.842-3.579H1.133c-.92 0-1.456-1.04-.92-1.787L9.91.473c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.578 1.842 3.578h11.377c.943 0 1.473 1.088.89 1.832L25.843 44.94z" style="fill:#000;fill-opacity:1"/></mask><g mask="url(#a)"><g filter="url(#b)"><ellipse cx="5.508" cy="14.704" fill="#ede6ff" rx="5.508" ry="14.704" style="fill:#ede6ff;fill:color(display-p3 .9275 .9033 1);fill-opacity:1" transform="matrix(.00324 1 1 -.00324 -4.47 31.516)"/></g><g filter="url(#c)"><ellipse cx="10.399" cy="29.851" fill="#ede6ff" rx="10.399" ry="29.851" style="fill:#ede6ff;fill:color(display-p3 .9275 .9033 1);fill-opacity:1" transform="matrix(.00324 1 1 -.00324 -39.328 7.883)"/></g><g filter="url(#d)"><ellipse cx="5.508" cy="30.487" fill="#7e14ff" rx="5.508" ry="30.487" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.814 -25.913 -14.639)scale(1 -1)"/></g><g filter="url(#e)"><ellipse cx="5.508" cy="30.599" fill="#7e14ff" rx="5.508" ry="30.599" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.814 -32.644 -3.334)scale(1 -1)"/></g><g filter="url(#f)"><ellipse cx="5.508" cy="30.599" fill="#7e14ff" rx="5.508" ry="30.599" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="matrix(.00324 1 1 -.00324 -34.34 30.47)"/></g><g filter="url(#g)"><ellipse cx="14.072" cy="22.078" fill="#ede6ff" rx="14.072" ry="22.078" style="fill:#ede6ff;fill:color(display-p3 .9275 .9033 1);fill-opacity:1" transform="rotate(93.35 24.506 48.493)scale(-1 1)"/></g><g filter="url(#h)"><ellipse cx="3.47" cy="21.501" fill="#7e14ff" rx="3.47" ry="21.501" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.009 28.708 47.59)scale(-1 1)"/></g><g filter="url(#i)"><ellipse cx="3.47" cy="21.501" fill="#7e14ff" rx="3.47" ry="21.501" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.009 28.708 47.59)scale(-1 1)"/></g><g filter="url(#j)"><ellipse cx=".387" cy="8.972" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(39.51 .387 8.972)"/></g><g filter="url(#k)"><ellipse cx="47.523" cy="-6.092" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 47.523 -6.092)"/></g><g filter="url(#l)"><ellipse cx="41.412" cy="6.333" fill="#47bfff" rx="5.971" ry="9.665" style="fill:#47bfff;fill:color(display-p3 .2799 .748 1);fill-opacity:1" transform="rotate(37.892 41.412 6.333)"/></g><g filter="url(#m)"><ellipse cx="-1.879" cy="38.332" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 -1.88 38.332)"/></g><g filter="url(#n)"><ellipse cx="-1.879" cy="38.332" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 -1.88 38.332)"/></g><g filter="url(#o)"><ellipse cx="35.651" cy="29.907" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 35.651 29.907)"/></g><g filter="url(#p)"><ellipse cx="38.418" cy="32.4" fill="#47bfff" rx="5.971" ry="15.297" style="fill:#47bfff;fill:color(display-p3 .2799 .748 1);fill-opacity:1" transform="rotate(37.892 38.418 32.4)"/></g></g><defs><filter id="b" width="60.045" height="41.654" x="-19.77" y="16.149" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="7.659"/></filter><filter id="c" width="90.34" height="51.437" x="-54.613" y="-7.533" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="7.659"/></filter><filter id="d" width="79.355" height="29.4" x="-49.64" y="2.03" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="e" width="79.579" height="29.4" x="-45.045" y="20.029" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="f" width="79.579" height="29.4" x="-43.513" y="21.178" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="g" width="74.749" height="58.852" x="15.756" y="-17.901" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="7.659"/></filter><filter id="h" width="61.377" height="25.362" x="23.548" y="2.284" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="i" width="61.377" height="25.362" x="23.548" y="2.284" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="j" width="56.045" height="63.649" x="-27.636" y="-22.853" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="k" width="54.814" height="64.646" x="20.116" y="-38.415" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="l" width="33.541" height="35.313" x="24.641" y="-11.323" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="m" width="54.814" height="64.646" x="-29.286" y="6.009" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="n" width="54.814" height="64.646" x="-29.286" y="6.009" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="o" width="54.814" height="64.646" x="8.244" y="-2.416" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter><filter id="p" width="39.409" height="43.623" x="18.713" y="10.588" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse"><feFlood flood-opacity="0" result="BackgroundImageFix"/><feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/><feGaussianBlur result="effect1_foregroundBlur_2002_17158" stdDeviation="4.596"/></filter></defs></svg>
```


---

# Route map (from `App.jsx`)

All routes are nested under `AppShell` (the sidebar + topbar wrapper), matching a shared layout:

| Path              | Page component  |
|-------------------|-----------------|
| `/` (index)       | `Dashboard`     |
| `/upload`         | `Upload`        |
| `/processing`     | `Processing`    |
| `/extraction`     | `Extraction`    |
| `/validation`     | `Validation`    |
| `/documents`      | `Documents`     |
| `/agents`         | `Agents`        |
| `/analytics`      | `Analytics`     |
| `/settings`       | `Settings`      |
| `/templates`      | `Templates`     |
| `/claim-process`  | `ClaimProcess`  |
| `/claim-workflow` | `ClaimWorkflow` |

# Rebuild checklist

1. Scaffold the project and install deps (see section 1 above).
2. Recreate the exact folder tree under `src/` and `public/`.
3. Paste each section of this file into its matching path, unmodified.
4. Confirm `main.jsx` imports `index.css` and mounts `<App />`, and `App.jsx`
   wires the router exactly as in the table above.
5. Run `npm run dev` and diff the rendered UI against the original — text,
   spacing, and colors should match exactly since the CSS/JSX is copied
   verbatim, not re-implemented.
6. If the new project calls a different backend, only change `src/api/client.js`
   (base URL / endpoints) — leave every UI file untouched so the visuals stay identical.
