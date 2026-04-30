/**
 * @file        RequirementBoard.tsx
 * @description 需求看板 — 開發者接單、理解需求、產生開發建議規格
 * @lastUpdate  2026-04-27 15:00:00
 * @author      AI Agent
 * @version     1.1.0
 */

import { useState, useEffect } from 'react';
import { Table, Button, Tag, Space, App, Modal, Descriptions, Spin, Typography, Divider, Input } from 'antd';
import { EyeOutlined, PlayCircleOutlined, CheckCircleOutlined, FileTextOutlined, HistoryOutlined, CodeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { agentApi } from '../services/api';
import type { Demand } from '../services/api';
import { authStore } from '../stores/auth';
import { MarkdownContent } from '../components/FloatingAssistant/ChatMarkdown';

const { Text, Paragraph } = Typography;

type RequirementStatus = 'pending_accept' | 'analyzing' | 'spec_ready' | 'accepted' | 'in_development' | 'completed';

interface RequirementRecord {
  _key: string;
  agent_key: string;
  demand_key: string;
  agent_name: string;
  account: string;
  version: string;
  status: RequirementStatus;
  goal: string;
  expected_effect: string;
  problem_description: string;
  ai_review: Demand['ai_review'];
  dev_spec?: Record<string, unknown>;
  submitted_at: string;
  created_at: string;
}

const statusMap: Record<RequirementStatus, { label: string; color: string }> = {
  pending_accept: { label: '待接單', color: 'blue' },
  analyzing: { label: '分析中', color: 'orange' },
  spec_ready: { label: '規格就緒', color: 'cyan' },
  accepted: { label: '已承接', color: 'green' },
  in_development: { label: '開發中', color: 'purple' },
  completed: { label: '已完成', color: 'default' },
};

function flattenApiResponse(raw: unknown): RequirementRecord[] {
  if (Array.isArray(raw)) return raw as RequirementRecord[];
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.data)) return obj.data as RequirementRecord[];
    if (obj.data && typeof obj.data === 'object') {
      const inner = obj.data as Record<string, unknown>;
      if (Array.isArray(inner.records)) return inner.records as RequirementRecord[];
      if (Array.isArray(inner.data)) return inner.data as RequirementRecord[];
    }
    if (Array.isArray(obj.records)) return obj.records as RequirementRecord[];
  }
  return [];
}

