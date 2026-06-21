/**
 * @file        SCMDashboard.tsx
 * @description AI-SCM 供應鏈智能儀表板 — 展示 6 點 AI 價值與 5 個 AI Agent 的範式總覽
 * @lastUpdate  2026-06-16 19:30:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useEffect, useMemo } from 'react';
import { Card, Col, Row, Statistic, Typography, Tag, Divider, Tooltip, App, Space } from 'antd';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import { pageContextManager } from '../../services/PageContextManager';
import {
  BulbOutlined,
  WarningOutlined,
  SearchOutlined,
  CheckCircleOutlined,
  BellOutlined,
  ApiOutlined,
  FundOutlined,
  DeploymentUnitOutlined,
  SafetyOutlined,
  RocketOutlined,
  ExperimentOutlined,
  TeamOutlined,
  GatewayOutlined,
  NodeIndexOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
  CloudServerOutlined,
  RobotOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

/* ─── Data Definitions ─── */

interface ValueProposition {
  id: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  items: string[];
  tag: string;
  tagColor: string;
  description: string;
}

const VALUE_PROPOSITIONS: ValueProposition[] = [
  {
    id: 'P1',
    icon: <BulbOutlined style={{ fontSize: 28 }} />,
    title: '預測',
    subtitle: 'Prediction',
    items: ['需求預測', '價格趨勢', '風險預警'],
    tag: '預測型',
    tagColor: 'geekblue',
    description: '基於歷史數據與市場趨勢，提供採購需求、價格波動與供應風險的前瞻性預測，協助管理層提前佈局。',
  },
  {
    id: 'P2',
    icon: <WarningOutlined style={{ fontSize: 28 }} />,
    title: '異常偵測',
    subtitle: 'Anomaly Detection',
    items: ['跨維度異常', '合規缺口', '價格偏離'],
    tag: '偵測型',
    tagColor: 'volcano',
    description: '跨表單、跨維度自動比對，即時標記異常交易與潛在合規風險，從被動查核轉為主動預警。',
  },
  {
    id: 'P3',
    icon: <SearchOutlined style={{ fontSize: 28 }} />,
    title: '自然語言查詢',
    subtitle: 'NL Query',
    items: ['7 角色跨表查詢', '一句話取得資料', '智慧解析'],
    tag: '查詢型',
    tagColor: 'cyan',
    description: '7 種供應鏈角色均可使用自然語言提問，一句話跨表查詢，無需學習 SQL 或複雜篩選條件。',
  },
  {
    id: 'P4',
    icon: <CheckCircleOutlined style={{ fontSize: 28 }} />,
    title: '決策建議',
    subtitle: 'Decision Support',
    items: ['TCO 建議', '替代方案', '供應商推薦'],
    tag: '建議型',
    tagColor: 'green',
    description: '綜合 TCO 分析、品質評分與交期數據，提供量化比較的採購決策建議，減少人為盲點。',
  },
  {
    id: 'P5',
    icon: <BellOutlined style={{ fontSize: 28 }} />,
    title: '自動溝通',
    subtitle: 'Auto Communication',
    items: ['LINE 催貨', 'Email 通報', '異常通知'],
    tag: '溝通型',
    tagColor: 'purple',
    description: '逾期自動催貨、異常即時通報，透過 LINE / Email 多渠道自動溝通，告別人工逐一追蹤。',
  },
  {
    id: 'P6',
    icon: <ApiOutlined style={{ fontSize: 28 }} />,
    title: '跨系統串聯',
    subtitle: 'Cross-system',
    items: ['採購→生產', '財務→客戶', '全鏈路關聯'],
    tag: '串聯型',
    tagColor: 'orange',
    description: '打破 Ragic 表單孤島，將採購、生產、財務、客戶全鏈路自動關聯，一鍵追溯影響範圍。',
  },
];

interface AgentInfo {
  id: string;
  name: string;
  layer: number;
  layerName: string;
  aiDensity: string;
  description: string;
  valuePoints: string[];
  modules?: string[];
}

