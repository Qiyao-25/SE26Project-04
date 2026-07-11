import { Input, Button, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { useState } from 'react';
import ChatPanel from './ChatPanel';

export default function ChatInput({ onSend, placeholder = '输入问题...' }) {
  const [value, setValue] = useState('');

  const handleSend = () => {
    const text = value.trim();
    if (!text) return;
    onSend(text);
    setValue('');
  };

  return (
    <Space.Compact style={{ width: '100%', marginTop: 8 }}>
      <Input
        value={value}
        placeholder={placeholder}
        onChange={(e) => setValue(e.target.value)}
        onPressEnter={handleSend}
      />
      <Button type="primary" icon={<SendOutlined />} onClick={handleSend}>发送</Button>
    </Space.Compact>
  );
}

export function ChatBox({ messages, onSend, placeholder, minHeight = 120 }) {
  return (
    <div>
      <ChatPanel messages={messages} minHeight={minHeight} />
      <ChatInput onSend={onSend} placeholder={placeholder} />
    </div>
  );
}
