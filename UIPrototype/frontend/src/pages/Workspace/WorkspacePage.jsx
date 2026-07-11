import { useState } from 'react';
import { Card, Typography, Row, Col, message } from 'antd';
import { useApp } from '../../context/AppContext';
import { PAPER_LIST } from '../../data/papers';
import { mockWorkspaceReply } from '../../utils/mock';
import { ChatBox } from '../../components/common/ChatBox';
import PaperCard from '../../components/paper/PaperCard';

const { Title, Text } = Typography;

const DAILY = ['attention', 'gpt3', 'vlm'];
const RECOMMENDED = ['bert', 'lora', 'rag'];

export default function WorkspacePage() {
  const { workspaceSearched, setWorkspaceSearched, lastSearchQuery, setLastSearchQuery } = useApp();
  const [messages, setMessages] = useState([
    { role: 'bot', text: '您好，可输入自然语言检索论文，支持多轮追问。搜索后将展示检索结果。' }
  ]);
  const [resultIds, setResultIds] = useState(PAPER_LIST.map((p) => p.id));

  const handleSearch = (text) => {
    setMessages((m) => [...m, { role: 'user', text }]);
    setLastSearchQuery(text);
    setWorkspaceSearched(true);
    const q = text.toLowerCase();
    const filtered = PAPER_LIST.filter((p) =>
      p.title.toLowerCase().includes(q) ||
      p.summary.includes(text) ||
      (p.keywords || []).some((k) => k.toLowerCase().includes(q))
    ).map((p) => p.id);
    setResultIds(filtered.length ? filtered : PAPER_LIST.map((p) => p.id));
    setTimeout(() => {
      setMessages((m) => [...m, { role: 'bot', text: mockWorkspaceReply(text) }]);
    }, 400);
    message.info('已更新检索结果');
  };

  return (
    <div className="page-workspace">
      <Card title="智能搜索 / 多轮问答" className="section-card">
        <ChatBox
          messages={messages}
          onSend={handleSearch}
          placeholder="输入关键词搜索或提问，支持追问..."
          minHeight={140}
        />
        <Text type="secondary" style={{ fontSize: 12 }}>搜索或提问后移除推荐论文，显示检索结果列表</Text>
      </Card>

      {!workspaceSearched ? (
        <>
          <Card title="每日 ArXiv 精选" className="section-card">
            <Row gutter={[16, 16]}>
              {DAILY.map((id) => (
                <Col xs={24} sm={12} lg={8} key={id}><PaperCard paperId={id} /></Col>
              ))}
            </Row>
          </Card>
          <Card title="基于画像推荐的论文" className="section-card">
            <Row gutter={[16, 16]}>
              {RECOMMENDED.map((id) => (
                <Col xs={24} sm={12} lg={8} key={id}><PaperCard paperId={id} /></Col>
              ))}
            </Row>
          </Card>
        </>
      ) : (
        <Card title={`检索结果${lastSearchQuery ? ` · 「${lastSearchQuery}」` : ''}`} className="section-card">
          <Row gutter={[16, 16]}>
            {resultIds.map((id) => (
              <Col xs={24} sm={12} lg={8} key={id}><PaperCard paperId={id} /></Col>
            ))}
          </Row>
        </Card>
      )}
    </div>
  );
}
