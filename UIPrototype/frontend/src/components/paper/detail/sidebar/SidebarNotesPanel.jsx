import { useEffect, useState } from 'react';
import { Input, Button, List, Typography, Badge, message } from 'antd';
import { useApp } from '../../../../context/AppContext';
import { createAction, isPersistedPaperId, listPaperNotes } from '../../../../services/learningService';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

export default function SidebarNotesPanel({ paperId }) {
  const { userId, getPaperNotes, replacePaperNotes, saveNote, addComment } = useApp();
  const [noteText, setNoteText] = useState('');
  const [commentText, setCommentText] = useState('');
  const [loading, setLoading] = useState(false);
  const data = getPaperNotes(paperId);
  const persist = isPersistedPaperId(paperId);

  useEffect(() => {
    let cancelled = false;
    if (!persist) return undefined;
    replacePaperNotes(paperId, { notes: [], comments: [] });
    setLoading(true);
    listPaperNotes(userId, paperId)
      .then((actions) => {
        if (cancelled) return;
        const notes = actions
          .filter((action) => action.payload_json?.kind !== 'comment')
          .map((action) => ({
            id: action.id,
            highlight: action.payload_json?.highlight,
            text: action.payload_json?.text || '',
            date: action.occurred_at?.slice(0, 10) || ''
          }));
        const comments = actions
          .filter((action) => action.payload_json?.kind === 'comment')
          .map((action) => ({
            id: action.id,
            text: action.payload_json?.text || '',
            date: action.occurred_at?.slice(0, 10) || ''
          }));
        replacePaperNotes(paperId, { notes, comments });
      })
      .catch((error) => {
        if (!cancelled) message.error(error.message || '笔记加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [paperId, persist, replacePaperNotes, userId]);

  const addBackendAction = async (text, kind) => {
    await createAction({
      userId,
      paperId,
      actionType: 'note',
      payload: {
        kind,
        text,
        highlight: kind === 'note' ? '选中文本高亮' : undefined
      }
    });
  };

  const handleSaveNote = async () => {
    const text = noteText.trim();
    if (!text) return message.warning('请输入笔记内容');
    try {
      if (persist) await addBackendAction(text, 'note');
      saveNote(paperId, text);
      setNoteText('');
      message.success('笔记已保存');
    } catch (error) {
      message.error(error.message || '笔记保存失败');
    }
  };

  const handleAddComment = async () => {
    const text = commentText.trim();
    if (!text) return;
    try {
      if (persist) await addBackendAction(text, 'comment');
      addComment(paperId, text);
      setCommentText('');
      message.success('评论已发表');
    } catch (error) {
      message.error(error.message || '评论保存失败');
    }
  };

  return (
    <div className="sidebar-scroll">
      <Text className="block-label">添加笔记</Text>
      <Paragraph type="secondary" style={{ fontSize: 11, padding: 8, background: '#fafafa', borderLeft: '3px solid #d9d9d9' }}>
        笔记和评论会保存到当前账户，可在学习空间查看。
      </Paragraph>
      <TextArea rows={3} value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="记录阅读笔记..." />
      <Button type="primary" block loading={loading} style={{ marginTop: 8 }} onClick={handleSaveNote}>保存笔记</Button>

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
          onPressEnter={handleAddComment}
          suffix={
            <Button type="link" size="small" onClick={handleAddComment}>发表</Button>
          }
        />
      </div>
    </div>
  );
}
