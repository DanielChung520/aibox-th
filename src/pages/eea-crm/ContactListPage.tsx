/**
 * @file        EEA-CRM 聯絡人管理頁面
 * @description 聯絡人資料表格，含 LINE 狀態標籤、主要聯絡人識別、Agent K 整合
 *              — 使用後端 API 資料，支援伺服器端搜尋 / 分頁 / LINE 狀態篩選
 * @lastUpdate  2026-06-22 12:00:00
 * @author      Daniel Chung
 * @version     1.1.0
 */

import { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Input,
  Select,
  Tag,
  App,
  Space,
  Typography,
  Card,
  Row,
  Col,
  Empty,
  Segmented,
  Pagination,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  StarFilled,
  MessageOutlined,
  AppstoreOutlined,
  UnorderedListOutlined,
  PhoneOutlined,
  MailOutlined,
  BuildOutlined,
} from '@ant-design/icons';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { useCrmStore } from '../../stores/crmStore';
import { crmApi, CRMContact, CRMContactListParams } from '../../services/api';

const { Text } = Typography;

/* ---------- LINE status map ---------- */

const LINE_STATUS_MAP: Record<string, { label: string; color: string }> = {
  connected: { label: '🟢 連線中', color: 'green' },
  disconnected: { label: '⚪ 未連結', color: 'default' },
  expired: { label: '🔴 已過期', color: 'red' },
};

/* ========== Main Component ========== */

