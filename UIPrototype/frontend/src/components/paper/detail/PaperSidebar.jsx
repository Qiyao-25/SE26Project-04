import { useEffect, useState } from 'react';
import { Button, Card, Tabs, message } from 'antd';
import { MenuFoldOutlined } from '@ant-design/icons';
import { askPaper } from '../../../services/qaService';
import SidebarAllPanel from './sidebar/SidebarAllPanel';
import SidebarInfoPanel from './sidebar/SidebarInfoPanel';
import SidebarQaPanel from './sidebar/SidebarQaPanel';
import SidebarAssistPanel from './sidebar/SidebarAssistPanel';
import SidebarNotesPanel from './sidebar/SidebarNotesPanel';
import SidebarComparePanel from './sidebar/SidebarComparePanel';

function createWelcomeMessage(paperTitle) {
  return {
    messageId: 'paper-qa-welcome',
    role: 'assistant',
    content: `《${paperTitle}》`,
    status: 'success',
    citations: []
  };
}

export default function PaperSidebar({ paperId, paper, onCollapse }) {
  const [activeKey, setActiveKey] = useState('all');
  const [conversationId, setConversationId] = useState(null);
  const [qaStatus, setQaStatus] = useState('idle');
  const [qaScope, setQaScope] = useState('both');
  const [messages, setMessages] = useState(() => [createWelcomeMessage(paper.title)]);

  useEffect(() => {
    setActiveKey('all');
    setConversationId(null);
    setQaStatus('idle');
    setQaScope('both');
    setMessages([createWelcomeMessage(paper.title)]);
  }, [paperId, paper.title]);

  const goTab = (key) => {
    setActiveKey(key);
    const labels = {
      all: '全部',
      info: '信息',
      qa: '问答',
      assist: '辅助',
      notes: '笔记',
      compare: '对比阅读'
    };
    message.info(`已展开${labels[key] || ''}`);
  };

  const handleQaSend = async (question) => {
    if (qaStatus === 'generating') return;

    const timestamp = Date.now();
    const generatingMessageId = `paper-qa-generating-${timestamp}`;
    const userMessage = {
      messageId: `paper-qa-user-${timestamp}`,
      role: 'user',
      content: question,
      status: 'success',
      createdAt: new Date().toISOString(),
      citations: []
    };

    const history = [...messages, userMessage]
      .filter((item) => item.status !== 'generating')
      .map(({ role, content }) => ({ role, content }));

    setMessages((current) => [
      ...current,
      userMessage,
      {
        messageId: generatingMessageId,
        role: 'assistant',
        content: '生成中…',
        status: 'generating',
        citations: []
      }
    ]);
    setQaStatus('generating');

    try {
      const data = await askPaper({
        conversationId,
        paperId,
        question,
        history,
        scope: qaScope
      });

      setConversationId(data.conversationId);
      setMessages((current) => [
        ...current.filter((item) => item.messageId !== generatingMessageId),
        {
          messageId: data.messageId,
          role: 'assistant',
          content: data.answer,
          status: 'success',
          createdAt: data.createdAt,
          citations: data.citations || [],
          answerMode: data.answerMode || 'agent'
        }
      ]);
      setQaStatus('success');
      setActiveKey('qa');
    } catch (error) {
      const raw = error.message || '';
      setMessages((current) => [
        ...current.filter((item) => item.messageId !== generatingMessageId),
        {
          messageId: `paper-qa-error-${Date.now()}`,
          role: 'assistant',
          content: raw || '回答生成失败',
          status: 'failed',
          errorMessage: raw || '未知错误',
          citations: []
        }
      ]);
      setQaStatus('failed');
      setActiveKey('qa');
    }
  };

  const items = [
    {
      key: 'all',
      label: '全部',
      children: (
        <SidebarAllPanel
          paper={paper}
          paperId={paperId}
          onGoTab={goTab}
          messages={messages}
          onSend={handleQaSend}
          qaStatus={qaStatus}
        />
      )
    },
    {
      key: 'info',
      label: '信息',
      children: <SidebarInfoPanel paper={paper} paperId={paperId} />
    },
    {
      key: 'qa',
      label: '问答',
      children: (
        <SidebarQaPanel
          messages={messages}
          onSend={handleQaSend}
          qaStatus={qaStatus}
          scope={qaScope}
          onScopeChange={setQaScope}
        />
      )
    },
    {
      key: 'assist',
      label: '辅助',
      children: <SidebarAssistPanel paper={paper} paperId={paperId} />
    },
    {
      key: 'notes',
      label: '笔记',
      forceRender: true,
      children: <SidebarNotesPanel paperId={paperId} />
    },
    {
      key: 'compare',
      label: '对比',
      children: <SidebarComparePanel paperId={paperId} paper={paper} />
    }
  ];

  return (
    <Card
      className="section-card paper-sidebar-card"
      size="small"
      title="论文侧栏"
      extra={onCollapse ? (
        <Button
          type="text"
          size="small"
          icon={<MenuFoldOutlined />}
          onClick={onCollapse}
          aria-label="收起论文详情侧栏"
        >
          收起侧栏
        </Button>
      ) : null}
    >
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        size="small"
        items={items}
        className="sidebar-tabs"
      />
    </Card>
  );
}
