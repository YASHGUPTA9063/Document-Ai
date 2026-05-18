import { createContext, useContext, useState } from 'react';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [activePage, setActivePage] = useState('dashboard');
  const [showModal, setShowModal] = useState(false);

  const navigate = (page) => {
    if (page) setActivePage(page);
  };

  return (
    <AppContext.Provider value={{ activePage, navigate, showModal, setShowModal }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