const AGENTS: AgentInfo[] = [
  {
    id: 'A',
    name: '供應鏈 Data Agent',
    layer: 1,
    layerName: '資料與感知層',
    aiDensity: '10%',
    description: '唯一能直接查詢 Ragic 的層級。NL2Query、跨表關聯、快取加速，AI-SCM 的資料底座。',
    valuePoints: ['P3', 'P6'],
  },
  {
    id: 'B',
    name: '採購智能助理',
    layer: 2,
    layerName: '執行與決策層',
    aiDensity: '20–40%',
    description: '日常採購作業的 AI 輔助 — 請購規劃、詢比價、驗收比對、品質監控。',
    valuePoints: ['P1', 'P2', 'P3', 'P4', 'P5', 'P6'],
    modules: ['請購規劃', '詢比價', '驗收比對', '品質監控'],
  },
  {
    id: 'B',
    name: '採購智能助理',
    layer: 3,
    layerName: '協同與異常層',
    aiDensity: '40%',
    description: '跨部門協調與異常處理 — 跟單催貨、變更評估、影響鏈追蹤。',
    valuePoints: ['P1', 'P2', 'P4', 'P5', 'P6'],
    modules: ['跟單催貨', '變更評估'],
  },
  {
    id: 'C',
    name: '供應商治理官',
    layer: 4,
    layerName: '治理與策略層',
    aiDensity: '60%',
    description: '供應商評鑑自動化、績效趨勢、風險預警、策略建議。',
    valuePoints: ['P1', 'P2', 'P4', 'P6'],
  },
  {
    id: 'D',
    name: '供應鏈指揮官',
    layer: 4,
    layerName: '治理與策略層',
    aiDensity: '60%',
    description: '跨流程儀表板、異常摘要、預算預測、Why 分析。',
    valuePoints: ['P1', 'P2', 'P3', 'P6'],
  },
  {
    id: 'E',
    name: '合規監察官',
    layer: 4,
    layerName: '治理與策略層',
    aiDensity: '60%',
    description: '比價合規檢查、授權差異偵測、SOP 偏離預警、審計追蹤。',
    valuePoints: ['P2', 'P4', 'P6'],
  },
];

const LAYER_COLORS: Record<number, { bg: string; border: string; label: string }> = {
  1: { bg: 'rgba(22, 119, 255, 0.06)', border: '#1677ff', label: '資料層 L1' },
  2: { bg: 'rgba(82, 196, 26, 0.06)', border: '#52c41a', label: '執行層 L2' },
  3: { bg: 'rgba(250, 173, 20, 0.06)', border: '#faad14', label: '協同層 L3' },
  4: { bg: 'rgba(114, 46, 209, 0.06)', border: '#722ed1', label: '策略層 L4' },
};

const VALUE_COLORS: Record<string, string> = {
  P1: '#1677ff',
  P2: '#ff4d4f',
  P3: '#13c2c2',
  P4: '#52c41a',
  P5: '#722ed1',
  P6: '#fa8c16',
};

const AGENT_EMOJI: Record<string, string> = {
  A: '🅰',
  B: '🅱',
  C: '🅲',
  D: '🅳',
  E: '🅴',
};

/* ─── Sub-components ─── */

