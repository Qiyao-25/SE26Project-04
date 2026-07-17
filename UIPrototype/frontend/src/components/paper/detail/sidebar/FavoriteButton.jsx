import { useEffect, useState } from 'react';
import { Button, message } from 'antd';
import { StarFilled, StarOutlined } from '@ant-design/icons';
import { useApp } from '../../../../context/AppContext';
import { isPersistedPaperId, listActions, setFavorite } from '../../../../services/learningService';

export default function FavoriteButton({ paperId, block = false, size }) {
  const { userId } = useApp();
  const persist = isPersistedPaperId(paperId);
  const [favorite, setFavoriteState] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!persist) return undefined;
    listActions({ userId, paperId, actionType: 'favorite' })
      .then((actions) => {
        if (!cancelled) setFavoriteState(actions.length > 0);
      })
      .catch(() => {
        if (!cancelled) message.error('收藏状态加载失败');
      });
    return () => { cancelled = true; };
  }, [paperId, persist, userId]);

  const toggle = async (event) => {
    event.stopPropagation();
    if (!persist) {
      message.warning('当前论文尚未入库，无法持久化收藏');
      return;
    }
    const next = !favorite;
    setLoading(true);
    try {
      await setFavorite({ userId, paperId, favorite: next });
      setFavoriteState(next);
      message.success(next ? '已加入收藏' : '已取消收藏');
    } catch (error) {
      message.error(error.message || '收藏操作失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      block={block}
      size={size}
      loading={loading}
      icon={favorite ? <StarFilled style={{ color: '#f59e0b' }} /> : <StarOutlined />}
      onClick={toggle}
    >
      {favorite ? '已收藏' : '收藏'}
    </Button>
  );
}
