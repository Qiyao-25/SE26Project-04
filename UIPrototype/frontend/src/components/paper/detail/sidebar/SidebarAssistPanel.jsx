import { Typography, Segmented } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { useApp } from '../../../../context/AppContext';
import { PERSONAS } from '../../../../data/papers';
import { getReadingAssist } from '../../../../services/paperService';
import ReadingAssistView from '../ReadingAssistView';

export default function SidebarAssistPanel({ paper, paperId }) {
  const { persona, setPersona } = useApp();
  const resolvedId = paperId || paper?.paperId || paper?.id;
  const parsed = ['completed', 'qa_ready'].includes(paper.parseStatus);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);

  const load = useCallback(async ({ force = false, mode = persona } = {}) => {
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
  }, [parsed, persona, resolvedId]);

  useEffect(() => {
    if (!parsed) {
      setData(null);
      setError('');
      return undefined;
    }
    load({ force: false, mode: persona });
    return undefined;
  }, [load, parsed, persona]);

  return (
    <div>
      <Segmented
        block
        options={PERSONAS}
        value={persona}
        onChange={setPersona}
        style={{ marginBottom: 12 }}
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
        <Typography.Text type="secondary">完成解析后可用</Typography.Text>
      )}
    </div>
  );
}