function ValueCard({ vp }: { vp: ValueProposition }) {
  return (
    <Card
      hoverable
      size="small"
      style={{
        height: '100%',
        borderRadius: 12,
        transition: 'all 0.3s ease',
      }}
      styles={{
        body: { padding: 20, height: '100%', display: 'flex', flexDirection: 'column' as const },
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
        <Space size={12}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: `linear-gradient(135deg, ${VALUE_COLORS[vp.id]}20, ${VALUE_COLORS[vp.id]}08)`,
              color: VALUE_COLORS[vp.id],
            }}
          >
            {vp.icon}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text strong style={{ fontSize: 18, lineHeight: 1.2 }}>
                {vp.id} {vp.title}
              </Text>
              <Tag color={vp.tagColor} style={{ fontSize: 10, lineHeight: '18px', borderRadius: 4, padding: '0 6px' }}>
                {vp.tag}
              </Tag>
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>{vp.subtitle}</Text>
          </div>
        </Space>
      </div>

      <Paragraph type="secondary" style={{ fontSize: 13, marginBottom: 12, flex: 1 }}>
        {vp.description}
      </Paragraph>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {vp.items.map((item) => (
          <Tag
            key={item}
            style={{
              borderRadius: 6,
              padding: '2px 10px',
              fontSize: 12,
              border: `1px solid ${VALUE_COLORS[vp.id]}30`,
              background: `${VALUE_COLORS[vp.id]}10`,
              color: VALUE_COLORS[vp.id],
            }}
          >
            {item}
          </Tag>
        ))}
      </div>
    </Card>
  );
}

