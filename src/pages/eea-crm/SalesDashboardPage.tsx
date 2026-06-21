import { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Select,
  DatePicker,
  Typography,
} from 'antd';
import {
  RiseOutlined,
  AimOutlined,
  TeamOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import { PieChart, Pie, Cell, Bar, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ComposedChart } from 'recharts';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';

const { RangePicker } = DatePicker;
const { Text } = Typography;

const KPI_DATA = {
  revenue: 38600000,
  growthRate: 12.3,
  targetRate: 78.5,
  activeCustomers: 42,
};

const REGION_DATA = [
  { region: '北部', amount: 8500000, pct: 44.7 },
  { region: '中部', amount: 6200000, pct: 32.6 },
  { region: '南部', amount: 4300000, pct: 22.6 },
];

const DEPT_DATA = [
  { product: 'A產品', amount: 5200000, pct: 27.4 },
  { product: 'B產品', amount: 3800000, pct: 20.0 },
  { product: 'C產品', amount: 2900000, pct: 15.3 },
  { product: 'D產品', amount: 7100000, pct: 37.4 },
];

const PIE_COLORS = ['#1677ff', '#52c41a', '#fa8c16', '#ff4d4f', '#722ed1', '#13c2c2', '#eb2f96', '#faad14'];

const REGION_COLORS: Record<string, string> = { '北部': '#1677ff', '中部': '#52c41a', '南部': '#fa8c16' };

const MONTH_DATA = [
  { month: '7月', 北部: 1100000, 中部: 750000, 南部: 600000, total: 2450000, cumulative: 2450000 },
  { month: '8月', 北部: 1400000, 中部: 950000, 南部: 750000, total: 3100000, cumulative: 5550000 },
  { month: '9月', 北部: 1200000, 中部: 900000, 南部: 700000, total: 2800000, cumulative: 8350000 },
  { month: '10月', 北部: 1600000, 中部: 1100000, 南部: 900000, total: 3600000, cumulative: 11950000 },
  { month: '11月', 北部: 1800000, 中部: 1300000, 南部: 1100000, total: 4200000, cumulative: 16150000 },
  { month: '12月', 北部: 1600000, 中部: 1200000, 南部: 1000000, total: 3800000, cumulative: 19950000 },
  { month: '1月', 北部: 1800000, 中部: 1300000, 南部: 1000000, total: 4100000, cumulative: 24050000 },
  { month: '2月', 北部: 1200000, 中部: 900000, 南部: 800000, total: 2900000, cumulative: 26950000 },
  { month: '3月', 北部: 2000000, 中部: 1400000, 南部: 1100000, total: 4500000, cumulative: 31450000 },
  { month: '4月', 北部: 1400000, 中部: 1000000, 南部: 900000, total: 3300000, cumulative: 34750000 },
  { month: '5月', 北部: 900000, 中部: 650000, 南部: 550000, total: 2100000, cumulative: 36850000 },
  { month: '6月', 北部: 750000, 中部: 550000, 南部: 450000, total: 1750000, cumulative: 38600000 },
];

const QUARTER_DATA = [
  { label: 'Q3', revenue: 8350000, growth: 8.2, target: 72.0, customers: 38 },
  { label: 'Q4', revenue: 11950000, growth: 10.5, target: 75.3, customers: 40 },
  { label: 'Q1', revenue: 8450000, growth: 14.1, target: 80.1, customers: 43 },
  { label: 'Q2', revenue: 7150000, growth: 11.8, target: 76.8, customers: 42 },
];

function MiniSparkline({ data, dataKey, color }: { data: typeof QUARTER_DATA; dataKey: string; color: string }) {
  const max = Math.max(...data.map(d => Number(d[dataKey as keyof typeof d])));
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 48 }}>
      {data.map((d, i) => {
        const v = Number(d[dataKey as keyof typeof d]);
        const h = max > 0 ? (v / max) * 100 : 0;
        return (
          <div key={d.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <div style={{ width: '100%', height: `${Math.max(h * 0.55, 10)}px`, background: color, borderRadius: '3px 3px 0 0', opacity: 0.6 + (i === 3 ? 0.4 : 0), transition: 'height 0.3s' }} />
            <span style={{ fontSize: 9, color: '#999' }}>{d.label}</span>
          </div>
        );
      })}
    </div>
  );
}

