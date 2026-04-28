/**
 * @file        企業流程代理頁面
 * @description 企業流程代理功能，展示各種企業經營相關的 AI 代理
 * @lastUpdate  2026-03-25 15:54:25
 * @author      Daniel Chung
 * @version     1.0.1
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, Input, Row, Col, Button, Empty, App, Spin, Switch } from 'antd';
import { useContentTokens } from '../contexts/AppThemeProvider';
import { SearchOutlined, PlusOutlined, ReloadOutlined, HeartOutlined } from '@ant-design/icons';
import AgentCard from '../components/AgentCard';
import AgentFormModal from '../components/AgentFormModal';
import { agentApi, Agent as ApiAgent } from '../services/api';
import { authStore } from '../stores/auth';
import RagicLogisticProcess from '../components/RagicLogisticProcess';

const groupConfig = [
  { key: 'all', label: '全部', icon: 'AppstoreOutlined' },
  { key: 'inventory', label: '進銷存', icon: 'InboxOutlined' },
  { key: 'finance', label: '財務管理', icon: 'AccountBookOutlined' },
  { key: 'strategy', label: '企業戰略', icon: 'RadarChartOutlined' },
  { key: 'admin', label: '行政助理', icon: 'TeamOutlined' },
  { key: 'ragic_flow', label: 'Ragic 採購流程', icon: 'FlowchartOutlined' },
];

export default function BrowseAgent() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const contentTokens = useContentTokens();
  const [activeTab, setActiveTab] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [agents, setAgents] = useState<ApiAgent[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<ApiAgent | null>(null);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const res = await agentApi.list('bpa');
      const data = res.data.data || [];
      setAgents(data);
      const favs = new Set<string>();
      data.forEach((a: ApiAgent) => {
        if (a.is_favorite && a._key) favs.add(a._key);
      });
      setFavorites(favs);
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const mapApiToCard = (agent: ApiAgent) => ({
    id: agent._key || '',
    name: agent.name,
    description: agent.description || '',
    icon: agent.icon || 'RobotOutlined',
    status: agent.status || 'online',
    usageCount: agent.usage_count || 0,
    groupKey: agent.group_key || 'productivity',
  });

  const filteredAgents = agents.map(mapApiToCard).filter((agent: any) => {
    if (activeTab !== 'all' && agent.groupKey !== activeTab) {
      return false;
    }
    if (showFavoritesOnly && !favorites.has(agent.id)) {
      return false;
    }
    if (searchText) {
      const search = searchText.toLowerCase();
      return (
        agent.name.toLowerCase().includes(search) ||
        agent.description.toLowerCase().includes(search)
      );
    }
    return true;
  });

  // 處理收藏
  const handleFavorite = async (agentId: string, isFavorite: boolean) => {
    try {
      await agentApi.toggleFavorite(agentId);
      setFavorites((prev) => {
        const next = new Set(prev);
        if (isFavorite) {
          next.add(agentId);
        } else {
          next.delete(agentId);
        }
        return next;
      });
    } catch (err) {
      message.error('操作失敗');
    }
  };

  // 處理對話：導航到聊天頁，帶 agent_key 參數
  const handleChat = (agentId: string) => {
    navigate(`/app/task-session/chat?agent_key=${agentId}`);
  };

  // 處理編輯
  const handleEdit = (agentId: string) => {
    const agent = agents.find((a) => a._key === agentId);
    if (agent) {
      setEditingAgent(agent);
      setModalMode('edit');
      setModalOpen(true);
    }
  };

  // 處理刪除
  const handleDelete = async (agentId: string) => {
    try {
      await agentApi.delete(agentId);
      message.success('刪除成功');
      fetchAgents();
    } catch (err) {
      message.error('刪除失敗');
    }
  };

  // 處理新增
  const handleCreate = () => {
    setEditingAgent(null);
    setModalMode('create');
    setModalOpen(true);
  };

  // 處理表單提交
  const handleFormSubmit = async (values: any) => {
    try {
      const currentUser = authStore.getState().user;
      const isThirdParty = values.source === true || values.source === 'third_party';
      const apiData: Record<string, unknown> = {
        name: values.name,
        description: values.description || '',
        icon: values.icon || '',
        status: values.status || 'online',
        group_key: values.groupKey || activeTab,
        source: isThirdParty ? 'third_party' : 'local',
        endpoint_url: isThirdParty ? (values.endpointUrl || '') : undefined,
        api_key: isThirdParty ? (values.apiKey || '') : undefined,
        auth_type: isThirdParty ? (values.authType || 'none') : undefined,
        llm_model: values.llmModel || '',
        temperature: values.temperature ?? 0.7,
        max_tokens: values.maxTokens ?? 2000,
        system_prompt: values.systemPrompt || '',
        knowledge_bases: values.knowledgeBases || [],
        data_sources: values.dataSources || [],
        tools: values.tools || [],
        opening_lines: values.openingLines || [],
        capabilities: values.capabilities || [],
        visibility: values.visibility || 'private',
        visibility_roles: values.visibility_roles || [],
      };

      // Only send agent_type on create; on edit preserve existing value
      if (modalMode === 'create') {
        apiData.agent_type = values.agentType || 'bpa';
        apiData.created_by = currentUser?.username || 'unknown';
      }
      
      if (modalMode === 'create') {
        await agentApi.create(apiData);
        message.success(`新增 Agent: ${values.name}`);
      } else if (editingAgent?._key) {
        await agentApi.update(editingAgent._key, apiData);
        message.success(`更新 Agent: ${values.name}`);
      }
      setModalOpen(false);
      fetchAgents();
    } catch (err: any) {
      const msg = err?.response?.data?.message || err?.message || '操作失敗';
      message.error(msg);
    }
  };

  // 刷新數據
  const handleRefresh = () => {
    setLoading(true);
    // 模擬 API 調用
    setTimeout(() => {
      setLoading(false);
      message.success('數據已刷新');
    }, 500);
  };

  // Tab 項目
  const tabItems = groupConfig.map((group) => ({
    key: group.key,
    label: group.label,
    children: group.key === 'ragic_flow' ? (
      <RagicLogisticProcess />
    ) : (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', gap: 12 }}>
          <Input
            placeholder="搜索 Agent 名稱或描述..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ maxWidth: 300 }}
            allowClear
          />
          {activeTab !== 'all' && (
            <Button icon={<PlusOutlined />} onClick={handleCreate}>新增 Agent</Button>
          )}
          <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
            刷新
          </Button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
            <HeartOutlined style={{ color: contentTokens.colorError }} />
            <span>我的收藏</span>
            <Switch 
              checked={showFavoritesOnly} 
              onChange={setShowFavoritesOnly} 
              size="small"
            />
          </div>
        </div>

        {/* Agent 卡片網格 */}
        {filteredAgents.length > 0 ? (
          <Row gutter={[16, 16]} style={{ margin: 0 }}>
            {filteredAgents.map((agent) => (
              <Col 
                key={agent.id} 
                xs={24} 
                sm={12} 
                md={12} 
                lg={8} 
                xl={6}
                style={{ marginBottom: 16 }}
              >
                <AgentCard
                    agent={agent}
                    isFavorite={favorites.has(agent.id)}
                    onFavorite={handleFavorite}
                    onChat={handleChat}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                  />
              </Col>
            ))}
          </Row>
        ) : (
          <Empty
            description="沒有找到匹配的 Agent"
            style={{ marginTop: 48 }}
          />
        )}
      </div>
    ),
  }));

  return (
    <div>
      <Spin spinning={loading}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          style={{ marginTop: -8 }}
        />
      </Spin>
       <AgentFormModal
         open={modalOpen}
         agent={editingAgent ? {
           id: editingAgent._key || '',
           name: editingAgent.name,
           description: editingAgent.description || '',
           icon: editingAgent.icon || 'RobotOutlined',
           status: editingAgent.status || 'online',
           usageCount: editingAgent.usage_count || 0,
           groupKey: editingAgent.group_key || 'productivity',
          agentType: editingAgent.agent_type,
          source: editingAgent.source,
          endpointUrl: editingAgent.endpoint_url,
          apiKey: editingAgent.api_key,
          authType: editingAgent.auth_type,
          llmModel: editingAgent.llm_model,
          temperature: editingAgent.temperature,
          maxTokens: editingAgent.max_tokens,
          systemPrompt: editingAgent.system_prompt,
          knowledgeBases: editingAgent.knowledge_bases,
          dataSources: editingAgent.data_sources,
          tools: editingAgent.tools,
          openingLines: editingAgent.opening_lines,
          capabilities: editingAgent.capabilities,
          visibility: editingAgent.visibility || 'private',
          visibility_roles: editingAgent.visibility_roles || [],
        } : null}
        mode={modalMode}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleFormSubmit}
        onDelete={handleDelete}
        groupKey={activeTab !== 'all' ? activeTab : undefined}
        defaultAgentType="bpa"
      />
    </div>
  );
}
