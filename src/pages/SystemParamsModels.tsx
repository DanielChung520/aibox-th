/**
 * @file        SystemParamsModels.tsx
 * @description 模型 Provider 與模型管理頁面
 * @lastUpdate  2026-03-27 12:44:46
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  Popconfirm,
  App,
  Badge,
  Typography,
  InputNumber,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SyncOutlined,
  DownOutlined,
  RightOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import { modelProviderApi, ModelProvider, LLMModel } from '../services/api';
import { useContentTokens } from '../contexts/AppThemeProvider';

const { Title } = Typography;

export default function SystemParamsModels() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ModelProvider | null>(null);
  const [syncingKeys, setSyncingKeys] = useState<Record<string, boolean>>({});
  const [form] = Form.useForm();
  const [modelModalVisible, setModelModalVisible] = useState(false);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [editingProviderKey, setEditingProviderKey] = useState<string | null>(null);
  const [modelForm] = Form.useForm();

  const fetchProviders = async () => {
    setLoading(true);
    try {
      const response = await modelProviderApi.list();
      setProviders(response.data?.data || []);
    } catch (error: any) {
      console.error('Fetch providers failed:', error);
      message.error(error.response?.data?.message || '獲取 Provider 列表失敗，使用測試資料');
      // Mock data fallback
      setProviders([
        {
          _key: 'mock-1',
          code: 'openai',
          name: 'OpenAI',
          description: 'OpenAI API',
          base_url: 'https://api.openai.com/v1',
          status: 'enabled',
          sort_order: 1,
          models: [
            {
              model_id: 'gpt-4o',
              name: 'GPT-4o',
              display_name: 'GPT-4o',
              context_window: 128000,
              input_cost_per_1k: 0.005,
              output_cost_per_1k: 0.015,
              supports_vision: true,
              status: 'active'
            } as LLMModel
          ],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  const handleSync = async (key: string) => {
    setSyncingKeys(prev => ({ ...prev, [key]: true }));
    try {
      await modelProviderApi.sync(key);
      message.success('同步成功');
      fetchProviders();
    } catch (error: any) {
      message.error(error.response?.data?.message || '同步失敗');
    } finally {
      setSyncingKeys(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleDelete = async (key: string) => {
    try {
      await modelProviderApi.delete(key);
      message.success('刪除成功');
      fetchProviders();
    } catch (error: any) {
      message.error(error.response?.data?.message || '刪除失敗');
    }
  };

  const handleStatusChange = async (checked: boolean, record: ModelProvider) => {
    const newStatus = checked ? 'enabled' : 'disabled';
    try {
      await modelProviderApi.update(record._key, { status: newStatus });
      message.success('狀態更新成功');
      fetchProviders();
    } catch (error: any) {
      message.error(error.response?.data?.message || '狀態更新失敗');
    }
  };

  const openAddModal = () => {
    setEditingProvider(null);
    form.resetFields();
    form.setFieldsValue({
      status: 'enabled',
      sort_order: 99
    });
    setModalVisible(true);
  };

  const openEditModal = (record: ModelProvider) => {
    setEditingProvider(record);
    form.resetFields();
    form.setFieldsValue({
      name: record.name,
      code: record.code,
      description: record.description,
      base_url: record.base_url,
      api_key: record.api_key || '',
      status: record.status,
      sort_order: record.sort_order
    });
    setModalVisible(true);
  };

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingProvider) {
        await modelProviderApi.update(editingProvider._key, values);
        message.success('更新成功');
      } else {
        await modelProviderApi.create(values);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchProviders();
    } catch (error: any) {
      if (error.errorFields) return; // Validation error
      message.error(error.response?.data?.message || '操作失敗');
    }
  };

  const handleModalCancel = () => {
    setModalVisible(false);
  };

  const openAddModelModal = (providerKey: string) => {
    setEditingModel(null);
    setEditingProviderKey(providerKey);
    modelForm.resetFields();
    modelForm.setFieldsValue({
      status: 'enabled',
      supports_vision: false,
    });
    setModelModalVisible(true);
  };

  const openEditModelModal = (providerKey: string, model: LLMModel) => {
    setEditingModel(model);
    setEditingProviderKey(providerKey);
    modelForm.resetFields();
    modelForm.setFieldsValue({
      ...model,
      status: model.status === 'active' || model.status === 'enabled' ? 'enabled' : 'disabled'
    });
    setModelModalVisible(true);
  };

  const handleModelModalOk = async () => {
    try {
      const values = await modelForm.validateFields();
      if (!editingProviderKey) return;
      
      const provider = providers.find(p => p._key === editingProviderKey);
      if (!provider) return;

      const currentModels = provider.models || [];
      let updatedModels: LLMModel[];

      const newModel: LLMModel = {
        ...values,
      };

      if (editingModel) {
        updatedModels = currentModels.map(m => m.model_id === editingModel.model_id ? newModel : m);
      } else {
        if (currentModels.some(m => m.model_id === newModel.model_id)) {
          message.error('該 Model ID 已存在');
          return;
        }
        updatedModels = [...currentModels, newModel];
      }

      await modelProviderApi.update(editingProviderKey, { models: updatedModels });
      message.success(editingModel ? '模型編輯成功' : '模型新增成功');
      setModelModalVisible(false);
      fetchProviders();
    } catch (error: any) {
      if (error.errorFields) return;
      message.error(error.response?.data?.message || '操作失敗');
    }
  };

  const handleModelModalCancel = () => {
    setModelModalVisible(false);
  };

  const handleModelDelete = async (providerKey: string, modelId: string) => {
    try {
      const provider = providers.find(p => p._key === providerKey);
      if (!provider) return;
      
      const updatedModels = (provider.models || []).filter(m => m.model_id !== modelId);
      await modelProviderApi.update(providerKey, { models: updatedModels });
      message.success('模型刪除成功');
      fetchProviders();
    } catch (error: any) {
      message.error(error.response?.data?.message || '刪除失敗');
    }
  };

  const handleModelStatusChange = async (checked: boolean, providerKey: string, modelId: string) => {
    try {
      const provider = providers.find(p => p._key === providerKey);
      if (!provider) return;
      
      const newStatus = checked ? 'enabled' : 'disabled';
      const updatedModels = (provider.models || []).map(m => 
        m.model_id === modelId ? { ...m, status: newStatus } : m
      );
      
      await modelProviderApi.update(providerKey, { models: updatedModels });
      message.success('狀態更新成功');
      fetchProviders();
    } catch (error: any) {
      message.error(error.response?.data?.message || '狀態更新失敗');
    }
  };

  const expandedRowRender = (record: ModelProvider) => {
    const modelColumns = [
      { title: 'Model ID', dataIndex: 'model_id', key: 'model_id' },
      { title: '名稱', dataIndex: 'name', key: 'name' },
      { title: '顯示名稱', dataIndex: 'display_name', key: 'display_name' },
      { title: 'Context Window', dataIndex: 'context_window', key: 'context_window' },
      { title: '輸入成本/1k', dataIndex: 'input_cost_per_1k', key: 'input_cost_per_1k' },
      { title: '輸出成本/1k', dataIndex: 'output_cost_per_1k', key: 'output_cost_per_1k' },
      {
        title: '視覺支援',
        dataIndex: 'supports_vision',
        key: 'supports_vision',
        render: (val: boolean) => (val ? <Badge status="success" text="是" /> : <Badge status="default" text="否" />)
      },
      {
        title: '狀態',
        dataIndex: 'status',
        key: 'status',
        render: (status: string, model: LLMModel) => {
          const isEnabled = status === 'active' || status === 'enabled';
          return (
            <Switch
              checked={isEnabled}
              onChange={(checked) => handleModelStatusChange(checked, record._key, model.model_id)}
            />
          );
        }
      },
      {
        title: '操作',
        key: 'action',
        render: (_: any, model: LLMModel) => (
          <Space size="middle">
            <Button type="text" icon={<EditOutlined />} onClick={() => openEditModelModal(record._key, model)}>
              編輯
            </Button>
            <Popconfirm
              title="確定要刪除這個模型嗎？"
              onConfirm={() => handleModelDelete(record._key, model.model_id)}
              okText="確定"
              cancelText="取消"
            >
              <Button type="text" danger icon={<DeleteOutlined />}>
                刪除
              </Button>
            </Popconfirm>
          </Space>
        )
      }
    ];

    return (
        <div style={{ padding: '12px 16px', background: contentTokens.tableExpandedRowBg }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => openAddModelModal(record._key)}>
            新增模型
          </Button>
        </div>
        <Table
          columns={modelColumns}
          dataSource={record.models || []}
          pagination={false}
          rowKey="model_id"
          size="small"
        />
      </div>
    );
  };

  const columns = [
    { title: '名稱', dataIndex: 'name', key: 'name' },
    { title: '代碼', dataIndex: 'code', key: 'code' },
    { title: 'Base URL', dataIndex: 'base_url', key: 'base_url' },
    {
      title: '排序',
      dataIndex: 'sort_order',
      key: 'sort_order',
      sorter: (a: ModelProvider, b: ModelProvider) => (a.sort_order || 99) - (b.sort_order || 99)
    },
    {
      title: '狀態',
      key: 'status',
      render: (_: any, record: ModelProvider) => (
        <Switch
          checked={record.status === 'enabled'}
          onChange={(checked) => handleStatusChange(checked, record)}
        />
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ModelProvider) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<SyncOutlined spin={syncingKeys[record._key]} />}
            onClick={() => handleSync(record._key)}
            loading={syncingKeys[record._key]}
          >
            同步
          </Button>
          <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(record)}>
            編輯
          </Button>
          <Popconfirm
            title="確定要刪除這個 Provider 嗎？"
            onConfirm={() => handleDelete(record._key)}
            okText="確定"
            cancelText="取消"
          >
            <Button type="text" danger icon={<DeleteOutlined />}>
              刪除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  const handleSyncAll = () => {
    message.info('功能預留中，未來將自動搜尋並更新各 Provider 的最新模型');
  };

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>模型</Title>
        <Space>
          <Button icon={<GlobalOutlined />} onClick={handleSyncAll}>
            同步最新模型
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openAddModal}>
            新增 Provider
          </Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={providers}
        rowKey="_key"
        loading={loading}
        expandable={{
          expandedRowRender,
          expandIcon: ({ expanded, onExpand, record }) =>
            expanded ? (
              <DownOutlined onClick={(e) => onExpand(record, e)} style={{ cursor: 'pointer', marginRight: 8 }} />
            ) : (
              <RightOutlined onClick={(e) => onExpand(record, e)} style={{ cursor: 'pointer', marginRight: 8 }} />
            )
        }}
      />

       <Modal
         title={editingProvider ? '編輯 Provider' : '新增 Provider'}
         open={modalVisible}
         onOk={handleModalOk}
         onCancel={handleModalCancel}
         forceRender
       >
         <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名稱"
            rules={[{ required: true, message: '請輸入名稱' }]}
          >
            <Input placeholder="例如: OpenAI" />
          </Form.Item>
          <Form.Item
            name="code"
            label="代碼"
            rules={[{ required: true, message: '請輸入代碼' }]}
          >
            <Input placeholder="例如: openai" disabled={!!editingProvider} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="請輸入描述" />
          </Form.Item>
          <Form.Item
            name="base_url"
            label="Base URL"
            rules={[{ required: true, message: '請輸入 Base URL' }]}
          >
            <Input placeholder="例如: https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="請輸入 API Key (如不修改請留空)" />
          </Form.Item>
          <Form.Item name="status" label="狀態">
            <Select>
              <Select.Option value="enabled">啟用</Select.Option>
              <Select.Option value="disabled">停用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <Input type="number" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingModel ? '編輯模型' : '新增模型'}
        open={modelModalVisible}
        onOk={handleModelModalOk}
        onCancel={handleModelModalCancel}
        forceRender
      >
        <Form form={modelForm} layout="vertical">
          <Form.Item
            name="model_id"
            label="Model ID"
            rules={[{ required: true, message: '請輸入 Model ID' }]}
          >
            <Input placeholder="例如: gpt-4o" disabled={!!editingModel} />
          </Form.Item>
          <Form.Item
            name="name"
            label="名稱"
            rules={[{ required: true, message: '請輸入名稱' }]}
          >
            <Input placeholder="例如: GPT-4o" />
          </Form.Item>
          <Form.Item name="display_name" label="顯示名稱">
            <Input placeholder="請輸入顯示名稱" />
          </Form.Item>
          <Form.Item name="context_window" label="Context Window">
            <InputNumber style={{ width: '100%' }} placeholder="例如: 128000" />
          </Form.Item>
          <Form.Item name="input_cost_per_1k" label="輸入成本/1k">
            <InputNumber style={{ width: '100%' }} step={0.001} placeholder="例如: 0.005" />
          </Form.Item>
          <Form.Item name="output_cost_per_1k" label="輸出成本/1k">
            <InputNumber style={{ width: '100%' }} step={0.001} placeholder="例如: 0.015" />
          </Form.Item>
          <Form.Item name="supports_vision" label="視覺支援" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="status" label="狀態">
            <Select>
              <Select.Option value="enabled">啟用</Select.Option>
              <Select.Option value="disabled">停用</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
