/**
 * @file        智能體中心
 * @description 顯示各部門 AI 智能體，Tab 分類：產(生產+品保)、銷(業務+維保+行銷)、人(人資總務)、行(行政管理)、發(研發)、財(財務)
 * @lastUpdate  2026-06-16 18:00:00
 * @author      Sisyphus
 * @version     1.1.0
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, Input, Row, Col, Button, Empty, App, Spin, Switch, Tag } from 'antd';
import {
  SearchOutlined, PlusOutlined, ReloadOutlined, HeartOutlined,
} from '@ant-design/icons';
import { useContentTokens } from '../contexts/AppThemeProvider';
import AgentCard from '../components/AgentCard';
import AgentFormModal from '../components/AgentFormModal';
import { agentApi, Agent as ApiAgent } from '../services/api';
import { authStore } from '../stores/auth';
import { useEntityPerception } from '../hooks/useEntityPerception';
import { pageContextManager } from '../services/PageContextManager';

const TAB_COLORS: Record<string, string> = {
  prod: '#1677ff',
  sales: '#52c41a',
  hr: '#722ed1',
  exec: '#fa8c16',
  rd: '#13c2c2',
  finance: '#ff4d4f',
};

const groupConfig = [
  { key: 'all',    label: '全部', icon: 'AppstoreOutlined',    color: '#8c8c8c' },
  { key: 'prod',   label: '產',   icon: 'ToolOutlined',            sub: '生產+品保',    color: TAB_COLORS.prod },
  { key: 'sales',  label: '銷',   icon: 'ShoppingCartOutlined',    sub: '業務+維保+行銷', color: TAB_COLORS.sales },
  { key: 'hr',     label: '人',   icon: 'TeamOutlined',            sub: '人資總務',      color: TAB_COLORS.hr },
  { key: 'exec',   label: '行',   icon: 'CrownOutlined',           sub: '行政管理 (主管策略+總經辦)', color: TAB_COLORS.exec },
  { key: 'rd',     label: '發',   icon: 'BulbOutlined',            sub: '研發',          color: TAB_COLORS.rd },
  { key: 'finance', label: '財', icon: 'DollarOutlined',           sub: '財務',          color: TAB_COLORS.finance },
];

const VIRTUAL_AGENTS = [
  { id: 'v_sales_1', name: '市場分析助手',      description: '分析市場趨勢與競爭動態，提供銷售策略建議與商機洞察',     icon: 'RiseOutlined',        groupKey: 'sales' },
  { id: 'v_sales_2', name: '維保排程助手',      description: '自動安排客戶設備保養時程，主動提醒到期服務',            icon: 'ToolOutlined',        groupKey: 'sales' },
  { id: 'v_sales_3', name: '行銷文案生成器',    description: '依客戶分群與活動目標，自動生成個人化行銷內容',          icon: 'EditOutlined',        groupKey: 'sales' },
  { id: 'v_sales_5', name: '合約到期提醒',      description: '自動追蹤客戶合約到期日，提前通知業務進行續約（規劃中）', icon: 'CalendarOutlined',    groupKey: 'sales' },
];

export default function AgentCenter() {
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

  useEntityPerception({ defaultEntityType: 'agent', defaultAction: 'list' });

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

  useEffect(() => {
    pageContextManager.report({ component: 'AgentCenter', entityType: 'agent', action: 'list' });
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

  const allCards = useMemo(() => {
    const real = agents.map(mapApiToCard);
    const virtual = VIRTUAL_AGENTS.map((v) => ({
      id: v.id, name: v.name, description: v.description,
      icon: v.icon, status: 'developing' as const,
      usageCount: 0, groupKey: v.groupKey, isVirtual: true,
    }));
    return [...real, ...virtual];
  }, [agents]);

  const virtualIds = useMemo(() => new Set(VIRTUAL_AGENTS.map((v) => v.id)), []);

  const filteredCards = allCards.filter((agent: any) => {
    if (activeTab !== 'all' && agent.groupKey !== activeTab) return false;
    if (showFavoritesOnly) {
      if (agent.isVirtual) return false;
      if (!favorites.has(agent.id)) return false;
    }
    if (searchText) {
      const s = searchText.toLowerCase();
      return agent.name.toLowerCase().includes(s) || agent.description.toLowerCase().includes(s);
    }
    return true;
  });

  const handleFavorite = async (agentId: string, isFavorite: boolean) => {
    try {
      await agentApi.toggleFavorite(agentId);
      setFavorites((prev) => {
        const next = new Set(prev);
        if (isFavorite) next.add(agentId);
        else next.delete(agentId);
        return next;
      });
    } catch { message.error('操作失敗'); }
  };

  const handleChat = (agentId: string) => {
    if (virtualIds.has(agentId)) { message.info('此為規劃中的智能體，即將推出'); return; }
    navigate(`/app/task-session/chat?agent_key=${agentId}`);
  };

  const handleEdit = (agentId: string) => {
    if (virtualIds.has(agentId)) { message.info('此為規劃中的智能體，請先建立實體 Agent'); return; }
    const agent = agents.find((a) => a._key === agentId);
    if (agent) { setEditingAgent(agent); setModalMode('edit'); setModalOpen(true); }
  };

  const handleDelete = async (agentId: string) => {
    if (virtualIds.has(agentId)) { message.info('範例卡片不可刪除'); return; }
    try { await agentApi.delete(agentId); message.success('刪除成功'); fetchAgents(); }
    catch { message.error('刪除失敗'); }
  };

  const handleCreate = () => { setEditingAgent(null); setModalMode('create'); setModalOpen(true); };

  const handleFormSubmit = async (values: any) => {
    try {
      const currentUser = authStore.getState().user;
      const isThirdParty = values.source === true || values.source === 'third_party';
      const apiData: Record<string, unknown> = {
        name: values.name, description: values.description || '',
        icon: values.icon || '', status: values.status || 'online',
        group_key: values.groupKey || activeTab,
        source: isThirdParty ? 'third_party' : 'local',
        endpoint_url: values.endpointUrl || '',
        api_key: isThirdParty ? (values.apiKey || '') : undefined,
        auth_type: isThirdParty ? (values.authType || 'none') : undefined,
        llm_model: values.llmModel || '',
        temperature: values.temperature ?? 0.7, max_tokens: values.maxTokens ?? 2000,
        system_prompt: values.systemPrompt || '',
        knowledge_bases: values.knowledgeBases || [], data_sources: values.dataSources || [],
        tools: values.tools || [], opening_lines: values.openingLines || [],
        capabilities: values.capabilities || [],
        visibility: values.visibility || 'private',
        visibility_roles: values.visibility_roles || [],
      };
      if (modalMode === 'create') {
        apiData.agent_type = values.agentType || 'bpa';
        apiData.created_by = currentUser?.username || 'unknown';
      }
      if (modalMode === 'create') {
        const createRes = await agentApi.create(apiData);
        message.success(`新增 Agent: ${values.name}`);
        const newKey = createRes?.data?.data?._key || createRes?.data?._key;
        if (newKey) {
          fetchAgents();
          const demandFields = ['goal', 'expected_effect', 'problem_description'];
          if (demandFields.some(f => values[f])) {
            try { await agentApi.createDemand(newKey, { goal: values.goal || '', expected_effect: values.expected_effect || '', problem_description: values.problem_description || '' }); }
            catch (e) { console.warn('demand fail', e); }
          }
          try {
            const getRes = await agentApi.get(newKey);
            const newAgent = getRes?.data?.data;
            if (newAgent) {
              setEditingAgent({
                _key: newAgent._key || '', name: newAgent.name, description: newAgent.description || '',
                icon: newAgent.icon || 'RobotOutlined', status: newAgent.status || 'online',
                usage_count: newAgent.usage_count || 0, group_key: newAgent.group_key || 'productivity',
                agent_type: newAgent.agent_type, source: newAgent.source,
                endpoint_url: newAgent.endpoint_url, api_key: newAgent.api_key,
                auth_type: newAgent.auth_type, llm_model: newAgent.llm_model,
                temperature: newAgent.temperature, max_tokens: newAgent.max_tokens,
                system_prompt: newAgent.system_prompt,
                knowledge_bases: newAgent.knowledge_bases, data_sources: newAgent.data_sources,
                tools: newAgent.tools, opening_lines: newAgent.opening_lines,
                capabilities: newAgent.capabilities,
                visibility: newAgent.visibility || 'private',
                visibility_roles: newAgent.visibility_roles || [],
              });
              setModalMode('edit'); message.success('Agent 已建立，可繼續設定需求'); return;
            }
          } catch (e) { console.warn('fetch new agent fail', e); }
        }
        setModalOpen(false);
      } else if (editingAgent?._key) {
        await agentApi.update(editingAgent._key, apiData);
        message.success(`更新 Agent: ${values.name}`); setModalOpen(false); fetchAgents();
      }
    } catch (err: any) {
      message.error(err?.response?.data?.message || err?.message || '操作失敗');
    }
  };

  const handleRefresh = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); message.success('數據已刷新'); }, 500);
  };

  const tabItems = groupConfig.map((group) => ({
    key: group.key,
    label: (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        background: group.color, color: '#fff',
        padding: '3px 14px', borderRadius: 4,
        fontWeight: group.key === 'all' ? 500 : 600, lineHeight: '22px',
      }}>
        <span>{group.label}</span>
        {group.sub && <span style={{ fontSize: 11, opacity: 0.7, marginLeft: 2, color: 'rgba(255,255,255,0.8)' }}>{group.sub}</span>}
      </span>
    ),
    children: (
      <div>
        {filteredCards.length > 0 ? (
          <>
            <Row gutter={[16, 16]} style={{ margin: 0 }}>
              {filteredCards.map((agent: any) => (
                <Col key={agent.id} xs={24} sm={12} md={12} lg={8} xl={6} style={{ marginBottom: 16 }}>
                  <div style={{ position: 'relative' }}>
                    {agent.isVirtual && (
                      <Tag color="blue" style={{ position: 'absolute', top: 8, right: 8, zIndex: 1, fontSize: 11, lineHeight: '18px', margin: 0 }}>規劃中</Tag>
                    )}
                    <AgentCard agent={agent} isFavorite={favorites.has(agent.id)}
                      onFavorite={agent.isVirtual ? undefined : handleFavorite}
                      onChat={handleChat} onEdit={handleEdit} onDelete={handleDelete}
                      onCardClick={handleEdit} showMenu={!agent.isVirtual} />
                  </div>
                </Col>
              ))}
            </Row>
            {activeTab !== 'all' && (
              <div style={{ textAlign: 'center', marginTop: 8, opacity: 0.5, fontSize: 13 }}>藍色「規劃中」標籤為建議導入的智能體，點擊「新增 Agent」即可開始建置</div>
            )}
          </>
        ) : (
          <Empty description={searchText ? '沒有找到匹配的 Agent' : '此分類尚無 Agent，點擊「新增 Agent」開始建置'} style={{ marginTop: 48 }} />
        )}
      </div>
    ),
  }));

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 8, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Input placeholder="搜索 Agent 名稱或描述..." prefix={<SearchOutlined />}
          value={searchText} onChange={(e) => setSearchText(e.target.value)}
          style={{ maxWidth: 300 }} allowClear />
        {activeTab !== 'all' && <Button icon={<PlusOutlined />} onClick={handleCreate}>新增 Agent</Button>}
        <Button icon={<ReloadOutlined />} onClick={handleRefresh}>刷新</Button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
          <HeartOutlined style={{ color: contentTokens.colorError }} />
          <span>我的收藏</span>
          <Switch checked={showFavoritesOnly} onChange={setShowFavoritesOnly} size="small" />
        </div>
      </div>
      <Spin spinning={loading}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} tabBarGutter={2} style={{ marginTop: 0 }} />
      </Spin>
      <AgentFormModal
        open={modalOpen}
        agent={editingAgent ? {
          id: editingAgent._key || '', name: editingAgent.name, description: editingAgent.description || '',
          icon: editingAgent.icon || 'RobotOutlined', status: editingAgent.status || 'online',
          usageCount: editingAgent.usage_count || 0, groupKey: editingAgent.group_key || 'productivity',
          agentType: editingAgent.agent_type, source: editingAgent.source,
          endpointUrl: editingAgent.endpoint_url, apiKey: editingAgent.api_key,
          authType: editingAgent.auth_type, llmModel: editingAgent.llm_model,
          temperature: editingAgent.temperature, maxTokens: editingAgent.max_tokens,
          systemPrompt: editingAgent.system_prompt,
          knowledgeBases: editingAgent.knowledge_bases, dataSources: editingAgent.data_sources,
          tools: editingAgent.tools, openingLines: editingAgent.opening_lines,
          capabilities: editingAgent.capabilities,
          visibility: editingAgent.visibility || 'private',
          visibility_roles: editingAgent.visibility_roles || [],
        } : null}
        mode={modalMode} onCancel={() => setModalOpen(false)} onSubmit={handleFormSubmit}
        onDelete={handleDelete} groupKey={activeTab !== 'all' ? activeTab : undefined}
        defaultAgentType="bpa"
      />
    </div>
  );
}
