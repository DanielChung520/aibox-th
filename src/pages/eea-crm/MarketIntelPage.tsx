/**
 * @file        MarketIntelPage.tsx
 * @description 市場觀察 — 每日快報、關鍵字管理、歷史查詢
 * @lastUpdate  2026-06-14
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Tabs, Tag, Typography, Button, Card, Badge, Empty, Select, Switch, Input, App, Spin } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { pageContextManager } from '../../services/PageContextManager';

const { Text } = Typography;

const REL_COLORS: Record<string, string> = { high: 'red', medium: 'orange', low: 'blue' };
const REL_LABELS: Record<string, string> = { high: '高關聯', medium: '中關聯', low: '一般' };
const IMPACT_ICONS: Record<string, string> = { positive: '📈', negative: '📉', neutral: '➖' };

/* ─── Tab: 個人化設定 ──────────────────────────── */

function SettingsTab() {
  const { message } = App.useApp();
  const [topics, setTopics] = useState('政府長照預算、各縣市復康巴士標案、沐浴車補助辦法、競爭對手動態、無障礙設備法規變動');
  const [keywords, setKeywords] = useState(['復康巴士', '沐浴車', '長照標案', '輪椅升降機', '無障礙']);
  const [pushEnabled, setPushEnabled] = useState(true);
  const [allowForward, setAllowForward] = useState(true);
  const [pushTime, setPushTime] = useState('08:00');

  return (
    <div style={{ maxWidth: 600 }}>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16, fontSize: 12 }}>
        此設定僅影響你的個人市場快報 — LLM Provider/Model 由 Admin 在系統參數中統一管理
      </Text>

      <div style={{ marginBottom: 20 }}>
        <Text strong style={{ fontSize: 14 }}>🎯 關注領域</Text>
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 6 }}>
          告訴 LLM 你關心什麼，會納入每日摘要的篩選與分析重點
        </Text>
        <Input.TextArea rows={3} value={topics} onChange={e => setTopics(e.target.value)}
          placeholder="例如：政府長照預算、各縣市復康巴士標案、沐浴車補助辦法…" />
      </div>

      <div style={{ marginBottom: 20 }}>
        <Text strong style={{ fontSize: 14 }}>🔑 關注關鍵詞</Text>
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 6 }}>
          輔助爬蟲蒐集資料（關鍵詞越多，搜尋範圍越廣）
        </Text>
        <Select mode="tags" value={keywords} onChange={setKeywords}
          style={{ width: '100%' }} placeholder="輸入關鍵字後 Enter" open={false} />
      </div>

      <div style={{ marginBottom: 20 }}>
        <Text strong style={{ fontSize: 14 }}>⏰ 接收設定</Text>
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, width: 80 }}>推送時間</span>
            <Select value={pushTime} onChange={setPushTime} style={{ width: 120 }} size="small"
              options={[
                { label: '08:00', value: '08:00' },
                { label: '09:00', value: '09:00' },
                { label: '10:00', value: '10:00' },
                { label: '不推播', value: '' },
              ]} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch checked={pushEnabled} onChange={setPushEnabled} size="small" />
            <span style={{ fontSize: 13 }}>接收 LINE 推播</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch checked={allowForward} onChange={setAllowForward} size="small" />
            <span style={{ fontSize: 13 }}>允許轉發快報給聯絡人（業務可將有價值的資訊分享給客戶）</span>
          </div>
        </div>
      </div>

      <Button type="primary" onClick={() => {
        localStorage.setItem('market_intel_settings', JSON.stringify({
          topics, keywords, pushEnabled, allowForward, pushTime,
        }));
        message.success('個人設定已儲存，點擊「今日快報」重新整理即可套用');
      }}>儲存設定</Button>
    </div>
  );
}

/* ─── Tab: 今日快報 ────────────────────────────── */

