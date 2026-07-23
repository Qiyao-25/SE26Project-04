import { Alert, Typography, Spin } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { useApp } from '../../../../context/AppContext';
import { getReadingAssist } from '../../../../services/paperService';

const { Text, Paragraph } = Typography;

/**
 * Compact assist summary for the "全部" sidebar tab:
 * no mode switcher, no mode descriptions — only a short preview of generated text.
 */
export default function SidebarAssistPreview({ paper, paperId }) {
  const { persona } = useApp();
  const resolvedId = paperId || paper?.paperId || paper?.id;
  const parsed = ['completed', 'qa_ready'].includes(paper?.parseStatus);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    if (!resolvedId || !parsed) return;
    setLoading(true);
    setError('');
    try {
      const next = await getReadingAssist(resolvedId, { mode: persona, force: false });
      setData(next);
    } catch (err) {
      setError(err.message || '辅助阅读加载失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [parsed, persona, resolvedId]);

  useEffect(() => {
    if (!parsed) {
      setData(null);
      setError('');
      return undefined;
    }
    load();
    return undefined;
  }, [load, parsed]);

  if (!parsed) {
    return (
      <Text type="secondary" style={{ fontSize: 12 }}>
        完成解析后可生成辅助阅读预览。
      </Text>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: '8px 0', textAlign: 'center' }}>
        <Spin size="small" tip="加载预览..." />
      </div>
    );
  }

  if (error) {
    return (
      <Alert type="warning" showIcon message={error} style={{ margin: 0 }} />
    );
  }

  if (!data) {
    return (
      <Text type="secondary" style={{ fontSize: 12 }}>
        暂无辅助内容预览。
      </Text>
    );
  }

  const takeaways = (data.takeaways || []).slice(0, 2);
  const firstBullets = (data.sections || [])
    .flatMap((section) => section.bullets || [])
    .slice(0, 2);

  return (
    <div className="sidebar-assist-preview">
      <Text type="secondary" style={{ fontSize: 11 }}>
        当前 {data.mode || persona}模式 · 预览
      </Text>
      {data.headline ? (
        <Paragraph
          ellipsis={{ rows: 2 }}
          style={{ margin: '6px 0 0', fontSize: 13, fontWeight: 600 }}
        >
          {data.headline}
        </Paragraph>
      ) : null}
      {(takeaways.length ? takeaways : firstBullets).slice(0, 2).map((line) => (
        <Paragraph
          key={line}
          type="secondary"
          ellipsis={{ rows: 1 }}
          style={{ margin: '4px 0 0', fontSize: 12 }}
        >
          · {line}
        </Paragraph>
      ))}
      {!takeaways.length && !firstBullets.length && !data.headline ? (
        <Text type="secondary" style={{ fontSize: 12 }}>点击右上角前往查看完整内容</Text>
      ) : (
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 6 }}>
          仅显示部分内容…
        </Text>
      )}
    </div>
  );
}
