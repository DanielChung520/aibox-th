/**
 * @file        Agent 表單組件
 * @description Agent 創建/編輯 Modal，包含基本資訊、權限配置、模型配置
 * @lastUpdate  2026-03-18 08:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useEffect, useState } from 'react';
import { Modal, Form, Input, Select, Switch, InputNumber, Tabs, Button, Space, App, Radio, Table, Popconfirm, Tag, Divider } from 'antd';
import { iconMap } from '../utils/icons';
import IconPicker from './IconPicker';
import { roleApi, knowledgeApi, toolApi, daApi, agentApi } from '../services/api';
import DemandTab from './DemandTab';
import { trackModal, trackAgentAction } from '../utils/analytics';
import { pageContextManager } from '../services/PageContextManager';

interface Agent {
  id: string;
  _key?: string;
  name: string;
  description: string;
  icon: string;
  status: 'registering' | 'online' | 'maintenance' | 'deprecated' | 'developing';
  usageCount: number;
  groupKey?: string;
  agentType?: string;
  source?: 'local' | 'third_party';
  endpointUrl?: string;
  apiKey?: string;
  authType?: 'none' | 'bearer' | 'basic' | 'oauth2';
  llmModel?: string;
  temperature?: number;
  maxTokens?: number;
  systemPrompt?: string;
  knowledgeBases?: string[];
  dataSources?: string[];
  tools?: string[];
  openingLines?: string[];
  capabilities?: string[];
  visibility?: 'public' | 'private' | 'role';
  visibility_roles?: string[];
  group_key?: string;
  agent_type?: string;
  endpoint_url?: string;
  api_key?: string;
  auth_type?: string;
  llm_model?: string;
  max_tokens?: number;
  system_prompt?: string;
  knowledge_bases?: string[];
  data_sources?: string[];
  opening_lines?: string[];
}

const { TextArea } = Input;

const statusOptions = [
  { value: 'online', label: '在線' },
  { value: 'maintenance', label: '維修中' },
  { value: 'deprecated', label: '已作廢' },
];

const agentTypeOptions = [
  { value: 'knowledge', label: '知識代理' },
  { value: 'data', label: '資料代理' },
  { value: 'bpa', label: 'BPA代理' },
  { value: 'tool', label: '工具代理' },
];

const authTypeOptions = [
  { value: 'none', label: '無' },
  { value: 'bearer', label: 'Bearer Token' },
  { value: 'basic', label: 'Basic Auth' },
  { value: 'oauth2', label: 'OAuth 2.0' },
];

const llmModelOptions = [
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  { value: 'llama3', label: 'Llama 3' },
  { value: 'llama2', label: 'Llama 2' },
  { value: 'mistral', label: 'Mistral' },
  { value: 'claude-3', label: 'Claude 3' },
];

interface AgentFormModalProps {
  open: boolean;
  agent?: Agent | null;
  mode: 'create' | 'edit';
  onCancel: () => void;
  onSubmit: (values: Partial<Agent>) => void;
  onDelete?: (agentId: string) => void;
  groupKey?: string;
  defaultAgentType?: string;
}

export default function AgentFormModal({ 
  open, 
  agent, 
  mode, 
  onCancel,
  onSubmit,
  onDelete,
  groupKey,
  defaultAgentType = 'tool',
}: AgentFormModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [iconPickerVisible, setIconPickerVisible] = useState(false);
  const [isThirdParty, setIsThirdParty] = useState(false);
  const [roles, setRoles] = useState<{ value: string; label: string }[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<{ value: string; label: string }[]>([]);
  const [tools, setTools] = useState<{ value: string; label: string }[]>([]);
  const [dataSources, setDataSources] = useState<{ value: string; label: string }[]>([]);
  const [visibility, setVisibility] = useState<'public' | 'private' | 'role'>('private');
  const [intents, setIntents] = useState<any[]>([]);
  const [intentsLoading, setIntentsLoading] = useState(false);
  const [editingIntent, setEditingIntent] = useState<any | null>(null);
  const [intentForm] = Form.useForm();
  const [demandKey, setDemandKey] = useState<string | null>(null);
  const [demandStatusColor, setDemandStatusColor] = useState<string>('#fa8c16');
  const [currentDemand, setCurrentDemand] = useState<any>(null);

  const loadIntents = (agentKey: string) => {
    setIntentsLoading(true);
    agentApi.listIntents(agentKey).then((res: any) => {
      setIntents(res.data.data || []);
    }).catch(() => {
      message.error('載好意圖失敗');
    }).finally(() => setIntentsLoading(false));
  };

  useEffect(() => {
    roleApi.list().then((res: any) => {
      const opts = (res.data.data || []).map((r: any) => ({ value: r._key, label: r.name }));
      setRoles(opts);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (open) {
      knowledgeApi.listRoots().then((res: any) => {
        const opts = (res.data.data || []).map((kb: any) => ({ value: kb._key, label: kb.name }));
        setKnowledgeBases(opts);
      }).catch(() => {});
      toolApi.list().then((res: any) => {
        const opts = (res.data.data || []).map((t: any) => ({ value: t._key, label: t.name }));
        setTools(opts);
      }).catch(() => {});
      daApi.listSchemaModules().then((res: any) => {
        const opts = (res.data.data || []).map((m: any) => ({ value: m.key, label: `${m.label} (${m.source})` }));
        setDataSources(opts);
      }).catch(() => {});
    }
  }, [open]);

  useEffect(() => {
    if (open) {
      const detail = {
        modal: 'AgentFormModal',
        mode,
        agent_key: agent?._key || agent?.id,
        agent_name: agent?.name,
        demand: currentDemand ? {
          key: currentDemand._key,
          goal: currentDemand.goal,
          expected_effect: currentDemand.expected_effect,
          problem_description: currentDemand.problem_description,
          status: currentDemand.status,
        } : null,
        action: 'open',
      };
      trackModal('AgentFormModal', 'open', { mode, agent_key: agent?._key || agent?.id, agent_name: agent?.name });
      window.dispatchEvent(new CustomEvent('modal-context-change', { detail }));
      pageContextManager.report({
        component: 'AgentFormModal',
        componentName: agent?.name,
        entity: currentDemand?.goal,
        entityType: 'demand',
        action: 'editing',
        data: { agent_key: agent?._key || agent?.id, demand: currentDemand },
      });
    }
    return () => {
      if (open) {
        const detail = {
          modal: 'AgentFormModal',
          mode,
          agent_key: agent?._key || agent?.id,
          agent_name: agent?.name,
          demand: currentDemand ? {
            key: currentDemand._key,
            goal: currentDemand.goal,
            expected_effect: currentDemand.expected_effect,
            problem_description: currentDemand.problem_description,
            status: currentDemand.status,
          } : null,
          action: 'close',
        };
        trackModal('AgentFormModal', 'close', { mode, agent_key: agent?._key || agent?.id, agent_name: agent?.name });
        window.dispatchEvent(new CustomEvent('modal-context-change', { detail }));
        pageContextManager.report({ component: undefined, action: undefined });
      }
    };
  }, [open, mode, currentDemand]);

  useEffect(() => {
    if (open && agent && mode === 'edit') {
      form.setFieldsValue({
        ...agent,
        agentType: agent.agentType || agent.agent_type || defaultAgentType,
        groupKey: agent.groupKey || agent.group_key || 'productivity',
        endpointUrl: agent.endpointUrl || agent.endpoint_url || '',
        apiKey: agent.apiKey || agent.api_key || '',
        llmModel: agent.llmModel || agent.llm_model || '',
        maxTokens: agent.maxTokens ?? agent.max_tokens ?? 2000,
        systemPrompt: agent.systemPrompt || agent.system_prompt || '',
        knowledgeBases: agent.knowledgeBases || agent.knowledge_bases || [],
        dataSources: agent.dataSources || agent.data_sources || [],
        source: agent.source || 'local',
        authType: agent.authType || agent.auth_type || 'none',
        openingLines: agent.openingLines || agent.opening_lines || [],
        visibility: agent.visibility || 'private',
        visibility_roles: agent.visibility_roles || [],
      });
      setVisibility(agent.visibility || 'private');
      setIsThirdParty(agent.source === 'third_party');
      loadIntents(agent.id || agent._key || '');

      const agentKey = agent.id || agent._key || '';
      agentApi.listDemands(agentKey).then((res: any) => {
        const demands = res.data.data || [];
        if (demands.length > 0) {
          const latestDemand = demands[0];
          setDemandKey(latestDemand._key);
        } else {
          agentApi.createDemand(agentKey, {
            goal: '',
            expected_effect: '',
            problem_description: '',
          }).then((res2: any) => {
            const newKey = res2.data.data?._key;
            if (newKey) setDemandKey(newKey);
          }).catch(() => {});
        }
      }).catch(() => {});
    } else if (open && mode === 'create') {
      form.setFieldsValue({
        status: 'online',
        source: 'local',
        authType: 'none',
        groupKey: groupKey || 'productivity',
        knowledgeBases: [],
        dataSources: [],
        tools: [],
        openingLines: [],
        capabilities: [],
        temperature: 0.7,
        maxTokens: 2000,
        visibility: 'private',
        visibility_roles: [],
      });
      setVisibility('private');
      setIsThirdParty(false);
    }
  }, [open, agent, mode, form, groupKey]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      trackAgentAction(mode === 'create' ? 'create' : 'update', agent?._key || agent?.id || '', agent?.name);
      onSubmit(values);
    } catch (err) {
      message.error('請填寫必填欄位');
    }
  };

  const handleDelete = () => {
    if (agent?.id && onDelete) {
      Modal.confirm({
        title: '確認刪除',
        content: `確定要刪除 Agent「${agent.name}」嗎？此操作無法復原。`,
        okText: '刪除',
        okType: 'danger',
        cancelText: '取消',
        onOk: () => {
          trackAgentAction('delete', agent.id, agent.name);
          onDelete(agent.id);
        },
      });
    }
  };

  const IconPreview = () => {
    const iconValue = form.getFieldValue('icon');
    const IconComp = iconValue ? iconMap[iconValue] : null;
    return IconComp ? <IconComp style={{ fontSize: 20 }} /> : null;
  };

  const infoTabItems = [
    {
      key: 'basic',
      label: '基本資訊',
      children: (
        <>
          <Form.Item label="圖標">
            <Space>
              <Button onClick={() => setIconPickerVisible(true)}>
                <Space>
                  <IconPreview />
                  選擇圖標
                </Space>
              </Button>
              <span>{form.getFieldValue('icon') || '未設置'}</span>
            </Space>
          </Form.Item>
          <Form.Item name="name" label="名稱" rules={[{ required: true, message: '請輸入名稱' }]}>
            <Input placeholder="例如：文檔處理助手" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} placeholder="描述這個 Agent 的用途..." />
          </Form.Item>
          <Form.Item name="status" label="狀態" initialValue="online">
            <Select options={statusOptions} />
          </Form.Item>
        </>
      ),
    },
    {
      key: 'category',
      label: '分類',
      children: (
        <>
          <Form.Item name="agentType" label="類型" initialValue={defaultAgentType}>
            <Select options={agentTypeOptions} placeholder="選擇 Agent 類型" />
          </Form.Item>
          <Form.Item name="groupKey" label="分組 Key">
            <Input placeholder="例如：productivity, finance, inventory" />
          </Form.Item>
        </>
      ),
    },
    {
      key: 'source',
      label: '來源',
      children: (
        <>
          <Form.Item name="source" label="來源" valuePropName="checked">
            <Switch 
              checkedChildren="第三方" 
              unCheckedChildren="本機" 
              defaultChecked={false}
              onChange={(checked) => setIsThirdParty(checked)}
            />
          </Form.Item>
          <Form.Item 
            name="endpointUrl" 
            label="Endpoint URL" 
            rules={[{ required: true, message: '請輸入 Endpoint URL' }]}
          >
            <Input placeholder={isThirdParty ? 'https://api.example.com/agent' : 'http://localhost:8000'} />
          </Form.Item>
          {isThirdParty && (
            <>
              <Form.Item name="apiKey" label="API Key">
                <Input.Password placeholder="第三方 API Key" />
              </Form.Item>
              <Form.Item name="authType" label="認證方式" initialValue="none">
                <Select options={authTypeOptions} />
              </Form.Item>
            </>
          )}
        </>
      ),
    },
  ];

  const permissionTab = (
    <>
      <Form.Item label="可見性" name="visibility" initialValue="private">
        <Radio.Group value={visibility} onChange={(e) => setVisibility(e.target.value)}>
          <Radio.Button value="public">公開</Radio.Button>
          <Radio.Button value="private">私人</Radio.Button>
          <Radio.Button value="role">按角色</Radio.Button>
        </Radio.Group>
      </Form.Item>
      {visibility === 'role' && (
        <Form.Item label="可見角色" name="visibility_roles">
          <Select mode="multiple" placeholder="選擇可見的角色" options={roles} />
        </Form.Item>
      )}
      <Form.Item name="knowledgeBases" label="知識庫權限">
        <Select
          mode="multiple"
          placeholder="選擇可存取的知識庫"
          options={knowledgeBases}
        />
      </Form.Item>
      <Form.Item name="dataSources" label="資料權限">
        <Select
          mode="multiple"
          placeholder="選擇可存取的資料來源"
          options={dataSources}
        />
      </Form.Item>
      <Form.Item name="tools" label="工具權限">
        <Select
          mode="multiple"
          placeholder="選擇可使用的工具"
          options={tools}
        />
      </Form.Item>
    </>
  );

  const modelTab = (
    <>
      <Form.Item name="llmModel" label="LLM 模型">
        <Select options={llmModelOptions} placeholder="選擇模型" />
      </Form.Item>
      <Form.Item name="temperature" label="Temperature" initialValue={0.7}>
        <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item name="maxTokens" label="最大 Tokens" initialValue={2000}>
        <InputNumber min={100} max={32000} step={100} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item name="systemPrompt" label="System Prompt">
        <TextArea rows={4} placeholder="輸入系統提示詞..." />
      </Form.Item>
    </>
  );

  const chatTab = (
    <>
      <Form.Item name="openingLines" label="開場白">
        <Select
          mode="tags"
          placeholder="輸入開場白，按 Enter 確認"
        />
      </Form.Item>
      <Form.Item name="capabilities" label="能力描述">
        <Select
          mode="tags"
          placeholder="輸入能力描述，按 Enter 確認"
        />
      </Form.Item>
    </>
  );

  const handleSaveIntent = async () => {
    if (!editingIntent) return;
    const key = agent?.id || agent?._key || '';
    if (!key) return;
    try {
      if (editingIntent._key) {
        await agentApi.updateIntent(key, editingIntent._key, editingIntent);
        message.success('更新成功');
      } else {
        await agentApi.createIntent(key, editingIntent);
        message.success('新增成功');
      }
      setEditingIntent(null);
      intentForm.resetFields();
      loadIntents(key);
    } catch {
      message.error('儲存失敗');
    }
  };

  const handleDeleteIntent = async (intentKey: string) => {
    const key = agent?.id || agent?._key || '';
    if (!key) return;
    try {
      await agentApi.deleteIntent(key, intentKey);
      message.success('刪除成功');
      loadIntents(key);
    } catch {
      message.error('刪除失敗');
    }
  };

  const handleSyncIntents = async () => {
    const key = agent?.id || agent?._key || '';
    if (!key) return;
    try {
      await agentApi.syncIntents(key);
      message.success('同步成功');
    } catch {
      message.error('同步失敗');
    }
  };

  const handleAISuggestIntents = async () => {
    const key = agent?.id || agent?._key || '';
    if (!key) return;
    if (!demandKey) {
      message.warning('請先儲存需求後再使用此功能');
      return;
    }
    try {
      const hide = message.loading('AI 正在分析需求，生成建議意圖...', 0);
      const response = await agentApi.suggestIntents(key, demandKey);
      hide();
      const suggestedIntents = response.data.data || [];
      if (suggestedIntents.length === 0) {
        message.info('AI 未生成建議意圖，請確認需求內容是否足夠詳細');
        return;
      }
      const newIntents = [...intents];
      for (const intent of suggestedIntents) {
        const exists = newIntents.some(
          (i) => i.name === intent.name || i.description === intent.description
        );
        if (!exists) {
          newIntents.push({ ...intent, _key: `temp_${Date.now()}_${Math.random()}` });
        }
      }
      setIntents(newIntents);
      message.success(`已新增 ${suggestedIntents.length} 個建議意圖`);
    } catch {
      message.error('生成建議失敗');
    }
  };

  const intentColumns = [
    { title: '名稱', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '動作類型',
      dataIndex: 'action_type',
      key: 'action_type',
      width: 120,
      render: (t: string) => {
        const map: Record<string, string> = { direct_answer: '直接回答', tool_call: '工具調用', process_orchestration: '流程編排' };
        return map[t] || '-';
      },
    },
    {
      title: '目標工具',
      dataIndex: 'tool_name',
      key: 'tool_name',
      width: 120,
      render: (t: string) => t || '-',
    },
    {
      title: '響應策略',
      dataIndex: 'response_strategy',
      key: 'response_strategy',
      width: 100,
      render: (t: string) => {
        const map: Record<string, string> = { direct_llm: '直接回答', confirm_then_execute: '確認後執行', clarify_first: '先釐清', handoff_bpa: '轉交BPA' };
        return map[t] || '-';
      },
    },
    { title: '優先級', dataIndex: 'priority', key: 'priority', width: 80 },
    {
      title: '範例',
      dataIndex: 'nl_examples',
      key: 'nl_examples',
      width: 80,
      render: (arr: string[]) => arr?.length ? `${arr.length} 個` : '-',
    },
    {
      title: '模式',
      dataIndex: 'nl_patterns',
      key: 'nl_patterns',
      width: 80,
      render: (arr: string[]) => arr?.length ? `${arr.length} 個` : '-',
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: string) => <Tag color={s === 'enabled' ? 'green' : 'default'}>{s === 'enabled' ? '啟用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: any) => (
        <Space>
          <Button size="small" onClick={() => { setEditingIntent(record); intentForm.setFieldsValue(record); }}>編輯</Button>
          <Popconfirm title="確認刪除？" onConfirm={() => handleDeleteIntent(record._key)}>
            <Button size="small" danger>刪除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const intentsTab = (
    <>
      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        <Button
          type="primary"
          onClick={() => {
            setEditingIntent({ name: '', description: '', priority: 0, status: 'enabled', nl_examples: [], nl_patterns: [], action_type: undefined, tool_category: undefined, tool_name: undefined, response_strategy: undefined, target_agent: undefined, requires_approval: false });
            intentForm.resetFields();
          }}
        >
          新增意圖
        </Button>
        <Button onClick={handleSyncIntents}>同步到 Qdrant</Button>
        <Button onClick={handleAISuggestIntents} disabled={!demandKey}>🤖 AI大神給建議</Button>
      </div>
      {editingIntent && (
        <div style={{ border: '1px solid #d9d9d9', padding: 16, marginBottom: 16, borderRadius: 8 }}>
          <h4>{editingIntent._key ? '編輯意圖' : '新增意圖'}</h4>
          <Form form={intentForm} layout="vertical" initialValues={editingIntent} component="div">
            <Space style={{ width: '100%' }}>
              <Form.Item name="name" label="名稱" rules={[{ required: true }]} style={{ width: 200 }}>
                <Input placeholder="例如：查詢庫存" />
              </Form.Item>
              <Form.Item name="description" label="描述" style={{ flex: 1 }}>
                <Input placeholder="描述這個意圖的用途" />
              </Form.Item>
              <Form.Item name="priority" label="優先級" style={{ width: 100 }}>
                <InputNumber min={0} max={100} defaultValue={0} />
              </Form.Item>
              <Form.Item name="status" label="狀態" style={{ width: 120 }}>
                <Select
                  options={[
                    { value: 'enabled', label: '啟用' },
                    { value: 'disabled', label: '停用' },
                  ]}
                />
              </Form.Item>
            </Space>

            <Divider style={{ margin: '12px 0' }}>匹配配置</Divider>

            <Form.Item name="nl_examples" label="範例語句" style={{ marginBottom: 8 }}>
              <Input placeholder="每行一個範例，例如：還有多少庫存" />
            </Form.Item>
            <Form.Item name="nl_patterns" label="匹配模式" style={{ marginBottom: 8 }}>
              <Input placeholder="每行一個模式，例如：庫存.*查|.*數量.*" />
            </Form.Item>

            <Divider style={{ margin: '12px 0' }}>動作配置</Divider>

            <Space style={{ width: '100%' }}>
              <Form.Item name="action_type" label="動作類型" style={{ width: 180 }}>
                <Select
                  allowClear
                  placeholder="選擇動作類型"
                  options={[
                    { value: 'direct_answer', label: '直接回答' },
                    { value: 'tool_call', label: '工具調用' },
                    { value: 'process_orchestration', label: '流程編排' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="tool_category" label="工具類別" style={{ width: 150 }}>
                <Select
                  allowClear
                  placeholder="選擇類別"
                  options={[
                    { value: 'web_search', label: '網路搜尋' },
                    { value: 'data', label: '資料查詢' },
                    { value: 'knowledge', label: '知識庫' },
                    { value: 'mcp', label: 'MCP工具' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="tool_name" label="目標工具" style={{ width: 180 }}>
                <Input placeholder="工具名稱" />
              </Form.Item>
              <Form.Item name="target_agent" label="目標代理" style={{ width: 120 }}>
                <Select
                  allowClear
                  placeholder="選擇代理"
                  options={[
                    { value: 'chat', label: 'Chat' },
                    { value: 'tool', label: 'Tool' },
                    { value: 'pdca', label: 'PDCA' },
                    { value: 'bpa', label: 'BPA' },
                    { value: 'ca', label: 'CA' },
                  ]}
                />
              </Form.Item>
            </Space>

            <Space style={{ width: '100%' }}>
              <Form.Item name="response_strategy" label="響應策略" style={{ width: 180 }}>
                <Select
                  allowClear
                  placeholder="選擇策略"
                  options={[
                    { value: 'direct_llm', label: '直接回答' },
                    { value: 'confirm_then_execute', label: '確認後執行' },
                    { value: 'clarify_first', label: '先釐清' },
                    { value: 'handoff_bpa', label: '轉交BPA' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="requires_approval" label="需要審批" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Space>

            <Space style={{ marginTop: 12 }}>
              <Button type="primary" onClick={handleSaveIntent}>儲存</Button>
              <Button onClick={() => { setEditingIntent(null); intentForm.resetFields(); }}>取消</Button>
            </Space>
          </Form>
        </div>
      )}
      <Table
        dataSource={intents}
        columns={intentColumns}
        rowKey="_key"
        loading={intentsLoading}
        pagination={false}
        size="small"
      />
    </>
  );

  return (
    <>
        <Modal
          title={
            <span>{mode === 'create' ? '新增 Agent' : `編輯 Agent${agent?.name ? ` — ${agent.name}` : ''}`}</span>
          }
          open={open}
         onCancel={onCancel}
width="60vw"
          style={{ top: 20 }}
          styles={{ body: { minHeight: '60vh' } }}
          forceRender
         footer={
           <Space>
             {mode === 'edit' && onDelete && (
               <Button danger onClick={handleDelete}>
                 刪除
               </Button>
             )}
             <Button onClick={onCancel}>取消</Button>
             <Button type="primary" onClick={handleSubmit}>
               {mode === 'create' ? '建立' : '儲存'}
             </Button>
           </Space>
         }
       >
         <Form form={form} layout="vertical">
          <Tabs 
            defaultActiveKey="basic" 
            items={[
              ...infoTabItems,
              {
                key: 'permission',
                label: '權限配置',
                children: permissionTab,
              },
              {
                key: 'model',
                label: '模型配置',
                children: modelTab,
              },
              {
                key: 'chat',
                label: '對話配置',
                children: chatTab,
              },
              {
                key: 'intents',
                label: '意圖表',
                children: intentsTab,
              },
              ...(mode === 'edit' && demandKey ? [{
                key: 'demand',
                label: (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    需求
                    <span style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: demandStatusColor,
                      display: 'inline-block',
                    }} />
                  </span>
                ),
                children: (
                  <DemandTab
                    agentKey={agent?.id || agent?._key || ''}
                    demandKey={demandKey}
                    onStatusChange={setDemandStatusColor}
                    onDemandChange={setCurrentDemand}
                  />
                ),
              }] : []),
            ]}
          />
        </Form>
      </Modal>
      <IconPicker
        open={iconPickerVisible}
        onCancel={() => setIconPickerVisible(false)}
        onSelect={(icon) => form.setFieldValue('icon', icon)}
      />
    </>
  );
}
