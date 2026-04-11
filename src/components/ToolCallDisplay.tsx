/**
 * @file        工具調用狀態顯示
 * @description 顯示工具調用的執行狀態、名稱與結果
 * @lastUpdate  2026-04-11 08:54:32
 * @author      AI Agent
 * @version     1.0.0
 */

import { CheckCircleOutlined, CloseCircleOutlined, ToolOutlined } from '@ant-design/icons';
import { Spin, Space, Tag, Typography } from 'antd';
import { useContentTokens } from '../contexts/AppThemeProvider';
import type { ToolCallInfo } from '../stores/chatOrchestrator';

const { Text } = Typography;

interface ToolCallDisplayProps {
  toolCalls: ToolCallInfo[];
}

function getResultPreview(result: unknown): string | null {
  if (result === undefined || result === null) return null;
  if (typeof result === 'string') return result;

  try {
    return JSON.stringify(result);
  } catch {
    return String(result);
  }
}

export default function ToolCallDisplay({ toolCalls }: ToolCallDisplayProps) {
  const contentTokens = useContentTokens();

  if (toolCalls.length === 0) return null;

  return (
    <div style={{ width: '100%', padding: '4px 0' }}>
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        {toolCalls.map((toolCall, idx) => {
          const resultPreview = getResultPreview(toolCall.result);

          return (
            <div
              key={`${toolCall.tool}-${idx}`}
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                background: contentTokens.chatAssistantBubble,
                border: `1px solid ${contentTokens.chatInputBg}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                {toolCall.status === 'executing' ? (
                  <Spin size="small" />
                ) : toolCall.status === 'completed' ? (
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                ) : (
                  <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                )}
                <Tag
                  icon={<ToolOutlined />}
                  color={toolCall.status === 'executing' ? 'processing' : toolCall.status === 'completed' ? 'success' : 'error'}
                  style={{ marginInlineEnd: 0 }}
                >
                  {toolCall.tool}
                </Tag>
                {toolCall.duration !== undefined && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {toolCall.duration}ms
                  </Text>
                )}
              </div>
              {resultPreview && (
                <Text
                  type="secondary"
                  style={{
                    display: 'block',
                    marginTop: 6,
                    fontSize: 12,
                    color: contentTokens.textSecondary,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {resultPreview}
                </Text>
              )}
            </div>
          );
        })}
      </Space>
    </div>
  );
}
