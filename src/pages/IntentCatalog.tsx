/**
 * @file        統一意圖目錄管理頁面
 * @description 支援 TopOrchestrator / DataAgent 分頁切換的意圖 CRUD 管理
 * @lastUpdate  2026-04-13 05:31:39
 * @author      Daniel Chung
 * @version     3.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Tag, Space, Typography, Descriptions, Select, Input,
  Drawer, Tabs, App, Statistic, Row, Col, theme, Modal, Form, InputNumber, Divider, Alert
} from 'antd';
import {
  EyeOutlined, DeleteOutlined, ReloadOutlined, EditOutlined, PlusOutlined,
  CloudSyncOutlined, AimOutlined, SettingOutlined
} from '@ant-design/icons';
import { intentCatalogApi, IntentCatalogEntry } from '../services/intentCatalogApi';
import { paramsApi } from '../services/api';
import DataAgentTables from './DataAgentTables';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

const { Text } = Typography;
const { TextArea } = Input;

function OrchestratorPanel() {
  const { message, modal } = App.useApp();
  const { token } = theme.useToken();
  const [form] = Form.useForm();
  const [settingsForm] = Form.useForm();
  const watchedIntentType = Form.useWatch('intent_type', form);

  const [intents, setIntents] = useState<IntentCatalogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [search, setSearch] = useState('');
  const [intentType, setIntentType] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  const [detailVisible, setDetailVisible] = useState(false);
  const [currentIntent, setCurrentIntent] = useState<IntentCatalogEntry | null>(null);

  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [settingsVisible, setSettingsVisible] = useState(false);
  const [settings, setSettings] = useState({ embeddingModel: '', embeddingDimension: 1536, matchThreshold: 0.75 });
  const [isSyncing, setIsSyncing] = useState(false);

  const STRATEGY_COLORS: Record<string, string> = {
    direct_llm: 'blue',
    confirm_then_execute: 'orange',
    clarify_first: 'gold',
    handoff_bpa: 'green',
  };

  const loadIntents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await intentCatalogApi.list({
        agent_scope: 'orchestrator',
        page,
        page_size: pageSize,
        search: search || undefined,
        status: statusFilter || undefined,
        intent_type: intentType || undefined,
      });
      if (res.data.code === 0) {
        setIntents(res.data.data.records || []);
        setTotal(res.data.data.total || 0);
      } else {
        message.error('載入失敗');
      }
    } catch (e) {
      message.error('載入意圖失敗');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, statusFilter, intentType, message]);

  useEffect(() => {
    loadIntents();
  }, [loadIntents]);

  const loadSettings = async () => {
    try {
      const res = await paramsApi.list();
      if (res.data.code === 0) {
        const p = res.data.data.reduce((acc, curr) => ({ ...acc, [curr.param_key]: curr.param_value }), {} as Record<string, string>);
        const newSettings = {
          embeddingModel: p['orch.embedding_model'] || '',
          embeddingDimension: Number(p['orch.embedding_dimension']) || 1536,
          matchThreshold: Number(p['orch.match_threshold']) || 0.75,
        };
        setSettings(newSettings);
        settingsForm.setFieldsValue(newSettings);
      }
    } catch (e) {
      message.error('載入設定失敗');
    }
  };

  useEffect(() => {
    if (settingsVisible) {
      loadSettings();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settingsVisible]);

  const handleSyncQdrant = async () => {
    setIsSyncing(true);
    try {
      const res = await intentCatalogApi.syncToQdrant({ agent_scope: 'orchestrator', model: settings.embeddingModel });
      if (res.data.status === 'ok') {
        message.success(`同步成功，共 ${res.data.synced_count} 筆`);
      } else {
        message.error('同步失敗');
      }
    } catch (e) {
      message.error('同步發生錯誤');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      const vals = await settingsForm.validateFields();
      modal.confirm({
        title: '確認儲存設定？',
        content: '變更 Embedding 模型或維度後，建議重新執行「同步到 Qdrant」以確保向量資料一致。',
        onOk: async () => {
          try {
            await Promise.all([
              paramsApi.update('orch.embedding_model', vals.embeddingModel),
              paramsApi.update('orch.embedding_dimension', String(vals.embeddingDimension)),
              paramsApi.update('orch.match_threshold', String(vals.matchThreshold)),
            ]);
            message.success('設定已儲存');
            setSettings(vals);
            setSettingsVisible(false);
          } catch (e) {
            message.error('儲存設定失敗');
          }
        }
      });
    } catch (e) {
      // validation failed
    }
  };

  const handleDelete = (id: string) => {
    modal.confirm({
      title: '確認刪除',
      content: `確定要刪除意圖 ${id} 嗎？此操作無法還原。`,
      okType: 'danger',
      onOk: async () => {
        try {
          await intentCatalogApi.delete(id);
          message.success('刪除成功');
          if (intents.length === 1 && page > 1) {
            setPage(page - 1);
          } else {
            loadIntents();
          }
        } catch (e) {
          message.error('刪除失敗');
        }
      }
    });
  };

  const openNew = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({ intent_type: 'task', status: 'enabled', confidence_threshold: 0.7, priority: 0 });
    setModalVisible(true);
  };

  const openEdit = (record: IntentCatalogEntry) => {
    setEditingId(record.intent_id);
    form.resetFields();
    form.setFieldsValue({
      ...record,
      nl_examples: record.nl_examples?.join('\n') || '',
      capabilities: record.capabilities || [],
      domain: record.domain ? [record.domain] : [],
      bpa_id: record.bpa_id ? [record.bpa_id] : [],
      response_strategy: record.response_strategy || '',
    });
    setModalVisible(true);
  };

  const handleSave = async () => {
    try {
      const formValues = await form.validateFields();
      const { 
        intent_id, name, description, priority, status, nl_examples, 
        intent_type, domain, bpa_id, task_type, response_strategy, capabilities, confidence_threshold 
      } = formValues;

      const payload: Partial<IntentCatalogEntry> = {
        intent_id,
        name,
        description,
        priority,
        status,
        agent_scope: 'orchestrator',
        nl_examples: nl_examples ? nl_examples.split('\n').map((s: string) => s.trim()).filter(Boolean) : [],
        intent_type,
        domain: Array.isArray(domain) ? domain[0] : domain,
        bpa_id: Array.isArray(bpa_id) ? bpa_id[0] : bpa_id,
        task_type: intent_type === 'task' ? task_type : undefined,
        response_strategy: response_strategy || undefined,
        capabilities: Array.isArray(capabilities) ? capabilities : [],
        confidence_threshold,
      };

      if (editingId) {
        await intentCatalogApi.update(editingId, payload);
        message.success('更新成功');
      } else {
        await intentCatalogApi.create(payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      loadIntents();
    } catch (e) {
      console.error(e);
    }
  };

  const columns = [
    { title: 'Intent ID', dataIndex: 'intent_id', key: 'intent_id', render: (text: string) => <Text code>{text}</Text> },
    { title: '名稱', dataIndex: 'name', key: 'name' },
    { 
      title: '類型', dataIndex: 'intent_type', key: 'intent_type',
      render: (type: string) => {
        const color = type === 'chat' ? 'blue' : type === 'task' ? 'green' : 'default';
        return <Tag color={color}>{type || '-'}</Tag>;
      }
    },
    { 
      title: 'Domain', dataIndex: 'domain', key: 'domain',
      render: (domain: string) => domain ? <Tag>{domain}</Tag> : '-'
    },
    { 
      title: 'BPA', dataIndex: 'bpa_id', key: 'bpa_id',
      render: (bpa: string) => bpa ? <Tag color="geekblue">{bpa}</Tag> : '-'
    },
    { 
      title: 'Task Type', dataIndex: 'task_type', key: 'task_type',
      render: (task: string) => task ? <Tag color="purple">{task}</Tag> : '-'
    },
    {
      title: 'Strategy',
      dataIndex: 'response_strategy',
      key: 'response_strategy',
      render: (s: string) => s ? <Tag color={STRATEGY_COLORS[s] || 'default'}>{s}</Tag> : '-'
    },
    {
      title: '信賴度', dataIndex: 'confidence_threshold', key: 'confidence',
      render: (val: number) => val != null ? `${(val * 100).toFixed(0)}%` : '-'
    },
    {
      title: '狀態', dataIndex: 'status', key: 'status',
      render: (status: string) => <Tag color={status === 'enabled' ? 'green' : 'default'}>{status === 'enabled' ? '啟用' : '停用'}</Tag>
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: IntentCatalogEntry) => (
        <Space size="small">
          <Button type="text" icon={<EyeOutlined />} onClick={() => { setCurrentIntent(record); setDetailVisible(true); }} />
          <Button type="text" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.intent_id)} />
        </Space>
      )
    }
  ];

  return (
    <Space orientation="vertical" size="middle" style={{ display: 'flex' }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="總意圖數" value={total} prefix={<AimOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="Chat 型" value={intents.filter(i => i.intent_type === 'chat').length} styles={{ content: { color: token.colorSuccess } }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="Task 型" value={intents.filter(i => i.intent_type === 'task').length} styles={{ content: { color: token.colorInfo } }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="已啟用" value={intents.filter(i => i.status === 'enabled').length} styles={{ content: { color: token.colorSuccess } }} />
          </Card>
        </Col>
      </Row>

      <Card size="small">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Space>
            <Input.Search placeholder="搜尋描述或ID" onSearch={(v) => { setSearch(v); setPage(1); }} style={{ width: 200 }} allowClear />
            <Select value={intentType} onChange={(v) => { setIntentType(v); setPage(1); }} style={{ width: 120 }} options={[{ label: '全部類型', value: '' }, { label: 'chat', value: 'chat' }, { label: 'task', value: 'task' }]} />
            <Select value={statusFilter} onChange={(v) => { setStatusFilter(v); setPage(1); }} style={{ width: 120 }} options={[{ label: '全部狀態', value: '' }, { label: '啟用', value: 'enabled' }, { label: '停用', value: 'disabled' }]} />
            <Button icon={<ReloadOutlined />} onClick={loadIntents}>重新整理</Button>
            <Button icon={<SettingOutlined />} onClick={() => setSettingsVisible(true)}>設定</Button>
          </Space>
          <Space>
            <Button icon={<CloudSyncOutlined />} onClick={handleSyncQdrant} loading={isSyncing}>同步到Qdrant</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openNew}>新增意圖</Button>
          </Space>
        </div>

        <Table
          columns={columns}
          dataSource={intents}
          rowKey="intent_id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); }
          }}
        />
      </Card>

      <Drawer title="意圖詳細資訊" size="large" open={detailVisible} onClose={() => setDetailVisible(false)}>
        {currentIntent && (
          <Tabs defaultActiveKey="1" items={[
            {
              key: '1',
              label: '基本資訊',
              children: (
                <Descriptions bordered column={1} size="small">
                  <Descriptions.Item label="Intent ID" span={1}><Text code>{currentIntent.intent_id}</Text></Descriptions.Item>
                  <Descriptions.Item label="名稱" span={1}>{currentIntent.name}</Descriptions.Item>
                  <Descriptions.Item label="說明" span={1}>{currentIntent.description}</Descriptions.Item>
                  <Descriptions.Item label="狀態" span={1}><Tag color={currentIntent.status === 'enabled' ? 'green' : 'default'}>{currentIntent.status}</Tag></Descriptions.Item>
                  <Descriptions.Item label="優先度" span={1}>{currentIntent.priority}</Descriptions.Item>
                  <Descriptions.Item label="類型" span={1}><Tag color={currentIntent.intent_type === 'chat' ? 'blue' : 'green'}>{currentIntent.intent_type || '-'}</Tag></Descriptions.Item>
                  <Descriptions.Item label="Domain" span={1}><Tag>{currentIntent.domain || '-'}</Tag></Descriptions.Item>
                  <Descriptions.Item label="BPA ID" span={1}>{currentIntent.bpa_id ? <Tag color="geekblue">{currentIntent.bpa_id}</Tag> : '-'}</Descriptions.Item>
                  <Descriptions.Item label="Task Type" span={1}><Tag color="purple">{currentIntent.intent_type === 'task' ? (currentIntent.task_type || '-') : '-'}</Tag></Descriptions.Item>
                  <Descriptions.Item label="Response Strategy" span={1}>
                    {currentIntent.response_strategy
                      ? <Tag color={STRATEGY_COLORS[currentIntent.response_strategy] || 'default'}>{currentIntent.response_strategy}</Tag>
                      : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Capabilities" span={1}>
                    {currentIntent.capabilities?.length ? currentIntent.capabilities.map((c: string) => <Tag key={c}>{c}</Tag>) : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="信賴度" span={1}>{currentIntent.confidence_threshold != null ? `${(currentIntent.confidence_threshold * 100).toFixed(0)}%` : '-'}</Descriptions.Item>
                </Descriptions>
              )
            },
            {
              key: '2',
              label: 'NL Examples',
              children: (
                <Card size="small">
                  <ol style={{ paddingLeft: 20, margin: 0 }}>
                    {currentIntent.nl_examples?.map((ex: string, i: number) => <li key={i} style={{ marginBottom: 8 }}>{ex}</li>) || <li>無範例</li>}
                  </ol>
                </Card>
              )
            }
          ]} />
        )}
      </Drawer>

      <Modal title={editingId ? '編輯 Orchestrator 意圖' : '新增 Orchestrator 意圖'} open={modalVisible} onCancel={() => setModalVisible(false)} onOk={handleSave} width={700}>
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="intent_id" label="Intent ID" rules={[{ required: true }]}>
                <Input placeholder="例如: orch_web_search" disabled={!!editingId} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="name" label="名稱" rules={[{ required: true }]}>
                <Input placeholder="例如: 上網搜尋" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="說明">
            <TextArea placeholder="描述此意圖的用途" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="intent_type" label="類型" rules={[{ required: true }]}>
                <Select options={[{ label: 'chat（直接回覆）', value: 'chat' }, { label: 'task（路由 BPA）', value: 'task' }]} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="domain" label="Domain">
                <Select mode="tags" maxCount={1} options={[
                  { label: 'general', value: 'general' },
                  { label: 'order', value: 'order' },
                  { label: 'material', value: 'material' },
                  { label: 'finance', value: 'finance' },
                  { label: 'data_query', value: 'data_query' }
                ]} placeholder="請選擇或輸入" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="bpa_id" label="BPA ID">
                <Select mode="tags" maxCount={1} options={[
                  { label: 'order-bpa', value: 'order-bpa' },
                  { label: 'material-bpa', value: 'material-bpa' },
                  { label: 'finance-bpa', value: 'finance-bpa' },
                  { label: 'data-agent', value: 'data-agent' }
                ]} placeholder="請選擇或輸入" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            {watchedIntentType === 'task' && (
              <Col span={8}>
                <Form.Item name="task_type" label="Task Type">
                  <Select options={[
                    { label: 'query', value: 'query' },
                    { label: 'action', value: 'action' },
                    { label: 'workflow', value: 'workflow' }
                  ]} allowClear placeholder="請選擇" />
                </Form.Item>
              </Col>
            )}
            {watchedIntentType === 'task' && (
              <Col span={8}>
                <Form.Item name="response_strategy" label="Response Strategy">
                  <Select
                    options={[
                      { label: 'direct_llm', value: 'direct_llm' },
                      { label: 'handoff_bpa', value: 'handoff_bpa' },
                      { label: 'confirm_then_execute', value: 'confirm_then_execute' },
                      { label: 'clarify_first', value: 'clarify_first' },
                    ]}
                    allowClear
                    placeholder="請選擇"
                  />
                </Form.Item>
              </Col>
            )}
            <Col span={watchedIntentType === 'task' ? 8 : 12}>
              <Form.Item name="capabilities" label="Capabilities">
                <Select mode="tags" placeholder="輸入後按 Enter" />
              </Form.Item>
            </Col>
            <Col span={watchedIntentType === 'task' ? 8 : 12}>
              <Form.Item name="confidence_threshold" label="信賴度">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label="優先度">
                <InputNumber style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="status" label="狀態">
                <Select options={[{ label: '啟用', value: 'enabled' }, { label: '停用', value: 'disabled' }]} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="nl_examples" label="NL Examples">
            <TextArea placeholder="每行一個自然語言範例" rows={4} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer title="Orchestrator 設定" styles={{ wrapper: { width: '480px' } }} open={settingsVisible} onClose={() => setSettingsVisible(false)} extra={<Button type="primary" onClick={handleSaveSettings}>儲存設定</Button>}>
        <Alert title="變更提醒" description="修改 Embedding 模型或維度後，必須重新執行「同步到 Qdrant」，否則查詢可能失效。" type="warning" showIcon style={{ marginBottom: 16 }} />
        <Form form={settingsForm} layout="vertical">
          <Form.Item name="embeddingModel" label="Embedding 模型" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="embeddingDimension" label="Embedding 維度" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="matchThreshold" label="比對閾值 (Match Threshold)" rules={[{ required: true }]}>
            <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
        <Divider />
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="目前模型">{settings.embeddingModel}</Descriptions.Item>
          <Descriptions.Item label="目前維度">{settings.embeddingDimension}</Descriptions.Item>
          <Descriptions.Item label="目前閾值">{settings.matchThreshold}</Descriptions.Item>
        </Descriptions>
      </Drawer>
    </Space>
  );
}

export default function IntentCatalog() {
  useEntityPerception({ defaultEntityType: 'intent', defaultAction: 'list' });

  useEffect(() => {
    pageContextManager.report({ component: 'IntentCatalog', entityType: 'intent', action: 'list' });
    return () => {
      pageContextManager.report({ component: 'IntentCatalog', entityType: 'intent', action: undefined });
    };
  }, []);

  return (
    <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
      <Tabs
        defaultActiveKey="orchestrator"
        items={[
          { key: 'orchestrator', label: 'TopOrchestrator', children: <OrchestratorPanel /> },
          { key: 'data_agent', label: 'DataAgent', children: <DataAgentTables /> }
        ]}
      />
    </div>
  );
}
