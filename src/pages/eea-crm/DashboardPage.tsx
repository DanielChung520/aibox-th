/**
 * @file        EEA-CRM 信息看板頁面
 * @description 包含客戶地圖與銷售業績統計兩個子分頁，純 Mock 資料展示
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Tabs,
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
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import CustomerMapComponent from '../../components/crm/CustomerMap';

const { RangePicker } = DatePicker;
const { Text } = Typography;

/* ---------- Mock data ---------- */

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

const TOP_SALES = [
  { name: '王大明', amount: 12800000, deals: 8 },
  { name: '陳小華', amount: 9500000, deals: 6 },
  { name: '張偉強', amount: 8700000, deals: 5 },
  { name: '林怡君', amount: 7200000, deals: 7 },
  { name: '李志明', amount: 6500000, deals: 4 },
  { name: '黃淑芬', amount: 5800000, deals: 5 },
  { name: '劉建宏', amount: 4900000, deals: 3 },
  { name: '吳佩珊', amount: 4100000, deals: 4 },
  { name: '楊宗翰', amount: 3200000, deals: 3 },
  { name: '趙雅婷', amount: 2800000, deals: 2 },
];

/* ---------- CSS Bar component ---------- */

function CSSBar({ label, value, pct, color }: { label: string; value: string; pct: number; color?: string }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
        <Text style={{ fontSize: 12 }}>{label}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>{value}</Text>
      </div>
      <div style={{ height: 20, background: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: color || '#1677ff',
          borderRadius: 4,
          transition: 'width 0.6s ease',
        }} />
      </div>
    </div>
  );
}

/* ========== Page Components ========== */

function CustomerMap() {
  return (
    <div style={{ height: 'calc(100vh - 180px)', position: 'relative' }}>
      <CustomerMapComponent />
    </div>
  );
}

function SalesPerformance() {
  const [period, setPeriod] = useState<string>('month');

  const maxAmount = Math.max(...TOP_SALES.map(s => s.amount));
  const maxRegion = Math.max(...REGION_DATA.map(r => r.amount));
  const maxDept = Math.max(...DEPT_DATA.map(d => d.amount));

  return (
    <div>
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

      {/* Row 1: KPI cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" hoverable>
            <Statistic
              title="營業額 (YTD)"
              value={KPI_DATA.revenue}
              precision={0}
              prefix={<DollarOutlined />}
              suffix="元"
              valueStyle={{ fontSize: 20, fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable>
            <Statistic
              title="年增率"
              value={KPI_DATA.growthRate}
              precision={1}
              prefix={<RiseOutlined />}
              suffix="%"
              valueStyle={{ fontSize: 20, fontWeight: 600, color: KPI_DATA.growthRate >= 0 ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable>
            <Statistic
              title="目標達成率"
              value={KPI_DATA.targetRate}
              precision={1}
              prefix={<AimOutlined />}
              suffix="%"
              valueStyle={{ fontSize: 20, fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable>
            <Statistic
              title="活躍客戶數"
              value={KPI_DATA.activeCustomers}
              prefix={<TeamOutlined />}
              valueStyle={{ fontSize: 20, fontWeight: 600 }}
            />
          </Card>
        </Col>
      </Row>

      {/* Row 2: Charts */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="區域業績" size="small">
            {REGION_DATA.map(r => (
              <CSSBar
                key={r.region}
                label={r.region}
                value={`${(r.amount / 10000).toFixed(0)}萬`}
                pct={(r.amount / maxRegion) * 100}
                color="#1677ff"
              />
            ))}
            <div style={{ textAlign: 'right', marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                合計：{(REGION_DATA.reduce((s, r) => s + r.amount, 0) / 10000).toFixed(0)}萬
              </Text>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="部門業績" size="small">
            {DEPT_DATA.map(d => (
              <CSSBar
                key={d.product}
                label={d.product}
                value={`${(d.amount / 10000).toFixed(0)}萬`}
                pct={(d.amount / maxDept) * 100}
                color="#722ed1"
              />
            ))}
            <div style={{ textAlign: 'right', marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                合計：{(DEPT_DATA.reduce((s, d) => s + d.amount, 0) / 10000).toFixed(0)}萬
              </Text>
            </div>
          </Card>
        </Col>
      </Row>

      {/* Row 3: Top Sales */}
      <Card title="業務員業績 Top 10" size="small">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {TOP_SALES.map((s, i) => (
            <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 22,
                height: 22,
                borderRadius: '50%',
                background: i < 3 ? '#ff4d4f' : '#f0f0f0',
                color: i < 3 ? '#fff' : '#666',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 11,
                fontWeight: 600,
              }}>
                {i + 1}
              </div>
              <Text style={{ width: 80, fontSize: 13 }}>{s.name}</Text>
              <div style={{ flex: 1, height: 18, background: '#f5f5f5', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{
                  width: `${(s.amount / maxAmount) * 100}%`,
                  height: '100%',
                  background: i < 3
                    ? 'linear-gradient(90deg, #ff4d4f, #ff7875)'
                    : 'linear-gradient(90deg, #1677ff, #4096ff)',
                  borderRadius: 4,
                  transition: 'width 0.6s ease',
                }} />
              </div>
              <Text style={{ width: 90, textAlign: 'right', fontSize: 12, fontWeight: 500 }}>
                {(s.amount / 10000).toFixed(0)}萬
              </Text>
              <Text type="secondary" style={{ width: 50, textAlign: 'right', fontSize: 11 }}>
                {s.deals}件
              </Text>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

/* ========== Main Page ========== */

export default function DashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const contentTokens = useContentTokens();

  const tabFromUrl = searchParams.get('tab') === 'sales-performance' ? 'sales-performance' : 'customer-map';

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/dashboard',
      pageName: 'EEA-CRM 信息看板',
      entityType: 'dashboard',
      action: 'view',
    });
  }, []);

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      <Tabs
        activeKey={tabFromUrl}
        onChange={(key) => setSearchParams({ tab: key })}
        items={[
          { key: 'customer-map', label: '🗺️ 客戶地圖', children: <CustomerMap /> },
          { key: 'sales-performance', label: '📈 銷售業績統計', children: <SalesPerformance /> },
        ]}
        size="large"
      />
    </div>
  );
}
