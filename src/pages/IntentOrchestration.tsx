/**
 * @file        意圖決策管理頁面
 * @description Orchestrator 意圖目錄 CRUD 管理，含 Qdrant 同步與設定
 * @lastUpdate  2026-03-28 11:27:55
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Tag, Space, Typography,
  Descriptions, Select, Input, Drawer, Tabs, App, Statistic, Row, Col, theme, Modal, Form,
  InputNumber, Divider, Alert
} from 'antd';
import {
  EyeOutlined, DeleteOutlined, ReloadOutlined,
  EditOutlined, PlusOutlined, CloudSyncOutlined,
  AimOutlined, SettingOutlined
} from '@ant-design/icons';
import { paramsApi } from '../services/api';
import { orchestratorApi, OrchIntentEntry } from '../services/orchestratorApi';

const { Text } = Typography;
const { TextArea } = Input;

const ORCH_PARAM_KEYS = {
  embeddingModel: 'orch.embedding_model',
  embeddingDimension: 'orch.embedding_dimension',
  matchThreshold: 'orch.match_threshold',
} as const;

interface OrchSettings {
  embeddingModel: string;
  embeddingDimension: number;
  matchThreshold: number;
}

const DEFAULT_SETTINGS: OrchSettings = {
  embeddingModel: 'bge-m3:latest',
  embeddingDimension: 1024,
  matchThreshold: 0.75,
};

export default function IntentOrchestration() {
  const { message, modal } = App.useApp();
  const { token } = theme.useToken();

  const [intents, setIntents] = useState<OrchIntentEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filterType, setFilterType] = useState<string>('ALL');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [searchText, setSearchText] = useState('');

  const [settings, setSettings] = useState<OrchSettings>(DEFAULT_SETTINGS);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [settingsForm] = Form.useForm();

  const [detailVisible, setDetailVisible] = useState(false);
  const [currentIntent, setCurrentIntent] = useState<OrchIntentEntry | null>(null);

  const [crudVisible, setCrudVisible] = useState(false);
  const [editingIntent, setEditingIntent] = useState<OrchIntentEntry | null>(null);
  const [crudForm] = Form.useForm();

  const loadSettings = useCallback(async () => {
    try {
      const res = await paramsApi.list();
      const records = res.data.data || [];
      const newSettings = { ...DEFAULT_SETTINGS };
      records.forEach((r: unknown) => {
        const param = r as { param_key: string; param_value: string | number };
        if (param.param_key === ORCH_PARAM_KEYS.embeddingModel) newSettings.embeddingModel = String(param.param_value);
        if (param.param_key === ORCH_PARAM_KEYS.embeddingDimension) newSettings.embeddingDimension = Number(param.param_value);
        if (param.param_key === ORCH_PARAM_KEYS.matchThreshold) newSettings.matchThreshold = Number(param.param_value);
      });
      setSettings(newSettings);
      settingsForm.setFieldsValue(newSettings);
    } catch {
      message.error('載入設定失敗');
    }
  }, [message, settingsForm]);

  const loadIntents = useCallback(async (page = 1, pageSize = 20, search?: string) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterType !== 'ALL') params.intent_type = filterType;
      if (filterStatus !== 'ALL') params.status = filterStatus;
      if (search) params.search = search;
      const res = await orchestratorApi.listCatalog(params);
      setIntents(res.data.data?.records || []);
      setPagination({ current: page, pageSize, total: res.data.data?.total || 0 });
    } catch {
      message.error('載入意圖目錄失敗');
    } finally {
      setLoading(false);
    }
  }, [filterType, filterStatus, message]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    loadIntents(1, pagination.pageSize, searchText);
  }, [loadIntents, searchText]);

  const handleDelete = async (intentId: string) => {
    modal.confirm({
      title: '確定要刪除此意圖嗎？',
      content: '刪除後無法恢復，且會影響相關工作流判斷。',
      okText: '確定',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await orchestratorApi.deleteIntent(intentId);
          message.success('刪除成功');
          loadIntents(pagination.current, pagination.pageSize, searchText);
        } catch {
          message.error('刪除失敗');
        }
      },
    });
  };

  const handleSyncQdrant = async () => {
    setSyncing(true);
    try {
      const res = await orchestratorApi.syncToQdrant({ model: settings.embeddingModel });
      message.success(`同步完成，共同步 ${res.data.data?.synced_count ?? 0} 個意圖`);
    } catch {
      message.error('同步失敗');
    } finally {
      setSyncing(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      const values = await settingsForm.validateFields();
      modal.confirm({
        title: '確認變更設定？',
        content: '變更 Embedding 模型或維度後，必須重新執行「同步到 Qdrant」以重建向量庫。',
        onOk: async () => {
          try {
            await paramsApi.update(ORCH_PARAM_KEYS.embeddingModel, String(values.embeddingModel));
            await paramsApi.update(ORCH_PARAM_KEYS.embeddingDimension, String(values.embeddingDimension));
            await paramsApi.update(ORCH_PARAM_KEYS.matchThreshold, String(values.matchThreshold));
            message.success('設定已儲存');
            setSettingsVisible(false);
            loadSettings();
          } catch {
            message.error('儲存設定失敗');
          }
        }
      });
    } catch {
    }
  };

  const openCreateModal = () => {
    setEditingIntent(null);
    crudForm.resetFields();
    crudForm.setFieldsValue({
      intent_type: 'tool',
      status: 'enabled',
      confidence_threshold: 0.75,
      priority: 0
    });
    setCrudVisible(true);
  };

  const openEditModal = (intent: OrchIntentEntry) => {
    setEditingIntent(intent);
    crudForm.setFieldsValue({
      ...intent,
      nl_examples: intent.nl_examples ? intent.nl_examples.join('\n') : ''
    });
    setCrudVisible(true);
  };

  const handleCreateUpdate = async () => {
    try {
      const values = await crudForm.validateFields();
      const payload = {
        ...values,
        nl_examples: values.nl_examples.split('\n').map((s: string) => s.trim()).filter(Boolean)
      };

      if (editingIntent) {
        await orchestratorApi.updateIntent(editingIntent.intent_id, payload);
        message.success('更新成功');
      } else {
        await orchestratorApi.createIntent(payload);
        message.success('新增成功');
      }
      setCrudVisible(false);
      loadIntents(pagination.current, pagination.pageSize, searchText);
    } catch (error) {
      if ((error as Record<string, unknown>).errorFields) return;
      message.error('儲存失敗');
    }
  };

  const columns = [
    {
      title: 'Intent ID',
      dataIndex: 'intent_id',
      width: 150,
      render: (id: string) => <Text code>{id}</Text>
    },
    {
      title: '名稱',
      dataIndex: 'name',
      width: 140
    },
    {
      title: '說明',
      dataIndex: 'description',
      ellipsis: true
    },
    {
      title: '類型',
      dataIndex: 'intent_type',
      width: 100,
      render: (type: string) => {
        let color = 'default';
        if (type === 'tool') color = 'green';
        if (type === 'workflow') color = 'blue';
        if (type === 'fallback') color = 'orange';
        return <Tag color={color}>{type}</Tag>;
      }
    },
    {
      title: '工具',
      dataIndex: 'tool_name',
      width: 130,
      render: (name: string) => name ? <Tag color="geekblue">{name}</Tag> : '-'
    },
    {
      title: '優先度',
      dataIndex: 'priority',
      width: 80
    },
    {
      title: '信賴度',
      dataIndex: 'confidence_threshold',
      width: 90,
      render: (val: number) => `${(val * 100).toFixed(0)}%`
    },
    {
      title: '狀態',
      dataIndex: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={status === 'enabled' ? 'green' : 'default'}>
          {status === 'enabled' ? '啟用' : '停用'}
        </Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: OrchIntentEntry) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => {
              setCurrentIntent(record);
              setDetailVisible(true);
            }}
          />
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          />
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.intent_id)}
          />
        </Space>
      )
    }
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="總意圖數"
              value={pagination.total}
              prefix={<AimOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="工具型"
              value={intents.filter(i => i.intent_type === 'tool').length}
              styles={{ content: { color: token.colorSuccess } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="工作流型"
              value={intents.filter(i => i.intent_type === 'workflow').length}
              styles={{ content: { color: token.colorInfo } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="備援型"
              value={intents.filter(i => i.intent_type === 'fallback').length}
              styles={{ content: { color: token.colorWarning } }}
            />
          </Card>
        </Col>
      </Row>

      <Card size="small">
        <Space style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', width: '100%' }}>
          <Space>
            <Input.Search
              placeholder="搜尋描述或ID"
              style={{ width: 200 }}
              onSearch={val => setSearchText(val)}
              allowClear
            />
            <Select
              value={filterType}
              onChange={setFilterType}
              style={{ width: 120 }}
              options={[
                { label: '全部類型', value: 'ALL' },
                { label: 'tool', value: 'tool' },
                { label: 'workflow', value: 'workflow' },
                { label: 'fallback', value: 'fallback' }
              ]}
            />
            <Select
              value={filterStatus}
              onChange={setFilterStatus}
              style={{ width: 120 }}
              options={[
                { label: '全部狀態', value: 'ALL' },
                { label: '啟用 (enabled)', value: 'enabled' },
                { label: '停用 (disabled)', value: 'disabled' }
              ]}
            />
          </Space>
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
              新增意圖
            </Button>
            <Button icon={<CloudSyncOutlined />} loading={syncing} onClick={handleSyncQdrant}>
              同步到 Qdrant
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => loadIntents(pagination.current, pagination.pageSize, searchText)}>
              重新整理
            </Button>
            <Button icon={<SettingOutlined />} onClick={() => setSettingsVisible(true)}>
              設定
            </Button>
          </Space>
        </Space>

        <Table
          rowKey="intent_id"
          size="small"
          columns={columns}
          dataSource={intents}
          loading={loading}
          pagination={{
            ...pagination,
            onChange: (page, pageSize) => loadIntents(page, pageSize, searchText)
          }}
        />
      </Card>

      <Drawer
        title="意圖詳情"
        placement="right"
        size="large"
        onClose={() => setDetailVisible(false)}
        open={detailVisible}
        destroyOnHidden
      >
        {currentIntent && (
          <Tabs
            items={[
              {
                key: 'info',
                label: '基本資訊',
                children: (
                  <Descriptions bordered column={1} size="small">
                    <Descriptions.Item label="Intent ID"><Text code>{currentIntent.intent_id}</Text></Descriptions.Item>
                    <Descriptions.Item label="名稱">{currentIntent.name}</Descriptions.Item>
                    <Descriptions.Item label="說明">{currentIntent.description}</Descriptions.Item>
                    <Descriptions.Item label="類型"><Tag>{currentIntent.intent_type}</Tag></Descriptions.Item>
                    <Descriptions.Item label="綁定工具">{currentIntent.tool_name}</Descriptions.Item>
                    <Descriptions.Item label="優先度">{currentIntent.priority}</Descriptions.Item>
                    <Descriptions.Item label="信賴度">{currentIntent.confidence_threshold}</Descriptions.Item>
                    <Descriptions.Item label="狀態">{currentIntent.status}</Descriptions.Item>
                    <Descriptions.Item label="建立時間">{currentIntent.created_at || '-'}</Descriptions.Item>
                    <Descriptions.Item label="更新時間">{currentIntent.updated_at || '-'}</Descriptions.Item>
                  </Descriptions>
                )
              },
              {
                key: 'examples',
                label: 'NL Examples',
                children: (
                  <Card size="small">
                    <ol style={{ margin: 0, paddingLeft: 20 }}>
                      {currentIntent.nl_examples?.map((ex, i) => (
                        <li key={i} style={{ marginBottom: 8 }}>{ex}</li>
                      ))}
                    </ol>
                  </Card>
                )
              }
            ]}
          />
        )}
      </Drawer>

      <Modal
        title={editingIntent ? '編輯意圖' : '新增意圖'}
        open={crudVisible}
        onCancel={() => setCrudVisible(false)}
        onOk={handleCreateUpdate}
        width={700}
        destroyOnHidden
      >
        <Form form={crudForm} layout="vertical" preserve={false}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="intent_id" label="Intent ID" rules={[{ required: true }]}>
                <Input disabled={!!editingIntent} placeholder="例如: orch_web_search" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="name" label="名稱" rules={[{ required: true }]}>
                <Input placeholder="例如: 上網搜尋" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="intent_type" label="意圖類型" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: '工具 (tool)', value: 'tool' },
                    { label: '工作流 (workflow)', value: 'workflow' },
                    { label: '備援 (fallback)', value: 'fallback' }
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tool_name" label="綁定工具 (Tool Name)" rules={[{ required: true }]}>
                <Input placeholder="例如: web_search" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="說明" rules={[{ required: true }]}>
            <Input placeholder="描述此意圖的用途" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="priority" label="優先度">
                <InputNumber min={0} max={100} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="confidence_threshold" label="信賴度閥值">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="status" label="狀態">
                <Select
                  options={[
                    { label: '啟用', value: 'enabled' },
                    { label: '停用', value: 'disabled' }
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="nl_examples" label="自然語言範例 (NL Examples)" rules={[{ required: true }]}>
            <TextArea rows={4} placeholder="每行一個自然語言範例" />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="Orchestrator 設定"
        placement="right"
        width={480}
        onClose={() => setSettingsVisible(false)}
        open={settingsVisible}
        destroyOnHidden
        extra={
          <Button type="primary" onClick={handleSaveSettings}>
            儲存設定
          </Button>
        }
      >
        <Alert
          type="info"
          showIcon
          message="變更提醒"
          description="Embedding 模型用於將意圖文字轉為向量，寫入 Qdrant。變更模型或維度後必須重新同步。"
          style={{ marginBottom: 24 }}
        />
        <Form form={settingsForm} layout="vertical">
          <Form.Item name="embeddingModel" label="Embedding 模型名稱" rules={[{ required: true }]}>
            <Input placeholder="例如: bge-m3:latest" />
          </Form.Item>
          <Form.Item name="embeddingDimension" label="Embedding 維度" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={1} />
          </Form.Item>
          <Form.Item name="matchThreshold" label="全局匹配閥值 (Match Threshold)" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={0} max={1} step={0.05} />
          </Form.Item>
        </Form>
        <Divider />
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="當前模型">{settings.embeddingModel}</Descriptions.Item>
          <Descriptions.Item label="當前維度">{settings.embeddingDimension}</Descriptions.Item>
          <Descriptions.Item label="當前閥值">{settings.matchThreshold}</Descriptions.Item>
        </Descriptions>
      </Drawer>
    </Space>
  );
}
