/**
 * @file        宣告意圖分頁組件
 * @description Agent 宣告意圖（Declared Intents）的 CRUD 管理分頁
 * @lastUpdate  2026-06-20 00:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import { Form, Input, Select, Switch, InputNumber, Button, Space, Table, Tag, Divider, Popconfirm, App, Modal } from 'antd';
import { agentApi, toolApi } from '../services/api';

interface DeclaredIntent {
  _key?: string;
  name: string;
  description?: string;
  keywords?: string[];
  nl_patterns?: string[];
  exclusion_patterns?: string[];
  routing: {
    target_type: 'skill' | 'subagent' | 'handoff' | 'tool';
    target: string;
    parallel?: boolean;
  };
  confidence: {
    auto_route: number;
    verify: number;
  };
  scope?: 'customer' | 'internal' | 'both';
  /** @deprecated 請使用 scope — 後端 AQL 查詢 i.scope */
  scene?: 'customer' | 'internal' | 'both';
  auth?: {
    trust_level?: 'T1' | 'T2' | 'T3' | 'T4';
  };
  priority?: number;
  status: 'enabled' | 'disabled';
}

interface DeclaredIntentTabProps {
  agentKey: string;
}

const scopeOptions = [
  { value: 'customer', label: '客戶端' },
  { value: 'internal', label: '內部' },
  { value: 'both', label: '雙場景' },
];

const targetTypeOptions = [
  { value: 'skill', label: 'Skill' },
  { value: 'subagent', label: 'Subagent' },
  { value: 'handoff', label: 'Handoff' },
  { value: 'tool', label: 'Tool' },
];

const trustLevelOptions = [
  { value: 'T1', label: 'T1' },
  { value: 'T2', label: 'T2' },
  { value: 'T3', label: 'T3' },
  { value: 'T4', label: 'T4' },
];

const SKILL_OPTIONS = [
  { value: 'greeting_engine', label: 'greeting_engine' },
  { value: 'image_processor', label: 'image_processor' },
  { value: 'timeline_engine', label: 'timeline_engine' },
  { value: 'push_engine', label: 'push_engine' },
  { value: 'customer_safe_reply', label: 'customer_safe_reply' },
  { value: 'business_notification', label: 'business_notification' },
  { value: 'crm_query', label: 'crm_query' },
  { value: 'visit_plan', label: 'visit_plan' },
  { value: 'knowledge_agent', label: 'knowledge_agent' },
  { value: 'ragic_timeline_poller', label: 'ragic_timeline_poller' },
  { value: 'contact_share', label: 'contact_share' },
  { value: 'market_subscribe', label: 'market_subscribe' },
];

const statusOptions = [
  { value: 'enabled', label: '啟用' },
  { value: 'disabled', label: '停用' },
];

