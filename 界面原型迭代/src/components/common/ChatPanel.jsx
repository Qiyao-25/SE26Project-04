import { Typography } from 'antd';

const { Text } = Typography;

export default function ChatPanel({ messages, minHeight = 120 }) {
  return (
    <div className="chat-panel" style={{ minHeight }}>
      {messages.map((m, i) => (
        <div key={i} className={`chat-bubble ${m.role}`}>
          <Text style={{ fontSize: 13 }}>{m.text}</Text>
        </div>
      ))}
    </div>
  );
}
