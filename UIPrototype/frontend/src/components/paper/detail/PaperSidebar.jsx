import { useEffect, useState } from 'react';
import { Card, Tabs, message } from 'antd';
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
    content: `当前问答范围：《${paperTitle}》。可询问核心创新、方法、实验结果或局限性。`,
    status: 'success',
    citations: []
  };
}

export default function PaperSidebar({ paperId, paper }) {
  const [activeKey, setActiveKey] = useState('all');
  const [conversationId, setConversationId] = useState(null);
  const [qaStatus, setQaStatus] = useState('idle');
  const [messages, setMessages] = useState(() => [createWelcomeMessage(paper.title)]);

  useEffect(() => {
    setActiveKey('all');
    setConversationId(null);
    setQaStatus('idle');
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
        content: '正在基于论文内容生成回答...',
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
        history
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
          citations: data.citations || []
        }
      ]);
      setQaStatus('success');
      setActiveKey('qa');
    } catch (error) {
      setMessages((current) => [
        ...current.filter((item) => item.messageId !== generatingMessageId),
        {
          messageId: `paper-qa-error-${Date.now()}`,
          role: 'assistant',
          content: error.message?.includes('没有可核验') || error.message?.includes('尚未完成解析') || error.message?.includes('依据不足')
            ? '当前论文还没有可用的原文依据，暂时无法进行带出处的问答。请先在详情页完成解析，待状态变为「可问答」后再试。'
            : (error.message || '回答生成失败。'),
          status: 'failed',
          errorMessage: error.message || '未知错误',
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
        />
      )
    },
    {
      key: 'assist',
      label: '辅助',
      children: <SidebarAssistPanel paper={paper} />
    },
    {
      key: 'notes',
      label: '笔记',
      children: <SidebarNotesPanel paperId={paperId} />
    },
    {
      key: 'compare',
      label: '对比',
      children: <SidebarComparePanel paperId={paperId} paper={paper} />
    }
  ];

  return (
    <Card className="section-card paper-sidebar-card">
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
