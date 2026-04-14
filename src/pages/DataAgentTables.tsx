/**
 * @file        Data Agent 表管理頁面
 * @description da_tables / da_intents 意圖管理
 * @lastUpdate  2026-04-13 12:00:00
 * @author      Daniel Chung
 * @version     2.0.0
 */

import { useState, useEffect } from 'react';
import { Card, Table, Button, Tag, Space, Typography, Select, Input, Drawer, App, Statistic, Row, Col, Form, InputNumber, Switch } from 'antd';
import { EyeOutlined, ReloadOutlined, CloudSyncOutlined, DatabaseOutlined, SettingOutlined, RightOutlined, DownOutlined, TableOutlined } from '@ant-design/icons';
import { daTablesApi, daExpressionsApi, DaTable } from '../services/daTablesApi';
import { paramsApi } from '../services/api';
import { intentCatalogApi } from '../services/intentCatalogApi';
import DataAgentTableDetail from './DataAgentTableDetail';

const { Title } = Typography;

interface Props {
  fillHeight?: boolean;
}

export default function DataAgentTables({ fillHeight }: Props) {
  const { message } = App.useApp();

  const [tables, setTables] = useState<DaTable[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState<string>();

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [settingsForm] = Form.useForm();
  const [expandedRowKeys, setExpandedRowKeys] = useState<readonly React.Key[]>([]);

  const fetchTables = async () => {
    setLoading(true);
    try {
      const res = await daTablesApi.list({ page, page_size: pageSize, search, domain: domainFilter });
      setTables(res.data.data.records || []);
      setTotal(res.data.data.total || 0);
    } catch (err: unknown) {
      message.error('載入失敗');
    } finally {
      setLoading(false);
    }
  };

  const fetchModels = async () => {
    try {
      const res = await intentCatalogApi.listModels('data_agent');
      setModels(res.data?.models || []);
    } catch (err: unknown) { }
  };

  const fetchSettings = async () => {
    try {
      const res = await paramsApi.list();
      const params = res.data?.data || [];
      const getVal = (k: string) => params.find(p => p.param_key === k)?.param_value;
      settingsForm.setFieldsValue({
        embedding_model: getVal('da.embedding_model'),
        embedding_dimension: Number(getVal('da.embedding_dimension')) || 1024,
        small_llm_model: getVal('da.small_llm_model'),
        large_llm_model: getVal('da.large_llm_model')
      });
    } catch (err: unknown) {
      message.error('獲取設定失敗');
    }
  };

  useEffect(() => {
    fetchTables();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, search, domainFilter]);

  const handleSyncQdrant = async () => {
    try {
      const res = await daExpressionsApi.syncToQdrant();
      message.success(`同步到Qdrant 成功（${res.data.synced_count} 筆）`);
    } catch (err: unknown) {
      message.error('同步失敗');
    }
  };

  const handleToggleStatus = async (key: string, checked: boolean) => {
    try {
      await daTablesApi.update(key, { status: checked ? 'enabled' : 'disabled' });
      message.success(checked ? '已啟用' : '已停用');
      fetchTables();
    } catch (err: unknown) {
      message.error('狀態更新失敗');
    }
  };

  const openSettings = () => {
    fetchModels();
    fetchSettings();
    setSettingsOpen(true);
  };

  const saveSettings = async () => {
    try {
      const vals = await settingsForm.validateFields();
      await paramsApi.update('da.embedding_model', vals.embedding_model);
      await paramsApi.update('da.embedding_dimension', String(vals.embedding_dimension));
      await paramsApi.update('da.small_llm_model', vals.small_llm_model);
      await paramsApi.update('da.large_llm_model', vals.large_llm_model);
      message.success('設定已儲存');
      setSettingsOpen(false);
    } catch (err: unknown) {
      message.error('儲存設定失敗');
    }
  };

  const uniqueDomains = new Set(tables.map(t => t.domain)).size;
  const enabledCount = tables.filter(t => t.status === 'enabled').length;

  const cols = [
    { title: 'Key', dataIndex: '_key', key: '_key' },
    { title: '名稱', dataIndex: 'display_name', key: 'display_name' },
    { title: '領域 (Domain)', dataIndex: 'domain', key: 'domain', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: '欄位數', key: 'fields', render: (_: unknown, r: DaTable) => r.fields?.length || 0 },
    { title: '關聯數', key: 'rels', render: (_: unknown, r: DaTable) => r.relationships?.length || 0 },
    {
      title: '能力',
      key: 'caps',
      render: (_: unknown, r: DaTable) => (
        <Space size={[0, 4]} wrap>
          {r.capabilities?.simple_filter && <Tag color="green">Filter</Tag>}
          {r.capabilities?.aggregate && <Tag color="orange">Agg</Tag>}
          {r.capabilities?.time_series && <Tag color="purple">Time</Tag>}
          {r.capabilities?.cross_table && <Tag color="cyan">Cross</Tag>}
        </Space>
      )
    },
    { title: '狀態', dataIndex: 'status', key: 'status', render: (v: string, r: DaTable) => <Switch checked={v === 'enabled'} checkedChildren="啟" unCheckedChildren="停" onChange={(checked) => handleToggleStatus(r._key, checked)} size="small" /> }
  ];

  return (
    <div style={{ padding: 24, height: fillHeight ? '85vh' : 'auto', display: 'flex', flexDirection: 'column', minHeight: fillHeight ? 0 : 'auto', flex: fillHeight ? undefined : 1 }}>
      <Row gutter={[16, 16]} style={{ marginBottom: 16, flexShrink: 0 }}>
        <Col span={8}><Card size="small"><Statistic title="總表數" value={total} prefix={<DatabaseOutlined />} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="當前頁領域數" value={uniqueDomains} prefix={<TableOutlined />} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="當前頁啟用數" value={enabledCount} prefix={<EyeOutlined />} /></Card></Col>
      </Row>

      <Card
        title={<Title level={4} style={{ margin: 0 }}>Data Agent 意圖表</Title>}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
        styles={{ body: { flex: 1, overflow: 'auto', padding: 0, display: 'flex', flexDirection: 'column' } }}
        extra={
          <Space>
            <Input.Search placeholder="搜尋..." allowClear onSearch={setSearch} style={{ width: 200 }} />
            <Select allowClear placeholder="過濾領域" style={{ width: 120 }} onChange={setDomainFilter} options={Array.from(new Set(tables.map(t => t.domain))).map(d => ({ label: d, value: d }))} />
            <Button icon={<ReloadOutlined />} onClick={fetchTables}>重新整理</Button>
            <Button icon={<CloudSyncOutlined />} onClick={handleSyncQdrant}>同步到Qdrant</Button>
            <Button icon={<SettingOutlined />} onClick={openSettings}>設定</Button>
          </Space>
        }
      >
        <Table
          columns={cols}
          dataSource={tables}
          rowKey="_key"
          loading={loading}
          style={{ flex: 1, minHeight: 0 }}
          scroll={{ y: 'calc(95vh - 300px)' }}
          pagination={{ current: page, pageSize, total, onChange: (p, s) => { setPage(p); setPageSize(s); } }}
          expandable={{
            expandedRowRender: (record) => <DataAgentTableDetail tableData={record} />,
            expandedRowKeys,
            onExpand: (expanded, record) => setExpandedRowKeys(expanded ? [...expandedRowKeys, record._key] : expandedRowKeys.filter(k => k !== record._key)),
            expandIcon: ({ expanded, onExpand, record }) => expanded ? <DownOutlined onClick={e => onExpand(record, e)} style={{ marginRight: 8, cursor: 'pointer' }} /> : <RightOutlined onClick={e => onExpand(record, e)} style={{ marginRight: 8, cursor: 'pointer' }} />
          }}
        />
      </Card>

      <Drawer title="Data Agent 設定" open={settingsOpen} onClose={() => setSettingsOpen(false)} extra={<Button type="primary" onClick={saveSettings}>儲存</Button>}>
        <Form form={settingsForm} layout="vertical">
          <Form.Item name="embedding_model" label="Embedding Model"><Select options={models.map(m => ({ label: m, value: m }))} /></Form.Item>
          <Form.Item name="embedding_dimension" label="Embedding Dimension"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="small_llm_model" label="Small LLM Model"><Select options={models.map(m => ({ label: m, value: m }))} /></Form.Item>
          <Form.Item name="large_llm_model" label="Large LLM Model"><Select options={models.map(m => ({ label: m, value: m }))} /></Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}