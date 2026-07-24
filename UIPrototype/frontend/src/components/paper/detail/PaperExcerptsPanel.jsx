import { useRef } from 'react';
import { Alert, Empty, Typography } from 'antd';
import {
  highlightDomSelection,
  pushAnnotationSelection,
} from '../../../utils/annotationSelection';

const { Paragraph, Text } = Typography;

/**
 * Selectable parsed text (no PDF hosting). Selection fills the notes-panel quote.
 */
export default function PaperExcerptsPanel({ abstractText, chunks = [], parseReady }) {
  const bodyRef = useRef(null);

  const handleMouseUp = (event) => {
    event.stopPropagation();
    const text = highlightDomSelection(bodyRef.current);
    if (!text || text.length < 2) return;
    const marked = bodyRef.current?.querySelector('mark.pm-annotation-highlight');
    const host = marked?.closest?.('[data-chunk-id]');
    const selectedId = host?.getAttribute('data-chunk-id') || undefined;
    const meta = chunks.find((item) => item.chunk_id === selectedId);
    pushAnnotationSelection({
      text,
      chunkId: selectedId || null,
      pageNo: meta?.page_no ?? null,
      section: meta?.section || (host?.getAttribute('data-section') || null),
    });
  };

  const hasChunks = chunks.length > 0;
  const hasAbstract = Boolean(String(abstractText || '').trim());

  if (!hasChunks && !hasAbstract) {
    return (
      <Empty
        description={
          parseReady
            ? '暂无可用原文段落'
            : '论文解析完成后，这里会显示可划选的原文段落'
        }
      />
    );
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="划选原文即可批注"
        description="此处展示解析后的文本（不托管 PDF）。在段落中划选后，摘录会自动填入右侧批注框。"
      />
      <div
        ref={bodyRef}
        className="paper-excerpts-body"
        onMouseUp={handleMouseUp}
        role="region"
        aria-label="可划选原文段落"
      >
        {hasAbstract && (
          <div data-section="Abstract" className="paper-excerpt-chunk">
            <Text type="secondary" style={{ fontSize: 11 }}>摘要 · Abstract</Text>
            <Paragraph style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>
              {abstractText}
            </Paragraph>
          </div>
        )}
        {chunks.map((item) => (
          <div
            key={item.chunk_id}
            data-chunk-id={item.chunk_id}
            data-section={item.section || ''}
            className="paper-excerpt-chunk"
          >
            <Text type="secondary" style={{ fontSize: 11 }}>
              {item.section || '段落'}
              {item.page_no ? ` · p${item.page_no}` : ''}
            </Text>
            <Paragraph style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>
              {item.content || item.preview}
            </Paragraph>
          </div>
        ))}
      </div>
    </div>
  );
}