const TOP_SALES = [
  { name: '王大明', amount: 12800000, deals: 8 },
  { name: '陳小華', amount: 9500000, deals: 6 },
  { name: '張偉強', amount: 8700000, deals: 5 },
  { name: '林怡君', amount: 7200000, deals: 7 },
  { name: '李志明', amount: 6500000, deals: 4 },
  { name: '黃淑芬', amount: 5800000, deals: 5 },
];

export default function SalesDashboardPage() {
  const contentTokens = useContentTokens();
  const [period, setPeriod] = useState<string>('month');

  const maxAmount = Math.max(...TOP_SALES.map(s => s.amount));

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/sales-performance',
      pageName: 'EEA-CRM 銷售業績統計',
      entityType: 'dashboard',
      action: 'view',
    });
  }, []);

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Period selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Text strong style={{ fontSize: 16 }}>銷售業績統計</Text>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Select
            value={period}
            onChange={setPeriod}
            style={{ width: 100 }}
            size="small"
            options={[
              { label: '本月', value: 'month' },
              { label: '本季', value: 'quarter' },
              { label: '本年', value: 'year' },
            ]}
          />
          {period === 'custom' && <RangePicker size="small" />}
        </div>
      </div>

      {/* Row 1: KPI cards + 季趨勢簡圖 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" hoverable styles={{ body: { padding: '20px 16px 12px', minHeight: 190, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } }}>
            <Statistic title="營業額 (YTD)" value={KPI_DATA.revenue} precision={0}
              prefix={<DollarOutlined />} suffix="元"
              valueStyle={{ fontSize: 22, fontWeight: 600 }} />
            <MiniSparkline data={QUARTER_DATA} dataKey="revenue" color="#1677ff" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable styles={{ body: { padding: '20px 16px 12px', minHeight: 190, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } }}>
            <Statistic title="年增率" value={KPI_DATA.growthRate} precision={1}
              prefix={<RiseOutlined />} suffix="%"
              valueStyle={{ fontSize: 22, fontWeight: 600, color: KPI_DATA.growthRate >= 0 ? '#52c41a' : '#ff4d4f' }} />
            <MiniSparkline data={QUARTER_DATA} dataKey="growth" color="#52c41a" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable styles={{ body: { padding: '20px 16px 12px', minHeight: 190, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } }}>
            <Statistic title="目標達成率" value={KPI_DATA.targetRate} precision={1}
              prefix={<AimOutlined />} suffix="%"
              valueStyle={{ fontSize: 22, fontWeight: 600 }} />
            <MiniSparkline data={QUARTER_DATA} dataKey="target" color="#fa8c16" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable styles={{ body: { padding: '20px 16px 12px', minHeight: 190, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } }}>
            <Statistic title="活躍客戶數" value={KPI_DATA.activeCustomers}
              prefix={<TeamOutlined />}
              valueStyle={{ fontSize: 22, fontWeight: 600 }} />
            <MiniSparkline data={QUARTER_DATA} dataKey="customers" color="#722ed1" />
          </Card>
        </Col>
      </Row>

      {/* Row 2: 左側兩張圖 + 右側業務員排名 — 統一高度 */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={7}>
          <Card title="區域業績分布" size="small" styles={{ body: { padding: '12px 12px 4px', height: 230 } }}>
            <div style={{ display: 'flex', justifyContent: 'center', height: 210 }}>
              <ResponsiveContainer width="100%" height={210}>
                <PieChart>
                  <Pie data={REGION_DATA} cx="50%" cy="50%" innerRadius={48} outerRadius={82}
                    dataKey="amount" nameKey="region" paddingAngle={2} strokeWidth={0}>
                    {REGION_DATA.map((_, i) => (
                      <Cell key={i} fill={Object.values(REGION_COLORS)[i]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => `${(Number(value) / 10000).toFixed(0)}萬`}
                    contentStyle={{ borderRadius: 6, fontSize: 12 }} />
                  <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 11 }}
                    formatter={(value: string) => <span style={{ fontSize: 11, color: '#555' }}>{value}</span>} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Col>
        <Col span={7}>
          <Card title="產品類別績效占比" size="small" styles={{ body: { padding: '12px 12px 4px', height: 230 } }}>
            <div style={{ display: 'flex', justifyContent: 'center', height: 210 }}>
              <ResponsiveContainer width="100%" height={210}>
                <PieChart>
                  <Pie data={DEPT_DATA} cx="50%" cy="50%" innerRadius={48} outerRadius={82}
                    dataKey="amount" nameKey="product" paddingAngle={2} strokeWidth={0}>
                    {DEPT_DATA.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => `${(Number(value) / 10000).toFixed(0)}萬`}
                    contentStyle={{ borderRadius: 6, fontSize: 12 }} />
                  <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 11 }}
                    formatter={(value: string) => <span style={{ fontSize: 11, color: '#555' }}>{value}</span>} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Col>
        <Col span={10}>
          <Card title="業務員業績排名" size="small" styles={{ body: { padding: '12px 16px 8px', height: 230 } }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, height: '100%', justifyContent: 'space-around' }}>
              {TOP_SALES.map((s, i) => (
                <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%',
                    background: i < 3 ? '#ff4d4f' : '#f0f0f0',
                    color: i < 3 ? '#fff' : '#666',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 600, flexShrink: 0,
                  }}>
                    {i + 1}
                  </div>
                  <Text style={{ width: 60, fontSize: 12, flexShrink: 0 }}>{s.name}</Text>
                  <div style={{ flex: 1, height: 14, background: '#f5f5f5', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{
                      width: `${(s.amount / maxAmount) * 100}%`, height: '100%',
                      background: i < 3
                        ? 'linear-gradient(90deg, #ff4d4f, #ff7875)'
                        : 'linear-gradient(90deg, #1677ff, #4096ff)',
                      borderRadius: 3, transition: 'width 0.6s ease',
                    }} />
                  </div>
                  <Text style={{ width: 70, textAlign: 'right', fontSize: 11, fontWeight: 500, flexShrink: 0 }}>
                    {(s.amount / 10000).toFixed(0)}萬
                  </Text>
                  <Text type="secondary" style={{ width: 36, textAlign: 'right', fontSize: 10, flexShrink: 0 }}>
                    {s.deals}件
                  </Text>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      {/* Row 3: 全年趨勢複合圖 — 堆疊北中南 bar + 總金額線 */}
      <Card title="近 12 個月業績趨勢" size="small">
        <ResponsiveContainer width="100%" height={250}>
          <ComposedChart data={MONTH_DATA} margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
            <XAxis dataKey="month" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="left" tick={{ fontSize: 11 }} axisLine={false} tickLine={false}
              tickFormatter={(v: number) => `${(v / 10000).toFixed(0)}萬`} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} axisLine={false} tickLine={false}
              tickFormatter={(v: number) => `${(v / 10000).toFixed(0)}萬`} />
            <Tooltip
              formatter={(value: any, name: any, entry: any) => {
                const v = Number(value);
                if (name === 'total') return [`${(v / 10000).toFixed(0)}萬`, '月總額'];
                if (name === 'cumulative') return [`${(v / 10000).toFixed(0)}萬`, '累計績效'];
                const pct = entry?.payload?.total ? ((v / entry.payload.total) * 100).toFixed(1) : '0';
                return [`${(v / 10000).toFixed(0)}萬 (${pct}%)`, name];
              }}
              contentStyle={{ borderRadius: 6, fontSize: 12 }}
            />
            <Legend verticalAlign="top" iconType="rect" wrapperStyle={{ fontSize: 12, marginBottom: -8 }}
              formatter={(value: string) => {
                const labels: Record<string, string> = { 北部: '北部', 中部: '中部', 南部: '南部', total: '月總額', cumulative: '累計績效' };
                return <span style={{ color: '#555' }}>{labels[value] || value}</span>;
              }} />
            {(['北部', '中部', '南部'] as const).map(r => (
              <Bar key={r} yAxisId="left" dataKey={r} stackId="month" fill={REGION_COLORS[r]}
                barSize={36} radius={[0, 0, 0, 0]} />
            ))}
            <Line yAxisId="right" type="monotone" dataKey="total" stroke="#8c8c8c"
              strokeWidth={2} dot={{ fill: '#8c8c8c', r: 3 }} activeDot={{ r: 5 }}
              strokeDasharray="4 2" />
            <Line yAxisId="right" type="monotone" dataKey="cumulative" stroke="#ff4d4f"
              strokeWidth={2.5} dot={{ fill: '#ff4d4f', r: 3 }} activeDot={{ r: 5 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}