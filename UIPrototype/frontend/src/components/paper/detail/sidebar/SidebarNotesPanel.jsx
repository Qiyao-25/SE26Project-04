import { useEffect, useState } from 'react';
import { Input, Button, List, Typography, Badge, message, Select, Space, Tag, Segmented } from 'antd';
import { useApp } from '../../../../context/AppContext';
import {
  createAction,
  isPersistedPaperId,
  listPaperNotes,
  listPublicComments,
} from '../../../../services/learningService';
import { listPaperChunks } from '../../../../services/paperService';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

export default function SidebarNotesPanel({ paperId }) {
  const { userId, getPaperNotes, replacePaperNotes, saveNote, addComment } = useApp();
  const [noteText, setNoteText] = useState('');
  const [commentText, setCommentText] = useState('');
  const [noteMode, setNoteMode] = useState('note'); // note | annotation
  const [quote, setQuote] = useState('');
  const [chunkId, setChunkId] = useState(undefined);
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(false);
  const data = getPaperNotes(paperId);
  const persist = isPersistedPaperId(paperId);

  const reload = async () => {
    if (!persist) return;
    setLoading(true);
    try {
      const [privateActions, publicComments, chunkRows] = await Promise.all([
        listPaperNotes(userId, paperId),
        listPublicComments(paperId),
        listPaperChunks(paperId).catch(() => []),
      ]);
      const notes = privateActions
        .filter((action) => action.payload_json?.kind !== 'comment')
        .map((action) => ({
          id: action.id,
          kind: action.payload_json?.kind || 'note',
          highlight: action.payload_json?.highlight,
          text: action.payload_json?.text || '',
          chunkId: action.payload_json?.chunk_id,
          pageNo: action.payload_json?.page_no,
          section: action.payload_json?.section,
          date: action.occurred_at?.slice(0, 10) || '',
        }));
      const comments = (publicComments || []).map((action) => ({
        id: action.id,
        text: action.payload_json?.text || '',
        author: action.user_id,
        date: action.occurred_at?.slice(0, 10) || '',
        mine: String(action.user_id) === String(userId),
      }));
      replacePaperNotes(paperId, { notes, comments });
      setChunks(chunkRows || []);
    } catch (error) {
      message.error(error.message || '笔记加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    if (!persist) return undefined;
    replacePaperNotes(paperId, { notes: [], comments: [] });
    reload().then(() => { if (cancelled) return; });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId, persist, userId]);

  const selectedChunk = chunks.find((item) => item.chunk_id === chunkId);

  const handleSaveNote = async () => {
    const text = noteText.trim();
    if (!text) return message.warning('请输入笔记内容');
    if (noteMode === 'annotation' && !quote.trim() && !chunkId) {
      return message.warning('批注请填写摘录或选择段落');
    }
    const payload = {
      kind: noteMode === 'annotation' ? 'annotation' : 'note',
      text,
      highlight: quote.trim() || selectedChunk?.preview || undefined,
      chunk_id: chunkId || undefined,
      page_no: selectedChunk?.page_no ?? undefined,
      section: selectedChunk?.section || undefined,
      visibility: 'private',
    };
    try {
      if (persist) {
        await createAction({
          userId,
          paperId,
          actionType: 'note',
          payload,
        });
        await reload();
      } else {
        saveNote(paperId, text);
      }
      setNoteText('');
      setQuote('');
      message.success(noteMode === 'annotation' ? '批注已保存（仅自己可见）' : '笔记已保存（仅自己可见）');
    } catch (error) {
      message.error(error.message || '笔记保存失败');
    }
  };

  const handleAddComment = async () => {
    const text = commentText.trim();
    if (!text) return;
    try {
      if (persist) {
        await createAction({
          userId,
          paperId,
          actionType: 'note',
          payload: { kind: 'comment', text, visibility: 'public' },
        });
        await reload();
      } else {
        addComment(paperId, text);
      }
      setCommentText('');
      message.success('评论已发表（所有人可见）');
    } catch (error) {
      message.error(error.message || '评论保存失败');
    }
  };

  return (
    <div className="sidebar-scroll">
      <Text className="block-label">笔记 / 批注</Text>
      <Paragraph type="secondary" style={{ fontSize: 11, padding: 8, background: '#fafafa', borderLeft: '3px solid #d9d9d9' }}>
        笔记与批注仅自己可见；评论对所有登录用户公开。可选择正文段落做段落笔记。
      </Paragraph>
      <Segmented
        block
        size="small"
        value={noteMode}
        onChange={setNoteMode}
        options={[
          { label: '笔记', value: 'note' },
          { label: '批注', value: 'annotation' },
        ]}
        style={{ marginBottom: 8 }}
      />
      {chunks.length > 0 && (
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="选择段落（可选）"
          style={{ width: '100%', marginBottom: 8 }}
          value={chunkId}
          onChange={setChunkId}
          options={chunks.map((item) => ({
            value: item.chunk_id,
            label: `${item.section || '段落'}${item.page_no ? ` · p${item.page_no}` : ''} · ${(item.preview || '').slice(0, 40)}`,
          }))}
        />
      )}
      {(noteMode === 'annotation' || chunkId) && (
        <TextArea
          rows={2}
          value={quote}
          onChange={(e) => setQuote(e.target.value)}
          placeholder="摘录 / 高亮原文（批注建议填写）"
          style={{ marginBottom: 8 }}
        />
      )}
      <TextArea rows={3} value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder={noteMode === 'annotation' ? '写下批注...' : '记录阅读笔记...'} />
      <Button type="primary" block loading={loading} style={{ marginTop: 8 }} onClick={handleSaveNote}>
        {noteMode === 'annotation' ? '保存批注' : '保存笔记'}
      </Button>

      <div style={{ marginTop: 16 }}>
        <Badge count={data.notes.length} offset={[8, 0]}>
          <Text strong>我的笔记 / 批注</Text>
        </Badge>
        <List
          size="small"
          dataSource={data.notes}
          locale={{ emptyText: '暂无笔记' }}
          renderItem={(n) => (
            <List.Item>
              <div style={{ fontSize: 12, width: '100%' }}>
                <Space size={4} wrap>
                  <Tag>{n.kind === 'annotation' ? '批注' : '笔记'}</Tag>
                  {n.section ? <Tag color="blue">{n.section}</Tag> : null}
                  {n.pageNo ? <Tag>p{n.pageNo}</Tag> : null}
                </Space>
                {n.highlight && <Text type="secondary">「{n.highlight}」</Text>}
                <Paragraph style={{ margin: '4px 0', fontSize: 12 }}>{n.text}</Paragraph>
                <Text type="secondary" style={{ fontSize: 10 }}>{n.date}</Text>
              </div>
            </List.Item>
          )}
        />
      </div>

      <div style={{ marginTop: 16 }}>
        <Badge count={data.comments.length} offset={[8, 0]}>
          <Text strong>公开评论</Text>
        </Badge>
        <List
          size="small"
          dataSource={data.comments}
          locale={{ emptyText: '暂无评论' }}
          renderItem={(c) => (
            <List.Item>
              <div style={{ fontSize: 12 }}>
                <Text type="secondary" style={{ fontSize: 10 }}>{c.mine ? '我' : `用户 ${c.author}`}</Text>
                <Paragraph style={{ margin: '2px 0', fontSize: 12 }}>{c.text}</Paragraph>
                <Text type="secondary" style={{ fontSize: 10 }}>{c.date}</Text>
              </div>
            </List.Item>
          )}
        />
        <Input
          value={commentText}
          onChange={(e) => setCommentText(e.target.value)}
          placeholder="添加公开评论..."
          onPressEnter={handleAddComment}
          suffix={
            <Button type="link" size="small" onClick={handleAddComment}>发表</Button>
          }
        />
      </div>
    </div>
  );
}
