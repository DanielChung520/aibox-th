/**
 * @file        AgentDrawer 元件
 * @description EEA-CRM 通用 AI Agent 右側抽屜面板 — 包含推薦 Agent 網格與對話視圖
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useRef, useEffect } from 'react';
import { Drawer, Input, Button, Tag, Divider, Typography, App } from 'antd';
import { ArrowLeftOutlined, SendOutlined } from '@ant-design/icons';
import { useCrmStore, CRMContext } from '../../stores/crmStore';

const { Text, Paragraph } = Typography;

/* ---------- Agent Data ---------- */

interface AgentInfo {
  code: string;
  name: string;
  phase: number;
  color: string;
  description: string;
}

const ALL_AGENTS: AgentInfo[] = [
  { code: 'A', name: '客戶開發智能引擎', phase: 1, color: '#2ECC71', description: '自動發掘潛在客戶並評估商機優先級' },
  { code: 'B', name: '需求診斷顧問系統', phase: 1, color: '#2ECC71', description: '透過引導式問卷釐清客戶深層需求' },
  { code: 'C', name: '方案規劃設計師', phase: 3, color: '#7B3FD4', description: '根據需求自動產出客製化解決方案' },
  { code: 'D', name: '提案溝通生成器', phase: 2, color: '#F5A623', description: '生成專業提案簡報與溝通腳本' },
  { code: 'E', name: '決策支援分析台', phase: 2, color: '#F5A623', description: '數據驅動的銷售策略與決策建議' },
  { code: 'F', name: '合約談判助手', phase: 2, color: '#F5A623', description: '合約條款分析與談判策略建議' },
  { code: 'G', name: '導入追蹤管理台', phase: 3, color: '#7B3FD4', description: '客戶導入進度追蹤與風險預警' },
  { code: 'H', name: '客戶關係深耕系統', phase: 4, color: '#E74C3C', description: '定期關懷排程與客戶健康度評估' },
  { code: 'I', name: '市場情報雷達', phase: 4, color: '#E74C3C', description: '產業動態監控與競爭者分析' },
  { code: 'J', name: '學習與持續優化引擎', phase: 4, color: '#E74C3C', description: '從成功案例中自動提煉最佳實踐' },
  { code: 'K', name: 'LINE智慧客情助手', phase: 1, color: '#2ECC71', description: 'LINE 對話分析與自動化客情回應' },
];

const PHASE_LABELS: Record<number, string> = {
  1: 'Phase 1',
  2: 'Phase 2',
  3: 'Phase 3',
  4: 'Phase 4',
};

const PHASE_TAG_COLORS: Record<number, string> = {
  1: 'green',
  2: 'orange',
  3: 'purple',
  4: 'red',
};

/* ---------- Context → Recommendation mapping ---------- */

const RECOMMENDATION_MAP: Record<CRMContext, { recommended: string[]; available: string[] }> = {
  dashboard:  { recommended: ['E', 'I', 'J'], available: ['A', 'B', 'C', 'H', 'K'] },
  customers:  { recommended: ['A', 'H', 'K'], available: ['B', 'I', 'J'] },
  contacts:   { recommended: ['K', 'H'],       available: ['A', 'B', 'J'] },
  timeline:   { recommended: ['K', 'J'],       available: ['A', 'B', 'H'] },
  tags:       { recommended: ['J', 'E'],       available: ALL_AGENTS.map(a => a.code) },
  params:     { recommended: ['E', 'J'],       available: ALL_AGENTS.map(a => a.code) },
};

const CONTEXT_LABELS: Record<CRMContext, string> = {
  dashboard:  '信息看板',
  customers:  '客戶管理',
  contacts:   '聯絡人管理',
  timeline:   '互動 Timeline',
  tags:       '機構分類標籤',
  params:     'CRM 參數設置',
};

/* ---------- Mock conversation data per agent ---------- */

