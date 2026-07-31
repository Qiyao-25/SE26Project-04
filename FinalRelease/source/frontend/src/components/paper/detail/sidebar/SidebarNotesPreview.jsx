import { Typography } from 'antd';
import { useApp } from '../../../../context/AppContext';

const { Text, Paragraph } = Typography;

export default function SidebarNotesPreview({ paperId }) {
  const { getPaperNotes } = useApp();
  const data = getPaperNotes(paperId);
  if (!data.notes.length && !data.comments.length) {
    return <Text type="secondary" style={{ fontSize: 12 }}>暂无笔记与评论</Text>;
  }
  return (
    <div style={{ fontSize: 12 }}>
      {data.notes[0] && (
        <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 4, fontSize: 12 }}>
          {data.notes[0].text}
        </Paragraph>
      )}
      {data.comments[0] && (
        <Text type="secondary">{data.comments[0].text}</Text>
      )}
    </div>
  );
}
