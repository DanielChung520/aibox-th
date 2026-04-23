/**
 * @file        PlatformBotPage.tsx
 * @description 通信平台 Bot 設定頁面框架（通用模板）
 * @lastUpdate  2026-04-23 15:30:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Typography, Card, Row, Col, Empty } from 'antd';
import { useParams } from 'react-router-dom';


const { Title, Text } = Typography;

const PLATFORM_META: Record<string, {
  label: string;
  logo: string;
  description: string;
  docs: string;
}> = {
  whatsapp: {
    label: 'WhatsApp Bot',
    logo: '/whatsapp-logo.png',
    description: 'WhatsApp 官方帳號智能機器人平台，支援多帳號管理與 Bot 發布',
    docs: 'https://developers.facebook.com/docs/whatsapp',
  },
  wecom: {
    label: 'WeCom Bot',
    logo: '/wecom-logo.svg',
    description: '企業微信（WeCom）官方帳號智能機器人平台，支援多帳號管理與 Bot 發布',
    docs: 'https://developer.work.weixin.qq.com/document/path/91716',
  },
  dingtalk: {
    label: 'DingTalk Bot',
    logo: '/dingtalk-logo.png',
    description: '釘釘（DingTalk）官方帳號智能機器人平台，支援多帳號管理與 Bot 發布',
    docs: 'https://open.dingtalk.com/document/org/bots',
  },
  xchat: {
    label: 'XChat Bot',
    logo: '/xchat-logo.svg',
    description: 'XChat 平台官方帳號智能機器人平台，支援多帳號管理與 Bot 發布',
    docs: '',
  },
  slack: {
    label: 'Slack Bot',
    logo: '/slack-logo.png',
    description: 'Slack 官方帳號智能機器人平台，支援多帳號管理與 Bot 發布',
    docs: 'https://api.slack.com/bot-v4',
  },
};

export default function PlatformBotPage() {
  const { platform } = useParams<{ platform: string }>();
  const meta = PLATFORM_META[platform || ''];

  if (!meta) {
    return (
      <div style={{ padding: 24 }}>
        <Empty description="平台不存在" />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <Card hoverable style={{ marginBottom: 24 }}>
        <Row gutter={16} align="middle">
          <Col span={3} style={{ textAlign: 'center' }}>
            <img
              src={meta.logo}
              alt={meta.label}
              style={{ height: 48, objectFit: 'contain' }}
            />
          </Col>
          <Col span={14}>
            <Title level={4} style={{ margin: 0 }}>
              {meta.label}
            </Title>
            <Text type="secondary">{meta.description}</Text>
          </Col>
          <Col span={7} style={{ textAlign: 'right' }}>
            <Text type="warning" style={{ fontSize: 16 }}>🚧 開發中</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              此平台正在整合中，敬請期待
            </Text>
          </Col>
        </Row>
      </Card>

      <Card>
        <Empty
          description={
            <span>
              {meta.label} 平台整合功能正在開發中...
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>
                预计将支持：多帳號管理、Bot 設定、訊息處理、Webhook 整合
              </Text>
            </span>
          }
        />
      </Card>
    </div>
  );
}