function DailyBrief() {
  const [report, setReport] = useState<any>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // 啟動時立即載入最新快報
  useEffect(() => {
    fetch('/api/v1/market-intel/latest').then(r => r.json()).then(d => {
      if (d.date) setReport(d);
    }).catch(() => {});
  }, []);

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    const saved = localStorage.getItem('market_intel_settings');
    const settings = saved ? JSON.parse(saved) : {};
    const kwList = settings.keywords || ['復康巴士', '沐浴車', '長照標案'];

    try {
      const res = await fetch('/api/v1/market-intel/refresh-celery', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(kwList),
      });
      const data = await res.json();
      const tid = data.task_id;
      if (!tid) { setRefreshing(false); return; }
      setTaskId(tid);

      const poll = async () => {
        const sr = await fetch(`/api/v1/market-intel/task/${tid}`);
        const st = await sr.json();
        if (st.status === 'SUCCESS') {
          const rr = await fetch('/api/v1/market-intel/latest');
          const rd = await rr.json();
          if (rd.date) setReport(rd);
          setTaskId(null);
          setRefreshing(false);
        } else if (st.status !== 'FAILURE') {
          setTimeout(poll, 5000);
        } else {
          setTaskId(null);
          setRefreshing(false);
        }
      };
      setTimeout(poll, 3000);
    } catch { setRefreshing(false); }
  };

  if (!report) return (
    <div style={{ textAlign: 'center', padding: 80 }}>
      <Empty description="尚無快報，點擊按鈕產生" />
      <Button type="primary" style={{ marginTop: 12 }} loading={refreshing} onClick={handleRefresh}>📡 產生今日快報</Button>
    </div>
  );

  const high = report.items?.filter((i: any) => i.relevance === 'high') || [];
  const medium = report.items?.filter((i: any) => i.relevance === 'medium') || [];
  const low = report.items?.filter((i: any) => i.relevance === 'low') || [];

  const renderItems = (items: any[]) => {
    if (items.length === 0) return null;
    return (
      <div style={{ maxHeight: 420, overflow: 'auto' }}>
        {items.map((item: any, i: number) => (
          <Card key={i} size="small" style={{ marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <Tag color={REL_COLORS[item.relevance]} style={{ fontSize: 10 }}>{REL_LABELS[item.relevance]}</Tag>
                  <span style={{ fontSize: 12 }}>{IMPACT_ICONS[item.impact] || ''}</span>
                  <Text strong style={{ fontSize: 13, cursor: 'pointer' }}
                    onClick={() => window.open(item.url, '_blank')}>{item.title}</Text>
                </div>
                <div style={{ fontSize: 12, color: '#555', margin: '2px 0' }}>{item.summary}</div>
                {item.action && (
                  <div style={{ fontSize: 12, color: '#1677ff', marginTop: 2 }}>💡 {item.action}</div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    );
  };

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16, background: '#f0f5ff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Badge status="processing" /><Text strong style={{ fontSize: 14 }}>{report.daily_focus || '無資訊'}</Text>
          </div>
          <Button size="small" icon={<ReloadOutlined spin={refreshing} />} disabled={refreshing} onClick={handleRefresh}>重新整理</Button>
        </div>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>{report.overall_assessment || ''}</Text>
      </Card>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <Card size="small" title="📈 趨勢" style={{ flex: 1 }}>
          {(report.key_trends || []).map((t: string, i: number) => (
            <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>• {t}</div>
          ))}
        </Card>
        <Card size="small" title="⚠️ 注意" style={{ flex: 1 }}>
          {(report.attention_points || []).map((t: string, i: number) => (
            <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>• {t}</div>
          ))}
        </Card>
        <Card size="small" title="💡 商機" style={{ flex: 1 }}>
          {(report.opportunities || []).map((t: string, i: number) => (
            <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>• {t}</div>
          ))}
        </Card>
      </div>

      <Tabs
        size="small"
        style={{ marginTop: 4 }}
        items={[
          { label: `🔴 高關聯`, key: 'high', children: renderItems(high) },
          { label: `🟡 中關聯`, key: 'medium', children: renderItems(medium) },
          { label: `ℹ️ 一般資訊`, key: 'low', children: renderItems(low) },
        ].filter(tab => tab.children)}
      />
      {report.token_usage && (
        <div style={{ textAlign: 'right', marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            🤖 本次 LLM {report.token_usage.total?.toLocaleString() || 0} tokens（輸入 {report.token_usage.prompt?.toLocaleString() || 0} / 輸出 {report.token_usage.completion?.toLocaleString() || 0}）
          </Text>
        </div>
      )}
      {taskId && (
        <div style={{ textAlign: 'right', marginTop: 2 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>🔧 Celery 任務：{taskId.slice(0, 8)}...</Text>
        </div>
      )}
    </div>
  );
}

/* ─── Tab: 執行記錄 ──────────────────────────── */

function HistoryTab() {
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/market-intel/history?limit=20')
      .then(r => r.json())
      .then(d => setRecords(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin style={{ display: 'block', margin: 40 }} />;
  if (records.length === 0) return <Empty description="尚無執行記錄" />;

  return (
    <div>
      {records.map((r, i) => {
        const tokens = r.token_usage || {};
        const total = tokens.total || 0;
        return (
          <Card key={i} size="small" style={{ marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Text strong style={{ fontSize: 13 }}>{r.date}</Text>
                <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>{r.daily_focus || '—'}</Text>
              </div>
              <div style={{ textAlign: 'right' }}>
                <Tag>{r.items_count || 0} 篇</Tag>
                <Tag color="purple">🤖 {total.toLocaleString()} tokens</Tag>
              </div>
            </div>
            {r.task_id && (
              <Text type="secondary" style={{ fontSize: 10, display: 'block', marginTop: 2 }}>
                任務: {r.task_id.slice(0, 8)}... | {r.created_at ? new Date(r.created_at).toLocaleString('zh-TW') : ''}
              </Text>
            )}
          </Card>
        );
      })}
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────── */

const TABS = [
  { key: 'brief', label: '📋 今日快報', component: <DailyBrief /> },
  { key: 'settings', label: '⚙️ 觀察系統信息', component: <SettingsTab /> },
  { key: 'history', label: '📅 執行記錄', component: <HistoryTab /> },
];

export default function MarketIntelPage() {
  const contentTokens = useContentTokens();
  const [activeTab, setActiveTab] = useState(TABS[0].key);

  useEffect(() => {
    pageContextManager.report({ page: 'eea-crm/market-intel', pageName: '市場觀察', entityType: 'market_intel', action: 'view' });
  }, []);

  return (
    <div style={{ padding: '0 20px 20px', background: contentTokens.contentBg, minHeight: '100%' }}>
      <Tabs activeKey={activeTab} onChange={setActiveTab}
        items={TABS.map(t => ({ key: t.key, label: t.label, children: t.component }))} />
    </div>
  );
}
