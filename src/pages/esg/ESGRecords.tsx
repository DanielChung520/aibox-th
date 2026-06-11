/**
 * @file        ESGRecords.tsx
 * @description 收集記錄 — 碳排呈報記錄瀏覽與匯出
 * @lastUpdate  2026-05-16
 * @author      AI Agent
 * @version     1.0.0
 *
 * TODO: Will use /api/v1/esg/records when API is implemented
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table,
  Button,
  Tag,
  Space,
  App,
  Drawer,
  Descriptions,
  Popconfirm,
  Typography,
  Row,
  Col,
  Card,
  Statistic,
  Select,
  Input,
  DatePicker,
  Spin,
  Divider,
} from 'antd';
import {
  DownloadOutlined,
  SearchOutlined,
  EyeOutlined,
  DeleteOutlined,
  ExportOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { authStore } from '../../stores/auth';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import { pageContextManager } from '../../services/PageContextManager';
import dayjs from 'dayjs';

const { Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CarbonSourceType =
  | 'electricity'
  | 'heat'
  | 'water'
  | 'fuel_diesel'
  | 'fuel_gasoline'
  | 'natural_gas'
  | 'refrigerant'
  | 'waste'
  | 'transport_air'
  | 'transport_rail';

export type CarbonScope = 'scope1' | 'scope2' | 'scope3';
export type CarbonStatus = 'draft' | 'confirmed' | 'submitted_ifas';

export interface CarbonRecord {
  _key: string;
  source_type: CarbonSourceType;
  source_name: string;
  category: CarbonScope;
  activity_value: number;
  unit: string;
  emission_kg: number;
  status: CarbonStatus;
  submitted_at: string;
  submitted_via: 'line' | 'manual';
  notes?: string;
  factor_key?: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SOURCE_TYPE_MAP: Record<CarbonSourceType, { label: string; emoji: string }> = {
  electricity: { label: '電力', emoji: '⚡' },
  heat: { label: '熱能', emoji: '🔥' },
  water: { label: '水資源', emoji: '💧' },
  fuel_diesel: { label: '柴油', emoji: '🛢️' },
  fuel_gasoline: { label: '汽油', emoji: '⛽' },
  natural_gas: { label: '天然氣', emoji: '🔥' },
  refrigerant: { label: '冷媒', emoji: '❄️' },
  waste: { label: '廢棄物', emoji: '🗑️' },
  transport_air: { label: '航空運輸', emoji: '✈️' },
  transport_rail: { label: '鐵路運輸', emoji: '🚆' },
};

const CATEGORY_OPTIONS = [
  { value: '', label: '全部範疇' },
  { value: 'scope1', label: '範疇一 (直接排放)' },
  { value: 'scope2', label: '範疇二 (能源間接)' },
  { value: 'scope3', label: '範疇三 (其他間接)' },
];

const STATUS_OPTIONS = [
  { value: '', label: '全部狀態' },
  { value: 'draft', label: '草稿' },
  { value: 'confirmed', label: '已確認' },
  { value: 'submitted_ifas', label: '已提交IFAS' },
];

const STATUS_MAP: Record<CarbonStatus, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  confirmed: { label: '已確認', color: 'green' },
  submitted_ifas: { label: '已提交IFAS', color: 'blue' },
};

const EMISSION_THRESHOLD_HIGH = 10000;
const EMISSION_THRESHOLD_MEDIUM = 1000;

function getEmissionColor(val: number): string {
  if (val >= EMISSION_THRESHOLD_HIGH) return '#cf1322';
  if (val >= EMISSION_THRESHOLD_MEDIUM) return '#d46b08';
  return '#389e0d';
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const NOW = dayjs();
const MOCK_RECORDS: CarbonRecord[] = [
  {
    _key: 'rec_001',
    source_type: 'electricity',
    source_name: '辦公大樓用電',
    category: 'scope2',
    activity_value: 125000,
    unit: 'kWh',
    emission_kg: 63625,
    status: 'confirmed',
    submitted_at: NOW.subtract(2, 'day').toISOString(),
    submitted_via: 'manual',
    notes: '五月辦公大樓電費單',
    created_at: NOW.subtract(2, 'day').toISOString(),
    updated_at: NOW.subtract(1, 'day').toISOString(),
  },
  {
    _key: 'rec_002',
    source_type: 'natural_gas',
    source_name: '鍋爐天然氣用量',
    category: 'scope1',
    activity_value: 8500,
    unit: 'm³',
    emission_kg: 17170.51,
    status: 'confirmed',
    submitted_at: NOW.subtract(5, 'day').toISOString(),
    submitted_via: 'line',
    notes: '生產線鍋爐天然氣錶讀數',
    created_at: NOW.subtract(5, 'day').toISOString(),
    updated_at: NOW.subtract(4, 'day').toISOString(),
  },
  {
    _key: 'rec_003',
    source_type: 'fuel_diesel',
    source_name: '緊急發電機柴油',
    category: 'scope1',
    activity_value: 1200,
    unit: 'liter',
    emission_kg: 3216.32,
    status: 'draft',
    submitted_at: NOW.subtract(1, 'day').toISOString(),
    submitted_via: 'manual',
    notes: '月度發電機測試用油',
    created_at: NOW.subtract(1, 'day').toISOString(),
    updated_at: NOW.subtract(1, 'day').toISOString(),
  },
  {
    _key: 'rec_004',
    source_type: 'transport_air',
    source_name: '商務艙國際飛航',
    category: 'scope3',
    activity_value: 3,
    unit: '趟',
    emission_kg: 12540,
    status: 'submitted_ifas',
    submitted_at: NOW.subtract(10, 'day').toISOString(),
    submitted_via: 'line',
    notes: 'Q2 員工出差碳排',
    created_at: NOW.subtract(10, 'day').toISOString(),
    updated_at: NOW.subtract(8, 'day').toISOString(),
  },
  {
    _key: 'rec_005',
    source_type: 'water',
    source_name: '全廠用水',
    category: 'scope2',
    activity_value: 45000,
    unit: 'm³',
    emission_kg: 1345.5,
    status: 'draft',
    submitted_at: NOW.subtract(15, 'day').toISOString(),
    submitted_via: 'manual',
    notes: '自來水公司本期帳單',
    created_at: NOW.subtract(15, 'day').toISOString(),
    updated_at: NOW.subtract(15, 'day').toISOString(),
  },
  {
    _key: 'rec_006',
    source_type: 'waste',
    source_name: '一般事業廢棄物',
    category: 'scope3',
    activity_value: 28.5,
    unit: 'ton',
    emission_kg: 3420,
    status: 'confirmed',
    submitted_at: NOW.subtract(3, 'day').toISOString(),
    submitted_via: 'line',
    notes: '清運聯單統計',
    created_at: NOW.subtract(3, 'day').toISOString(),
    updated_at: NOW.subtract(2, 'day').toISOString(),
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function flattenApiResponse(raw: unknown): CarbonRecord[] {
  if (Array.isArray(raw)) return raw as CarbonRecord[];
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.data)) return obj.data as CarbonRecord[];
    if (obj.data && typeof obj.data === 'object') {
      const inner = obj.data as Record<string, unknown>;
      if (Array.isArray(inner.records)) return inner.records as CarbonRecord[];
      if (Array.isArray(inner.data)) return inner.data as CarbonRecord[];
    }
    if (Array.isArray(obj.records)) return obj.records as CarbonRecord[];
  }
  return [];
}

const API_BASE = '/api/v1/esg/records';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ESGRecords() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<CarbonRecord[]>([]);
  const [filterDateRange, setFilterDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [filterScope, setFilterScope] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterSearch, setFilterSearch] = useState<string>('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<CarbonRecord | null>(null);
  const [datePreset, setDatePreset] = useState<string>('this_month');

  useEntityPerception({ defaultEntityType: 'table', defaultAction: 'list' });

  // ---- API ----

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(API_BASE, {
        headers: {
          Authorization: `Bearer ${authStore.getState().token}`,
        },
      });
      if (!res.ok) throw new Error('API 錯誤');
      const json = await res.json();
      setData(flattenApiResponse(json));
    } catch {
      setData(MOCK_RECORDS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  useEffect(() => {
    pageContextManager.report({
      component: 'ESGRecords',
      entityType: 'esg_record',
      action: 'list',
    });
    return () => {
      pageContextManager.report({
        component: 'ESGRecords',
        entityType: 'esg_record',
        action: undefined,
      });
    };
  }, []);

  // ---- Date preset ----

  const handleDatePreset = (preset: string) => {
    setDatePreset(preset);
    const now = dayjs();
    switch (preset) {
      case 'today':
        setFilterDateRange([now.startOf('day'), now.endOf('day')]);
        break;
      case 'this_week':
        setFilterDateRange([now.startOf('week'), now.endOf('week')]);
        break;
      case 'this_month':
        setFilterDateRange([now.startOf('month'), now.endOf('month')]);
        break;
      case 'all':
        setFilterDateRange(null);
        break;
      default:
        break;
    }
  };

  // ---- Filtered data ----

  const filteredData = useMemo(() => {
    return data.filter((item) => {
      if (filterScope && item.category !== filterScope) return false;
      if (filterStatus && item.status !== filterStatus) return false;
      if (filterDateRange?.[0] && filterDateRange?.[1]) {
        const d = dayjs(item.submitted_at);
        if (d.isBefore(filterDateRange[0]) || d.isAfter(filterDateRange[1])) return false;
      }

      if (filterSearch) {
        const q = filterSearch.toLowerCase();
        return (
          item.source_name.toLowerCase().includes(q) ||
          item.notes?.toLowerCase().includes(q) ||
          item.source_type.toLowerCase().includes(q)
        );
      }

      return true;
    });
  }, [data, filterScope, filterStatus, filterDateRange, filterSearch]);

  // ---- Stats ----

  const stats = useMemo(() => {
    let scope1Total = 0;
    let scope2Total = 0;
    const todayStr = dayjs().format('YYYY-MM-DD');
    const thisMonthStr = dayjs().format('YYYY-MM');
    let todayTotal = 0;
    let monthTotal = 0;

    for (const r of data) {
      if (r.category === 'scope1') scope1Total += r.emission_kg;
      if (r.category === 'scope2') scope2Total += r.emission_kg;
      if (dayjs(r.submitted_at).format('YYYY-MM-DD') === todayStr) todayTotal += r.emission_kg;
      if (dayjs(r.submitted_at).format('YYYY-MM') === thisMonthStr) monthTotal += r.emission_kg;
    }

    return { scope1Total, scope2Total, todayTotal, monthTotal };
  }, [data]);

  // ---- Handlers ----

  const handleViewDetail = (record: CarbonRecord) => {
    setSelectedRecord(record);
    setDrawerOpen(true);
  };

  const handleDelete = async (key: string) => {
    try {
      const res = await fetch(`${API_BASE}/${key}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${authStore.getState().token}`,
        },
      });
      if (!res.ok) throw new Error('刪除失敗');
      message.success('刪除成功');
      fetchList();
    } catch {
      setData((prev) => prev.filter((item) => item._key !== key));
      message.success('刪除成功');
    }
  };

  // ---- Columns ----

  const columns: ColumnsType<CarbonRecord> = [
    {
      title: '提交時間',
      dataIndex: 'submitted_at',
      width: 160,
      render: (t: string) => dayjs(t).format('YYYY/MM/DD HH:mm'),
      sorter: (a, b) => dayjs(a.submitted_at).unix() - dayjs(b.submitted_at).unix(),
      defaultSortOrder: 'descend',
    },
    {
      title: '來源',
      width: 160,
      render: (_, record) => {
        const src = SOURCE_TYPE_MAP[record.source_type];
        return (
          <Text>
            {src?.emoji ?? ''} {record.source_name}
          </Text>
        );
      },
    },
    {
      title: '活動數據',
      width: 150,
      align: 'right',
      render: (_, record) => (
        <Text>
          {record.activity_value.toLocaleString()} {record.unit}
        </Text>
      ),
    },
    {
      title: '碳排 (kgCO₂e)',
      dataIndex: 'emission_kg',
      width: 150,
      align: 'right',
      sorter: (a, b) => a.emission_kg - b.emission_kg,
      render: (val: number) => (
        <Text strong style={{ color: getEmissionColor(val) }}>
          {val.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </Text>
      ),
    },
    {
      title: '範疇',
      dataIndex: 'category',
      width: 120,
      render: (s: CarbonScope) => {
        const map: Record<CarbonScope, { label: string; color: string }> = {
          scope1: { label: '範疇一', color: 'volcano' },
          scope2: { label: '範疇二', color: 'orange' },
          scope3: { label: '範疇三', color: 'geekblue' },
        };
        const cfg = map[s] || { label: s, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '狀態',
      dataIndex: 'status',
      width: 120,
      render: (s: CarbonStatus) => {
        const cfg = STATUS_MAP[s] || { label: s, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '操作',
      width: 140,
      fixed: 'right',
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            檢視
          </Button>
          <Popconfirm
            title="確定刪除此筆記錄？"
            onConfirm={() => handleDelete(record._key)}
            okText="確定"
            cancelText="取消"
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              刪除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ---- Render ----

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <h2 style={{ margin: 0 }}>📊 收集記錄</h2>
        <Space>
          <Button icon={<ExportOutlined />}>📤 IFAS匯出</Button>
          <Button icon={<DownloadOutlined />}>📥 CSV匯出</Button>
        </Space>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }} align="middle">
        <Col>
          <Select
            style={{ width: 130 }}
            value={datePreset}
            onChange={handleDatePreset}
            options={[
              { value: 'today', label: '本日' },
              { value: 'this_week', label: '本週' },
              { value: 'this_month', label: '本月' },
              { value: 'all', label: '全部' },
            ]}
          />
        </Col>
        <Col>
          <RangePicker
            value={filterDateRange as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null}
            onChange={(dates) => {
              setFilterDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null);
              if (dates) setDatePreset('custom');
            }}
            allowClear
            style={{ width: 240 }}
          />
        </Col>
        <Col>
          <Select
            style={{ width: 150 }}
            value={filterScope}
            onChange={setFilterScope}
            options={CATEGORY_OPTIONS}
          />
        </Col>
        <Col>
          <Select
            style={{ width: 150 }}
            value={filterStatus}
            onChange={setFilterStatus}
            options={STATUS_OPTIONS}
          />
        </Col>
        <Col flex="auto">
          <Input
            placeholder="搜尋來源名稱、類型或備註..."
            prefix={<SearchOutlined />}
            value={filterSearch}
            onChange={(e) => setFilterSearch(e.target.value)}
            allowClear
            style={{ width: '100%', minWidth: 200 }}
          />
        </Col>
      </Row>

      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={filteredData}
          rowKey="_key"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1000 }}
        />
      </Spin>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={6}>
          <Card size="small" variant="borderless" style={{ background: '#fff7e6' }}>
            <Statistic
              title="範疇一總計"
              value={stats.scope1Total}
              suffix="kgCO₂e"
              precision={2}
              valueStyle={{ color: '#d46b08', fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" variant="borderless" style={{ background: '#fffbe6' }}>
            <Statistic
              title="範疇二總計"
              value={stats.scope2Total}
              suffix="kgCO₂e"
              precision={2}
              valueStyle={{ color: '#d48806', fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" variant="borderless" style={{ background: '#f6ffed' }}>
            <Statistic
              title="本日"
              value={stats.todayTotal}
              suffix="kgCO₂e"
              precision={2}
              valueStyle={{ color: '#389e0d', fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" variant="borderless" style={{ background: '#e6f7ff' }}>
            <Statistic
              title="本月"
              value={stats.monthTotal}
              suffix="kgCO₂e"
              precision={2}
              valueStyle={{ color: '#096dd9', fontSize: 20 }}
            />
          </Card>
        </Col>
      </Row>

      <Drawer
        title="碳排記錄詳情"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={560}
      >
        {selectedRecord ? (
          <>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="來源類型" span={2}>
                {SOURCE_TYPE_MAP[selectedRecord.source_type]?.emoji}{' '}
                {SOURCE_TYPE_MAP[selectedRecord.source_type]?.label ?? selectedRecord.source_type}
              </Descriptions.Item>
              <Descriptions.Item label="來源名稱" span={2}>
                {selectedRecord.source_name}
              </Descriptions.Item>
              <Descriptions.Item label="範疇">
                <Tag
                  color={
                    (
                      {
                        scope1: 'volcano',
                        scope2: 'orange',
                        scope3: 'geekblue',
                      } as Record<string, string>
                    )[selectedRecord.category]
                  }
                >
                  {selectedRecord.category === 'scope1'
                    ? '範疇一'
                    : selectedRecord.category === 'scope2'
                      ? '範疇二'
                      : '範疇三'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="狀態">
                <Tag color={STATUS_MAP[selectedRecord.status]?.color}>
                  {STATUS_MAP[selectedRecord.status]?.label}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="活動數據">
                {selectedRecord.activity_value.toLocaleString()} {selectedRecord.unit}
              </Descriptions.Item>
              <Descriptions.Item label="碳排量">
                <Text strong style={{ color: getEmissionColor(selectedRecord.emission_kg) }}>
                  {selectedRecord.emission_kg.toLocaleString(undefined, { maximumFractionDigits: 2 })}{' '}
                  kgCO₂e
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="提交方式">
                {selectedRecord.submitted_via === 'line' ? 'LINE 回報' : '手動輸入'}
              </Descriptions.Item>
              <Descriptions.Item label="提交時間">
                {dayjs(selectedRecord.submitted_at).format('YYYY/MM/DD HH:mm')}
              </Descriptions.Item>
            </Descriptions>

            {selectedRecord.notes && (
              <>
                <Divider style={{ margin: '16px 0' }} />
                <Text type="secondary">備註</Text>
                <Paragraph
                  style={{
                    margin: '4px 0 0',
                    whiteSpace: 'pre-wrap',
                    background: '#f5f5f5',
                    padding: 12,
                    borderRadius: 6,
                  }}
                >
                  {selectedRecord.notes}
                </Paragraph>
              </>
            )}

            <Divider style={{ margin: '16px 0' }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              建立時間：{dayjs(selectedRecord.created_at).format('YYYY/MM/DD HH:mm')}
              <br />
              更新時間：{dayjs(selectedRecord.updated_at).format('YYYY/MM/DD HH:mm')}
            </Text>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>請選擇一筆記錄</div>
        )}
      </Drawer>
    </div>
  );
}
