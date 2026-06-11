/**
 * @file        LineToolCard.tsx
 * @description LINE 工具市集卡片元件
 * @lastUpdate  2026-04-19 03:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Card, Row, Col, Typography, Badge, Space } from 'antd';
import { MessageOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

interface LineToolCardProps {
  officialAccountCount: number;
  channelCount: number;
  connectionStatus: 'connected' | 'disconnected' | 'error';
}

export default function LineToolCard({
  officialAccountCount,
  channelCount,
  connectionStatus,
}: LineToolCardProps) {
  const statusMap = {
    connected: { status: 'success' as const, text: '已連接' },
    disconnected: { status: 'default' as const, text: '未連接' },
    error: { status: 'error' as const, text: '連接錯誤' },
  };

  const { status, text } = statusMap[connectionStatus];

  return (
    <Card hoverable style={{ marginBottom: 24 }}>
      <Row gutter={16} align="middle">
        <Col span={4}>
          <img
            src="/line-logo.png"
            alt="LINE"
            style={{ height: 40, objectFit: 'contain' }}
          />
        </Col>
        <Col span={12}>
          <Title level={5} style={{ margin: 0 }}>
            LINE 官方帳號
          </Title>
          <Text type="secondary">
            官方帳號：{officialAccountCount} 個 | Channels：{channelCount} 個
          </Text>
        </Col>
        <Col span={8} style={{ textAlign: 'right' }}>
          <Space direction="vertical" align="end">
            <Badge status={status} text={text} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              <MessageOutlined style={{ marginRight: 4 }} />
              智能機器人平台
            </Text>
          </Space>
        </Col>
      </Row>
    </Card>
  );
}
