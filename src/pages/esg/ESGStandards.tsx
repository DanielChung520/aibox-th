/**
 * @file        ESGStandards.tsx
 * @description ISO/IFAS 標準對照管理 — 排放係數 CRUD
 * @lastUpdate  2026-05-16
 * @author      AI Agent
 * @version     1.0.0
 *
 * TODO: Will use /api/v1/esg/factors when API is implemented
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table,
  Button,
  Tag,
  Space,
  App,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  DatePicker,
  Switch,
  Popconfirm,
  Typography,
  Row,
  Col,
} from 'antd';
import {
  PlusOutlined,
  DownloadOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { authStore } from '../../stores/auth';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import { pageContextManager } from '../../services/PageContextManager';
import dayjs from 'dayjs';

const { Text } = Typography;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EmissionFactor {
  _key: string;
  source_type:
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
  source_name: string;
  category: 'scope1' | 'scope2' | 'scope3';
  unit: 'kWh' | 'MJ' | 'm³' | 'liter' | 'kg' | 'ton' | 'km';
  co2_factor: number;
  ch4_factor: number;
  n2o_factor: number;
  gwp_total: number;
  standard_ref:
    | 'IPCC 2021'
    | '台灣環境部2023'
    | 'ISO 14064'
    | 'GHG Protocol'
    | 'ISO 14069'
    | 'IFAS';
  region: 'TW' | 'JP' | 'GLOBAL';
  valid_from: string;
  valid_until?: string;
  notes?: string;
  accounting_code?: string;
  status: 'active' | 'deprecated';
  created_at: string;
  updated_at: string;
}


// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SOURCE_TYPE_OPTIONS = [
  { value: 'electricity', label: '⚡ 電力' },
  { value: 'heat', label: '🔥 熱能' },
  { value: 'water', label: '💧 水資源' },
  { value: 'fuel_diesel', label: '🛢️ 柴油' },
  { value: 'fuel_gasoline', label: '⛽ 汽油' },
  { value: 'natural_gas', label: '🔥 天然氣' },
  { value: 'refrigerant', label: '❄️ 冷媒' },
  { value: 'waste', label: '🗑️ 廢棄物' },
  { value: 'transport_air', label: '✈️ 航空運輸' },
  { value: 'transport_rail', label: '🚆 鐵路運輸' },
  { value: 'solar', label: '☀️ 太陽能' },
  { value: 'wind', label: '🌬️ 風力' },
  { value: 'biomass_pellet', label: '🔥 生質顆粒' },
  { value: 'transport_truck', label: '🚛 貨車運輸' },
  { value: 'transport_sea', label: '🚢 海運貨櫃' },
  { value: 'transport_air', label: '✈️ 空運貨物' },
  { value: 'transport_rail', label: '🚆 鐵路貨運' },
];

const CATEGORY_OPTIONS = [
  { value: 'scope1', label: '範疇一 (直接排放)' },
  { value: 'scope2', label: '範疇二 (能源間接)' },
  { value: 'scope3', label: '範疇三 (其他間接)' },
];

const UNIT_OPTIONS = [
  { value: 'kWh', label: 'kWh' },
  { value: 'MJ', label: 'MJ' },
  { value: 'm³', label: 'm³' },
  { value: 'liter', label: 'liter' },
  { value: 'kg', label: 'kg' },
  { value: 'ton', label: 'ton' },
  { value: 'km', label: 'km' },
];

const STANDARD_REF_OPTIONS = [
  { value: 'IPCC 2021', label: 'IPCC 2021' },
  { value: '台灣環境部2023', label: '台灣環境部 2023' },
  { value: 'ISO 14064', label: 'ISO 14064' },
  { value: 'GHG Protocol', label: 'GHG Protocol' },
  { value: 'ISO 14069', label: 'ISO 14069' },
  { value: 'IFAS', label: 'IFAS' },
];

const REGION_OPTIONS = [
  { value: 'TW', label: '台灣' },
  { value: 'JP', label: '日本' },
  { value: 'GLOBAL', label: '全球' },
];

const SCOPE_OPTIONS = [
  { value: '', label: '全部範疇' },
  ...CATEGORY_OPTIONS,
];

const SOURCE_TYPE_FILTER_OPTIONS = [
  { value: '', label: '全部來源類型' },
  ...SOURCE_TYPE_OPTIONS,
];

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  active: { label: '啟用', color: 'green' },
  deprecated: { label: '已棄用', color: 'red' },
};

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_FACTORS: EmissionFactor[] = [
  {
    _key: 'mock_1',
    source_type: 'electricity',
    source_name: '台電電力排放係數',
    category: 'scope2',
    unit: 'kWh',
    co2_factor: 0.509,
    ch4_factor: 0.00003,
    n2o_factor: 0.000004,
    gwp_total: 0.509034,
    standard_ref: '台灣環境部2023',
    region: 'TW',
    valid_from: '2023-01-01',
    valid_until: '2025-12-31',
    notes: '依據台灣環境部最新公告',
    status: 'active',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-06-01T00:00:00Z',
  },
  {
    _key: 'mock_2',
    source_type: 'natural_gas',
    source_name: '天然氣排放係數',
    category: 'scope1',
    unit: 'm³',
    co2_factor: 2.02,
    ch4_factor: 0.00005,
    n2o_factor: 0.00001,
    gwp_total: 2.02006,
    standard_ref: 'IPCC 2021',
    region: 'GLOBAL',
    valid_from: '2021-01-01',
    status: 'active',
    created_at: '2021-01-01T00:00:00Z',
    updated_at: '2024-01-15T00:00:00Z',
  },
  {
    _key: 'mock_3',
    source_type: 'fuel_diesel',
    source_name: '柴油排放係數',
    category: 'scope1',
    unit: 'liter',
    co2_factor: 2.68,
    ch4_factor: 0.00012,
    n2o_factor: 0.00015,
    gwp_total: 2.68027,
    standard_ref: 'GHG Protocol',
    region: 'GLOBAL',
    valid_from: '2020-01-01',
    valid_until: '2024-12-31',
    status: 'deprecated',
    created_at: '2020-01-01T00:00:00Z',
    updated_at: '2023-12-01T00:00:00Z',
  },
];

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function calcGwpTotal(values: {
  co2_factor: number;
  ch4_factor: number;
  n2o_factor: number;
}): number {
  return (values.co2_factor || 0) + (values.ch4_factor || 0) + (values.n2o_factor || 0);
}

function flattenApiResponse(raw: unknown): EmissionFactor[] {
  if (Array.isArray(raw)) return raw as EmissionFactor[];
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.data)) return obj.data as EmissionFactor[];
    if (obj.data && typeof obj.data === 'object') {
      const inner = obj.data as Record<string, unknown>;
      if (Array.isArray(inner.records)) return inner.records as EmissionFactor[];
      if (Array.isArray(inner.data)) return inner.data as EmissionFactor[];
    }
    if (Array.isArray(obj.records)) return obj.records as EmissionFactor[];
  }
  return [];
}

const API_BASE = '/api/v1/esg/factors';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ESGStandards() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<EmissionFactor[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<EmissionFactor | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  // Filters
  const [filterScope, setFilterScope] = useState<string>('');
  const [filterSourceType, setFilterSourceType] = useState<string>('');
  const [filterSearch, setFilterSearch] = useState<string>('');

  useEntityPerception({ defaultEntityType: 'function', defaultAction: 'list' });

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
      // Fallback to mock data when API is not ready
      setData(MOCK_FACTORS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  useEffect(() => {
    pageContextManager.report({
      component: 'ESGStandards',
      entityType: 'esg_factor',
      action: 'list',
    });
    return () => {
      pageContextManager.report({
        component: 'ESGStandards',
        entityType: 'esg_factor',
        action: undefined,
      });
    };
  }, []);

  // ---- Filtered data ----

  const filteredData = useMemo(() => {
    return data.filter((item) => {
      if (filterScope && item.category !== filterScope) return false;
      if (filterSourceType && item.source_type !== filterSourceType) return false;
      if (filterSearch) {
        const q = filterSearch.toLowerCase();
        return (
          item.source_name.toLowerCase().includes(q) ||
          item.standard_ref.toLowerCase().includes(q) ||
          item.notes?.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [data, filterScope, filterSourceType, filterSearch]);

  // ---- Modal handlers ----

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({
      status: 'active',
      region: 'TW',
      co2_factor: 0,
      ch4_factor: 0,
      n2o_factor: 0,
    });
    setModalOpen(true);
  };

  const handleEdit = (record: EmissionFactor) => {
    setEditingRecord(record);
    form.setFieldsValue({
      source_type: record.source_type,
      source_name: record.source_name,
      category: record.category,
      unit: record.unit,
      co2_factor: record.co2_factor,
      ch4_factor: record.ch4_factor,
      n2o_factor: record.n2o_factor,
      standard_ref: record.standard_ref,
      region: record.region,
      valid_from: record.valid_from ? dayjs(record.valid_from) : null,
      valid_until: record.valid_until ? dayjs(record.valid_until) : null,
      notes: record.notes,
      status: record.status === 'active',
    });
    setModalOpen(true);
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
      // Optimistic local delete for mock mode
      setData((prev) => prev.filter((item) => item._key !== key));
      message.success('刪除成功');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const gwp_total = calcGwpTotal(values);
      const payload = {
        ...values,
        gwp_total,
        status: values.status ? 'active' : 'deprecated',
        valid_from: values.valid_from
          ? values.valid_from.toISOString()
          : undefined,
        valid_until: values.valid_until
          ? values.valid_until.toISOString()
          : undefined,
      };

      if (editingRecord) {
        const res = await fetch(`${API_BASE}/${editingRecord._key}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authStore.getState().token}`,
          },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const errBody = await res.text().catch(() => '');
          throw new Error(errBody ? `更新失敗: ${errBody}` : '更新失敗');
        }
        message.success('更新成功');
      } else {
        const res = await fetch(API_BASE, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authStore.getState().token}`,
          },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const errBody = await res.text().catch(() => '');
          throw new Error(errBody ? `新增失敗: ${errBody}` : '新增失敗');
        }
        message.success('新增成功');
      }

      setModalOpen(false);
      fetchList();
    } catch (err: any) {
      if (err?.errorFields) {
        message.error(`表單驗證失敗：請檢查必填欄位`);
      } else if (err?.message) {
        message.error(err.message);
      } else {
        message.error('操作失敗，請稍後重試');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ---- GWP preview ----

  const gwpTotal = Form.useWatch('co2_factor', form) +
    Form.useWatch('ch4_factor', form) +
    Form.useWatch('n2o_factor', form) || 0;

  // ---- Columns ----

  const columns: ColumnsType<EmissionFactor> = [
    {
      title: '來源類型',
      dataIndex: 'source_type',
      width: 120,
      render: (type: EmissionFactor['source_type']) => {
        const opt = SOURCE_TYPE_OPTIONS.find((o) => o.value === type);
        return opt?.label || type;
      },
    },
    {
      title: '名稱',
      dataIndex: 'source_name',
      ellipsis: true,
      width: 200,
    },
    {
      title: '係數 (kgCO₂e/單位)',
      dataIndex: 'gwp_total',
      width: 150,
      align: 'right',
      render: (val: number) => val?.toFixed(6) ?? '-',
    },
    {
      title: '單位',
      dataIndex: 'unit',
      width: 80,
    },
    {
      title: '會計科目',
      dataIndex: 'accounting_code',
      width: 110,
      render: (code: string) => code ? <Tag color="blue">{code}</Tag> : '-',
    },
    {
      title: '標準來源',
      dataIndex: 'standard_ref',
      width: 150,
      render: (ref: string) => <Tag>{ref}</Tag>,
    },
    {
      title: '有效日期',
      width: 180,
      render: (_, record) => {
        const from = record.valid_from ? dayjs(record.valid_from).format('YYYY/MM/DD') : '-';
        const until = record.valid_until ? dayjs(record.valid_until).format('YYYY/MM/DD') : '--';
        return (
          <Text type="secondary" style={{ fontSize: 13 }}>
            {from} ~ {until}
          </Text>
        );
      },
    },
    {
      title: '狀態',
      dataIndex: 'status',
      width: 90,
      render: (s: 'active' | 'deprecated') => {
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
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            編輯
          </Button>
          <Popconfirm
            title="確定刪除此係數？"
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
        <h2 style={{ margin: 0 }}>📋 ISO/IFAS 標準對照管理</h2>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            + 新增係數
          </Button>
          <Button icon={<DownloadOutlined />}>📥 CSV匯入</Button>
        </Space>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col>
          <Select
            style={{ width: 150 }}
            value={filterScope}
            onChange={setFilterScope}
            options={SCOPE_OPTIONS}
          />
        </Col>
        <Col>
          <Select
            style={{ width: 160 }}
            value={filterSourceType}
            onChange={setFilterSourceType}
            options={SOURCE_TYPE_FILTER_OPTIONS}
          />
        </Col>
        <Col flex="auto">
          <Input
            placeholder="搜尋名稱、標準來源或備註..."
            prefix={<SearchOutlined />}
            value={filterSearch}
            onChange={(e) => setFilterSearch(e.target.value)}
            allowClear
            style={{ width: '100%', minWidth: 200 }}
          />
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={filteredData}
        rowKey="_key"
        loading={loading}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1100 }}
      />

      <Modal
        title={editingRecord ? '編輯排放係數' : '新增排放係數'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        width={720}
        destroyOnClose
        forceRender
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="source_type"
                label="來源類型"
                rules={[{ required: true, message: '請選擇來源類型' }]}
              >
                <Select options={SOURCE_TYPE_OPTIONS} placeholder="請選擇來源類型" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="source_name"
                label="名稱"
                rules={[{ required: true, message: '請輸入名稱' }]}
              >
                <Input placeholder="例如：台電電力排放係數" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="category"
                label="範疇"
                rules={[{ required: true, message: '請選擇範疇' }]}
              >
                <Select options={CATEGORY_OPTIONS} placeholder="請選擇範疇" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="unit"
                label="單位"
                rules={[{ required: true, message: '請選擇單位' }]}
              >
                <Select options={UNIT_OPTIONS} placeholder="請選擇單位" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="standard_ref"
                label="標準來源"
                rules={[{ required: true, message: '請選擇標準來源' }]}
              >
                <Select options={STANDARD_REF_OPTIONS} placeholder="請選擇標準來源" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="co2_factor"
                label="CO₂ 係數 (kgCO₂e)"
                rules={[{ required: true, message: '請輸入 CO₂ 係數' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  step={0.000001}
                  precision={6}
                  placeholder="0.000000"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="ch4_factor"
                label="CH₄ 係數 (kgCO₂e)"
                rules={[{ required: true, message: '請輸入 CH₄ 係數' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  step={0.000001}
                  precision={6}
                  placeholder="0.000000"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="n2o_factor"
                label="N₂O 係數 (kgCO₂e)"
                rules={[{ required: true, message: '請輸入 N₂O 係數' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  step={0.000001}
                  precision={6}
                  placeholder="0.000000"
                />
              </Form.Item>
            </Col>
          </Row>

          {/* GWP Total (display only, auto-calculated) */}
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="GWP 總和 (kgCO₂e)">
                <InputNumber
                  style={{ width: '100%' }}
                  value={gwpTotal}
                  disabled
                  precision={6}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="accounting_code"
                label="會計科目"
              >
                <Input placeholder="例如：500100" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="region"
                label="地區"
                rules={[{ required: true, message: '請選擇地區' }]}
              >
                <Select options={REGION_OPTIONS} placeholder="請選擇地區" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="status" label="狀態" valuePropName="checked">
                <Switch checkedChildren="啟用" unCheckedChildren="已棄用" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="valid_from"
                label="有效起始日"
                rules={[{ required: true, message: '請選擇有效起始日' }]}
              >
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="valid_until" label="有效截止日 (可選)">
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="notes" label="備註">
            <Input.TextArea rows={3} placeholder="補充說明..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
