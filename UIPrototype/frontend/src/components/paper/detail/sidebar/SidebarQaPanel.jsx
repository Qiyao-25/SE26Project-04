import { Alert, Segmented, Typography } from 'antd';
import { ChatBox } from '../../../common/ChatBox';

const { Text } = Typography;

const SCOPE_OPTIONS = [
  { label: 'Wiki+原文', value: 'both' },
  { label: '仅 Wiki', value: 'wiki' },
  { label: '仅原文', value: 'chunks' }
];

export default function SidebarQaPanel({ messages, onSend, qaStatus, scope = 'both', onScopeChange }) {
  const hasFallback = messages.some((item) => item.answerMode === 'extractive_fallback');
  return (
    <div>
      <Alert
        type="info"
        showIcon
        message="单论文智能问答（支持 Wiki）"
        description="可基于论文知识 Wiki（摘要/概念/方法/实验/局限）与已解析原文块生成回答，并附出处。选择「仅 Wiki」时即使尚未切块也可提问。"
        style={{ marginBottom: 12 }}
      />
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 6, fontSize: 12 }}>
          问答依据范围
        </Text>
        <Segmented
          block
          size="small"
          value={scope}
          options={SCOPE_OPTIONS}
          onChange={(value) => onScopeChange?.(value)}
        />
      </div>
      {hasFallback ? (
        <Alert
          type="warning"
          showIcon
          message="本会话含降级摘录回答"
          style={{ marginBottom: 12 }}
        />
      ) : null}

      <ChatBox
        messages={messages}
        onSend={onSend}
        loading={qaStatus === 'generating'}
        placeholder="例如：这篇论文的核心创新是什么？"
        minHeight={320}
      />

      <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
        “全部”和“问答”标签共享同一会话；切换依据范围不会清空消息。
      </Text>
    </div>
  );
}
