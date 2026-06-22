/**
 * @file        EEA-CRM 客戶列表頁面
 * @description 客戶資料表格，含搜尋篩選、潛在客戶爬取 Modal、ABC 分類標籤
 * @lastUpdate  2026-06-22 12:00:00
 * @author      Daniel Chung
 * @version     2.0.0
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table,
  Button,
  Input,
  Select,
  Tag,
  Modal,
  App,
  Space,
  Typography,
  Spin,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  UploadOutlined,
  RocketOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { crmApi, CRMCustomer, CRMListResponse } from '../../services/api';

const { Text } = Typography;

/* ---------- Constants ---------- */

const ABC_COLOR: Record<string, string> = { A: 'green', B: 'gold', C: 'red' };
const STATUS_COLOR: Record<string, string> = { 活躍: 'success', 沉睡: 'warning', 流失: 'error' };

const REGION_OPTIONS = ['北部', '中部', '南部'];
const ABC_OPTIONS = ['A', 'B', 'C'];

const SCRAPE_SOURCES = [
  { label: '衛福部長照機構清單', value: 'mohw' },
  { label: '縣市立案機構', value: 'city' },
  { label: '政府公開資料', value: 'gov' },
];

/* ========== Main Component ========== */

export default function CustomerListPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();

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

  /* ---------- Scrape modal state ---------- */

  const [scrapeVisible, setScrapeVisible] = useState(false);
  const [scrapeSource, setScrapeSource] = useState<string>('mohw');
  const [scraping, setScraping] = useState(false);
  const [scrapeDone, setScrapeDone] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<{ imported: number; updated: number; skipped: number } | null>(null);

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
    params.page_size = 10;

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
  }, [debouncedSearch, regionFilter, abcFilter, page, message]);

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

  /* ---------- Scrape handler ---------- */

  const handleScrape = useCallback(async () => {
    setScraping(true);
    setScrapeDone(false);
    setScrapeResult(null);
    try {
      let result: { imported: number; updated: number; skipped: number };
      if (scrapeSource === 'mohw') {
        const res = await crmApi.importMohw();
        result = (res as { data: { imported: number; updated: number; skipped: number } }).data;
      } else {
        const res = await crmApi.importBusinessKindom([]);
        result = res.data;
      }
      setScrapeResult(result);
      setScrapeDone(true);
      message.success(`爬取完成，匯入 ${result.imported} 筆新機構`);
    } catch {
      message.error('爬取失敗，請稍後再試');
    } finally {
      setScraping(false);
    }
  }, [scrapeSource, message]);

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
        const grade = record.abc_grade || '-';
        return <Tag color={ABC_COLOR[grade] || 'default'}>{grade}類</Tag>;
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
          <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => message.info(`查看 ${record.name}`)}>
            詳情
          </Button>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => message.info(`編輯 ${record.name}`)}>
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
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
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
          <Button icon={<UploadOutlined />} size="small" onClick={() => message.info('匯入 CSV（開發中）')}>
            匯入CSV
          </Button>
          <Button icon={<RocketOutlined />} size="small" onClick={() => setScrapeVisible(true)}>
            潛在客戶爬取
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
            pageSize: 10,
            total: total,
            showTotal: (t) => `共 ${t} 筆`,
            onChange: (p) => setPage(p),
          }}
          scroll={{ x: 900 }}
          size="middle"
        />
      </Spin>

      {/* Scrape Modal */}
      <Modal
        title={<><RocketOutlined /> 潛在客戶爬取</>}
        open={scrapeVisible}
        onCancel={() => { setScrapeVisible(false); setScrapeDone(false); setScrapeResult(null); }}
        footer={null}
        width={600}
      >
        {!scrapeDone ? (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Text strong>選擇資料來源：</Text>
              <Select
                value={scrapeSource}
                onChange={setScrapeSource}
                style={{ width: '100%', marginTop: 8 }}
                options={SCRAPE_SOURCES}
              />
            </div>
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={handleScrape}
              loading={scraping}
            >
              {scraping ? '爬取中...' : '開始爬取'}
            </Button>
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text strong style={{ fontSize: 14 }}>
                爬取完成，匯入 {scrapeResult?.imported ?? 0} 筆新機構
                {scrapeResult && scrapeResult.updated > 0 && `，更新 ${scrapeResult.updated} 筆`}
              </Text>
              <Space>
                <Button size="small" icon={<ReloadOutlined />} onClick={() => { setScrapeDone(false); setScrapeResult(null); }}>
                  重新爬取
                </Button>
              </Space>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
