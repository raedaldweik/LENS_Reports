import { createContext, useContext, useState, useCallback } from 'react';

const ChatContext = createContext();

const id = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

const NEW_TITLE = 'محادثة جديدة';

// A fresh conversation starts empty — the hero empty-state replaces a welcome bubble.
const newChat = () => ({ id: id(), title: NEW_TITLE, messages: [], createdAt: new Date() });

export function ChatProvider({ children }) {
  const [chats, setChats] = useState(() => [newChat()]);
  const [activeChatId, setActiveChatId] = useState(chats[0].id);

  const activeChat = chats.find(c => c.id === activeChatId) || chats[0];

  const createNewChat = useCallback(() => {
    const c = newChat();
    setChats(p => [c, ...p]);
    setActiveChatId(c.id);
  }, []);

  const addMessage = useCallback((chatId, msg) => {
    setChats(p => p.map(c => {
      if (c.id !== chatId) return c;
      const updated = { ...c, messages: [...c.messages, msg] };
      if (msg.role === 'user' && c.title === NEW_TITLE)
        updated.title = msg.content.slice(0, 40) + (msg.content.length > 40 ? '…' : '');
      return updated;
    }));
  }, []);

  const renameChat = useCallback((chatId, newTitle) => {
    setChats(p => p.map(c => c.id === chatId ? { ...c, title: newTitle } : c));
  }, []);

  const deleteChat = useCallback((chatId) => {
    setChats(p => {
      const filtered = p.filter(c => c.id !== chatId);
      if (filtered.length === 0) {
        return [newChat()];
      }
      return filtered;
    });
    setActiveChatId(prev => {
      if (prev === chatId) {
        const remaining = chats.filter(c => c.id !== chatId);
        return remaining.length > 0 ? remaining[0].id : prev;
      }
      return prev;
    });
  }, [chats]);

  return (
    <ChatContext.Provider value={{ chats, activeChat, activeChatId, setActiveChatId, createNewChat, addMessage, renameChat, deleteChat }}>
      {children}
    </ChatContext.Provider>
  );
}

export const useChat = () => useContext(ChatContext);