const MOCK_RESPONSES: Record<string, { role: 'agent' | 'user'; text: string }[]> = {
  A: [
    { role: 'agent', text: '已掃描當前客戶列表，發現 3 家高潛力機構尚未被跟進。' },
    { role: 'agent', text: '建議優先聯絡：陽光老人養護中心（匹配度 92%）、仁愛居家長照（88%）。' },
  ],
  E: [
    { role: 'agent', text: '目前營收趨勢：本月 YTD 較去年同期成長 12.3%。' },
    { role: 'agent', text: '北部區域業績表現最佳，建議增加北部業務人員配置。' },
  ],
  H: [
    { role: 'agent', text: '已分析 5 位客戶的健康度：2 位需立即關懷，3 位維持良好。' },
    { role: 'agent', text: '陽光老人養護中心已 45 天未互動，建議安排拜訪。' },
  ],
  I: [
    { role: 'agent', text: '本月長照產業動態：衛福部發布新版評鑑指標，預計影響 60% 機構。' },
    { role: 'agent', text: '主要競爭對手 A 近期在北部拓展 3 家新據點，值得關注。' },
  ],
  J: [
    { role: 'agent', text: '從近期成功案例中提煉出 5 項最佳實踐，已整合至知識庫。' },
    { role: 'agent', text: '建議在下次團隊會議中分享「養護機構導入 SOP」模板。' },
  ],
  K: [
    { role: 'agent', text: '偵測到 3 則未回覆的 LINE 訊息，其中 2 則已超過 24 小時。' },
    { role: 'agent', text: '已自動發送關懷範本給陽光老人養護中心的張主任。' },
  ],
  B: [
    { role: 'agent', text: '根據初步對話，客戶可能需要的服務包含：居家護理、輔具租賃。' },
    { role: 'agent', text: '建議啟動「長照需求評估問卷」以深入診斷。' },
  ],
  C: [
    { role: 'agent', text: '已產出初步方案架構，包含 3 個服務模組與對應報價。' },
  ],
  D: [
    { role: 'agent', text: '已根據客戶需求生成提案大綱，可進一步編輯調整。' },
  ],
  F: [
    { role: 'agent', text: '合約條款分析完成：3 項條款需注意，其中第 7 條有潛在風險。' },
  ],
  G: [
    { role: 'agent', text: '目前 2 家機構處於導入階段，進度分別為 65% 與 30%。' },
    { role: 'agent', text: 'A 機構的導入進度落後，建議安排額外教育訓練。' },
  ],
};

/* ---------- Helper: Agent card ---------- */

function AgentCard({
  agent,
  recommended,
  onClick,
}: {
  agent: AgentInfo;
  recommended: boolean;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        cursor: 'pointer',
        padding: '10px 12px',
        borderRadius: 8,
        border: recommended
          ? `1.5px solid ${agent.color}66`
          : '1px solid #e8e8e8',
        borderLeft: `4px solid ${agent.color}`,
        background: recommended ? `${agent.color}0d` : '#fff',
        boxShadow: recommended
          ? `0 0 12px ${agent.color}33`
          : '0 1px 3px rgba(0,0,0,0.06)',
        transition: 'all 0.2s',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
      className="agent-card-hover"
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          fontWeight: 700,
          fontSize: 14,
          color: agent.color,
          background: `${agent.color}1a`,
          borderRadius: 4,
          width: 22,
          height: 22,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {agent.code}
        </span>
        <Text strong style={{ fontSize: 13, lineHeight: 1.3, flex: 1 }}>{agent.name}</Text>
      </div>
      <Paragraph
        type="secondary"
        style={{ fontSize: 11, margin: 0, lineHeight: 1.4 }}
        ellipsis={{ rows: 2 }}
      >
        {agent.description}
      </Paragraph>
      <Tag
        color={PHASE_TAG_COLORS[agent.phase]}
        style={{ fontSize: 10, lineHeight: '16px', padding: '0 6px', alignSelf: 'flex-start' }}
      >
        {PHASE_LABELS[agent.phase]}
      </Tag>
    </div>
  );
}

/* ========== Main Component ========== */