export default function DeclaredIntentTab({ agentKey }: DeclaredIntentTabProps) {
  const { message } = App.useApp();
  const [intents, setIntents] = useState<DeclaredIntent[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingIntent, setEditingIntent] = useState<DeclaredIntent | null>(null);
  const [intentModalVisible, setIntentModalVisible] = useState(false);
  const [intentForm] = Form.useForm();
  const [agentOptions, setAgentOptions] = useState<{ value: string; label: string }[]>([]);
  const [bpaAgentOptions, setBpaAgentOptions] = useState<{ value: string; label: string }[]>([]);
  const [toolOptions, setToolOptions] = useState<{ value: string; label: string }[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);

  const loadIntents = useCallback(() => {
    if (!agentKey) return;
    setLoading(true);
    agentApi.listIntents(agentKey)
      .then((res: any) => {
        setIntents(res.data.data || []);
      })
      .catch(() => message.error('載入宣告意圖失敗'))
      .finally(() => setLoading(false));
  }, [agentKey, message]);

  useEffect(() => {
    loadIntents();
  }, [loadIntents]);

  useEffect(() => {
    const loadOptions = async () => {
      setLoadingOptions(true);
      try {
        const [agentsRes, bpaRes, toolsRes] = await Promise.all([
          agentApi.list(),
          agentApi.list('bpa'),
          toolApi.list(),
        ]);
        const toOpt = (items: any[]) =>
          items.map((item: any) => ({ value: item._key || item.name, label: item.name || item._key }));
        setAgentOptions(toOpt(agentsRes.data?.data || []));
        setBpaAgentOptions(toOpt(bpaRes.data?.data || []));
        setToolOptions(toOpt(toolsRes.data?.data || []));
      } catch {}
      setLoadingOptions(false);
    };
    loadOptions();
  }, []);

  const handleSave = async () => {
    if (!editingIntent) return;
    if (!agentKey) return;
    try {
      const values = await intentForm.validateFields();
      const merged = { ...editingIntent, ...values };
      if (merged._key) {
        await agentApi.updateIntent(agentKey, merged._key, merged);
        message.success('更新成功');
      } else {
        await agentApi.createIntent(agentKey, merged);
        message.success('新增成功');
      }
      setIntentModalVisible(false);
      setEditingIntent(null);
      intentForm.resetFields();
      loadIntents();
    } catch {
      message.error('儲存失敗');
    }
  };

  const handleDelete = async (intentKey: string) => {
    if (!agentKey) return;
    try {
      await agentApi.deleteIntent(agentKey, intentKey);
      message.success('刪除成功');
      loadIntents();
    } catch {
      message.error('刪除失敗');
    }
  };

  const handleSync = async () => {
    if (!agentKey) return;
    try {
      await agentApi.syncIntents(agentKey);
      message.success('同步成功');
    } catch {
      message.error('同步失敗');
    }
  };

const scopeColorMap: Record<string, string> = {
  customer: 'blue',
  internal: 'purple',
  both: 'green',
};

const scopeLabelMap: Record<string, string> = {
  customer: '客戶端',
  internal: '內部',
  both: '雙場景',
};

  const trustColorMap: Record<string, string> = {
    T1: 'default',
    T2: 'blue',
    T3: 'orange',
    T4: 'red',
  };

  const columns = [
    {
      title: '#',
      key: 'index',
      width: 50,
      render: (_: any, __: any, idx: number) => idx + 1,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (t: string) => t || '-',
    },
    {
      title: '場景',
      dataIndex: 'scope',
      key: 'scope',
      width: 100,
      render: (s: string) =>
        s ? <Tag color={scopeColorMap[s] || 'default'}>{scopeLabelMap[s] || s}</Tag> : '-',
    },
    {
      title: '路由目標',
      key: 'routing_target',
      width: 200,
      render: (_: any, record: DeclaredIntent) => {
        const r = record.routing;
        if (!r?.target_type || !r?.target) return '-';
        return `${r.target_type}: ${r.target}`;
      },
    },
    {
      title: '置信度',
      key: 'confidence',
      width: 70,
      render: (_: any, record: DeclaredIntent) => {
        const c = record.confidence;
        if (!c?.auto_route) return '-';
        return c.auto_route.toFixed(2);
      },
    },
    {
      title: 'Trust',
      key: 'trust_level',
      width: 80,
      render: (_: any, record: DeclaredIntent) => {
        const tl = record.auth?.trust_level;
        return tl ? <Tag color={trustColorMap[tl] || 'default'}>{tl}</Tag> : '-';
      },
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: string) => (
        <Tag color={s === 'enabled' ? 'green' : 'red'}>
          {s === 'enabled' ? '啟用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '關鍵詞',
      key: 'keywords',
      width: 60,
      render: (_: any, record: DeclaredIntent) => {
        const k = record.keywords;
        return k?.length ? `${k.length} 個` : '-';
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: DeclaredIntent) => (
        <Space>
            <Button
              size="small"
              onClick={() => {
                setEditingIntent(record);
                setIntentModalVisible(true);
              }}
            >
              編輯
            </Button>
          <Popconfirm
            title="確認刪除此宣告意圖？"
            onConfirm={() => record._key && handleDelete(record._key)}
          >
            <Button size="small" danger>刪除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        <Button
          type="primary"
          onClick={() => {
            setEditingIntent({ name: '', routing: { target_type: 'skill', target: '' }, confidence: { auto_route: 0.85, verify: 0.6 }, status: 'enabled' });
            setIntentModalVisible(true);
          }}
        >
          新增意圖
        </Button>
        <Button onClick={handleSync}>同步到 Qdrant</Button>
      </div>

      <Modal
        title={editingIntent?._key ? '編輯意圖' : '新增意圖'}
        open={intentModalVisible}
        width={850}
        onCancel={() => { setIntentModalVisible(false); setEditingIntent(null); intentForm.resetFields(); }}
        footer={[
          <Button key="cancel" onClick={() => { setIntentModalVisible(false); setEditingIntent(null); intentForm.resetFields(); }}>取消</Button>,
          <Button key="save" type="primary" onClick={handleSave}>儲存</Button>,
        ]}
      >
        <Form form={intentForm} layout="vertical" initialValues={editingIntent || undefined}>
          <Space style={{ width: '100%' }}>
            <Form.Item name="name" label="名稱" rules={[{ required: true, message: '請輸入意圖名稱' }]} style={{ width: 220 }}>
              <Input placeholder="例如：greeting_customer" />
            </Form.Item>
            <Form.Item name="description" label="描述" style={{ flex: 2 }}>
              <Input placeholder="描述此意圖的用途" />
            </Form.Item>
            <Form.Item name={['scope']} label="場景" style={{ width: 130 }}>
              <Select options={scopeOptions} allowClear placeholder="選擇場景" />
            </Form.Item>
          </Space>

          <Divider style={{ margin: '12px 0' }}>路由配置</Divider>

          <Space style={{ width: '100%' }}>
            <Form.Item name={['routing', 'target_type']} label="路由類型" style={{ width: 160 }}>
              <Select options={targetTypeOptions} placeholder="選擇路由類型" />
            </Form.Item>
            <Form.Item shouldUpdate={(prev, curr) => prev.routing?.target_type !== curr.routing?.target_type} noStyle>
              {({ getFieldValue }) => {
                const type = getFieldValue(['routing', 'target_type']);
                let options: { value: string; label: string }[] | undefined;
                let placeholder = '請先選擇路由類型';

                if (type === 'skill') {
                  options = SKILL_OPTIONS;
                  placeholder = '選擇技能';
                } else if (type === 'subagent') {
                  options = agentOptions;
                  placeholder = loadingOptions ? '載入中...' : '選擇智能體';
                } else if (type === 'handoff') {
                  options = bpaAgentOptions;
                  placeholder = loadingOptions ? '載入中...' : '選擇 BPA Agent';
                } else if (type === 'tool') {
                  options = toolOptions;
                  placeholder = loadingOptions ? '載入中...' : '選擇工具';
                }

                return (
                  <Form.Item name={['routing', 'target']} label="路由目標" style={{ width: 260 }}>
                    {options ? (
                      <Select
                        options={options}
                        placeholder={placeholder}
                        loading={loadingOptions && type !== 'skill'}
                        allowClear
                      />
                    ) : (
                      <Input placeholder={placeholder} />
                    )}
                  </Form.Item>
                );
              }}
            </Form.Item>
            <Form.Item name={['routing', 'parallel']} label="並行派發" valuePropName="checked" style={{ width: 120 }}>
              <Switch />
            </Form.Item>
          </Space>

          <Divider style={{ margin: '12px 0' }}>信心度門檻</Divider>

          <Space style={{ width: '100%' }}>
            <Form.Item name={['confidence', 'auto_route']} label="自動路由置信度" style={{ width: 130 }}>
              <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name={['confidence', 'verify']} label="LLM驗證門檻" style={{ width: 130 }}>
              <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Divider style={{ margin: '12px 0' }}>權限與優先級</Divider>

          <Space style={{ width: '100%' }}>
            <Form.Item name={['auth', 'trust_level']} label="信任等級" style={{ width: 160 }}>
              <Select options={trustLevelOptions} allowClear placeholder="選擇等級" />
            </Form.Item>
            <Form.Item name="priority" label="優先級" style={{ width: 120 }}>
              <InputNumber min={0} max={100} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="status" label="狀態" style={{ width: 120 }}>
              <Select options={statusOptions} />
            </Form.Item>
          </Space>

          <Divider style={{ margin: '12px 0' }}>匹配配置</Divider>

          <Form.Item name="keywords" label="關鍵詞">
            <Select
              mode="tags"
              placeholder="逗號分隔，例如：早安,晚安,你好"
              tokenSeparators={[',']}
              open={false}
              suffixIcon={null}
            />
          </Form.Item>
          <Form.Item name="nl_patterns" label="自然語言範例">
            <Select
              mode="tags"
              placeholder="每行一個範例"
              tokenSeparators={[',', '\n']}
              open={false}
              suffixIcon={null}
            />
          </Form.Item>
          <Form.Item name="exclusion_patterns" label="排除模式">
            <Select
              mode="tags"
              placeholder="每行一個負面範例"
              tokenSeparators={[',', '\n']}
              open={false}
              suffixIcon={null}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Table
        dataSource={intents}
        columns={columns}
        rowKey={(record) => record._key || record.name}
        loading={loading}
        pagination={false}
        scroll={{ y: 600 }}
        size="small"
      />
    </>
  );
}
