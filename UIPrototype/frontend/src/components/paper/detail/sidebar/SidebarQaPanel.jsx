import { Segmented } from 'antd';
import { ChatBox } from '../../../common/ChatBox';

const SCOPE_OPTIONS = [
  { label: 'Wiki+原文', value: 'both' },
  { label: '仅 Wiki', value: 'wiki' },
  { label: '仅原文', value: 'chunks' }
];

export default function SidebarQaPanel({ messages, onSend, qaStatus, scope = 'both', onScopeChange }) {
  return (
    <div>
      <Segmented
        block
        size="small"
        value={scope}
        options={SCOPE_OPTIONS}
        onChange={(value) => onScopeChange?.(value)}
        style={{ marginBottom: 12 }}
      />
      <ChatBox
        messages={messages}
        onSend={onSend}
        loading={qaStatus === 'generating'}
        placeholder="围绕当前论文提问…"
        minHeight={320}
      />
    </div>
  );
}