export default function AgentDrawer() {
  const {
    agentDrawerOpen,
    agentDrawerContext,
    selectedAgentCode,
    selectedRecordId,
    closeAgentDrawer,
    selectAgent,
    backToAgentList,
  } = useCrmStore();

  const { message } = App.useApp();
  const [inputValue, setInputValue] = useState('');
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'agent'; text: string }[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const agents = ALL_AGENTS;
  const context = agentDrawerContext ?? 'dashboard';
  const recMap = RECOMMENDATION_MAP[context] ?? RECOMMENDATION_MAP.dashboard;
  const recommendedAgents = recMap.recommended.map(code => agents.find(a => a.code === code)!).filter(Boolean);
  const availableAgents = recMap.available.map(code => agents.find(a => a.code === code)!).filter(Boolean);
  const selectedAgent = selectedAgentCode ? agents.find(a => a.code === selectedAgentCode) ?? null : null;

  // Reset chat when agent changes
  useEffect(() => {
    if (selectedAgentCode) {
      const initial = MOCK_RESPONSES[selectedAgentCode];
      if (initial) {
        setChatMessages(initial.map(m => ({ ...m })));
      } else {
        setChatMessages([{ role: 'agent', text: `${agents.find(a => a.code === selectedAgentCode)?.name ?? selectedAgentCode} 已就緒，請輸入您的需求。` }]);
      }
    }
  }, [selectedAgentCode]);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text) return;
    setChatMessages(prev => [...prev, { role: 'user', text }]);
    setInputValue('');

    // Mock response
    setTimeout(() => {
      const mockReply = `已收到您的訊息。正在分析「${text}」相關的 CRM 資料，請稍候...`;
      setChatMessages(prev => [...prev, { role: 'agent', text: mockReply }]);
    }, 800);
  };

  /* ---------- Grid View ---------- */
  const renderGridView = () => (
    <div style={{ padding: '0 12px' }}>
      {/* Recommended agents */}
      <div style={{ marginBottom: 8 }}>
        <Text strong style={{ fontSize: 14 }}>⭐ 推薦 Agent</Text>
        <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
          · {CONTEXT_LABELS[context]}
        </Text>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {recommendedAgents.map(agent => (
          <AgentCard
            key={agent.code}
            agent={agent}
            recommended
            onClick={() => selectAgent(agent.code)}
          />
        ))}
      </div>

      <Divider style={{ margin: '12px 0' }} />

      {/* All agents */}
      <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>🤖 所有 Agent</Text>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {availableAgents.filter(a => !recMap.recommended.includes(a.code)).map(agent => (
          <AgentCard
            key={agent.code}
            agent={agent}
            recommended={false}
            onClick={() => selectAgent(agent.code)}
          />
        ))}
      </div>
    </div>
  );

  /* ---------- Chat View ---------- */
  const renderChatView = () => {
    if (!selectedAgent) return null;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Back button */}
        <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={backToAgentList}
            size="small"
          >
            🤖 所有Agent
          </Button>
        </div>

        {/* Agent header */}
        <div style={{
          padding: '12px 16px',
          borderLeft: `4px solid ${selectedAgent.color}`,
          background: `${selectedAgent.color}08`,
          margin: '0 12px',
          borderRadius: 8,
          marginTop: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{
              fontWeight: 700,
              fontSize: 16,
              color: selectedAgent.color,
              background: `${selectedAgent.color}1a`,
              borderRadius: 6,
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {selectedAgent.code}
            </span>
            <Text strong style={{ fontSize: 15 }}>{selectedAgent.name}</Text>
            <Tag color={PHASE_TAG_COLORS[selectedAgent.phase]} style={{ fontSize: 10, marginLeft: 'auto' }}>
              {PHASE_LABELS[selectedAgent.phase]}
            </Tag>
          </div>
          <Paragraph type="secondary" style={{ fontSize: 12, margin: 0 }}>
            {selectedAgent.description}
          </Paragraph>
          <div style={{ marginTop: 6, fontSize: 11, color: '#888' }}>
            當前頁面：{CONTEXT_LABELS[context]}
            {selectedRecordId && ` · 紀錄 ID：${selectedRecordId}`}
          </div>
        </div>

        {/* Messages */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '12px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}>
          {chatMessages.map((msg, i) => (
            <div
              key={i}
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%',
                padding: '8px 12px',
                borderRadius: 12,
                background: msg.role === 'user'
                  ? '#1677ff'
                  : '#f5f5f5',
                color: msg.role === 'user' ? '#fff' : '#333',
                fontSize: 13,
                lineHeight: 1.5,
                borderBottomRightRadius: msg.role === 'user' ? 4 : 12,
                borderBottomLeftRadius: msg.role === 'user' ? 12 : 4,
              }}
            >
              {msg.text}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div style={{
          padding: '10px 12px',
          borderTop: '1px solid #f0f0f0',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-end',
        }}>
          <Input.TextArea
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            placeholder="輸入訊息..."
            autoSize={{ minRows: 1, maxRows: 3 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            style={{ flex: 1, fontSize: 13, borderRadius: 8 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            style={{ borderRadius: 8 }}
          />
        </div>

        {/* Action buttons */}
        <div style={{
          padding: '8px 12px',
          borderTop: '1px solid #f0f0f0',
          display: 'flex',
          gap: 8,
        }}>
          <Button size="small" style={{ flex: 1, fontSize: 12, borderRadius: 6 }}>
            🤖 重新分析
          </Button>
          <Button
            size="small"
            style={{ flex: 1, fontSize: 12, borderRadius: 6 }}
            onClick={() => {
              window.dispatchEvent(new CustomEvent('crm:schedule', {
                detail: { recordId: selectedRecordId, agentCode: selectedAgentCode },
              }));
              message.success('已開啟行程規劃');
            }}
          >
            📅 行程
          </Button>
          <Button
            size="small"
            type="primary"
            ghost
            style={{ flex: 1, fontSize: 12, borderRadius: 6 }}
            onClick={() => message.success('分析結果已套用到 CRM')}
          >
            💾 套用到CRM
          </Button>
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Global style for hover effect */}
      <style>{`
        .agent-card-hover:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
        }
      `}</style>

      <Drawer
        title={
          selectedAgent
            ? `${selectedAgent.code} · ${selectedAgent.name}`
            : '🤖 AI Agent 助手'
        }
        placement="right"
        size="default"
        styles={{ wrapper: { maxWidth: '90vw', width: 380 }, body: { padding: selectedAgent ? 0 : '12px 0', overflow: 'hidden' } }}
        onClose={closeAgentDrawer}
        open={agentDrawerOpen}
        destroyOnClose
      >
        {selectedAgent ? renderChatView() : renderGridView()}
      </Drawer>
    </>
  );
}
