/**
 * @file        EEA-CRM 客戶列表頁面
 * @description 客戶資料表格，含搜尋篩選、衛服部資料更新、ABC 分類色塊、響應式行數、客戶詳情/編輯 Modal
 * @lastUpdate  2026-06-22 23:42:00
 * @author      Daniel Chung
 * @version     2.0.0
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Table,
  Button,
  Input,
  Select,
  Tag,
  App,
  Space,
  Typography,
  Spin,
  Drawer,
  Descriptions,
  Form,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  CloseOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { crmApi, CRMCustomer, CRMListResponse } from '../../services/api';

const { Text } = Typography;

/* ---------- Constants ---------- */

const ABC_BG: Record<string, string> = { A: '#52c41a', B: '#fa8c16', C: '#ff4d4f', E: '#b37feb' };
const STATUS_COLOR: Record<string, string> = { 活躍: 'success', 沉睡: 'warning', 流失: 'error' };

const REGION_OPTIONS = ['北部', '中部', '南部'];
const ABC_OPTIONS = ['A', 'B', 'C', 'E'];

/* ========== Main Component ========== */

export default function CustomerListPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();

  /* ---------- Container ref & responsive page size ---------- */

  const containerRef = useRef<HTMLDivElement>(null);
  const [pageSize, setPageSize] = useState(15);

  useEffect(() => {
    const calcPageSize = () => {
      const el = containerRef.current;
      if (!el) return;
      const vpH = window.innerHeight;
      const offsetTop = el.getBoundingClientRect().top;
      // Measured from rendered layout (Ant Design middle size):
      //   toolbar + margin-bottom = 24 + 16 = 40
      //   table header row       = 47
      //   pagination + gap       = 24 + 16 = 40
      //   container padding      = 20 + 20 = 40
      //   data row               = 51
      const nonRows = 40 + 47 + 40 + 40;
      const rowH = 51;
      const avail = vpH - offsetTop - nonRows;
      const n = Math.max(6, Math.min(100, Math.floor(avail / rowH)));
      setPageSize(n);
    };

    calcPageSize();
    window.addEventListener('resize', calcPageSize);
    return () => window.removeEventListener('resize', calcPageSize);
  }, []);

  /* ---------- Filter state ---------- */

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [regionFilter, setRegionFilter] = useState<string>('');
  const [abcFilter, setAbcFilter] = useState<string>('');
  const [repFilter, setRepFilter] = useState<string>('');
  const [page, setPage] = useState(1);

  /* ---------- Data state ---------- */

  const [loading, setLoading] = useState(false);
  const [customers, setCustomers] = useState<CRMCustomer[]>([]);
  const [total, setTotal] = useState(0);
  const [, setSummary] = useState<CRMListResponse['summary'] | null>(null);

  /* ---------- MOHW import state ---------- */

  const [mohwImporting, setMohwImporting] = useState(false);

  /* ---------- Page context ---------- */

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/customers',
      pageName: 'EEA-CRM 客戶列表',
      entityType: 'customer',
      action: 'list',
    });
  }, []);

  /* ---------- Search debounce ---------- */

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  /* ---------- Data fetching ---------- */

  useEffect(() => {
    const params: Parameters<typeof crmApi.list>[0] = {};
    if (debouncedSearch) params.q = debouncedSearch;
    if (regionFilter) params.city = regionFilter;
    if (abcFilter) params.abc_grade = abcFilter;
    params.page = page;
    params.page_size = pageSize;

    setLoading(true);
    crmApi.list(params)
      .then((res) => {
        const { data, pagination, summary: s } = res.data;
        setCustomers(data);
        setTotal(pagination.total);
        setSummary(s);
      })
      .catch(() => {
        message.error('載入客戶列表失敗');
        setCustomers([]);
        setTotal(0);
        setSummary(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [debouncedSearch, regionFilter, abcFilter, page, pageSize, message]);

  /* ---------- Client-side sales rep filter ---------- */

  const filteredCustomers = useMemo(() => {
    if (!repFilter) return customers;
    return customers.filter((c) => c.sales_rep === repFilter);
  }, [customers, repFilter]);

  /* ---------- Derive sales rep options from loaded data ---------- */

  const salesRepOptions = useMemo(() => {
    const reps = new Set<string>();
    customers.forEach((c) => {
      if (c.sales_rep) reps.add(c.sales_rep);
    });
    return Array.from(reps).sort();
  }, [customers]);

  /* ---------- MOHW import handler ---------- */

  const handleMohwImport = useCallback(async () => {
    setMohwImporting(true);
    try {
      const res = await crmApi.importMohw();
      const result = res.data;
      const parts: string[] = [];
      if (result.imported > 0) parts.push(`匯入 ${result.imported} 筆`);
      if (result.updated > 0) parts.push(`更新 ${result.updated} 筆`);
      if (result.skipped > 0) parts.push(`跳過 ${result.skipped} 筆`);
      message.success(`衛服部資料更新完成：${parts.join('、')}`);
      if (result.errors.length > 0) {
        message.warning(`部分處理異常：${result.errors.slice(0, 3).join('；')}`);
      }
    } catch {
      message.error('衛服部資料更新失敗，請稍後再試');
    } finally {
      setMohwImporting(false);
    }
  }, [message]);

  /* ---------- Customer detail/edit modal ---------- */

  const [customerModal, setCustomerModal] = useState<{
    visible: boolean;
    mode: 'view' | 'edit';
    customer: CRMCustomer | null;
  }>({ visible: false, mode: 'view', customer: null });
  const [saving, setSaving] = useState(false);
  const [editForm] = Form.useForm();

  const openCustomerModal = useCallback((mode: 'view' | 'edit', customer: CRMCustomer) => {
    setCustomerModal({ visible: true, mode, customer });
    if (mode === 'edit') {
      editForm.setFieldsValue({
        name: customer.name,
        phone: customer.phone || '',
        email: customer.email || '',
        address: customer.address || '',
        city: customer.city || '',
        district: customer.district || '',
        sales_rep: customer.sales_rep || '',
        abc_grade: customer.abc_grade || '',
        status: customer.status || '',
        contact_person: customer.contact_person || '',
      });
    }
  }, [editForm]);

  const closeCustomerModal = useCallback(() => {
    setCustomerModal({ visible: false, mode: 'view', customer: null });
    editForm.resetFields();
  }, [editForm]);

  const handleSaveCustomer = useCallback(async () => {
    const { customer } = customerModal;
    if (!customer) return;
    try {
      const values = await editForm.validateFields();
      setSaving(true);
      await crmApi.update(customer._key, values);
      message.success(`客戶「${values.name}」已更新`);
      closeCustomerModal();
      setPage(1); // trigger list refresh
    } catch (err: unknown) {
      // Form validation errors have errorFields — skip those, only show for API errors
      if (!err || typeof err !== 'object' || !('errorFields' in (err as Record<string, unknown>))) {
        message.error('儲存失敗，請稍後再試');
      }
    } finally {
      setSaving(false);
    }
  }, [customerModal, editForm, message, closeCustomerModal]);

  /* ---------- Table columns ---------- */

  const columns = [
    {
      title: '機構名稱',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '統一編號',
      key: 'taxId',
      width: 100,
      render: (_: unknown, record: CRMCustomer) => record.business_kindom_id || record.mohw_id || '-',
    },
    {
      title: '區域',
      key: 'region',
      width: 80,
      render: (_: unknown, record: CRMCustomer) => record.city || record.district || '-',
    },
    {
      title: 'ABC分類',
      key: 'abc',
      width: 90,
      render: (_: unknown, record: CRMCustomer) => {
        const grade = record.abc_grade || '';
        if (!grade) return <Text type="secondary">-</Text>;
        return (
          <div
            style={{
              background: ABC_BG[grade] || '#8c8c8c',
              color: '#fff',
              borderRadius: 4,
              padding: '0 10px',
              fontWeight: 700,
              fontSize: 13,
              lineHeight: '26px',
              textAlign: 'center',
              display: 'inline-block',
              minWidth: 32,
              letterSpacing: 1,
            }}
          >
            {grade}
          </div>
        );
      },
    },
    {
      title: '業務負責人',
      key: 'salesRep',
      width: 100,
      render: (_: unknown, record: CRMCustomer) => record.sales_rep || '-',
    },
    {
      title: '最近互動',
      key: 'lastInteraction',
      width: 110,
      render: (_: unknown, record: CRMCustomer) => record.last_contact_at || '-',
    },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => {
        const color = STATUS_COLOR[v] || 'default';
        return <Tag color={color}>{v}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: CRMCustomer) => (
        <Space size={4}>
          <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => openCustomerModal('view', record)}>
            詳情
          </Button>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openCustomerModal('edit', record)}>
            編輯
          </Button>
          <Button size="small" type="link" danger icon={<DeleteOutlined />} onClick={() => message.warning(`刪除 ${record.name}`)}>
            刪除
          </Button>
        </Space>
      ),
    },
  ];

  /* ========== Render ========== */

  return (
    <div ref={containerRef} style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Input
            placeholder="搜尋機構名稱或統編..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => { setSearch(e.target.value); }}
            style={{ width: 220 }}
            size="small"
          />
          <Select
            value={regionFilter}
            onChange={(v) => { setRegionFilter(v); setPage(1); }}
            placeholder="區域"
            style={{ width: 90 }}
            size="small"
            allowClear
            options={REGION_OPTIONS.map((r) => ({ label: r, value: r }))}
          />
          <Select
            value={abcFilter}
            onChange={(v) => { setAbcFilter(v); setPage(1); }}
            placeholder="ABC分類"
            style={{ width: 100 }}
            size="small"
            allowClear
            options={ABC_OPTIONS.map((a) => ({ label: `${a}類`, value: a }))}
          />
          <Select
            value={repFilter}
            onChange={(v) => { setRepFilter(v); setPage(1); }}
            placeholder="業務負責人"
            style={{ width: 110 }}
            size="small"
            allowClear
            options={salesRepOptions.map((r) => ({ label: r, value: r }))}
          />
        </div>
        <Space size={8}>
          <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => message.info('新增客戶表單（開發中）')}>
            新增客戶
          </Button>
          <Button icon={<ReloadOutlined />} size="small" onClick={handleMohwImport} loading={mohwImporting}>
            {mohwImporting ? '更新中...' : '從衛服部更新'}
          </Button>
        </Space>
      </div>

      {/* Table */}
      <Spin spinning={loading}>
        <Table
          dataSource={filteredCustomers}
          columns={columns}
          rowKey="_key"
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showTotal: (t) => `共 ${t} 筆 (每頁 ${pageSize} 行)`,
            onChange: (p) => setPage(p),
          }}
          scroll={{ x: 900 }}
          size="middle"
        />
      </Spin>

      {/* Customer Detail / Edit Drawer */}
      <Drawer
        title={
          <Space>
            {customerModal.mode === 'view' ? <EyeOutlined /> : <EditOutlined />}
            {customerModal.mode === 'view' ? '客戶詳情' : '編輯客戶'}
            {customerModal.customer && (
              <Text type="secondary" style={{ fontSize: 13, fontWeight: 400 }}>
                — {customerModal.customer.name}
              </Text>
            )}
          </Space>
        }
        open={customerModal.visible}
        onClose={closeCustomerModal}
        styles={{ wrapper: { width: '50%' } }}
        footer={
          customerModal.mode === 'view'
            ? [
                <Button key="close" icon={<CloseOutlined />} onClick={closeCustomerModal}>
                  關閉
                </Button>,
                <Button
                  key="edit"
                  type="primary"
                  icon={<EditOutlined />}
                  onClick={() => {
                    if (customerModal.customer) {
                      openCustomerModal('edit', customerModal.customer);
                    }
                  }}
                >
                  編輯
                </Button>,
              ]
            : [
                <Button key="cancel" onClick={closeCustomerModal}>
                  取消
                </Button>,
                <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSaveCustomer}>
                  儲存
                </Button>,
              ]
        }
      >
        {customerModal.customer && customerModal.mode === 'view' && (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="機構名稱" span={2}>{customerModal.customer.name}</Descriptions.Item>
            <Descriptions.Item label="統一編號">{customerModal.customer.business_kindom_id || customerModal.customer.mohw_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="ABC 分類">
              {customerModal.customer.abc_grade ? (
                <div style={{
                  background: ABC_BG[customerModal.customer.abc_grade] || '#8c8c8c',
                  color: '#fff', borderRadius: 4, padding: '0 8px',
                  fontWeight: 700, fontSize: 12, lineHeight: '22px',
                  display: 'inline-block', minWidth: 28, textAlign: 'center',
                }}>
                  {customerModal.customer.abc_grade}
                </div>
              ) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="狀態">
              <Tag color={STATUS_COLOR[customerModal.customer.status] || 'default'}>{customerModal.customer.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="縣市">{customerModal.customer.city || '-'}</Descriptions.Item>
            <Descriptions.Item label="區域">{customerModal.customer.district || '-'}</Descriptions.Item>
            <Descriptions.Item label="地址" span={2}>{customerModal.customer.address || '-'}</Descriptions.Item>
            <Descriptions.Item label="電話">{customerModal.customer.phone || '-'}</Descriptions.Item>
            <Descriptions.Item label="Email">{customerModal.customer.email || '-'}</Descriptions.Item>
            <Descriptions.Item label="聯絡人">{customerModal.customer.contact_person || '-'}</Descriptions.Item>
            <Descriptions.Item label="業務負責人">{customerModal.customer.sales_rep || '-'}</Descriptions.Item>
            <Descriptions.Item label="來源">{customerModal.customer.source || '-'}</Descriptions.Item>
            <Descriptions.Item label="最近互動">{customerModal.customer.last_contact_at || '-'}</Descriptions.Item>
            <Descriptions.Item label="建立時間" span={2}>{customerModal.customer.created_at}</Descriptions.Item>
            <Descriptions.Item label="更新時間" span={2}>{customerModal.customer.updated_at}</Descriptions.Item>
          </Descriptions>
        )}

        {customerModal.customer && customerModal.mode === 'edit' && (
          <Form
            form={editForm}
            layout="vertical"
            size="small"
            initialValues={{
              name: customerModal.customer.name,
              phone: customerModal.customer.phone || '',
              email: customerModal.customer.email || '',
              address: customerModal.customer.address || '',
              city: customerModal.customer.city || '',
              district: customerModal.customer.district || '',
              sales_rep: customerModal.customer.sales_rep || '',
              abc_grade: customerModal.customer.abc_grade || '',
              status: customerModal.customer.status || '',
              contact_person: customerModal.customer.contact_person || '',
            }}
          >
            <Form.Item label="機構名稱" name="name" rules={[{ required: true, message: '請輸入機構名稱' }]}>
              <Input />
            </Form.Item>
            <Space style={{ width: '100%' }} size={12}>
              <Form.Item label="縣市" name="city" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
              <Form.Item label="區域" name="district" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
            </Space>
            <Form.Item label="地址" name="address">
              <Input />
            </Form.Item>
            <Space style={{ width: '100%' }} size={12}>
              <Form.Item label="電話" name="phone" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
              <Form.Item label="Email" name="email" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
            </Space>
            <Space style={{ width: '100%' }} size={12}>
              <Form.Item label="聯絡人" name="contact_person" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
              <Form.Item label="業務負責人" name="sales_rep" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
            </Space>
            <Space style={{ width: '100%' }} size={12}>
              <Form.Item label="ABC 分類" name="abc_grade" style={{ width: '50%' }}>
                <Select allowClear options={ABC_OPTIONS.map((g) => ({ label: `${g}類`, value: g }))} />
              </Form.Item>
              <Form.Item label="狀態" name="status" style={{ width: '50%' }}>
                <Select allowClear options={[
                  { label: '潛在', value: 'potential' },
                  { label: 'Lead', value: 'lead' },
                  { label: '客戶', value: 'customer' },
                  { label: '已合併', value: 'merged' },
                ]} />
              </Form.Item>
            </Space>
          </Form>
        )}
      </Drawer>
    </div>
  );
}
