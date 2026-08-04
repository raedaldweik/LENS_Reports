import { ChatProvider } from './context/ChatContext';
import Header from './components/Header';
import ChatPage from './pages/ChatPage';

export default function App() {
  return (
    <ChatProvider>
      <div className="app-shell">
        <Header />
        <ChatPage />
      </div>
    </ChatProvider>
  );
}
