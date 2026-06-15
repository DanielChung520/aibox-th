/**
 * @file        EEA-CRM 客戶列表頁面
 * @description 客戶資料表格，含搜尋篩選、潛在客戶爬取 Modal、ABC 分類標籤
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
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

const { Text } = Typography;

/* ---------- Mock data ---------- */

interface CustomerRecord {
  id: string;
  name: string;
  taxId: string;
  region: string;
  abc: string;
  salesRep: string;
  lastInteraction: string;
  status: string;
}

const MOCK_CUSTOMERS: CustomerRecord[] = [
  { id: 'C001', name: '陽光老人養護中心', taxId: '12345678', region: '北部', abc: 'A', salesRep: '王大明', lastInteraction: '2026-06-05', status: '活躍' },
  { id: 'C002', name: '仁愛居家長照機構', taxId: '23456789', region: '中部', abc: 'B', salesRep: '陳小華', lastInteraction: '2026-05-28', status: '活躍' },
  { id: 'C003', name: '慈濟護理之家', taxId: '34567890', region: '南部', abc: 'A', salesRep: '張偉強', lastInteraction: '2026-06-01', status: '活躍' },
  { id: 'C004', name: '平安社區服務中心', taxId: '45678901', region: '北部', abc: 'C', salesRep: '林怡君', lastInteraction: '2026-04-15', status: '沉睡' },
  { id: 'C005', name: '康復長照中心', taxId: '56789012', region: '中部', abc: 'B', salesRep: '王大明', lastInteraction: '2026-06-03', status: '活躍' },
  { id: 'C006', name: '恩典護理之家', taxId: '67890123', region: '南部', abc: 'C', salesRep: '李志明', lastInteraction: '2026-03-20', status: '流失' },
  { id: 'C007', name: '希望居家服務', taxId: '78901234', region: '北部', abc: 'A', salesRep: '黃淑芬', lastInteraction: '2026-06-07', status: '活躍' },
  { id: 'C008', name: '雙連安養中心', taxId: '89012345', region: '北部', abc: 'B', salesRep: '陳小華', lastInteraction: '2026-05-20', status: '活躍' },
  { id: 'C009', name: '喜樂居家長照', taxId: '90123456', region: '中部', abc: 'C', salesRep: '劉建宏', lastInteraction: '2026-02-10', status: '流失' },
  { id: 'C010', name: '榮總護理之家', taxId: '01234567', region: '南部', abc: 'A', salesRep: '王大明', lastInteraction: '2026-06-06', status: '活躍' },
];

const ABC_COLOR: Record<string, string> = { A: 'green', B: 'gold', C: 'red' };
const STATUS_COLOR: Record<string, string> = { 活躍: 'success', 沉睡: 'warning', 流失: 'error' };

const REGION_OPTIONS = ['北部', '中部', '南部'];
const ABC_OPTIONS = ['A', 'B', 'C'];
const SALES_REP_OPTIONS = [...new Set(MOCK_CUSTOMERS.map(c => c.salesRep))];

/* ---------- Scrape Modal mock ---------- */

const SCRAPE_SOURCES = [
  { label: '衛福部長照機構清單', value: 'mohw' },
  { label: '縣市立案機構', value: 'city' },
  { label: '政府公開資料', value: 'gov' },
];

const SCRAPE_RESULTS = [
  { name: '新北陽光長照中心', address: '新北市板橋區...', phone: '02-2956-7890', match: 92, exists: false },
  { name: '桃園仁愛護理之家', address: '桃園市桃園區...', phone: '03-335-6789', match: 88, exists: false },
  { name: '台中慈濟居家服務', address: '台中市北區...', phone: '04-2206-1234', match: 75, exists: false },
  { name: '高雄平安長照站', address: '高雄市苓雅區...', phone: '07-335-5678', match: 85, exists: true },
  { name: '台南恩典居家機構', address: '台南市東區...', phone: '06-275-4321', match: 90, exists: false },
];

/* ========== Main Component ========== */

