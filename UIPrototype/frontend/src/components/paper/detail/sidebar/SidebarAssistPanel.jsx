import { useEffect, useState } from 'react';
import { Alert, Tag, Typography, Segmented } from 'antd';
import { useApp } from '../../../../context/AppContext';
import { MODE_DESC, PERSONAS } from '../../../../data/papers';
import { getReadingAssist } from '../../../../services/paperService';
import ReadingAssistView from '../ReadingAssistView';

const { Text } = Typography;

export default function SidebarAssistPanel({ paper, paperId }) {
  const { persona, setPersona } = useApp();
  const resolvedId = paperId || paper?.paperId || paper?.id;
  const parsed = ['completed', 'qa_ready'].includes(paper.parseStatus);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);

  const load = async ({ force = false, mode = persona } = {}) => {
    if (!resolvedId || !parsed) return;
    setLoading(true);
    setError('');
    try {
      const next = await getReadingAssist(resolvedId, { mode, force });
      setData(next);
    } catch (err) {
      setError(err.message || '辅助阅读生成失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!parsed) {
      setData(null);
      setError('');
      return undefined;
    }
    load({ force: false, mode: persona });
    return undefined;
  }, [resolvedId, persona, parsed]);

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        默认模式在学习空间设置 · 此处可快捷切换。切换后会按该模式重新组织导读。
      </Text>
      <Segmented
        block
        options={PERSONAS}
        value={persona}
        onChange={setPersona}
        style={{ margin: '12px 0' }}
      />
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message={`${persona}模式`}
        description={MODE_DESC[persona]}
      />
      {parsed ? (
        <ReadingAssistView
          data={data}
          loading={loading}
          error={error}
          onRetry={() => load({ force: true, mode: persona })}
          onRefresh={() => load({ force: true, mode: persona })}
        />
      ) : (
        <Alert
          type="info"
          showIcon
          message="完成解析后可用"
          description="论文解析完成后，会基于智能总结按阅读模式生成更易读的辅助内容。"
        />
      )}
    </div>
  );
}
