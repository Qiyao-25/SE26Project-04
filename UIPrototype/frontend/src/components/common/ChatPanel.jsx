import { Typography } from 'antd';

const { Text } = Typography;

function getBubbleRole(role) {
  return role === 'assistant' || role === 'bot' ? 'bot' : 'user';
}

export default function ChatPanel({ messages, minHeight = 120 }) {
  return (
    <div className="chat-panel" style={{ minHeight }}>
      {messages.map((messageItem, index) => {
        const content = messageItem.content ?? messageItem.text ?? '';
        const bubbleRole = getBubbleRole(messageItem.role);
        const citations = messageItem.citations || [];

        return (
          <div
            key={messageItem.messageId || `${bubbleRole}-${index}`}
            className={`chat-bubble ${bubbleRole}`}
          >
            <Text style={{ fontSize: 13 }}>{content}</Text>

            {citations.map((citation, citationIndex) => (
              <div
                key={citation.citationId || `${citation.paperId}-${citationIndex}`}
                style={{
                  marginTop: 8,
                  padding: '8px 10px',
                  borderLeft: '3px solid #8b5cf6',
                  borderRadius: 4,
                  background: 'rgba(139, 92, 246, 0.06)'
                }}
              >
                <Text strong style={{ fontSize: 11 }}>
                  引用 {citationIndex + 1}：{citation.sectionTitle || '论文原文'}
                </Text>
                <br />
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {citation.pageNumber ? `第 ${citation.pageNumber} 页 · ` : ''}
                  {citation.quote}
                </Text>
              </div>
            ))}

            {messageItem.status === 'failed' && messageItem.errorMessage && (
              <div style={{ marginTop: 6 }}>
                <Text type="danger" style={{ fontSize: 11 }}>
                  {messageItem.errorMessage}
                </Text>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
