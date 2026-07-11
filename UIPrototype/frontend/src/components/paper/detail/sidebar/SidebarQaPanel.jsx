import { useState } from 'react';
import { mockPaperReply } from '../../../../utils/mock';
import { ChatBox } from '../../../common/ChatBox';

export default function SidebarQaPanel({ paperId }) {
  const [messages, setMessages] = useState([
    { role: 'bot', text: '可围绕本篇论文提问' }
  ]);

  const handleSend = (text) => {
    setMessages((m) => [...m, { role: 'user', text }]);
    setTimeout(() => {
      setMessages((m) => [...m, { role: 'bot', text: mockPaperReply(text, paperId) }]);
    }, 400);
  };

  return <ChatBox messages={messages} onSend={handleSend} minHeight={280} />;
}
