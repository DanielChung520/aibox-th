/**
 * @file        MarketIntelPage.tsx
 * @description 市場觀察 — 每日快報、關鍵字管理、歷史查詢
 * @lastUpdate  2026-06-14
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Tabs, Tag, Typography, Button, Card, Badge, Empty, Select, Switch, Input, InputNumber, App, Spin, Table, Divider, Modal, Checkbox } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { pageContextManager } from '../../services/PageContextManager';
import { authStore } from '../../stores/auth';
import { crmApi, paramsApi } from '../../services/api';

const { Text } = Typography;

const REL_COLORS: Record<string, string> = { high: 'red', medium: 'orange', low: 'blue' };
const REL_LABELS: Record<string, string> = { high: '高關聯', medium: '中關聯', low: '一般' };
const IMPACT_ICONS: Record<string, string> = { positive: '📈', negative: '📉', neutral: '➖' };

/* ─── Tab: 操作設置 ────────────────────────────── */

function SettingsTab() {
  const { message } = App.useApp();
  const currentUser = authStore.getState().user;
  const isSupervisor = !!(currentUser?.role_names?.includes('業務主管')
    || currentUser?.role_keys?.includes('admin'));

  // Permission management state (supervisor)
  const [allUsers, setAllUsers] = useState<any[]>([]);
  const [permissions, setPermissions] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);

  // Personal settings state
  const [topics, setTopics] = useState('政府長照預算、各縣市復康巴士標案、沐浴車補助辦法、競爭對手動態、無障礙設備法規變動');
  const [keywords, setKeywords] = useState(['復康巴士', '沐浴車', '長照標案', '輪椅升降機', '無障礙']);
  const [pushEnabled, setPushEnabled] = useState(true);
  const [allowForward, setAllowForward] = useState(true);
  const [pushTime, setPushTime] = useState('08:00');
  const [userPerm, setUserPerm] = useState<'read' | 'update' | null>(null);

  useEffect(() => {
    if (isSupervisor) {
      loadSupervisorData();
    } else {
      loadPersonalSettings();
      checkUserPermission();
    }
  }, []);

  async function loadSupervisorData() {
    try {
      const [usersRes, permRes] = await Promise.all([
        crmApi.getUsersAndRoles().catch(() => ({ data: { data: { users: [], roles: [] } } })),
        paramsApi.get('market_intel.permissions').catch(() => ({ data: { data: { param_value: '{}' } } })),
      ]);
      const users = usersRes?.data?.data?.users || [];
      const nonSupervisors = users.filter((u: any) =>
        !u.role_names?.includes('業務主管')
        && !u.role_keys?.includes('admin')
        && u.status !== 'disabled'
      );
      setAllUsers(nonSupervisors);

      const raw = permRes?.data?.data?.param_value;
      const perm = raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {};
      setPermissions(perm.permissions || {});
    } catch { /* ignore */ }
    setLoading(false);
  }

  function loadPersonalSettings() {
    const saved = localStorage.getItem('market_intel_settings');
    if (saved) {
      try {
        const s = JSON.parse(saved);
        if (s.topics) setTopics(s.topics);
        if (s.keywords?.length) setKeywords(s.keywords);
        if (s.pushEnabled !== undefined) setPushEnabled(s.pushEnabled);
        if (s.allowForward !== undefined) setAllowForward(s.allowForward);
        if (s.pushTime) setPushTime(s.pushTime);
      } catch { /* ignore */ }
    }
  }

  async function checkUserPermission() {
    try {
      const permRes = await paramsApi.get('market_intel.permissions');
      const raw = permRes?.data?.data?.param_value;
      if (raw) {
        const perm = typeof raw === 'string' ? JSON.parse(raw) : raw;
        const userKey = currentUser?._key;
        if (userKey && perm.permissions?.[userKey]) {
          setUserPerm(perm.permissions[userKey]);
        }
      }
    } catch { /* ignore */ }
    setLoading(false);
  }

  const changePerm = (userKey: string, value: string) => {
    setPermissions(prev => ({ ...prev, [userKey]: value }));
    setDirty(true);
  };

  const handleSavePermissions = async () => {
    try {
      await paramsApi.update('market_intel.permissions', JSON.stringify({
        permissions,
        updated_by: currentUser?._key || '',
        updated_at: new Date().toISOString(),
      }));
      setDirty(false);
      message.success('權限設定已儲存');
    } catch {
      message.error('儲存失敗');
    }
  };

  // ── Supervisor: permission management + personal settings ──
  if (isSupervisor) {
    const columns = [
      { title: '姓名', dataIndex: 'name', key: 'name', width: 140 },
      { title: '帳號', dataIndex: 'username', key: 'username', width: 140 },
      { title: '角色', dataIndex: 'role_names', key: 'role_names', width: 160,
        render: (names: string[]) => names?.join('、') || '-' },
      { title: '權限', key: 'perm', width: 160,
        render: (_: any, record: any) => (
          <Select value={permissions[record._key] || ''} onChange={v => changePerm(record._key, v)}
            style={{ width: 110 }} size="small"
            options={[
              { label: '— 無', value: '' },
              { label: '📖 唯讀', value: 'read' },
              { label: '✏️ 可更新', value: 'update' },
            ]} />
        ),
      },
    ];

    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <Text strong style={{ fontSize: 15 }}>👥 權限管理</Text>
              <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 2 }}>
                設定各業務員對市場觀察的操作權限。有「可更新」權限的業務員能修改關鍵字與執行重新整理。
              </Text>
            </div>
            <Button type="primary" disabled={!dirty} onClick={handleSavePermissions}>儲存權限</Button>
          </div>
        </div>
        <Table dataSource={allUsers.filter(u =>
          !u.role_names?.includes('業務主管')
          && !u.role_keys?.includes('admin')
        )}
          columns={columns} rowKey="_key" loading={loading} size="small" pagination={false} />

        <Divider />
        <RetentionDaysSetting />
        <Divider />
        {renderPersonalSettings()}
      </div>
    );
  }

  // ── Non-supervisor: show permission-based UI ──
  if (loading) return <Spin style={{ display: 'block', margin: 40 }} />;

  if (userPerm === 'read') {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Text type="secondary" style={{ fontSize: 14 }}>📖 此帳號為唯讀權限</Text>
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 8 }}>
          你的市場觀察權限為「唯讀」，無法修改設定或執行重新整理。
          如需變更權限，請聯繫你的業務主管。
        </Text>
      </div>
    );
  }

  if (!userPerm) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Empty description="尚無操作權限" />
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 8 }}>
          你的帳號尚未被授予市場觀察的操作權限，請聯繫業務主管。
        </Text>
      </div>
    );
  }

  // ── Update permission: show full settings ──
  return renderPersonalSettings();

  function renderPersonalSettings() {
    return (
      <div style={{ maxWidth: 600 }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 16, fontSize: 12 }}>
          個人設定 — LLM Provider/Model 由主管在系統參數中統一管理
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
              <span style={{ fontSize: 13 }}>允許轉發快報給聯絡人</span>
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
}

