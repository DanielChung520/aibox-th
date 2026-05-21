import { useState, useEffect, useMemo, useCallback } from 'react';
import { Card, Col, Row, Statistic, Spin, App, DatePicker, Space, Button, Tag, Popconfirm } from 'antd';
import { authStore } from '../../stores/auth';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import { pageContextManager } from '../../services/PageContextManager';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';

const { RangePicker } = DatePicker;

const SOURCE_EMOJI: Record<string, string> = {
  electricity: '⚡', natural_gas: '🔥', fuel_diesel: '🛢️', water: '💧',
  solar: '☀️', wind: '🌬️', biomass_pellet: '🔥',
  transport_truck: '🚛', transport_sea: '🚢', transport_air: '✈️',
};

const SCOPE_COLORS: Record<string, string> = {
  scope1: '#ff4d4f', scope2: '#1890ff', scope3: '#52c41a',
};

const PIE_COLORS = ['#1890ff', '#ff4d4f', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#eb2f96'];

interface CarbonRecord {
  _key: string; submitted_at: string; source_type: string;
  source_description?: string; activity_value: number; activity_unit: string;
  total_co2e_kg: number; scope: string; status: string;
}

function flattenApiResponse(raw: unknown): CarbonRecord[] {
  if (Array.isArray(raw)) return raw as CarbonRecord[];
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.data)) return obj.data as CarbonRecord[];
    if (Array.isArray(obj.records)) return obj.records as CarbonRecord[];
  }
  return [];
}

function generateMockRecords(): CarbonRecord[] {
  const now = new Date();
  const records: CarbonRecord[] = [];
  let idx = 0;

  const sources: Array<{ type: string; scope: string; unit: string; base: number; volatility: number; label: string }> = [
    { type: 'electricity', scope: 'scope2', unit: 'kWh', base: 8500, volatility: 0.15, label: '廠區用電' },
    { type: 'natural_gas', scope: 'scope1', unit: 'm³', base: 320, volatility: 0.12, label: '鍋爐天然氣' },
    { type: 'fuel_diesel', scope: 'scope1', unit: 'liter', base: 180, volatility: 0.2, label: '堆高機柴油' },
    { type: 'water', scope: 'scope2', unit: 'm³', base: 420, volatility: 0.1, label: '全廠用水' },
    { type: 'transport_truck', scope: 'scope3', unit: 'ton-km', base: 12000, volatility: 0.18, label: '原料貨運' },
  ];

  for (let m = 0; m < 12; m++) {
    const month = new Date(now.getFullYear(), now.getMonth() - 5 + m, 1);
    const monthStr = month.toISOString().slice(0, 7);
    for (const src of sources) {
      idx++;
      const factor: Record<string, number> = {
        electricity: 0.495, natural_gas: 2.02, fuel_diesel: 2.68, water: 0.195, transport_truck: 0.92,
      };
      const activity = Math.round(src.base * (1 + (Math.random() - 0.5) * src.volatility * 2));
      const co2e = parseFloat((activity * (factor[src.type] || 1)).toFixed(1));
      const day = Math.floor(Math.random() * 25) + 1;
      records.push({
        _key: `mock_${idx}`,
        submitted_at: `${monthStr}-${String(day).padStart(2, '0')}T08:${String(10 + (idx % 50)).padStart(2, '0')}:00Z`,
        source_type: src.type,
        source_description: src.label,
        activity_value: activity,
        activity_unit: src.unit,
        total_co2e_kg: co2e,
        scope: src.scope,
        status: 'confirmed',
      });
    }
  }
  return records;
}

