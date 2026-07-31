import { Input, Button, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { useState } from 'react';
import ChatPanel from './ChatPanel';

export default function ChatInput({
  onSend,
  placeholder = '输入问题...',
  loading = false
}) {
  const [value, setValue] = useState('');

  const handleSend = () => {
    const text = value.trim();
    if (!text || loading) return;

    onSend(text);
    setValue('');
  };

  return (
    <Space.Compact style={{ width: '100%', marginTop: 8 }}>
      <Input
        value={value}
        placeholder={placeholder}
        disabled={loading}
        maxLength={500}
        onChange={(event) => setValue(event.target.value)}
        onPressEnter={handleSend}
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        loading={loading}
        disabled={loading || !value.trim()}
        onClick={handleSend}
      >
        发送
      </Button>
    </Space.Compact>
  );
}

export function ChatBox({
  messages,
  onSend,
  placeholder,
  minHeight = 120,
  loading = false
}) {
  return (
    <div>
      <ChatPanel messages={messages} minHeight={minHeight} />
      <ChatInput
        onSend={onSend}
        placeholder={placeholder}
        loading={loading}
      />
    </div>
  );
}
