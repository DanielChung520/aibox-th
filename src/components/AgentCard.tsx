/**
 * @file        Agent 卡片組件
 * @description 顯示 Agent 信息卡片，支持收藏、編輯、刪除和對話操作
 * @lastUpdate  2026-03-28 10:02:17
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState } from 'react';
import { Card, Button, Dropdown, Tag, Tooltip, theme } from 'antd';
import { 
  MoreOutlined, 
  EditOutlined, 
  DeleteOutlined, 
  HeartOutlined, 
  HeartFilled,
  MessageOutlined,
} from '@ant-design/icons';
import { iconMap } from '../utils/icons';
import { useContentTokens } from '../contexts/AppThemeProvider';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: 'registering' | 'online' | 'maintenance' | 'deprecated' | 'developing';
  usageCount: number;
  groupKey: string;
}

interface AgentCardProps {
  agent: Agent;
  onEdit?: (agentId: string) => void;
  onDelete?: (agentId: string) => void;
  onChat?: (agentId: string) => void;
  onFavorite?: (agentId: string, isFavorite: boolean) => void;
  isFavorite?: boolean;
  actionLabel?: string;
  actionIcon?: React.ReactNode;
  onAction?: (agentId: string) => void;
  actionDisabled?: boolean;
  actionStyle?: React.CSSProperties;
  showMenu?: boolean;
  onCardClick?: (agentId: string) => void;
}

const statusColors: Record<string, { color: string; text: string }> = {
  registering: { color: 'orange', text: '審查中' },
  online: { color: 'green', text: '在線' },
  maintenance: { color: 'gold', text: '維修中' },
  deprecated: { color: 'red', text: '已作廢' },
  developing: { color: 'blue', text: '開發中' },
};

export default function AgentCard({ 
  agent, 
  onEdit, 
  onDelete, 
  onChat,
  onFavorite, 
  isFavorite: initialIsFavorite = false,
  actionLabel,
  actionIcon,
  onAction,
  actionDisabled,
  actionStyle,
  showMenu = true,
  onCardClick,
}: AgentCardProps) {
  const { token } = theme.useToken();
  const contentTokens = useContentTokens();
  const [isHovered, setIsHovered] = useState(false);
  const [isFavorite, setIsFavorite] = useState(initialIsFavorite);

  const hoverShadow = contentTokens.cardShadowHover || token.boxShadowSecondary;
  const normalShadow = contentTokens.cardShadow || token.boxShadow;
  const iconBgColor = `${contentTokens.colorPrimary}1a`;
  const iconColor = contentTokens.colorPrimary;
  const descColor = contentTokens.textSecondary;
  const metaColor = contentTokens.textSecondary;

  const statusInfo = statusColors[agent.status] || { color: 'default', text: '未知' };
  const isIconUrl = agent.icon?.startsWith('http') || agent.icon?.startsWith('/');
  const IconComponent = !isIconUrl && agent.icon ? iconMap[agent.icon] : null;

  const menuItems = [
    {
      key: 'edit',
      icon: <EditOutlined />,
      label: '編輯',
      onClick: (e: any) => {
        e.domEvent?.stopPropagation();
        onEdit?.(agent.id);
      },
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '刪除',
      danger: true,
      onClick: (e: any) => {
        e.domEvent?.stopPropagation();
        onDelete?.(agent.id);
      },
    },
  ];

  const isDisabled = agent.status === 'registering' || agent.status === 'deprecated';

  return (
    <Card
      hoverable
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{ 
        opacity: isDisabled ? 0.6 : 1,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.3s ease',
        transform: isHovered && !isDisabled ? 'translateY(-4px)' : 'none',
        boxShadow: isHovered && !isDisabled ? hoverShadow : normalShadow,
        border: isHovered ? `1px solid ${contentTokens.colorPrimary}80` : undefined,
        width: '100%',
      }}
      onClick={() => {
        if (isDisabled || actionDisabled) return;
        onCardClick?.(agent.id);
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 96,
            height: 96,
            borderRadius: 8,
            background: iconBgColor,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 48,
            overflow: 'hidden',
          }}>
            {isIconUrl ? (
              <img
                src={agent.icon}
                alt={agent.name}
                style={{ width: 48, height: 48, objectFit: 'contain' }}
              />
            ) : IconComponent ? (
              <IconComponent style={{ color: iconColor }} />
            ) : (
              '🤖'
            )}
          </div>
          <div>
            <div style={{ 
              fontWeight: 600, 
              fontSize: 16, 
              marginBottom: 4,
              wordBreak: 'break-word',
              overflowWrap: 'break-word',
            }}>
              {agent.name}
            </div>
            <Tag color={statusInfo.color}>{statusInfo.text}</Tag>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: 8 }}>
          <Tooltip title={isFavorite ? '取消收藏' : '加入收藏'}>
            <Button 
              type="text" 
              size="small"
              icon={isFavorite ? <HeartFilled style={{ color: contentTokens.colorError }} /> : <HeartOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                const newState = !isFavorite;
                setIsFavorite(newState);
                onFavorite?.(agent.id, newState);
              }}
            />
          </Tooltip>
          
          {showMenu && (
            <Dropdown 
              menu={{ items: menuItems }} 
              trigger={['click']}
              placement="bottomRight"
            >
              <Button 
                type="text" 
                size="small"
                icon={<MoreOutlined />}
                onClick={(e) => e.stopPropagation()}
              />
            </Dropdown>
          )}
        </div>
      </div>

      {/* 卡片內容 */}
      <div style={{ 
        marginBottom: 16, 
        color: descColor, 
        minHeight: 44,
        wordBreak: 'break-word',
        overflowWrap: 'break-word',
        lineHeight: 1.5,
      }}>
        {agent.description || '暂无描述'}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ color: metaColor, fontSize: 12 }}>
          使用次數: {agent.usageCount}
        </div>
        <Button 
          type={isHovered && !actionDisabled ? 'primary' : 'default'}
          size="small"
          icon={actionIcon ?? <MessageOutlined />}
          disabled={isDisabled || actionDisabled}
          style={actionStyle}
          onClick={(e) => {
            e.stopPropagation();
            if (!isDisabled && !actionDisabled) (onAction || onChat)?.(agent.id);
          }}
        >
          {actionLabel ?? '對話'}
        </Button>
      </div>
    </Card>
  );
}