/* ─── 快報保留天數設定 ────────────────────────── */

function RetentionDaysSetting() {
  const { message } = App.useApp();
  const [days, setDays] = useState(10);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    paramsApi.get('market_intel.retention_days')
      .then(r => {
        const v = r?.data?.data?.param_value;
        if (v) setDays(parseInt(v, 10));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    try {
      await paramsApi.update('market_intel.retention_days', String(days));
      message.success('保留天數已更新');
    } catch { message.error('儲存失敗'); }
  };

  return (
    <div style={{ maxWidth: 400 }}>
      <Text strong style={{ fontSize: 14 }}>🗑️ 快報保留設定</Text>
      <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
        超過設定天數的快報記錄將由系統自動清理
      </Text>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <InputNumber min={1} max={365} value={days} onChange={v => v !== null && setDays(v)}
          style={{ width: 120 }} size="small" disabled={loading} />
        <Text type="secondary" style={{ fontSize: 13 }}>天</Text>
        <Button size="small" onClick={handleSave}>儲存</Button>
      </div>
    </div>
  );
}

function DailyBrief() {
  const [report, setReport] = useState<any>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [canRefresh, setCanRefresh] = useState(true);
  const [supervisorKey, setSupervisorKey] = useState<string | null>(null);

  // 載入自己的最新快報（無論權限檢查成功與否）
  useEffect(() => {
    const user = authStore.getState().user;
    if (!user) return;
    fetch(`/api/v1/market-intel/latest?user_key=${user._key}`)
      .then(r => r.json())
      .then(d => { if (d.date) setReport(d); })
      .catch(() => {});
  }, []);

  // 檢查權限（獨立 useEffect，不阻塞快報載入）
  useEffect(() => {
    const user = authStore.getState().user;
    if (!user) return;
    const isSupervisor = user.role_names?.includes('業務主管') || user.role_keys?.includes('admin');
    if (isSupervisor) { setCanRefresh(true); return; }

    paramsApi.get('market_intel.permissions').then(r => {
      const raw = r?.data?.data?.param_value;
      let perm: Record<string, string> = {};
      let updatedBy = '';
      if (raw) {
        const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
        perm = parsed.permissions || {};
        updatedBy = parsed.updated_by || '';
      }
      const userPerm = perm[user._key] || '';
      setCanRefresh(userPerm === 'update');

      // 若非主管但可更新 → 記錄主管 key 以便合併 items
      if (userPerm === 'update' && updatedBy) {
        setSupervisorKey(updatedBy);
      }
    }).catch(() => setCanRefresh(false));
  }, []);

  // 合併主管的 items（獨立 useEffect，不阻塞主渲染）
  const [supervisorItems, setSupervisorItems] = useState<any[]>([]);
  useEffect(() => {
    if (!supervisorKey) return;
    fetch(`/api/v1/market-intel/latest?user_key=${supervisorKey}`)
      .then(r => r.json())
      .then(d => { if (d.items) setSupervisorItems(d.items); })
      .catch(() => {});
  }, [supervisorKey]);

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    const user = authStore.getState().user;
    const saved = localStorage.getItem('market_intel_settings');
    const settings = saved ? JSON.parse(saved) : {};
    const kwList = settings.keywords || ['復康巴士', '沐浴車', '長照標案'];

    try {
      const res = await fetch('/api/v1/market-intel/refresh-celery', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: kwList, user_key: user?._key }),
      });
      const data = await res.json();
      const tid = data.task_id;
      if (!tid) { setRefreshing(false); return; }
      setTaskId(tid);

      const poll = async () => {
        const sr = await fetch(`/api/v1/market-intel/task/${tid}`);
        const st = await sr.json();
        if (st.status === 'SUCCESS') {
          const rr = await fetch(`/api/v1/market-intel/latest?user_key=${user?._key}`);
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
      <Empty description="尚無快報" />
      {canRefresh ? (
        <Button type="primary" style={{ marginTop: 12 }} loading={refreshing} onClick={handleRefresh}>📡 產生今日快報</Button>
      ) : (
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 8 }}>你的權限為唯讀，無法執行重新整理</Text>
      )}
    </div>
  );

  const allItems = [
    ...(report.items || []).map((i: any) => ({ ...i, _fromSupervisor: false })),
    ...supervisorItems.filter((si: any) =>
      !(report.items || []).some((mi: any) => mi.url === si.url)
    ).map((i: any) => ({ ...i, _fromSupervisor: true })),
  ];
  const high = allItems.filter((i: any) => i.relevance === 'high');
  const medium = allItems.filter((i: any) => i.relevance === 'medium');
  const low = allItems.filter((i: any) => i.relevance === 'low');

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
                    {item._fromSupervisor && <Tag color="purple" style={{ fontSize: 10, lineHeight: '18px', padding: '0 4px' }}>管</Tag>}
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
      <Card size="small" style={{ marginBottom: 16, background: 'var(--ant-color-primary-bg, #f0f5ff)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Badge status="processing" /><Text strong style={{ fontSize: 14 }}>{report.daily_focus || '無資訊'}</Text>
          </div>
          {canRefresh ? (
            <Button size="small" icon={<ReloadOutlined spin={refreshing} />} disabled={refreshing} onClick={handleRefresh}>重新整理</Button>
          ) : (
            <Tag color="default" style={{ fontSize: 11 }}>唯讀</Tag>
          )}
        </div>
        <div style={{ maxHeight: 80, overflow: 'auto', marginTop: 4, minHeight: 60 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>{report.overall_assessment || ''}</Text>
        </div>
      </Card>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <Card size="small" title="📈 趨勢" style={{ flex: 1, maxHeight: 160, overflow: 'auto' }}>
          <div style={{ minHeight: 48 }}>
            {(report.key_trends || []).map((t: string, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>• {t}</div>
            ))}
          </div>
        </Card>
        <Card size="small" title="⚠️ 注意" style={{ flex: 1, maxHeight: 160, overflow: 'auto' }}>
          <div style={{ minHeight: 48 }}>
            {(report.attention_points || []).map((t: string, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>• {t}</div>
            ))}
          </div>
        </Card>
        <Card size="small" title="💡 商機" style={{ flex: 1, maxHeight: 160, overflow: 'auto' }}>
          <div style={{ minHeight: 48 }}>
            {(report.opportunities || []).map((t: string, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>• {t}</div>
            ))}
          </div>
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
  const [selectedReport, setSelectedReport] = useState<any>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const { message } = App.useApp();

  const loadRecords = () => {
    setLoading(true);
    const user = authStore.getState().user;
    const q = user?._key ? `?limit=50&user_key=${user._key}` : '?limit=50';
    fetch(`/api/v1/market-intel/history${q}`)
      .then(r => r.json())
      .then(d => setRecords(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadRecords(); }, []);

  const filtered = records.filter(r =>
    !searchText || (r.daily_focus || '').includes(searchText) || (r.date || '').includes(searchText)
  );

  const toggleSelect = (key: string) => {
    setSelectedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedKeys.size === filtered.length) {
      setSelectedKeys(new Set());
    } else {
      setSelectedKeys(new Set(filtered.map(r => r._key).filter(Boolean)));
    }
  };

  const deleteSelected = async () => {
    if (selectedKeys.size === 0) return;
    setDeleting(true);
    try {
      const r = await fetch('/api/v1/market-intel/delete-reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys: Array.from(selectedKeys) }),
      });
      const d = await r.json();
      if (d.status === 'ok') {
        message.success(`已刪除 ${d.deleted} 筆記錄`);
        setSelectedKeys(new Set());
        loadRecords();
      } else {
        message.error('刪除失敗');
      }
    } catch { message.error('刪除失敗'); }
    setDeleting(false);
  };

  const openReport = async (key: string) => {
    setModalLoading(true);
    try {
      const r = await fetch(`/api/v1/market-intel/report-by-key/${key}`);
      const d = await r.json();
      if (d.date) setSelectedReport(d);
    } catch {}
    setModalLoading(false);
  };

  return (
    <div>
      <style>{`
        .history-record-card:hover {
          background: var(--ant-color-primary-bg, #f5f5f5) !important;
          transition: background 0.2s ease;
        }
      `}</style>
      {/* 搜索列 + 批量操作 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        <Input.Search placeholder="搜尋日期或摘要..." allowClear
          value={searchText} onChange={e => setSearchText(e.target.value)}
          style={{ maxWidth: 300 }} size="small" />
        {selectedKeys.size > 0 && (
          <>
            <Button size="small" onClick={selectAll}>
              {selectedKeys.size === filtered.length ? '取消全選' : `全選 (${filtered.length})`}
            </Button>
            <Badge count={selectedKeys.size} style={{ backgroundColor: '#ff4d4f' }}>
              <Button size="small" danger loading={deleting} onClick={deleteSelected}>刪除</Button>
            </Badge>
          </>
        )}
      </div>

      {loading ? <Spin style={{ display: 'block', margin: 40 }} /> :
       filtered.length === 0 ? <Empty description={searchText ? '無符合記錄' : '尚無執行記錄'} /> :
       filtered.map((r, i) => {
        const tokens = r.token_usage || {};
        const total = tokens.total || 0;
        const checked = selectedKeys.has(r._key);
        return (
          <Card key={r._key || i} size="small" className="history-record-card"
            style={{ marginBottom: 6, cursor: 'pointer', background: checked ? 'var(--ant-color-primary-bg, #e6f4ff)' : undefined }}
            onClick={() => { if (r._key) openReport(r._key); }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Checkbox checked={checked} onClick={e => e.stopPropagation()} onChange={() => r._key && toggleSelect(r._key)} />
              <div style={{ flex: 1 }}>
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
                {r.created_at && (
                  <Text type="secondary" style={{ fontSize: 10, display: 'block', marginTop: 2 }}>
                    {new Date(r.created_at).toLocaleString('zh-TW')}
                  </Text>
                )}
              </div>
            </div>
          </Card>
        );
      })}

      <Modal title={`快報詳情 — ${selectedReport?.date || ''}`}
        open={!!selectedReport} onCancel={() => setSelectedReport(null)}
        footer={null} width={720}>
        {modalLoading ? <Spin style={{ display: 'block', margin: 40 }} /> : selectedReport && <DailyBriefContent key={selectedReport._key} report={selectedReport} />}
      </Modal>
    </div>
  );
}

/* ─── 快報內容（可複用） ────────────────────────── */

function DailyBriefContent({ report }: { report: any }) {
  const allItems = [
    ...(report.items || []).map((i: any) => ({ ...i, _fromSupervisor: false })),
  ];
  const high = allItems.filter((i: any) => i.relevance === 'high');
  const medium = allItems.filter((i: any) => i.relevance === 'medium');
  const low = allItems.filter((i: any) => i.relevance === 'low');

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12, background: 'var(--ant-color-primary-bg, #f0f5ff)' }}>
        <Text strong style={{ fontSize: 14 }}>{report.daily_focus || '無資訊'}</Text>
        <div style={{ maxHeight: 80, overflow: 'auto', marginTop: 4, minHeight: 60 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>{report.overall_assessment || ''}</Text>
        </div>
      </Card>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <Card size="small" title="📈 趨勢" style={{ flex: 1, maxHeight: 140, overflow: 'auto' }}>
          <div style={{ minHeight: 36 }}>
            {(report.key_trends || []).map((t: string, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '1px 0' }}>• {t}</div>
            ))}
          </div>
        </Card>
        <Card size="small" title="⚠️ 注意" style={{ flex: 1, maxHeight: 140, overflow: 'auto' }}>
          <div style={{ minHeight: 36 }}>
            {(report.attention_points || []).map((t: string, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '1px 0' }}>• {t}</div>
            ))}
          </div>
        </Card>
        <Card size="small" title="💡 商機" style={{ flex: 1, maxHeight: 140, overflow: 'auto' }}>
          <div style={{ minHeight: 36 }}>
            {(report.opportunities || []).map((t: string, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '1px 0' }}>• {t}</div>
            ))}
          </div>
        </Card>
      </div>

      <Tabs size="small" items={[
        { label: `🔴 高關聯 (${high.length})`, key: 'high', children: renderItemsShort(high) },
        { label: `🟡 中關聯 (${medium.length})`, key: 'medium', children: renderItemsShort(medium) },
        { label: `ℹ️ 一般資訊 (${low.length})`, key: 'low', children: renderItemsShort(low) },
      ].filter(t => t.children)} />

      {report.token_usage?.total && (
        <Text type="secondary" style={{ fontSize: 11, display: 'block', textAlign: 'right' }}>
          🤖 LLM {report.token_usage.total.toLocaleString()} tokens
        </Text>
      )}
    </div>
  );
}

function renderItemsShort(items: any[]) {
  if (items.length === 0) return null;
  return (
    <div style={{ maxHeight: 360, overflow: 'auto' }}>
      {items.map((item: any, i: number) => (
        <Card key={i} size="small" style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <Tag color={REL_COLORS[item.relevance]} style={{ fontSize: 10 }}>{REL_LABELS[item.relevance]}</Tag>
            {item._fromSupervisor && <Tag color="purple" style={{ fontSize: 10 }}>管</Tag>}
            <Text strong style={{ fontSize: 13, cursor: 'pointer' }}
              onClick={() => window.open(item.url, '_blank')}>{item.title}</Text>
          </div>
          <div style={{ fontSize: 12, color: '#555' }}>{item.summary}</div>
          {item.action && <div style={{ fontSize: 12, color: '#1677ff', marginTop: 2 }}>💡 {item.action}</div>}
        </Card>
      ))}
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────── */

const TABS = [
    { key: 'brief', label: '📋 今日快報', component: <DailyBrief /> },
    { key: 'history', label: '📅 執行記錄', component: <HistoryTab /> },
    { key: 'settings', label: '⚙️ 操作設置', component: <SettingsTab /> },
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
