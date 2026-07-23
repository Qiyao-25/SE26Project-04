import { Tag, Typography } from 'antd';

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
        const citations = (messageItem.citations || []).filter(
          (citation) => (citation.quote || citation.sectionTitle || citation.pageNumber)
        );
        const isFallback = messageItem.answerMode === 'extractive_fallback';

        return (
          <div
            key={messageItem.messageId || `${bubbleRole}-${index}`}
            className={`chat-bubble ${bubbleRole}`}
          >
            {isFallback ? (
              <Tag color="orange" style={{ marginBottom: 6 }}>
                降级摘录（非 Agent 总结）
              </Tag>
            ) : null}
            <Text style={{ fontSize: 13 }}>{content}</Text>

            {citations.map((citation, citationIndex) => (
              <div
                key={citation.citationId || `${citation.paperId}-${citationIndex}`}
                className="qa-citation"
                style={{
                  marginTop: 8,
                  padding: '8px 10px',
                  borderLeft: '3px solid #3b63f4',
                  borderRadius: 4,
                  background: 'rgba(59, 99, 244, 0.06)'
                }}
              >
                <Text strong style={{ fontSize: 11 }}>
                  出处 {citationIndex + 1}：{citation.sectionTitle || '论文原文'}
                  {citation.pageNumber ? ` · 第 ${citation.pageNumber} 页` : ''}
                </Text>
                {citation.quote ? (
                  <>
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      “{citation.quote}”
                    </Text>
                  </>
                ) : null}
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