function buildMarkdownSpec(record: RequirementRecord): string {
  const spec = record.dev_spec || {};
  const aiReview = record.ai_review;
  const lines: string[] = [];

  lines.push(`# 開發規格書：${record.agent_name}`);
  lines.push('');
  lines.push(`| 項目 | 內容 |`);
  lines.push(`|------|------|`);
  lines.push(`| Agent | ${record.agent_name} |`);
  lines.push(`| 版本 | ${record.version} |`);
  lines.push(`| 提交者 | ${record.account} |`);
  lines.push(`| 提交時間 | ${record.submitted_at ? new Date(record.submitted_at).toLocaleString('zh-TW') : '-'} |`);
  lines.push('');

  lines.push('## 需求目標');
  lines.push(record.goal || '-');
  lines.push('');

  lines.push('## 預期效果');
  lines.push(record.expected_effect || '-');
  lines.push('');

  lines.push('## 問題描述');
  lines.push(record.problem_description || '-');
  lines.push('');

  if (aiReview) {
    lines.push('## AI 審查');
    lines.push(`- **評分**：${aiReview.score} 分`);
    lines.push(`- **信心度**：${aiReview.confidence}`);
    lines.push(`- **預估總工時**：${aiReview.estimated_hours}h`);
    if (aiReview.hour_breakdown) {
      const bd = aiReview.hour_breakdown;
      lines.push(`- **工時明細**：`);
      lines.push(`  - 顧問訪談：${bd.consulting}h`);
      lines.push(`  - 核心開發：${bd.development}h`);
      lines.push(`  - 測試品保：${bd.testing}h`);
      lines.push(`  - 審查上線：${bd.review}h`);
    }
    lines.push(`- **摘要**：${aiReview.summary}`);
    lines.push('');
  }

  if (spec && Object.keys(spec).length > 0 && !spec.error) {
    const s = spec as Record<string, unknown>;
    lines.push('## 開發建議');
    
    if (s.summary) {
      lines.push(`> ${s.summary}`);
      lines.push('');
    }

    if (Array.isArray(s.tech_stack) && s.tech_stack.length > 0) {
      lines.push('### 建議技術棧');
      for (const t of s.tech_stack as string[]) lines.push(`- ${t}`);
      lines.push('');
    }

    if (Array.isArray(s.modules) && s.modules.length > 0) {
      lines.push('### 模組規劃');
      lines.push('| 模組 | 說明 | 優先級 |');
      lines.push('|------|------|--------|');
      for (const m of s.modules as Array<Record<string, unknown>>) {
        lines.push(`| ${m.name || '-'} | ${m.description || '-'} | ${m.priority || '-'} |`);
      }
      lines.push('');
    }

    if (Array.isArray(s.data_sources) && s.data_sources.length > 0) {
      lines.push('### 資料來源');
      for (const d of s.data_sources as string[]) lines.push(`- ${d}`);
      lines.push('');
    }

    if (Array.isArray(s.integration_points) && s.integration_points.length > 0) {
      lines.push('### 整合點');
      for (const ip of s.integration_points as string[]) lines.push(`- ${ip}`);
      lines.push('');
    }

    if (s.hour_breakdown) {
      const bd = s.hour_breakdown as Record<string, number>;
      const total = (bd.consulting || 0) + (bd.development || 0) + (bd.testing || 0) + (bd.review || 0);
      lines.push('### 工時評估');
      lines.push('| 階段 | 工時 |');
      lines.push('|------|------|');
      lines.push(`| 🔍 顧問訪談與需求釐清 | ${bd.consulting || 0}h |`);
      lines.push(`| 💻 核心開發與整合 | ${bd.development || 0}h |`);
      lines.push(`| 🧪 測試與品質保證 | ${bd.testing || 0}h |`);
      lines.push(`| ✅ 審查與上線準備 | ${bd.review || 0}h |`);
      lines.push(`| **合計** | **${total}h** |`);
      lines.push('');
    }

    if (typeof s.mermaid_architecture === 'string' && s.mermaid_architecture.trim()) {
      lines.push('## 系統架構圖');
      lines.push('```mermaid');
      lines.push(s.mermaid_architecture as string);
      lines.push('```');
      lines.push('');
    }

    if (typeof s.mermaid_flow === 'string' && s.mermaid_flow.trim()) {
      lines.push('## 資料流程圖');
      lines.push('```mermaid');
      lines.push(s.mermaid_flow as string);
      lines.push('```');
      lines.push('');
    }

    if (Array.isArray(s.risks) && s.risks.length > 0) {
      lines.push('### 潛在風險');
      for (const r of s.risks as string[]) lines.push(`- ⚠️ ${r}`);
      lines.push('');
    }

    if (Array.isArray(s.suggestions) && s.suggestions.length > 0) {
      lines.push('### 開發建議');
      for (const sg of s.suggestions as string[]) lines.push(`- 💡 ${sg}`);
      lines.push('');
    }
  }

  return lines.join('\n');
}

