/**
 * @file        ChannelCard.tsx
 * @description LINE Channel 網格卡片元件，僅顯示圖示、名稱、描述
 */

import { Card, Typography } from 'antd';
import { MessageOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useState } from 'react';
import ChatHistoryDrawer from './ChatHistoryDrawer';
import type { LINEChannel } from '../../services/api';
import { resolveChannelIconSrc } from '../../utils/avatarUtils';

const { Text } = Typography;

interface ChannelCardProps {
  channel: LINEChannel;
  onClick: (channel: LINEChannel) => void;
  isSelected?: boolean;
}

export default function ChannelCard({ channel, onClick, isSelected = false }: ChannelCardProps) {
  const [historyVisible, setHistoryVisible] = useState(false);
  const iconSrc = resolveChannelIconSrc(channel.channel_icon);

  return (
    <>
    <Card
      hoverable
      onClick={() => onClick(channel)}
      style={{
        cursor: 'pointer',
        height: 160,
        border: isSelected ? '2px solid #00b900' : undefined,
      }}
      styles={{ body: { height: '100%', display: 'flex', flexDirection: 'column', padding: 16 } }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, overflow: 'hidden' }}>
          <div style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: '#00b90015',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            flexShrink: 0,
          }}>
            {iconSrc ? (
              <img
                src={iconSrc}
                alt={channel.channel_name}
                style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 8 }}
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            ) : (
              <MessageOutlined style={{ fontSize: 24, color: '#00b900' }} />
            )}
          </div>
          <Text strong style={{ fontSize: 15, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {channel.channel_name}
          </Text>
        </div>
        <div onClick={(e) => e.stopPropagation()}>
          <Tooltip title="對話歷史">
            <ClockCircleOutlined
              onClick={() => setHistoryVisible(true)}
              style={{ 
                fontSize: 16, 
                color: 'var(--ant-color-text-secondary, #8c8c8c)',
                padding: 4,
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = '#00b900'; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--ant-color-text-secondary, #8c8c8c)'; }}
            />
          </Tooltip>
        </div>
      </div>

      <Text
        type="secondary"
        style={{ fontSize: 12, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}
      >
        {(channel as any).channel_description || '尚無描述'}
      </Text>
    </Card>
      <ChatHistoryDrawer visible={historyVisible} onClose={() => setHistoryVisible(false)} channel={channel} />
    </>
  );
}
