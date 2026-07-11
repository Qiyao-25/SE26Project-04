import { useState } from 'react';
import { Input, Button, List, Typography, Badge, message } from 'antd';
import { useApp } from '../../../../context/AppContext';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

export default function SidebarNotesPanel({ paperId }) {
  const { getPaperNotes, saveNote, addComment } = useApp();
  const [noteText, setNoteText] = useState('');
  const [commentText, setCommentText] = useState('');
  const data = getPaperNotes(paperId);

  return (
    <div className="sidebar-scroll">
      <Text className="block-label">添加笔记</Text>
      <Paragraph type="secondary" style={{ fontSize: 11, padding: 8, background: '#fafafa', borderLeft: '3px solid #d9d9d9' }}>
        [ 选中文本高亮占位：Multi-Head Attention... ]
      </Paragraph>
      <TextArea rows={3} value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="记录阅读笔记..." />
      <Button type="primary" block style={{ marginTop: 8 }} onClick={() => {
        if (!noteText.trim()) return message.warning('请输入笔记内容');
        saveNote(paperId, noteText.trim());
        setNoteText('');
        message.success('笔记已保存');
      }}>保存笔记</Button>

      <div style={{ marginTop: 16 }}>
        <Badge count={data.notes.length} offset={[8, 0]}>
          <Text strong>我的笔记</Text>
        </Badge>
        <List
          size="small"
          dataSource={data.notes}
          locale={{ emptyText: '暂无笔记' }}
          renderItem={(n) => (
            <List.Item>
              <div style={{ fontSize: 12 }}>
                {n.highlight && <Text type="secondary">「{n.highlight}」</Text>}
                <Paragraph style={{ margin: '4px 0', fontSize: 12 }}>{n.text}</Paragraph>
                <Text type="secondary" style={{ fontSize: 10 }}>{n.date}</Text>
              </div>
            </List.Item>
          )}
        />
      </div>

      <div style={{ marginTop: 16 }}>
        <Text strong>评论</Text>
        <List
          size="small"
          dataSource={data.comments}
          locale={{ emptyText: '暂无评论' }}
          renderItem={(c) => (
            <List.Item>
              <div style={{ fontSize: 12 }}>
                <Paragraph style={{ margin: 0, fontSize: 12 }}>{c.text}</Paragraph>
                <Text type="secondary" style={{ fontSize: 10 }}>{c.date}</Text>
              </div>
            </List.Item>
          )}
        />
        <Input
          value={commentText}
          onChange={(e) => setCommentText(e.target.value)}
          placeholder="添加评论..."
          onPressEnter={() => {
            if (!commentText.trim()) return;
            addComment(paperId, commentText.trim());
            setCommentText('');
            message.success('评论已发表');
          }}
          suffix={
            <Button type="link" size="small" onClick={() => {
              if (!commentText.trim()) return;
              addComment(paperId, commentText.trim());
              setCommentText('');
              message.success('评论已发表');
            }}>发表</Button>
          }
        />
      </div>
    </div>
  );
}
