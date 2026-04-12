/**
 * @file        資料字典意圖 Modal（ArangoDB intent_catalog）
 * @description 展示 DataAgent 意圖目錄，含統計卡片、搜尋篩選、同步到 Qdrant、Detail Drawer
 * @lastUpdate  2026-04-11 22:24:32
 * @author      Daniel Chung
 * @version     2.0.0
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Modal, Table, Tag, Input, Select, Button, Card, Row, Col, Statistic, Space, Typography, App, theme,
} from 'antd';
import { CloudSyncOutlined, ReloadOutlined, DatabaseOutlined, EyeOutlined } from '@ant-design/icons';
import { intentCatalogApi } from '../../services/intentCatalogApi';
import type { IntentCatalogEntry } from '../../services/intentCatalogApi';
import IntentDetailDrawer from './IntentDetailDrawer';

const { Text } = Typography;

interface SchemaIntentModalProps {
  open: boolean;
  onClose: () => void;
}

const INTENT_TYPE_OPTIONS = [
  { label: '全部類型', value: '' },
  ...['aggregate', 'filter', 'join', 'time_series', 'ranking', 'comparison'].map(x => ({ label: x, value: x })),
];

const GROUP_OPTIONS = [
  { label: '全部群組', value: '' },
  ...Array.from('ABCDEF').map(x => ({ label: x, value: x })),
];

const STRATEGY_OPTIONS = [
  { label: '全部策略', value: '' },
  { label: 'template', value: 'template' },
  { label: 'small_llm', value: 'small_llm' },
  { label: 'large_llm', value: 'large_llm' },
];

export default function SchemaIntentModal({ open, onClose }: SchemaIntentModalProps) {
  const { message } = App.useApp();
  const { token } = theme.useToken();

  const [intents, setIntents] = useState<IntentCatalogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [search, setSearch] = useState('');
  const [intentType, setIntentType] = useState('');
  const [group, setGroup] = useState('');
  const [strategy, setStrategy] = useState('');

  const [isSyncing, setIsSyncing] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [currentIntent, setCurrentIntent] = useState<IntentCatalogEntry | null>(null);

  const loadIntents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await intentCatalogApi.list({
        agent_scope: 'data_agent',
        page,
        page_size: pageSize,
        search: search || undefined,
        intent_type: intentType || undefined,
        group: group || undefined,
        generation_strategy: strategy || undefined,
      });
      if (res.data.code === 0) {
        setIntents(res.data.data.records || []);
        setTotal(res.data.data.total || 0);
      } else {
        message.error('載入意圖失敗');
      }
    } catch {
      message.error('載入意圖失敗');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, intentType, group, strategy, message]);

  useEffect(() => {
    if (open) loadIntents();
  }, [open, loadIntents]);

  const handleSyncQdrant = async () => {
    setIsSyncing(true);
    try {
      const res = await intentCatalogApi.syncToQdrant({ agent_scope: 'data_agent' });
      if (res.data.status === 'ok') {
        message.success(`同步成功，共 ${res.data.synced_count} 筆`);
      } else {
        message.error('同步失敗');
      }
    } catch {
      message.error('同步發生錯誤');
    } finally {
      setIsSyncing(false);
    }
  };

  const columns = [
    { title: 'Intent ID', dataIndex: 'intent_id', key: 'intent_id', width: 160, render: (t: string) => <Text code>{t}</Text> },
    {
      title: '目標表單', dataIndex: 'table_key', key: 'table_key', width: 110,
      render: (t: string) => t ? <Tag color="blue">{t}</Tag> : '-',
    },
    { title: '動作', dataIndex: 'action', key: 'action', width: 80, render: (t: string) => t || '-' },
    { title: 'Domain Intent', dataIndex: 'bpa_domain_intent', key: 'bpa_domain_intent', width: 160, ellipsis: true },
    { title: '說明', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '類型', dataIndex: 'intent_type', key: 'intent_type', width: 100 },
    { title: '群組', dataIndex: 'group', key: 'group', width: 70 },
    { title: '策略', dataIndex: 'generation_strategy', key: 'generation_strategy', width: 100 },
    {
      title: '表', dataIndex: 'tables', key: 'tables', width: 160,
      render: (tables: string[]) => Array.isArray(tables) ? tables.map(t => <Tag key={t}>{t}</Tag>) : '-',
    },
    {
      title: '範例', key: 'examples', width: 100,
      render: (_: unknown, record: IntentCatalogEntry) => {
        const nlCount = record.nl_examples?.length || 0;
        const sqlCount = Array.isArray(record.example_sqls) ? record.example_sqls.length : 0;
        return <Text>{nlCount} NL / {sqlCount} SQL</Text>;
      },
    },
    {
      title: '', key: 'action', width: 50,
      render: (_: unknown, record: IntentCatalogEntry) => (
        <Button type="text" icon={<EyeOutlined />} onClick={() => { setCurrentIntent(record); setDetailOpen(true); }} />
      ),
    },
  ];

  const templateCount = intents.filter(i => i.generation_strategy === 'template').length;
  const smallLlmCount = intents.filter(i => i.generation_strategy === 'small_llm').length;
  const largeLlmCount = intents.filter(i => i.generation_strategy === 'large_llm').length;

  return (
    <>
      <Modal
        title={`DataAgent 資料字典意圖 (${total})`}
        open={open}
        onCancel={onClose}
        footer={null}
        width="92vw"
        styles={{ body: { height: '80vh', display: 'flex', flexDirection: 'column', overflow: 'auto', padding: '12px 16px' } }}
        destroyOnHidden
      >
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col span={6}>
            <Card size="small"><Statistic title="總意圖數" value={total} prefix={<DatabaseOutlined />} /></Card>
          </Col>
          <Col span={6}>
            <Card size="small"><Statistic title="模板策略" value={templateCount} styles={{ content: { color: token.colorSuccess } }} /></Card>
          </Col>
          <Col span={6}>
            <Card size="small"><Statistic title="小型LLM策略" value={smallLlmCount} styles={{ content: { color: token.colorInfo } }} /></Card>
          </Col>
          <Col span={6}>
            <Card size="small"><Statistic title="大型LLM策略" value={largeLlmCount} styles={{ content: { color: token.colorPrimary } }} /></Card>
          </Col>
        </Row>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <Space>
            <Input.Search placeholder="搜尋" onSearch={v => { setSearch(v); setPage(1); }} style={{ width: 160 }} allowClear />
            <Select value={intentType} onChange={v => { setIntentType(v); setPage(1); }} style={{ width: 120 }} options={INTENT_TYPE_OPTIONS} />
            <Select value={group} onChange={v => { setGroup(v); setPage(1); }} style={{ width: 100 }} options={GROUP_OPTIONS} />
            <Select value={strategy} onChange={v => { setStrategy(v); setPage(1); }} style={{ width: 120 }} options={STRATEGY_OPTIONS} />
            <Button icon={<ReloadOutlined />} onClick={loadIntents}>重新整理</Button>
          </Space>
          <Button icon={<CloudSyncOutlined />} onClick={handleSyncQdrant} loading={isSyncing}>同步到 Qdrant</Button>
        </div>

        <Table
          columns={columns}
          dataSource={intents}
          rowKey="intent_id"
          loading={loading}
          size="small"
          pagination={{
            current: page, pageSize, total, showSizeChanger: true, showTotal: t => `共 ${t} 條`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          scroll={{ y: 'calc(80vh - 280px)' }}
        />
      </Modal>

      <IntentDetailDrawer open={detailOpen} onClose={() => setDetailOpen(false)} intent={currentIntent} />
    </>
  );
}