export default function ContactListPage() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();
  const { openAgentDrawer } = useCrmStore();

  const [search, setSearch] = useState('');
  const [orgFilter, setOrgFilter] = useState<string>('');
  const [lineFilter, setLineFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [contacts, setContacts] = useState<CRMContact[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [institutions, setInstitutions] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<'list' | 'card'>('list');

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/contacts',
      pageName: 'EEA-CRM 聯絡人管理',
      entityType: 'contact',
      action: 'list',
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    const fetchContacts = async () => {
      setLoading(true);
      try {
        const params: CRMContactListParams = { page, page_size: pageSize };
        if (search.trim()) params.q = search.trim();
        if (lineFilter) params.line_status = lineFilter;

        const res = await crmApi.listContacts(params);

        if (cancelled) return;

        const { data, pagination } = res.data;
        setContacts(data);
        setTotal(pagination.total);

        const fetchedInstitutions: string[] = [];
        data.forEach((c) => {
          if (c.customer_name && !fetchedInstitutions.includes(c.customer_name)) {
            fetchedInstitutions.push(c.customer_name);
          }
        });
        setInstitutions((prev) => {
          const merged = new Set([...prev, ...fetchedInstitutions]);
          return Array.from(merged).sort();
        });
      } catch (err: unknown) {
        if (!cancelled) {
          const errResp = (err as { response?: { data?: { message?: string } } }).response?.data;
          message.error(errResp?.message || '載入聯絡人失敗');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchContacts();
    return () => {
      cancelled = true;
    };
  }, [search, lineFilter, page, pageSize, message]);

  const filtered = orgFilter
    ? contacts.filter((c) => c.customer_name === orgFilter)
    : contacts;

  const dataSource = filtered.map((c) => ({
    ...c,
    name: c.name_cn || c.name_en || '-',
    title: c.titles && c.titles.length > 0 ? c.titles[0].title : '-',
    phone: c.phones && c.phones.length > 0 ? c.phones[0].number : '-',
    email: c.emails && c.emails.length > 0 ? c.emails[0].address : '-',
    lineStatus: c.line_status || 'none',
    organization: c.customer_name || '-',
    isPrimary: !!c.is_primary,
  }));

  const columns = [
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      render: (v: string, record: (typeof dataSource)[number]) => (
        <span>
          {v}
          {record.isPrimary && (
            <StarFilled style={{ color: '#faad14', marginLeft: 4, fontSize: 12 }} />
          )}
        </span>
      ),
    },
    { title: '職稱', dataIndex: 'title', key: 'title', width: 110 },
    { title: '電話', dataIndex: 'phone', key: 'phone', width: 130 },
    { title: 'Email', dataIndex: 'email', key: 'email', width: 180, ellipsis: true },
    {
      title: 'LINE狀態',
      dataIndex: 'lineStatus',
      key: 'lineStatus',
      width: 110,
      render: (v: string) => {
        const info = LINE_STATUS_MAP[v] || { label: v, color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    { title: '所屬機構', dataIndex: 'organization', key: 'organization', width: 150 },
    {
      title: '主要聯絡人',
      dataIndex: 'isPrimary',
      key: 'isPrimary',
      width: 100,
      render: (v: boolean) =>
        v ? (
          <Tag icon={<StarFilled />} color="gold">
            主要
          </Tag>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: unknown, record: (typeof dataSource)[number]) => (
        <Space size={4}>
          <Button
            size="small"
            type="link"
            icon={<MessageOutlined />}
            onClick={() => {
              openAgentDrawer('contacts', record._key);
              message.info(`開啟 Agent K — LINE 智慧客情助手（${record.name}）`);
            }}
          >
            發送LINE訊息
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Input
            placeholder="搜尋姓名、電話或Email..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            style={{ width: 220 }}
            size="small"
          />
          <Select
            value={orgFilter}
            onChange={(v) => {
              setOrgFilter(v);
              setPage(1);
            }}
            placeholder="機構"
            style={{ width: 150 }}
            size="small"
            allowClear
            options={institutions.map((o) => ({ label: o, value: o }))}
          />
          <Select
            value={lineFilter}
            onChange={(v) => {
              setLineFilter(v);
              setPage(1);
            }}
            placeholder="LINE狀態"
            style={{ width: 110 }}
            size="small"
            allowClear
            options={[
              { label: '🟢 連線中', value: 'connected' },
              { label: '⚪ 未連結', value: 'disconnected' },
              { label: '🔴 已過期', value: 'expired' },
            ]}
          />
        </div>
        <Space size={8}>
          <Segmented
            size="small"
            value={viewMode}
            onChange={(v) => setViewMode(v as 'list' | 'card')}
            options={[
              { value: 'list', icon: <UnorderedListOutlined /> },
              { value: 'card', icon: <AppstoreOutlined /> },
            ]}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size="small"
            onClick={() => message.info('新增聯絡人表單（開發中）')}
          >
            新增聯絡人
          </Button>
        </Space>
      </div>

      <style>{`
        @keyframes cardFadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {viewMode === 'list' ? (
        <Table
          dataSource={dataSource}
          columns={columns}
          rowKey="_key"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showTotal: (t) => `共 ${t} 筆`,
            onChange: (p) => setPage(p),
          }}
          scroll={{ x: 1000 }}
          size="middle"
        />
      ) : (
        <div style={{ animation: 'cardFadeIn 0.3s ease' }}>
          {dataSource.length === 0 ? (
            <Empty description="暫無聯絡人" />
          ) : (
            <Row gutter={[16, 16]}>
              {dataSource.map((item) => (
                <Col xs={24} sm={12} md={8} lg={8} xl={6} key={item._key}>
                  <Card
                    hoverable
                    style={{
                      borderRadius: contentTokens.borderRadius ?? 10,
                      transition: 'all 0.3s ease',
                    }}
                    styles={{ body: { padding: 18 } }}
                  >
                    {/* Name row */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                      <Text strong style={{ fontSize: 15, lineHeight: 1.4 }} ellipsis={{ tooltip: item.name }}>
                        {item.name}
                      </Text>
                      {item.isPrimary && (
                        <StarFilled style={{ color: '#faad14', fontSize: 13, flexShrink: 0 }} />
                      )}
                      {item.isPrimary && (
                        <Tag
                          icon={<StarFilled />}
                          color="gold"
                          style={{ marginLeft: 'auto', flexShrink: 0, fontSize: 11, lineHeight: '18px', paddingInline: 6 }}
                        >
                          主要
                        </Tag>
                      )}
                    </div>

                    {/* Title */}
                    {item.title !== '-' && (
                      <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>
                        {item.title}
                      </Text>
                    )}

                    {/* Divider */}
                    <div style={{ height: 1, background: 'rgba(0,0,0,0.06)', marginBottom: 10 }} />

                    {/* Contact details */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                      <Space size={6} align="center">
                        <PhoneOutlined style={{ color: '#64748b', fontSize: 13, flexShrink: 0 }} />
                        <Text style={{ fontSize: 12 }}>{item.phone}</Text>
                      </Space>
                      <Space size={6} align="center" style={{ minWidth: 0 }}>
                        <MailOutlined style={{ color: '#64748b', fontSize: 13, flexShrink: 0 }} />
                        <Text style={{ fontSize: 12 }} ellipsis={{ tooltip: item.email }}>
                          {item.email}
                        </Text>
                      </Space>
                      <Space size={6} align="center">
                        <BuildOutlined style={{ color: '#64748b', fontSize: 13, flexShrink: 0 }} />
                        <Text style={{ fontSize: 12 }} ellipsis>
                          {item.organization}
                        </Text>
                      </Space>
                    </div>

                    {/* LINE Status */}
                    <div style={{ marginBottom: 10 }}>
                      {(() => {
                        const info = LINE_STATUS_MAP[item.lineStatus] || {
                          label: item.lineStatus,
                          color: 'default',
                        };
                        return <Tag color={info.color}>{info.label}</Tag>;
                      })()}
                    </div>

                    {/* Action button */}
                    <Button
                      size="small"
                      type="link"
                      icon={<MessageOutlined />}
                      block
                      style={{ padding: '4px 0', justifyContent: 'flex-start', fontSize: 12 }}
                      onClick={() => {
                        openAgentDrawer('contacts', item._key);
                        message.info(`開啟 Agent K — LINE 智慧客情助手（${item.name}）`);
                      }}
                    >
                      發送LINE訊息
                    </Button>
                  </Card>
                </Col>
              ))}
            </Row>
          )}

          {/* Pagination for card view */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              showTotal={(t) => `共 ${t} 筆`}
              onChange={(p) => setPage(p)}
              size="small"
            />
          </div>
        </div>
      )}
    </div>
  );
}