function AgentCard({ agent }: { agent: AgentInfo }) {
  const layerInfo = LAYER_COLORS[agent.layer];
  const agentKey = agent.id;

  return (
    <Card
      size="small"
      style={{
        borderRadius: 10,
        borderLeft: `3px solid ${layerInfo.border}`,
        background: layerInfo.bg,
        height: '100%',
        transition: 'all 0.25s ease',
      }}
      styles={{
        body: { padding: 14 },
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ fontSize: 22, lineHeight: 1 }}>{AGENT_EMOJI[agentKey]}</span>
        <div>
          <Text strong style={{ fontSize: 14 }}>{agent.name}</Text>
          <div>
            <Tag color="default" style={{ fontSize: 10, lineHeight: '18px', borderRadius: 4 }}>
              AI 濃度 {agent.aiDensity}
            </Tag>
          </div>
        </div>
      </div>
      <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
        {agent.description}
      </Paragraph>
      {agent.modules && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
          {agent.modules.map((m) => (
            <Tag key={m} style={{ fontSize: 10, borderRadius: 4, padding: '0 6px' }}>{m}</Tag>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {agent.valuePoints.map((vp) => (
          <Tooltip key={vp} title={VALUE_PROPOSITIONS.find((p) => p.id === vp)?.title}>
            <Tag
              color={VALUE_COLORS[vp]}
              style={{ fontSize: 10, borderRadius: 4, cursor: 'pointer' }}
            >
              {vp}
            </Tag>
          </Tooltip>
        ))}
      </div>
    </Card>
  );
}

/* ─── Main Component ─── */

export default function SCMDashboard() {
  App.useApp();

  useEntityPerception({ defaultEntityType: 'function', defaultAction: 'view' });
  useEffect(() => {
    pageContextManager.report({ component: 'SCMDashboard', action: 'view' });
  }, []);

  const totalValuePoints = VALUE_PROPOSITIONS.length;
  const totalAgents = useMemo(() => {
    const seen = new Set(AGENTS.map((a) => a.id));
    return seen.size;
  }, []);
  const totalQa = 35; // 7 roles × 5 questions
  const totalRoles = 7;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* ─── Header ─── */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(22,119,255,0.08) 0%, rgba(114,46,209,0.06) 100%)',
          borderRadius: 16,
          padding: '28px 32px',
          marginBottom: 24,
          border: '1px solid rgba(22,119,255,0.12)',
        }}
      >
        <Row align="middle" justify="space-between" wrap>
          <Col>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 14,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'linear-gradient(135deg, #1677ff, #722ed1)',
                  fontSize: 24,
                  color: '#fff',
                }}
              >
                <DeploymentUnitOutlined />
              </div>
              <div>
                <Title level={4} style={{ margin: 0, fontSize: 22 }}>
                  AI-SCM 供應鏈智能儀表板
                </Title>
                <Text type="secondary" style={{ fontSize: 14 }}>
                  AI-Enabled Supply Chain Intelligence — Ragic 管交易，AI 管 Intelligence
                </Text>
              </div>
            </div>
          </Col>
          <Col>
            <Space>
              <Tag icon={<RocketOutlined />} color="blue" style={{ borderRadius: 6, padding: '2px 12px' }}>
                AI-SCM 範式 v1.0
              </Tag>
              <Tag icon={<ExperimentOutlined />} color="purple" style={{ borderRadius: 6, padding: '2px 12px' }}>
                Phase 1–4 導入中
              </Tag>
            </Space>
          </Col>
        </Row>
      </div>

      {/* ─── Quick Stats ─── */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card
            size="small"
            style={{ borderRadius: 10, textAlign: 'center' }}
            styles={{ body: { padding: '16px 12px' } }}
          >
            <Statistic
              title={<Text type="secondary" style={{ fontSize: 13 }}>AI Agent 總數</Text>}
              value={totalAgents}
              prefix={<RobotOutlined style={{ color: '#1677ff' }} />}
              valueStyle={{ fontSize: 28, fontWeight: 600 }}
              suffix={<Text style={{ fontSize: 13, color: '#1677ff' }}>個</Text>}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card
            size="small"
            style={{ borderRadius: 10, textAlign: 'center' }}
            styles={{ body: { padding: '16px 12px' } }}
          >
            <Statistic
              title={<Text type="secondary" style={{ fontSize: 13 }}>AI 價值點</Text>}
              value={totalValuePoints}
              prefix={<BulbOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ fontSize: 28, fontWeight: 600 }}
              suffix={<Text style={{ fontSize: 13, color: '#faad14' }}>項</Text>}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card
            size="small"
            style={{ borderRadius: 10, textAlign: 'center' }}
            styles={{ body: { padding: '16px 12px' } }}
          >
            <Statistic
              title={<Text type="secondary" style={{ fontSize: 13 }}>QA 全覆蓋</Text>}
              value={totalQa}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ fontSize: 28, fontWeight: 600 }}
              suffix={<Text style={{ fontSize: 13, color: '#52c41a' }}>題</Text>}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card
            size="small"
            style={{ borderRadius: 10, textAlign: 'center' }}
            styles={{ body: { padding: '16px 12px' } }}
          >
            <Statistic
              title={<Text type="secondary" style={{ fontSize: 13 }}>涵蓋角色</Text>}
              value={totalRoles}
              prefix={<TeamOutlined style={{ color: '#722ed1' }} />}
              valueStyle={{ fontSize: 28, fontWeight: 600 }}
              suffix={<Text style={{ fontSize: 13, color: '#722ed1' }}>個</Text>}
            />
          </Card>
        </Col>
      </Row>

      {/* ─── Six AI Value Cards ─── */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <FundOutlined style={{ fontSize: 20, color: '#1677ff' }} />
          <Title level={5} style={{ margin: 0 }}>六點 AI 價值矩陣</Title>
          <Tag color="blue" style={{ borderRadius: 6 }}>P1 – P6</Tag>
        </div>
        <Row gutter={[16, 16]}>
          {VALUE_PROPOSITIONS.map((vp) => (
            <Col xs={24} sm={12} md={8} key={vp.id}>
              <ValueCard vp={vp} />
            </Col>
          ))}
        </Row>
      </div>

      {/* ─── Five Agents Architecture ─── */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <GatewayOutlined style={{ fontSize: 20, color: '#722ed1' }} />
          <Title level={5} style={{ margin: 0 }}>四層智能架構 · 五個 AI Agent</Title>
          <Tag color="purple" style={{ borderRadius: 6 }}>Layer 1 – 4</Tag>
        </div>

        {/* Layer 4 */}
        <div
          style={{
            background: LAYER_COLORS[4].bg,
            borderRadius: 12,
            border: `1px solid ${LAYER_COLORS[4].border}25`,
            padding: 16,
            marginBottom: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div
              style={{
                background: LAYER_COLORS[4].border,
                color: '#fff',
                borderRadius: 6,
                padding: '2px 12px',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.5px',
              }}
            >
              L4
            </div>
            <Text strong style={{ fontSize: 14 }}>治理與策略層</Text>
            <Tag color="purple" style={{ fontSize: 10, borderRadius: 4 }}>AI 濃度 60%</Tag>
            <div style={{ flex: 1 }} />
          </div>
          <Row gutter={[12, 12]}>
            {AGENTS.filter((a) => a.layer === 4).map((agent) => (
              <Col xs={24} sm={8} key={`${agent.id}-${agent.name}`}>
                <AgentCard agent={agent} />
              </Col>
            ))}
          </Row>
        </div>

        {/* Layer 3 */}
        <div
          style={{
            background: LAYER_COLORS[3].bg,
            borderRadius: 12,
            border: `1px solid ${LAYER_COLORS[3].border}25`,
            padding: 16,
            marginBottom: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div
              style={{
                background: LAYER_COLORS[3].border,
                color: '#fff',
                borderRadius: 6,
                padding: '2px 12px',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.5px',
              }}
            >
              L3
            </div>
            <Text strong style={{ fontSize: 14 }}>協同與異常層</Text>
            <Tag color="gold" style={{ fontSize: 10, borderRadius: 4 }}>AI 濃度 40%</Tag>
            <div style={{ flex: 1 }} />
          </div>
          <Row gutter={[12, 12]}>
            {AGENTS.filter((a) => a.layer === 3).map((agent) => (
              <Col xs={24} key={`${agent.id}-${agent.name}`}>
                <AgentCard agent={agent} />
              </Col>
            ))}
          </Row>
        </div>

        {/* Layer 2 */}
        <div
          style={{
            background: LAYER_COLORS[2].bg,
            borderRadius: 12,
            border: `1px solid ${LAYER_COLORS[2].border}25`,
            padding: 16,
            marginBottom: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div
              style={{
                background: LAYER_COLORS[2].border,
                color: '#fff',
                borderRadius: 6,
                padding: '2px 12px',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.5px',
              }}
            >
              L2
            </div>
            <Text strong style={{ fontSize: 14 }}>執行與決策層</Text>
            <Tag color="green" style={{ fontSize: 10, borderRadius: 4 }}>AI 濃度 20%</Tag>
            <div style={{ flex: 1 }} />
          </div>
          <Row gutter={[12, 12]}>
            {AGENTS.filter((a) => a.layer === 2).map((agent) => (
              <Col xs={24} key={`${agent.id}-${agent.name}`}>
                <AgentCard agent={agent} />
              </Col>
            ))}
          </Row>
        </div>

        {/* Layer 1 */}
        <div
          style={{
            background: LAYER_COLORS[1].bg,
            borderRadius: 12,
            border: `1px solid ${LAYER_COLORS[1].border}25`,
            padding: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div
              style={{
                background: LAYER_COLORS[1].border,
                color: '#fff',
                borderRadius: 6,
                padding: '2px 12px',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.5px',
              }}
            >
              L1
            </div>
            <Text strong style={{ fontSize: 14 }}>資料與感知層</Text>
            <Tag color="blue" style={{ fontSize: 10, borderRadius: 4 }}>AI 濃度 10%</Tag>
            <div style={{ flex: 1 }} />
          </div>
          <Row gutter={[12, 12]}>
            {AGENTS.filter((a) => a.layer === 1).map((agent) => (
              <Col xs={24} sm={12} key={`${agent.id}-${agent.name}`}>
                <AgentCard agent={agent} />
              </Col>
            ))}
          </Row>
        </div>

        {/* Cross-layer support */}
        <div
          style={{
            marginTop: 10,
            borderRadius: 12,
            border: '1px dashed rgba(22,119,255,0.2)',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 24,
            flexWrap: 'wrap',
            background: 'rgba(22,119,255,0.03)',
          }}
        >
          <Text type="secondary" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.5px' }}>
            ⚡ 橫向支撐層
          </Text>
          <Space size={[16, 8]} wrap>
            <Tag icon={<BellOutlined />} color="default" style={{ borderRadius: 6, padding: '2px 10px' }}>
              通知引擎 LINE / Email
            </Tag>
            <Tag icon={<CloudServerOutlined />} color="default" style={{ borderRadius: 6, padding: '2px 10px' }}>
              知識庫 SOP + FAQ
            </Tag>
            <Tag icon={<SafetyOutlined />} color="default" style={{ borderRadius: 6, padding: '2px 10px' }}>
              安全層 RBAC 審計
            </Tag>
            <Tag icon={<ThunderboltOutlined />} color="default" style={{ borderRadius: 6, padding: '2px 10px' }}>
              LLM 網關 12B 本地 + 雲端
            </Tag>
          </Space>
        </div>

        {/* Agent count summary */}
        <div style={{ marginTop: 12, textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Agent 總數 <Text strong style={{ fontSize: 16 }}>5</Text> 個
            <Divider type="vertical" />
            從 Excel 原始 10 個整併為 5 個（含 1 個全新 🅴 合規監察官）
          </Text>
        </div>
      </div>

      {/* ─── Data Flow Diagram ─── */}
      <div style={{ marginBottom: 28 }}>
        <Card
          size="small"
          title={
            <Space>
              <NodeIndexOutlined style={{ color: '#1677ff' }} />
              <span>資料與觸發流</span>
            </Space>
          }
          style={{ borderRadius: 12 }}
          styles={{ body: { padding: 16 } }}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              padding: '8px 0',
            }}
          >
            {/* Layer 4 */}
            <div
              style={{
                background: `${LAYER_COLORS[4].border}15`,
                border: `1px solid ${LAYER_COLORS[4].border}30`,
                borderRadius: 10,
                padding: '8px 24px',
                textAlign: 'center',
              }}
            >
              <Text style={{ fontSize: 13 }}>
                🅲 供應商治理官 &nbsp;&nbsp; 🅳 供應鏈指揮官 &nbsp;&nbsp; 🅴 合規監察官
              </Text>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>Layer 4 策略層</div>
            </div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: 16 }}>↑↓</div>
            {/* Layer 3-2 */}
            <div
              style={{
                background: `${LAYER_COLORS[3].border}15`,
                border: `1px solid ${LAYER_COLORS[3].border}30`,
                borderRadius: 10,
                padding: '8px 24px',
                textAlign: 'center',
              }}
            >
              <Text style={{ fontSize: 13 }}>🅱 採購智能助理 &nbsp; (L2 執行層 + L3 協同層)</Text>
            </div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: 16 }}>↑↓</div>
            {/* Layer 1 */}
            <div
              style={{
                background: `${LAYER_COLORS[1].border}15`,
                border: `1px solid ${LAYER_COLORS[1].border}30`,
                borderRadius: 10,
                padding: '8px 24px',
                textAlign: 'center',
              }}
            >
              <Text style={{ fontSize: 13 }}>🅰 供應鏈 Data Agent</Text>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>Layer 1 資料層</div>
            </div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: 16 }}>↑↓</div>
            {/* Ragic */}
            <div
              style={{
                background: 'rgba(0,0,0,0.04)',
                border: '1px dashed rgba(0,0,0,0.12)',
                borderRadius: 10,
                padding: '8px 32px',
                textAlign: 'center',
              }}
            >
              <Text style={{ fontSize: 13, color: 'var(--text-secondary)' }}>🗄️ Ragic ERP（交易層 · 唯讀）</Text>
            </div>
          </div>

          <Divider style={{ margin: '12px 0' }} />

          <div style={{ display: 'flex', justifyContent: 'center', gap: 32, flexWrap: 'wrap', fontSize: 12 }}>
            <Space>
              <span style={{ color: '#1677ff' }}>⬆</span>
              <Text type="secondary">資料流：Ragic → Data Agent → 採購助理 → 策略層</Text>
            </Space>
            <Space>
              <span style={{ color: '#fa8c16' }}>⬇</span>
              <Text type="secondary">觸發流：異常事件 → 合規檢查 → 策略調整 → 流程修正</Text>
            </Space>
          </div>
        </Card>
      </div>

      {/* ─── Boundary Principle Banner ─── */}
      <div
        style={{
          borderRadius: 16,
          overflow: 'hidden',
          border: '1px solid rgba(22,119,255,0.15)',
          marginBottom: 28,
        }}
      >
        <Row>
          {/* Ragic side */}
          <Col
            xs={24}
            md={12}
            style={{
              background: 'linear-gradient(135deg, rgba(22,119,255,0.10) 0%, rgba(22,119,255,0.03) 100%)',
              padding: '28px 32px',
              textAlign: 'center',
              borderRight: '1px solid rgba(22,119,255,0.10)',
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: 'rgba(22,119,255,0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 28,
                margin: '0 auto 12px',
                color: '#1677ff',
              }}
            >
              <DatabaseOutlined />
            </div>
            <Title level={4} style={{ margin: '0 0 4px', fontSize: 20 }}>Ragic 管交易</Title>
            <Paragraph type="secondary" style={{ margin: 0, fontSize: 13 }}>
              表單流程 · 簽核 · 交易記錄 · 供應商主檔<br />
              AI 不做 Ragic 能做的事
            </Paragraph>
          </Col>
          {/* AI side */}
          <Col
            xs={24}
            md={12}
            style={{
              background: 'linear-gradient(135deg, rgba(114,46,209,0.10) 0%, rgba(114,46,209,0.03) 100%)',
              padding: '28px 32px',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: 'rgba(114,46,209,0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 28,
                margin: '0 auto 12px',
                color: '#722ed1',
              }}
            >
              <RobotOutlined />
            </div>
            <Title level={4} style={{ margin: '0 0 4px', fontSize: 20 }}>AI 管 Intelligence</Title>
            <Paragraph type="secondary" style={{ margin: 0, fontSize: 13 }}>
              預測 · 異常偵測 · 自然語言查詢 · 決策建議<br />
              只做 Ragic 做不好的事
            </Paragraph>
          </Col>
        </Row>
        <div
          style={{
            background: 'linear-gradient(90deg, #1677ff 0%, #722ed1 100%)',
            padding: '10px',
            textAlign: 'center',
          }}
        >
          <Text style={{ color: '#fff', fontWeight: 600, fontSize: 14, letterSpacing: '1px' }}>
            不重疊 · 不取代 · 不競爭 — 疊加、增值、進化
          </Text>
        </div>
      </div>

      {/* ─── Footer Stats ─── */}
      <Card
        size="small"
        style={{ borderRadius: 12, marginBottom: 24 }}
        styles={{ body: { padding: '16px 24px' } }}
      >
        <Row gutter={[16, 12]} align="middle">
          <Col xs={24} sm={12} md={6}>
            <Space>
              <BarChartOutlined style={{ color: '#1677ff' }} />
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>導入階段</Text>
                <div>
                  <Text strong>Phase 1–4</Text>
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
                    立即有感 → 核心價值 → 管理優化 → 治理強化
                  </Text>
                </div>
              </div>
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>QA 覆蓋率</Text>
                <div>
                  <Text strong>35 / 35</Text>
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
                    7 角色 × 5 題全覆蓋
                  </Text>
                </div>
              </div>
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space>
              <TeamOutlined style={{ color: '#faad14' }} />
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>涵蓋角色</Text>
                <div>
                  <Text strong>7</Text>
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
                    總經理 · 管理部 · 採購 · 倉管 · 品管 · 生產 · 財務
                  </Text>
                </div>
              </div>
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space>
              <ApiOutlined style={{ color: '#722ed1' }} />
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>EEA 整合</Text>
                <div>
                  <Text strong>8</Text>
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
                    EEA 平台元件深度整合
                  </Text>
                </div>
              </div>
            </Space>
          </Col>
        </Row>
      </Card>
    </div>
  );
}
