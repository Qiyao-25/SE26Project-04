import { Typography, Spin } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { useApp } from '../../../../context/AppContext';
import { getReadingAssist } from '../../../../services/paperService';

const { Text, Paragraph } = Typography;

export default function SidebarAssistPreview({ paper, paperId }) {
  const { persona } = useApp();
  const resolvedId = paperId || paper?.paperId || paper?.id;
  const parsed = ['completed', 'qa_ready'].includes(paper?.parseStatus);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    if (!resolvedId || !parsed) return;
    setLoading(true);
    try {
      const next = await getReadingAssist(resolvedId, { mode: persona, force: false });
      setData(next);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [parsed, persona, resolvedId]);

  useEffect(() => {
    if (!parsed) {
      setData(null);
      return undefined;
    }
    load();
    return undefined;
  }, [load, parsed]);

  if (!parsed) return <Text type="secondary" style={{ fontSize: 12 }}>完成解析后可用</Text>;
  if (loading) {
    return (
      <div style={{ padding: '8px 0', textAlign: 'center' }}>
        <Spin size="small" />
      </div>
    );
  }
  if (!data) return null;

  const takeaways = (data.takeaways || []).slice(0, 2);
  const firstBullets = (data.sections || [])
    .flatMap((section) => section.bullets || [])
    .slice(0, 2);

  return (
    <div className="sidebar-assist-preview">
      {data.headline ? (
        <Paragraph
          ellipsis={{ rows: 2 }}
          style={{ margin: 0, fontSize: 13, fontWeight: 600 }}
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
    </div>
  );
}
