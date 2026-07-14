import { Alert, Typography } from 'antd';
import { ChatBox } from '../../../common/ChatBox';

const { Text } = Typography;

export default function SidebarQaPanel({ messages, onSend, qaStatus }) {
  return (
    <div>
      <Alert
        type="info"
        showIcon
        message="当前为单论文问答"
        description="回答基于当前论文的结构化内容生成，并展示引用章节与页码。"
        style={{ marginBottom: 12 }}
      />

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
