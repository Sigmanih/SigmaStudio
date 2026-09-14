import { useState } from 'react';
import Login from './components/Login';
import Register from './components/Register';
import Library from './components/Library';

export default function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState('login'); // 'login' | 'register' | 'library'

  const handleLoginSuccess = (userData) => {
    setUser(userData);
    setView('library');
  };

  const handleLogout = () => {
    setUser(null);
    setView('login');
  };

  if (view === 'register') {
    return <Register onSwitchToLogin={() => setView('login')} onRegisterSuccess={handleLoginSuccess} />;
  }

  if (user) {
    return <Library user={user} onLogout={handleLogout} />;
  }

  return <Login onSwitchToRegister={() => setView('register')} onLoginSuccess={handleLoginSuccess} />;
}
