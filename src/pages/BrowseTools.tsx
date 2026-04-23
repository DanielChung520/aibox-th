/**
 * @file        工具註冊頁面
 * @description 效率工具註冊管理，支持卡片與表格混合視圖，admin 授權控制
 * @lastUpdate  2026-03-28 10:22:08
 * @author      Daniel Chung
 * @version     2.0.0
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, Input, Row, Col, Button, Empty, App, Spin, Table, Tag, Tooltip, Space, Segmented } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { 
  SearchOutlined, PlusOutlined, ReloadOutlined,
  AppstoreOutlined, UnorderedListOutlined,
  SafetyCertificateOutlined, CheckCircleOutlined, StopOutlined,
  EditOutlined, DeleteOutlined, ToolOutlined,
} from '@ant-design/icons';
import AgentCard from '../components/AgentCard';
import ToolFormModal from '../components/ToolFormModal';
import { toolApi, Tool, authApi } from '../services/api';
import { authStore } from '../stores/auth';
import { useContentTokens } from '../contexts/AppThemeProvider';
import { iconMap } from '../utils/icons';

const groupConfig = [
  { key: 'all', label: '全部' },
  { key: 'oracle', label: '深度顧問' },
  { key: 'advisor', label: '顧問代理' },
  { key: 'weather', label: '天氣工具' },
  { key: 'search', label: '搜尋工具' },
  { key: 'data', label: '數據處理' },
  { key: 'messaging', label: '通信工具' },
  { key: 'utility', label: '實用工具' },
];

export default function BrowseTools() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const contentTokens = useContentTokens();
  const [currentUser, setCurrentUser] = useState(authStore.getState().user);
  const isAdmin = (currentUser as any)?.role_keys?.includes('admin') || currentUser?.role_key === 'admin';
  console.log('[DEBUG] currentUser:', currentUser);
  console.log('[DEBUG] isAdmin:', isAdmin);
  const [activeTab, setActiveTab] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'card' | 'table'>('card');
  const [tools, setTools] = useState<Tool[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<Tool | null>(null);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');

  // 重新獲取用戶資料（如果 token 存在但 user 為空）
  useEffect(() => {
    const state = authStore.getState();
    if (!state.user && state.token) {
      authApi.me().then((res: { data?: { data?: { _key: string; username: string; name: string; role_key: string; role_name: string; tier?: string } } }) => {
        const userData = res?.data?.data;
        if (userData) {
          authStore.login(userData as any, state.token!);
          setCurrentUser(userData);
        }
      }).catch(() => {});
    }
  }, []);

  // 監聽 authStore 變化
  useEffect(() => {
    const unsubscribe = authStore.subscribe(() => {
      setCurrentUser(authStore.getState().user);
    });
    return unsubscribe;
  }, []);

  const fetchTools = async () => {
    setLoading(true);
    try {
      const res = await toolApi.list();
      setTools(res.data.data || []);
    } catch (err) {
      console.error('Failed to fetch tools:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTools();
  }, []);

  const isAuthorized = (tool: Tool): boolean => {
    const vis = tool.visibility || 'public';
    if (vis === 'public') return true;
    if (vis === 'account') return (tool.visibility_accounts || []).includes(currentUser?.username || '');
    if (vis === 'role') return (tool.visibility_roles || []).includes(currentUser?.role_key || '');
    return false;
  };

  const mapToolToCard = (tool: Tool) => ({
    id: tool._key || '',
    name: tool.name,
    description: tool.description || '',
    icon: tool.icon || 'ToolOutlined',
    status: (tool.status || 'online') as 'online' | 'maintenance' | 'deprecated' | 'registering',
    usageCount: tool.usage_count || 0,
    groupKey: tool.group_key || 'utility',
  });

  const filteredTools = tools.filter((tool) => {
    if (activeTab !== 'all') {
      if (activeTab === 'oracle') {
        if (tool.tool_type !== 'oracle') return false;
      } else if (tool.group_key !== activeTab) {
        return false;
      }
    }
    if (searchText) {
      const search = searchText.toLowerCase();
      return (
        tool.name.toLowerCase().includes(search) ||
        (tool.description || '').toLowerCase().includes(search)
      );
    }
    return true;
  });

  const handleAuth = (toolKey: string) => {
    const tool = tools.find((t) => t._key === toolKey);
    setEditingTool(tool || null);
    setModalMode('edit');
    setModalOpen(true);
  };

  const handleEdit = (toolKey: string) => {
    const tool = tools.find((t) => t._key === toolKey);
    setEditingTool(tool || null);
    setModalMode('edit');
    setModalOpen(true);
  };

  const handleDelete = async (toolKey: string) => {
    try {
      await toolApi.delete(toolKey);
      message.success('刪除成功');
      fetchTools();
    } catch (err) {
      console.error('Failed to delete tool:', err);
      message.error('刪除失敗');
    }
  };

  const handleSyncIntents = async (toolKey: string, data: { intent_tags: string[]; nl_examples: string[] }) => {
    try {
      await toolApi.syncIntents(toolKey, data);
    } catch (err) {
      console.error('Failed to sync intents:', err);
      throw err;
    }
  };

  const handleCreate = () => {
    setEditingTool(null);
    setModalMode('create');
    setModalOpen(true);
  };

  const handleFormSubmit = async (values: Partial<Tool>) => {
    try {
      const apiData: Record<string, unknown> = {
        code: values.code,
        name: values.name,
        description: values.description || '',
        tool_type: values.tool_type || 'custom',
        icon: values.icon || '',
        status: values.status || 'online',
        group_key: values.group_key || activeTab,
        intent_tags: values.intent_tags || [],
        endpoint_url: values.endpoint_url || '',
        input_schema: values.input_schema,
        output_schema: values.output_schema,
        timeout_ms: values.timeout_ms ?? 30000,
        llm_model: values.llm_model || '',
        temperature: values.temperature ?? 0.7,
        max_tokens: values.max_tokens ?? 2000,
        visibility: values.visibility || 'public',
        visibility_roles: values.visibility_roles || [],
        visibility_accounts: values.visibility_accounts || [],
      };
      if (modalMode === 'create') {
        apiData.created_by = currentUser?.username || 'unknown';
        await toolApi.create(apiData);
        message.success(`新增工具: ${values.name}`);
      } else if (editingTool?._key) {
        await toolApi.update(editingTool._key, apiData);
        message.success(`更新工具: ${values.name}`);
      }
      setModalOpen(false);
      fetchTools();
    } catch (err) {
      console.error('Failed to submit tool:', err);
      message.error('操作失敗');
    }
  };

  const handleRefresh = () => {
    fetchTools();
  };

  const tableColumns: ColumnsType<Tool> = [
    {
      title: '工具名稱',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (text: string, record: Tool) => {
        const IconComp = record.icon ? iconMap[record.icon as keyof typeof iconMap] : null;
        return (
          <Space>
            {IconComp ? <IconComp /> : <ToolOutlined />}
            {text}
          </Space>
        );
      },
    },
    { title: '代碼', dataIndex: 'code', key: 'code', width: 120 },
    {
      title: '類型',
      dataIndex: 'tool_type',
      key: 'tool_type',
      width: 100,
      render: (type: string) => {
        const colors: Record<string, string> = { mcp: 'blue', builtin: 'green', custom: 'orange' };
        const labels: Record<string, string> = { mcp: 'MCP', builtin: '內建', custom: '自訂' };
        return <Tag color={colors[type] || 'default'}>{labels[type] || type}</Tag>;
      },
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          online: { color: 'green', text: '在線' },
          maintenance: { color: 'gold', text: '維修中' },
          deprecated: { color: 'red', text: '已作廢' },
          registering: { color: 'orange', text: '審查中' },
        };
        const info = statusMap[status] || { color: 'default', text: status };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    {
      title: '授權',
      dataIndex: 'visibility',
      key: 'visibility',
      width: 80,
      render: (vis: string) => {
        const visMap: Record<string, { color: string; text: string }> = {
          public: { color: 'green', text: '公開' },
          role: { color: 'blue', text: '角色' },
          account: { color: 'purple', text: '帳號' },
        };
        const info = visMap[vis] || { color: 'default', text: vis };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    { title: '使用次數', dataIndex: 'usage_count', key: 'usage_count', width: 90, sorter: (a: Tool, b: Tool) => (a.usage_count || 0) - (b.usage_count || 0) },
    { title: 'LLM', dataIndex: 'llm_model', key: 'llm_model', width: 100, render: (v: string) => v || '-' },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: Tool) => {
        if (!isAdmin) return null;
        return (
          <Space>
            <Tooltip title="編輯">
              <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record._key || '')} />
            </Tooltip>
            <Tooltip title="刪除">
              <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record._key || '')} />
            </Tooltip>
          </Space>
        );
      },
    },
  ];

  const tabItems = groupConfig.map((group) => ({
    key: group.key,
    label: group.label,
    children: (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
          <Input
            placeholder="搜索工具名稱或描述..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ maxWidth: 300 }}
            allowClear
          />
          {activeTab !== 'all' && isAdmin && (
            <Button icon={<PlusOutlined />} onClick={handleCreate}>新增工具</Button>
          )}
          <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
            刷新
          </Button>
          <div style={{ marginLeft: 'auto' }}>
            <Segmented
              value={viewMode}
              onChange={(v) => setViewMode(v as 'card' | 'table')}
              options={[
                { value: 'card', icon: <AppstoreOutlined /> },
                { value: 'table', icon: <UnorderedListOutlined /> },
              ]}
            />
          </div>
        </div>

        {filteredTools.length > 0 ? (
          viewMode === 'card' ? (
            <Row gutter={[16, 16]} style={{ margin: 0 }}>
              {filteredTools.map((tool) => {
                const cardAgent = mapToolToCard(tool);
                return (
                  <Col 
                    key={cardAgent.id} 
                    xs={24} 
                    sm={12} 
                    md={12} 
                    lg={8} 
                    xl={6}
                    style={{ marginBottom: 16 }}
                  >
                    <AgentCard
                      agent={cardAgent}
                      onCardClick={handleEdit}
                      onEdit={handleEdit}
                      onDelete={isAdmin ? handleDelete : undefined}
                      showMenu={true}
                      {...(isAdmin ? {
                        actionLabel: '設置',
                        actionIcon: <SafetyCertificateOutlined />,
                        onAction: (() => {
                          const platformMap: Record<string, string> = {
                            line_bot: '/app/platforms/line',
                            whatsapp_bot: '/app/platforms/whatsapp',
                            wecom_bot: '/app/platforms/wecom',
                            dingtalk_bot: '/app/platforms/dingtalk',
                            xchat_bot: '/app/platforms/xchat',
                            slack_bot: '/app/platforms/slack',
                          };
                          return platformMap[tool.code || '']
                            ? () => navigate(platformMap[tool.code || ''])
                            : handleAuth;
                        })(),
                      } : isAuthorized(tool) ? {
                        actionLabel: '已授權',
                        actionIcon: <CheckCircleOutlined />,
                        actionDisabled: true,
                        actionStyle: { color: contentTokens.colorSuccess, borderColor: contentTokens.colorSuccess },
                      } : {
                        actionLabel: '禁止',
                        actionIcon: <StopOutlined />,
                        actionDisabled: true,
                      })}
                    />
                  </Col>
                );
              })}
            </Row>
          ) : (
            <Table
              columns={tableColumns}
              dataSource={filteredTools}
              rowKey="_key"
              pagination={{ pageSize: 20 }}
              size="middle"
              style={{
                boxShadow: contentTokens.tableShadow,
                borderRadius: contentTokens.borderRadius,
              }}
            />
          )
        ) : (
          <Empty
            description="沒有找到匹配的工具"
            style={{ marginTop: 48 }}
          />
        )}
      </div>
    ),
  }));

  return (
    <div style={{ padding: '24px' }}>
      <Spin spinning={loading}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          style={{ marginTop: -8 }}
        />
      </Spin>
      <ToolFormModal
        open={modalOpen}
        tool={editingTool}
        mode={modalMode}
        readOnly={!isAdmin}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleFormSubmit}
        onDelete={isAdmin ? handleDelete : undefined}
        onSyncIntents={handleSyncIntents}
      />
    </div>
  );
}