export default function CustomerListPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();

  const [search, setSearch] = useState('');
  const [regionFilter, setRegionFilter] = useState<string>('');
  const [abcFilter, setAbcFilter] = useState<string>('');
  const [repFilter, setRepFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [scrapeVisible, setScrapeVisible] = useState(false);
  const [scrapeSource, setScrapeSource] = useState<string>('mohw');
  const [scraping, setScraping] = useState(false);
  const [scrapeDone, setScrapeDone] = useState(false);
  const [selectedScrape, setSelectedScrape] = useState<string[]>([]);

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/customers',
      pageName: 'EEA-CRM 客戶列表',
      entityType: 'customer',
      action: 'list',
    });
  }, []);

  /* Filtered data */
  const filtered = MOCK_CUSTOMERS.filter(c => {
    if (search && !c.name.includes(search) && !c.taxId.includes(search)) return false;
    if (regionFilter && c.region !== regionFilter) return false;
    if (abcFilter && c.abc !== abcFilter) return false;
    if (repFilter && c.salesRep !== repFilter) return false;
    return true;
  });

  const handleScrape = () => {
    setScraping(true);
    setScrapeDone(false);
    setTimeout(() => {
      setScraping(false);
      setScrapeDone(true);
      message.success('爬取完成，發現 12 筆新機構');
    }, 2000);
  };

  const columns = [
    { title: '機構名稱', dataIndex: 'name', key: 'name', width: 180, render: (v: string) => <Text strong>{v}</Text> },
    { title: '統一編號', dataIndex: 'taxId', key: 'taxId', width: 100 },
    { title: '區域', dataIndex: 'region', key: 'region', width: 80 },
    {
      title: 'ABC分類', dataIndex: 'abc', key: 'abc', width: 90,
      render: (v: string) => <Tag color={ABC_COLOR[v] || 'default'}>{v}類</Tag>,
    },
    { title: '業務負責人', dataIndex: 'salesRep', key: 'salesRep', width: 100 },
    { title: '最近互動', dataIndex: 'lastInteraction', key: 'lastInteraction', width: 110 },
    {
      title: '狀態', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{v}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 180,
      render: (_: unknown, record: CustomerRecord) => (
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

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Input
            placeholder="搜尋機構名稱或統編..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            style={{ width: 220 }}
            size="small"
          />
          <Select
            value={regionFilter}
            onChange={v => { setRegionFilter(v); setPage(1); }}
            placeholder="區域"
            style={{ width: 90 }}
            size="small"
            allowClear
            options={REGION_OPTIONS.map(r => ({ label: r, value: r }))}
          />
          <Select
            value={abcFilter}
            onChange={v => { setAbcFilter(v); setPage(1); }}
            placeholder="ABC分類"
            style={{ width: 100 }}
            size="small"
            allowClear
            options={ABC_OPTIONS.map(a => ({ label: `${a}類`, value: a }))}
          />
          <Select
            value={repFilter}
            onChange={v => { setRepFilter(v); setPage(1); }}
            placeholder="業務負責人"
            style={{ width: 110 }}
            size="small"
            allowClear
            options={SALES_REP_OPTIONS.map(r => ({ label: r, value: r }))}
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
      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="id"
        pagination={{
          current: page,
          pageSize: 10,
          total: filtered.length,
          showTotal: (t) => `共 ${t} 筆`,
          onChange: (p) => setPage(p),
        }}
        scroll={{ x: 900 }}
        size="middle"
      />

      {/* Scrape Modal */}
      <Modal
        title={<><RocketOutlined /> 潛在客戶爬取</>}
        open={scrapeVisible}
        onCancel={() => { setScrapeVisible(false); setScrapeDone(false); setSelectedScrape([]); }}
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
              <Text strong style={{ fontSize: 14 }}>發現 12 筆新機構（顯示前 5 筆）</Text>
              <Space>
                <Button size="small" onClick={() => message.success('已匯入選中機構')}>
                  匯入選中機構
                </Button>
                <Button size="small" icon={<ReloadOutlined />} onClick={() => setScrapeDone(false)}>
                  重新爬取
                </Button>
              </Space>
            </div>
            <Table
              dataSource={SCRAPE_RESULTS}
              rowKey="name"
              size="small"
              pagination={false}
              rowSelection={{
                selectedRowKeys: selectedScrape,
                onChange: (keys) => setSelectedScrape(keys as string[]),
              }}
              columns={[
                { title: '機構名稱', dataIndex: 'name', key: 'name' },
                { title: '地址', dataIndex: 'address', key: 'address', ellipsis: true },
                { title: '電話', dataIndex: 'phone', key: 'phone', width: 120 },
                {
                  title: '匹配度', dataIndex: 'match', key: 'match', width: 90,
                  render: (v: number) => (
                    <Tag color={v >= 90 ? 'green' : v >= 80 ? 'gold' : 'orange'}>{v}%</Tag>
                  ),
                },
                {
                  title: '已存在', dataIndex: 'exists', key: 'exists', width: 80,
                  render: (v: boolean) => v
                    ? <Tag color="red">已存在</Tag>
                    : <Tag color="green">新機構</Tag>,
                },
              ]}
            />
          </div>
        )}
      </Modal>
    </div>
  );
}
