/**
 * @file        意圖詳細資訊 Drawer（只讀）
 * @description 展示 IntentCatalogEntry 的基本資訊、NL Examples、SQL Template
 * @lastUpdate  2026-04-11 22:24:32
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { Button, Card, Descriptions, Drawer, Tabs, Tag, Typography, App, theme } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import type { IntentCatalogEntry } from '../../services/intentCatalogApi';

const { Text } = Typography;

interface IntentDetailDrawerProps {
  open: boolean;
  onClose: () => void;
  intent: IntentCatalogEntry | null;
}

export default function IntentDetailDrawer({ open, onClose, intent }: IntentDetailDrawerProps) {
  const { message } = App.useApp();
  const { token } = theme.useToken();

  if (!intent) return null;

  const handleCopySql = () => {
    navigator.clipboard.writeText(intent.sql_template || '');
    message.success('已複製 SQL Template');
  };

  return (
    <Drawer title="DataAgent 意圖詳細資訊" size="large" open={open} onClose={onClose} destroyOnHidden>
      <Tabs defaultActiveKey="1" items={[
        {
          key: '1',
          label: '基本資訊',
          children: (
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="Intent ID"><Text code>{intent.intent_id}</Text></Descriptions.Item>
              <Descriptions.Item label="Domain Intent">{intent.bpa_domain_intent || '-'}</Descriptions.Item>
              <Descriptions.Item label="說明">{intent.description}</Descriptions.Item>
              <Descriptions.Item label="查詢類型"><Tag>{intent.intent_type || '-'}</Tag></Descriptions.Item>
              <Descriptions.Item label="群組"><Tag>{intent.group || '-'}</Tag></Descriptions.Item>
              <Descriptions.Item label="生成策略"><Tag>{intent.generation_strategy || '-'}</Tag></Descriptions.Item>
              <Descriptions.Item label="Is Template">{intent.generation_strategy === 'template' ? 'Yes' : 'No'}</Descriptions.Item>
              <Descriptions.Item label="關聯表">
                {Array.isArray(intent.tables) ? intent.tables.map(t => <Tag key={t}>{t}</Tag>) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="核心欄位">
                {Array.isArray(intent.core_fields) ? intent.core_fields.map(f => <Tag key={f}>{f}</Tag>) : '-'}
              </Descriptions.Item>
            </Descriptions>
          ),
        },
        {
          key: '2',
          label: 'NL Examples',
          children: (
            <Card size="small">
              <ol style={{ paddingLeft: 20, margin: 0 }}>
                {intent.nl_examples?.length ? intent.nl_examples.map((ex, i) => {
                  const sqls = Array.isArray(intent.example_sqls) ? intent.example_sqls : [];
                  return (
                    <li key={i} style={{ marginBottom: 16 }}>
                      <Text strong>{ex}</Text>
                      {sqls[i] && (
                        <pre style={{ background: token.colorInfoBg, padding: 8, borderRadius: 4, marginTop: 4 }}>
                          {String(sqls[i])}
                        </pre>
                      )}
                    </li>
                  );
                }) : <li>無範例</li>}
              </ol>
            </Card>
          ),
        },
        {
          key: '3',
          label: 'SQL Template',
          children: (
            <Card size="small" extra={
              <Button type="text" icon={<CopyOutlined />} onClick={handleCopySql}>複製</Button>
            }>
              <pre style={{ margin: 0 }}>{intent.sql_template || '無'}</pre>
            </Card>
          ),
        },
      ]} />
    </Drawer>
  );
}
