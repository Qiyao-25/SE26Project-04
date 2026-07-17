import { Alert, Button, Space, Spin, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;

/**
 * Renders structured reading-mode assist content from ReadingModeAgent.
 */
export default function ReadingAssistView({
  data,
  loading = false,
  error = '',
  onRetry,
  onRefresh,
  compact = false
}) {
  if (loading) {
    return (
      <div style={{ padding: compact ? 12 : 24, textAlign: 'center' }}>
        <Spin tip="正在按阅读模式生成辅助内容..." />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="辅助阅读生成失败"
        description={error}
        action={
          onRetry ? (
            <Button size="small" onClick={onRetry}>
              重试
            </Button>
          ) : null
        }
      />
    );
  }

  if (!data || !(data.sections || []).length) {
    return (
      <Alert
        type="info"
        showIcon
        message="暂无辅助内容"
        description="可点击重新生成，或先完成论文解析以获得更准确的模式化导读。"
      />
    );
  }

  return (
    <div className="reading-assist-view">
      <Space wrap style={{ width: '100%', justifyContent: 'space-between', marginBottom: 8 }}>
        <Space wrap>
          <Tag color="blue">{data.mode}模式</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {data.source || ''}
            {data.generated ? ' · 刚生成' : ' · 已缓存'}
          </Text>
        </Space>
        {onRefresh && (
          <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh}>
            按此模式重生成
          </Button>
        )}
      </Space>

      {data.headline && (
        <Title level={compact ? 5 : 4} style={{ marginTop: 0, marginBottom: 12 }}>
          {data.headline}
        </Title>
      )}

      {(data.sections || []).map((section) => (
        <div
          key={section.title}
          style={{
            marginBottom: 12,
            padding: '10px 12px',
            background: '#fafafa',
            borderRadius: 8,
            border: '1px solid #f0f0f0'
          }}
        >
          <Text strong style={{ display: 'block', marginBottom: 6 }}>
            {section.title}
          </Text>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {(section.bullets || []).map((bullet, index) => (
              <li key={`${section.title}-${index}`} style={{ marginBottom: 4, fontSize: compact ? 12 : 13, lineHeight: 1.55 }}>
                {bullet}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {(data.takeaways || []).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Text strong>带走这几句</Text>
          <div style={{ marginTop: 6 }}>
            {(data.takeaways || []).map((item) => (
              <Tag key={item} color="geekblue" style={{ marginBottom: 6, whiteSpace: 'normal', height: 'auto' }}>
                {item}
              </Tag>
            ))}
          </div>
        </div>
      )}

      {(data.next_steps || []).length > 0 && !compact && (
        <div>
          <Text strong>下一步</Text>
          <Paragraph type="secondary" style={{ marginTop: 6, marginBottom: 0 }}>
            {(data.next_steps || []).map((step, index) => (
              <span key={step}>
                {index + 1}. {step}
                {index < data.next_steps.length - 1 ? '；' : ''}
              </span>
            ))}
          </Paragraph>
        </div>
      )}
    </div>
  );
}
