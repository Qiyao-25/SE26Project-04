import { Alert, Tag, Typography, Segmented, Spin } from 'antd';
import { useEffect, useState } from 'react';
import { useApp } from '../../../../context/AppContext';
import { PERSONAS } from '../../../../data/papers';
import { getReadingAssist } from '../../../../services/paperService';
import { isPersistedPaperId } from '../../../../services/learningService';

const { Paragraph, Text } = Typography;

export default function SidebarAssistPanel({ paper, paperId }) {
  const { persona, setPersona } = useApp();
  const parsed = ['completed', 'qa_ready'].includes(paper.parseStatus);
  const [assist, setAssist] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!parsed || !isPersistedPaperId(paperId)) {
      setAssist(null);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    getReadingAssist(paperId, { mode: persona })
      .then((data) => { if (!cancelled) setAssist(data); })
      .catch((requestError) => { if (!cancelled) setError(requestError.message || '辅助阅读加载失败'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [paperId, parsed, persona]);

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>默认模式在学习空间设置 · 此处可快捷切换</Text>
      <Segmented
        block
        options={PERSONAS}
        value={persona}
        onChange={setPersona}
        style={{ margin: '12px 0' }}
      />
      {parsed ? (
        <>
          <Text className="block-label">个性化总结 · <Tag>{persona}模式</Tag></Text>
          {loading && <Spin size="small" tip="正在生成辅助阅读..." />}
          {error && <Alert type="error" showIcon message="辅助阅读加载失败" description={error} />}
          {!loading && !error && assist && <>
            <Text strong>{assist.headline}</Text>
            {assist.sections.map((section) => <div key={section.title} style={{ marginTop: 10 }}><Text strong>{section.title}</Text><ul>{(section.bullets || []).map((bullet) => <li key={bullet}><Paragraph style={{ margin: 0, fontSize: 12 }}>{bullet}</Paragraph></li>)}</ul></div>)}
          </>}
        </>
      ) : (
        <Alert
          type="info"
          showIcon
          message="完成解析后可用"
          description="论文解析完成后，这里才会生成个性化辅助阅读内容。"
        />
      )}
    </div>
  );
}
