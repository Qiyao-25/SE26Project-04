import { Alert, Typography } from 'antd';
import { ChatBox } from '../../../common/ChatBox';

const { Text } = Typography;

export default function SidebarQaPanel({ messages, onSend, qaStatus }) {
  const hasFallback = messages.some((item) => item.answerMode === 'extractive_fallback');
  return (
    <div>
      <Alert
        type="info"
        showIcon
        message="当前为单论文智能问答"
        description="默认由 QA Agent 基于已解析原文块生成并附出处。若 LLM 不可用，会降级为「原文摘录」并单独标记，请勿将其视为 Agent 总结。"
        style={{ marginBottom: 12 }}
      />
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
        “全部”和“问答”标签共享同一会话，切换标签不会丢失消息。
      </Text>
    </div>
  );
}