export default function RequirementBoard() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<RequirementRecord[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [demandOpen, setDemandOpen] = useState(false);
  const [specOpen, setSpecOpen] = useState(false);
  const [specMd, setSpecMd] = useState('');
  const [selected, setSelected] = useState<RequirementRecord | null>(null);
  const [demandDetail, setDemandDetail] = useState<Demand | null>(null);
  const [demandLoading, setDemandLoading] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [revisionText, setRevisionText] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [specRecord, setSpecRecord] = useState<RequirementRecord | null>(null);

  const user = authStore.getState().user;

  const fetchList = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/agent-requirements', {
        headers: {
          Authorization: `Bearer ${authStore.getState().token}`,
        },
      });
      const json = await res.json();
      setData(flattenApiResponse(json));
    } catch {
      message.error('載入需求列表失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  const handleViewDemand = async (record: RequirementRecord) => {
    setDemandLoading(true);
    setDemandDetail(null);
    setDemandOpen(true);
    try {
      const res = await agentApi.getDemand(record.agent_key, record.demand_key);
      const loaded = (res.data as any)?.data || res.data;
      setDemandDetail(loaded);
    } catch {
      message.error('載入原始需求失敗');
    } finally {
      setDemandLoading(false);
    }
  };

  const handleAccept = async (record: RequirementRecord) => {
    setAccepting(true);
    try {
      const res = await fetch(`/api/v1/agent-requirements/${record._key}/accept`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.getState().token}`,
        },
        body: JSON.stringify({ developer: user?.username || 'unknown' }),
      });
      if (res.ok) {
        message.success(`已承接需求「${record.goal}」`);
        fetchList();
      } else {
        message.error('接單失敗');
      }
    } catch {
      message.error('接單失敗');
    } finally {
      setAccepting(false);
    }
  };

  const handleAnalyze = async (record: RequirementRecord) => {
    setAccepting(true);
    try {
      const res = await fetch(`/api/v1/agent-requirements/${record._key}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.getState().token}`,
        },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        message.success('已啟動需求分析，規格書產生中...');
        fetchList();
      } else {
        message.error('分析失敗');
      }
    } catch {
      message.error('分析失敗');
    } finally {
      setAccepting(false);
    }
  };

  const handleShowSpec = (record: RequirementRecord) => {
    setSpecRecord(record);
    setSpecMd(buildMarkdownSpec(record));
    setSpecOpen(true);
  };

  const handleStartDev = async (record: RequirementRecord) => {
    setAccepting(true);
    try {
      const res = await fetch(`/api/v1/agent-requirements/${record._key}/start-dev`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authStore.getState().token}` },
      });
      if (res.ok) {
        message.success('已建立開發工作區');
        window.location.href = `/app/dev-workspace/${record._key}`;
      } else {
        message.error('建立工作區失敗');
      }
    } catch {
      message.error('建立工作區失敗');
    } finally {
      setAccepting(false);
    }
  };

  const handleRegenerate = async () => {
    if (!specRecord || !revisionText.trim()) return;
    setRegenerating(true);
    setRevisionOpen(false);
    try {
      const res = await fetch(`/api/v1/agent-requirements/${specRecord._key}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.getState().token}`,
        },
        body: JSON.stringify({ revision: revisionText.trim() }),
      });
      if (res.ok) {
        message.success('規格書已重新產生');
        setRevisionText('');
        // Fetch updated record and refresh spec modal
        const updated = await fetch(`/api/v1/agent-requirements/${specRecord._key}`, {
          headers: { Authorization: `Bearer ${authStore.getState().token}` },
        });
        const json = await updated.json();
        const newRecord = (json as any).data || json;
        setSpecRecord(newRecord);
        setSpecMd(buildMarkdownSpec(newRecord));
        fetchList();
      } else {
        message.error('重新產生失敗');
      }
    } catch {
      message.error('重新產生失敗');
    } finally {
      setRegenerating(false);
    }
  };

  const columns: ColumnsType<RequirementRecord> = [
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      width: 180,
      ellipsis: true,
    },
    {
      title: '需求編號',
      dataIndex: 'req_no',
      width: 110,
      render: (no: string | undefined, record: RequirementRecord) => {
        const label = no || record._key.split('_')[0]?.slice(0, 8) || '-';
        return (
          <Tag
            style={{ cursor: 'pointer' }}
            onClick={() => {
              navigator.clipboard.writeText(no || label).then(() => message.success(`已複製 ${no || label}`));
            }}
          >
            {label}
          </Tag>
        );
      },
    },
    {
      title: '需求目標',
      dataIndex: 'goal',
      ellipsis: true,
      render: (text: string) => (
        <Text style={{ maxWidth: 300 }} ellipsis={{ tooltip: text }}>
          {text}
        </Text>
      ),
    },
    {
      title: '版本',
      dataIndex: 'version',
      width: 80,
      render: (version: string, record: RequirementRecord) => (
        <Button
          type="link"
          size="small"
          icon={<HistoryOutlined />}
          onClick={() => handleViewDemand(record)}
          style={{ padding: 0 }}
        >
          {version}
        </Button>
      ),
    },
    {
      title: '提交者',
      dataIndex: 'account',
      width: 100,
    },
    {
      title: 'AI 評分',
      dataIndex: ['ai_review', 'score'],
      width: 80,
      render: (score: number | undefined) =>
        score ? (
          <Tag color={score >= 70 ? 'green' : 'red'}>{score}</Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '狀態',
      dataIndex: 'status',
      width: 100,
      render: (s: RequirementStatus) => {
        const cfg = statusMap[s] || { label: s, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '提交時間',
      dataIndex: 'submitted_at',
      width: 160,
      render: (t: string) => (t ? new Date(t).toLocaleString('zh-TW') : '-'),
    },
    {
      title: '操作',
      width: 260,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setSelected(record);
              setDetailOpen(true);
            }}
          >
            查看
          </Button>
          {record.status === 'pending_accept' && (
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              loading={accepting}
              onClick={() => handleAccept(record)}
            >
              接單
            </Button>
          )}
          {record.status === 'accepted' && (
            <Button
              type="primary"
              size="small"
              icon={<CheckCircleOutlined />}
              loading={accepting}
              onClick={() => handleAnalyze(record)}
            >
              啟動分析
            </Button>
          )}
          {(record.status === 'spec_ready' || record.status === 'in_development') && (
            <Button
              type="primary"
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => handleShowSpec(record)}
            >
              查看規格書
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>📋 需求看板</h2>
        <Button onClick={fetchList}>刷新</Button>
      </div>

      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="_key"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1300 }}
        />
      </Spin>

      {/* 需求詳情 Modal */}
      <Modal
        title="需求詳情"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={700}
      >
        {selected && (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="Agent">{selected.agent_name}</Descriptions.Item>
            <Descriptions.Item label="版本">{selected.version}</Descriptions.Item>
            <Descriptions.Item label="提交者">{selected.account}</Descriptions.Item>
            <Descriptions.Item label="狀態">
              <Tag color={statusMap[selected.status]?.color}>{statusMap[selected.status]?.label || selected.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="需求目標" span={2}>
              {selected.goal}
            </Descriptions.Item>
            <Descriptions.Item label="預期效果" span={2}>
              {selected.expected_effect}
            </Descriptions.Item>
            <Descriptions.Item label="問題描述" span={2}>
              <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{selected.problem_description}</Paragraph>
            </Descriptions.Item>
            {selected.ai_review && (
              <>
                <Descriptions.Item label="AI 評分">
                  <Tag color={selected.ai_review.score >= 70 ? 'green' : 'red'}>{selected.ai_review.score}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="信心度">{selected.ai_review.confidence}</Descriptions.Item>
                <Descriptions.Item label="預估工時">{selected.ai_review.estimated_hours}h</Descriptions.Item>
                <Descriptions.Item label="摘要" span={2}>
                  {selected.ai_review.summary}
                </Descriptions.Item>
                {selected.ai_review.suggestions?.length > 0 && (
                  <Descriptions.Item label="建議" span={2}>
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {selected.ai_review.suggestions.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </Descriptions.Item>
                )}
              </>
            )}
          </Descriptions>
        )}
      </Modal>

      {/* 原始需求 Modal */}
      <Modal
        title={`原始需求 — ${demandDetail?.goal || ''}`}
        open={demandOpen}
        onCancel={() => setDemandOpen(false)}
        footer={null}
        width={700}
      >
        <Spin spinning={demandLoading}>
          {demandDetail ? (
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="版本">{demandDetail.version}</Descriptions.Item>
              <Descriptions.Item label="狀態">
                <Tag>{demandDetail.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="需求目標" span={2}>{demandDetail.goal}</Descriptions.Item>
              <Descriptions.Item label="預期效果" span={2}>{demandDetail.expected_effect}</Descriptions.Item>
              <Descriptions.Item label="問題描述" span={2}>
                <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{demandDetail.problem_description}</Paragraph>
              </Descriptions.Item>
              {demandDetail.target_users && <Descriptions.Item label="目標用戶" span={2}>{demandDetail.target_users}</Descriptions.Item>}
              {demandDetail.scope && <Descriptions.Item label="服務範圍">{demandDetail.scope}</Descriptions.Item>}
              {demandDetail.excluded_scope && <Descriptions.Item label="不包含">{demandDetail.excluded_scope}</Descriptions.Item>}
              {demandDetail.conversation_style && <Descriptions.Item label="對話風格" span={2}>{demandDetail.conversation_style}</Descriptions.Item>}
              {demandDetail.input_description && (
                <>
                  <Divider style={{ margin: '8px 0' }} />
                  <Descriptions.Item label="📥 輸入說明" span={2}>{demandDetail.input_description}</Descriptions.Item>
                  {demandDetail.input_format && <Descriptions.Item label="輸入格式" span={2}>{demandDetail.input_format}</Descriptions.Item>}
                </>
              )}
              {demandDetail.output_description && (
                <>
                  <Divider style={{ margin: '8px 0' }} />
                  <Descriptions.Item label="📤 輸出說明" span={2}>{demandDetail.output_description}</Descriptions.Item>
                  {demandDetail.output_format && <Descriptions.Item label="輸出格式" span={2}>{demandDetail.output_format}</Descriptions.Item>}
                </>
              )}
              {demandDetail.estimated_hours && <Descriptions.Item label="預估工時">{demandDetail.estimated_hours}h</Descriptions.Item>}
              {demandDetail.submitted_at && <Descriptions.Item label="提交時間">{new Date(demandDetail.submitted_at).toLocaleString('zh-TW')}</Descriptions.Item>}
            </Descriptions>
          ) : (
            <div style={{ textAlign: 'center', padding: 40 }}>尚無需求資料</div>
          )}
        </Spin>
      </Modal>

      {/* 開發規格書 Modal */}
      <Modal
        title="📄 開發規格書"
        open={specOpen}
        onCancel={() => setSpecOpen(false)}
        footer={[
          <Button key="close" onClick={() => setSpecOpen(false)}>關閉</Button>,
          <Button key="export" onClick={() => {
            if (specRecord) {
              window.open(`/api/v1/agent-requirements/${specRecord._key}/spec.md`, '_blank');
            }
          }}>匯出規格書</Button>,
          <Button key="regenerate" loading={regenerating} onClick={() => { setRevisionText(''); setRevisionOpen(true); }}>
            重新產生規格書
          </Button>,
          <Button key="copy" type="primary" onClick={() => {
            navigator.clipboard.writeText(specMd).then(() => message.success('已複製規格書'));
          }}>複製 Markdown</Button>,
        ]}
        width={800}
      >
        <Spin spinning={regenerating} tip="AI 重新產生規格書中...">
          <div style={{ maxHeight: '70vh', overflow: 'auto', padding: '8px 0' }}>
            <MarkdownContent content={specMd} />
          </div>
        </Spin>
      </Modal>

      {/* 重新產生規格書 Modal */}
      <Modal
        title="🔄 重新產生規格書"
        open={revisionOpen}
        onCancel={() => setRevisionOpen(false)}
        onOk={handleRegenerate}
        confirmLoading={regenerating}
        okText="重新產生"
      >
        <div style={{ marginBottom: 8 }}>
          請描述需要調整的方向，AI 將根據您的指示重新產生規格書：
        </div>
        <Input.TextArea
          rows={4}
          value={revisionText}
          onChange={(e) => setRevisionText(e.target.value)}
          placeholder="例如：增加安全性模組、調整技術棧改用 Python、補充 API 文件規範..."
        />
      </Modal>
    </div>
  );
}