function sourceTypeSummary(r: CarbonRecord[]): string {
  const map = new Map<string, number>();
  for (const rec of r) {
    const key = `${SOURCE_EMOJI[rec.source_type] || ''} ${rec.source_type}`;
    map.set(key, (map.get(key) || 0) + rec.total_co2e_kg);
  }
  return Array.from(map.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${k}: ${v.toFixed(0)} kg`)
    .join(' | ');
}

export default function ESGDashboard() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [apiRecords, setApiRecords] = useState<CarbonRecord[]>([]);
  const [mockRecords, setMockRecords] = useState<CarbonRecord[]>([]);
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [mode, setMode] = useState<'api' | 'mock'>('api');
  useEntityPerception({ defaultEntityType: 'function', defaultAction: 'list' });
  useEffect(() => { pageContextManager.report({ component: 'ESGDashboard', action: 'view' }); }, []);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/esg/records', {
        headers: { Authorization: `Bearer ${authStore.getState().token}` },
      });
      const json = await res.json();
      const data = flattenApiResponse(json);
      setApiRecords(data);
      if (data.length === 0) {
        const mock = generateMockRecords();
        setMockRecords(mock);
        setMode('mock');
        message.info('資料庫尚無記錄，已自動載入模擬數據。正式上線後點擊「清除模擬數據」即可切回 API');
      } else {
        setMode('api');
      }
    } catch {
      const mock = generateMockRecords();
      setMockRecords(mock);
      setMode('mock');
      message.info('API 連線失敗，已自動載入模擬數據供預覽');
    } finally { setLoading(false); }
  }, [message]);

  useEffect(() => { fetchRecords(); }, [fetchRecords]);

  const loadMock = () => {
    setMockRecords(generateMockRecords());
    setMode('mock');
    message.success('已載入模擬數據');
  };

  const clearMock = () => {
    setMockRecords([]);
    setMode('api');
    fetchRecords();
    message.success('已清除模擬數據，恢復 API 資料');
  };

  const records = mode === 'mock' ? mockRecords : apiRecords;

  const filtered = useMemo(() => {
    if (!dateRange) return records;
    const [start, end] = dateRange;
    return records.filter(r => r.submitted_at >= start && r.submitted_at <= end);
  }, [records, dateRange]);

  const trendData = useMemo(() => {
    const map = new Map<string, Record<string, number>>();
    for (const r of filtered) {
      const month = r.submitted_at?.slice(0, 7) || 'unknown';
      if (!map.has(month)) map.set(month, { month });
      const entry = map.get(month)!;
      const key = r.source_type || 'other';
      entry[key] = (entry[key] || 0) + r.total_co2e_kg;
    }
    return Array.from(map.values()).sort((a, b) => a.month.localeCompare(b.month));
  }, [filtered]);

  const sourceTypes = useMemo(() => {
    const set = new Set<string>();
    for (const r of filtered) if (r.source_type) set.add(r.source_type);
    return Array.from(set);
  }, [filtered]);

  const pieData = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of filtered) {
      const s = r.scope || 'unknown';
      map.set(s, (map.get(s) || 0) + r.total_co2e_kg);
    }
    return Array.from(map.entries()).map(([name, value]) => ({ name, value }));
  }, [filtered]);

  const stats = useMemo(() => {
    const total = filtered.reduce((s, r) => s + r.total_co2e_kg, 0);
    const scope2 = filtered.filter(r => r.scope === 'scope2').reduce((s, r) => s + r.total_co2e_kg, 0);
    const scope1 = filtered.filter(r => r.scope === 'scope1').reduce((s, r) => s + r.total_co2e_kg, 0);
    const scope3 = filtered.filter(r => r.scope === 'scope3').reduce((s, r) => s + r.total_co2e_kg, 0);
    return { total, scope1, scope2, scope3 };
  }, [filtered]);

  const hasData = filtered.length > 0;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <h2 style={{ margin: 0 }}>📊 ESG Dashboard</h2>
        <Space wrap>
          {mode === 'mock' && <Tag color="orange">🧪 模擬數據模式</Tag>}
          {mode === 'api' && <Tag color="green">✅ 正式數據</Tag>}
          <Button onClick={loadMock} size="small">📥 載入模擬數據</Button>
          <Popconfirm title="清除模擬數據，恢復 API 資料？" onConfirm={clearMock} okText="清除" cancelText="取消">
            <Button danger size="small">🗑️ 清除模擬數據</Button>
          </Popconfirm>
          <RangePicker
            onChange={(_, dateStrings) => {
              if (dateStrings[0] && dateStrings[1]) setDateRange([dateStrings[0], dateStrings[1]]);
              else setDateRange(null);
            }}
          />
        </Space>
      </div>

      <Spin spinning={loading}>
        {hasData ? (
          <>
            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
              <Col xs={12} sm={6}>
                <Card><Statistic title="🌍 總碳排" value={stats.total.toFixed(0)} suffix="kg CO₂e" /></Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card><Statistic title="📦 範疇一" value={stats.scope1.toFixed(0)} suffix="kg CO₂e" valueStyle={{ color: '#ff4d4f' }} /></Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card><Statistic title="⚡ 範疇二" value={stats.scope2.toFixed(0)} suffix="kg CO₂e" valueStyle={{ color: '#1890ff' }} /></Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card><Statistic title="🚛 範疇三" value={stats.scope3.toFixed(0)} suffix="kg CO₂e" valueStyle={{ color: '#52c41a' }} /></Card>
              </Col>
            </Row>

            <Card title="📈 各類能源排放趨勢" style={{ marginBottom: 24 }}>
              <ResponsiveContainer width="100%" height={350}>
                <ComposedChart data={trendData}>
                  <CartesianGrid stroke="#f5f5f5" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  {sourceTypes.map((st, i) => (
                    <Bar key={st} dataKey={st} fill={PIE_COLORS[i % PIE_COLORS.length]}
                      name={`${SOURCE_EMOJI[st] || ''} ${st}`} barSize={20} />
                  ))}
                  {sourceTypes.slice(0, 1).map(st => (
                    <Line key={`line-${st}`} type="monotone" dataKey={st}
                      stroke="#ff7300" strokeWidth={2} name={`${SOURCE_EMOJI[st] || ''} ${st} 趨勢`} />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </Card>

            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card title="🥧 範疇分類比率">
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={pieData} cx="50%" cy="50%" outerRadius={100}
                        label={({ name, value }) => `${name}: ${(value / stats.total * 100).toFixed(1)}%`}
                        dataKey="value">
                        {pieData.map(entry => (
                          <Cell key={entry.name} fill={SCOPE_COLORS[entry.name] || '#ccc'} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ marginTop: 12, fontSize: 13, color: '#666' }}>
                    {sourceTypeSummary(filtered)}
                  </div>
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card title="📋 統計摘要">
                  <Row gutter={[8, 8]}>
                    {pieData.map(d => (
                      <Col span={24} key={d.name}>
                        <Statistic
                          title={d.name === 'scope1' ? '📦 範疇一 (直接排放)' : d.name === 'scope2' ? '⚡ 範疇二 (能源間接)' : '🚛 範疇三 (運輸及其他)'}
                          value={d.value.toFixed(1)}
                          suffix="kg CO₂e"
                          valueStyle={{ color: SCOPE_COLORS[d.name] || '#000' }}
                        />
                      </Col>
                    ))}
                    <Col span={24}>
                      <div style={{ marginTop: 8, padding: 8, background: '#f5f5f5', borderRadius: 6 }}>
                        <small style={{ color: '#999' }}>
                          {mode === 'mock' ? '🧪 目前顯示為模擬數據，正式上線後點擊「清除模擬數據」切回 API' : '✅ 資料來自 API／資料庫'}
                        </small>
                      </div>
                    </Col>
                  </Row>
                </Card>
              </Col>
            </Row>
          </>
        ) : (
          <Card style={{ marginTop: 16, textAlign: 'center' }}>
            <p style={{ color: '#999', fontSize: 16, marginBottom: 16 }}>尚無碳排記錄</p>
            <Button type="primary" onClick={loadMock}>📥 載入模擬數據預覽</Button>
          </Card>
        )}
      </Spin>
    </div>
  );
}
