/**
 * DEBUG ONLY: manual crawl-scheduler trigger.
 * Delete this file + README in this folder, and the SettingsPage import, to remove.
 */
import { useState } from 'react';
import { Alert, Button, Card, Space, Typography, message } from 'antd';
import { BugOutlined } from '@ant-design/icons';
import apiClient from '../services/apiClient';
import { USE_MOCK } from '../services/runtimeConfig';

export const CRAWL_DEBUG_UI_ENABLED =
  String(import.meta.env.VITE_ENABLE_CRAWL_DEBUG ?? 'false').toLowerCase() === 'true';

async function runCrawlDebugTick(maxPerSubscription = 3) {
  return apiClient.post('/debug/crawl/run', {}, {
    params: { max_per_subscription: maxPerSubscription },
    timeout: 180000,
  });
}

export default function CrawlSchedulerDebugCard() {
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState('');

  if (!CRAWL_DEBUG_UI_ENABLED) {
    return null;
  }

  const onRun = async () => {
    if (USE_MOCK) {
      message.info('Mock 模式下跳过全站抓取调试');
      return;
    }
    setLoading(true);
    try {
      const data = await runCrawlDebugTick(3);
      const stats = data?.stats || {};
      const errHint = stats.errors
        ? ` errors=${stats.errors}${stats.error_samples?.length ? ` (${stats.error_samples[0]})` : ''}`
        : '';
      const text = `users=${stats.users ?? '-'} fetched=${stats.fetched ?? '-'} created=${stats.created ?? '-'}${errHint}`;
      setLastResult(text);
      if (stats.errors > 0 && !(stats.created > 0)) {
        message.warning(`抓取结束但 arXiv 请求失败：${text}`);
      } else {
        message.success(`调试抓取完成：${text}`);
      }
    } catch (error) {
      message.error(error.message || '调试抓取失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      size="small"
      title={
        <Space>
          <BugOutlined />
          <span>调试 · 定时抓取</span>
        </Space>
      }
      style={{ borderColor: '#faad14', marginTop: 16 }}
    >
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 12 }}
        message="临时调试入口（便于删除）"
        description="调用与后台调度器相同的 sync_all_users。删除 frontend/src/debug/ 并关闭 VITE_ENABLE_CRAWL_DEBUG 即可移除。"
      />
      <Button type="dashed" danger loading={loading} onClick={onRun}>
        立即执行一轮全站订阅抓取
      </Button>
      {lastResult ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          上次结果：{lastResult}
        </Typography.Paragraph>
      ) : null}
    </Card>
  );
}
