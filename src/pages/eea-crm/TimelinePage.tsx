/**
 * @file        EEA-CRM 互動 Timeline 頁面
 * @description 統一互動時間軸，含客戶篩選、日期範圍、互動類型篩選、折疊展開詳情
 * @lastUpdate  2026-06-08 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import {
  Timeline,
  Card,
  Select,
  Tag,
  Typography,
  DatePicker,
  Space,
  Button,
} from 'antd';
import {
  ReloadOutlined,
} from '@ant-design/icons';
import { pageContextManager } from '../../services/PageContextManager';
import { useContentTokens } from '../../contexts/AppThemeProvider';

const { Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;

/* ---------- Mock data ---------- */

interface TimelineItem {
  key: string;
  time: string;
  timeLabel: string;
  type: 'call' | 'visit' | 'line' | 'memo';
  icon: string;
  title: string;
  customer: string;
  description: string;
  details: string[];
}

const MOCK_ITEMS: TimelineItem[] = [
  {
    key: '1', time: '2026-06-08T10:30:00', timeLabel: '2 小時前',
    type: 'call', icon: '📞', title: '電話通話 — 討論合約細節',
    customer: '陽光老人養護中心',
    description: '與張院長通話 23 分鐘，討論年度續約方案與新增服務項目。',
    details: ['通話長度：23 分鐘', '通話對象：張淑芬 院長', '重點摘要：客戶對 A 方案有興趣，希望下週安排簡報'],
  },
  {
    key: '2', time: '2026-06-07T14:00:00', timeLabel: '昨天',
    type: 'visit', icon: '🏢', title: '實體拜訪 — 陽光老人養護中心',
    customer: '陽光老人養護中心',
    description: '實地拜訪陽光老人養護中心，參訪其日照中心設施。',
    details: ['拜訪時間：14:00-16:00', '參與人員：王大明、陳小華', '成果：確認服務需求，預計下週報價'],
  },
  {
    key: '3', time: '2026-06-05T09:15:00', timeLabel: '3 天前',
    type: 'line', icon: '💬', title: 'LINE 對話 — 確認服務時程',
    customer: '仁愛居家長照機構',
    description: '透過 LINE 與王執行長確認導入服務的具體時程安排。',
    details: ['對話對象：王雅慧 執行長', '確認事項：導入日期調整為 7/1', '附加檔案：服務說明手冊 v3.pdf'],
  },
  {
    key: '4', time: '2026-06-01T11:00:00', timeLabel: '1 週前',
    type: 'memo', icon: '📝', title: '備忘錄 — 客戶提到預算問題',
    customer: '平安社區服務中心',
    description: '客戶在會議中表示目前預算受限，可能需要調整服務範圍。',
    details: ['記錄人員：林怡君', '客戶原話：「下半年預算縮減 20%」', '建議行動：準備精簡版方案 B 供參考'],
  },
  {
    key: '5', time: '2026-05-25T10:00:00', timeLabel: '2 週前',
    type: 'visit', icon: '🏢', title: '實體拜訪 — 仁愛居家長照機構',
    customer: '仁愛居家長照機構',
    description: '初次拜訪仁愛居家長照機構，了解其營運模式與需求痛點。',
    details: ['拜訪時間：10:00-12:00', '參與人員：陳小華', '成果：收集需求清單，後續安排第二次會議'],
  },
  {
    key: '6', time: '2026-05-20T15:30:00', timeLabel: '3 週前',
    type: 'call', icon: '📞', title: '電話通話 — 售後服務回訪',
    customer: '慈濟護理之家',
    description: '定期售後服務回訪，了解使用滿意度與改善建議。',
    details: ['通話長度：15 分鐘', '通話對象：林美玲 主任', '滿意度評分：4.5/5', '改善建議：希望增加報表自訂功能'],
  },
  {
    key: '7', time: '2026-05-15T08:00:00', timeLabel: '1 個月前',
    type: 'line', icon: '💬', title: 'LINE 對話 — 確認報價內容',
    customer: '榮總護理之家',
    description: '回覆客戶關於報價單中服務項目的疑問。',
    details: ['對話對象：陶喆 執行副院長', '回覆時間：8:05', '重點：確認年約方案折扣'],
  },
  {
    key: '8', time: '2026-05-10T16:00:00', timeLabel: '1 個月前',
    type: 'memo', icon: '📝', title: '備忘錄 — 客戶引薦新商機',
    customer: '希望居家服務',
    description: '黃淑芬回報希望居家服務的吳營運長引薦了 2 家潛在客戶。',
    details: ['引薦人：吳佩珊 營運長', '引薦機構：新北陽光長照中心、桃園仁愛護理之家', '後續行動：安排業務員聯繫'],
  },
];

const TYPE_OPTIONS = [
  { label: '全部', value: 'all', icon: '' },
  { label: '📞 通話', value: 'call' },
  { label: '🏢 拜訪', value: 'visit' },
  { label: '💬 LINE', value: 'line' },
  { label: '📝 備忘', value: 'memo' },
];

const CUSTOMER_OPTIONS = [...new Set(MOCK_ITEMS.map(i => i.customer))];

/* ---------- Color mapping per type ---------- */

const TYPE_COLORS: Record<string, string> = {
  call: '#1677ff',
  visit: '#52c41a',
  line: '#722ed1',
  memo: '#faad14',
};

/* ========== Main Component ========== */

export default function TimelinePage() {
  const contentTokens = useContentTokens();

  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [customerFilter, setCustomerFilter] = useState<string>('');
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    pageContextManager.report({
      page: 'eea-crm/timeline',
      pageName: 'EEA-CRM 互動 Timeline',
      entityType: 'timeline',
      action: 'view',
    });
  }, []);

  const filtered = MOCK_ITEMS.filter(item => {
    if (typeFilter !== 'all' && item.type !== typeFilter) return false;
    if (customerFilter && item.customer !== customerFilter) return false;
    return true;
  });

  const toggleExpand = (key: string) => {
    setExpandedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div style={{ padding: 20, background: contentTokens.contentBg, minHeight: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <Text strong style={{ fontSize: 16 }}>🗓️ 客戶互動 Timeline</Text>
        <Space size={8} wrap>
          {/* Type filter chips */}
          <div style={{ display: 'flex', gap: 4 }}>
            {TYPE_OPTIONS.map(opt => (
              <Tag
                key={opt.value}
                color={typeFilter === opt.value ? TYPE_COLORS[opt.value] || '#1677ff' : 'default'}
                style={{ cursor: 'pointer', padding: '2px 10px', borderRadius: 16 }}
                onClick={() => setTypeFilter(opt.value)}
              >
                {opt.label || opt.icon} {opt.label}
              </Tag>
            ))}
          </div>

          <Select
            value={customerFilter}
            onChange={setCustomerFilter}
            placeholder="選擇客戶"
            style={{ width: 160 }}
            size="small"
            allowClear
            options={CUSTOMER_OPTIONS.map(c => ({ label: c, value: c }))}
          />

          <RangePicker size="small" />

          <Button size="small" icon={<ReloadOutlined />} onClick={() => { setTypeFilter('all'); setCustomerFilter(''); }}>
            重置
          </Button>
        </Space>
      </div>

      {/* Timeline */}
      <Card style={{ borderRadius: 10 }}>
        <Timeline
          items={filtered.map(item => {
            const isExpanded = expandedKeys.has(item.key);
            return {
              key: item.key,
              color: TYPE_COLORS[item.type] || '#1677ff',
              children: (
                <div
                  onClick={() => toggleExpand(item.key)}
                  style={{ cursor: 'pointer', marginBottom: 8 }}
                >
                  {/* Header row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <Text strong style={{ fontSize: 14 }}>
                        {item.icon} {item.title}
                      </Text>
                    </div>
                    <Space size={8}>
                      <Tag color={TYPE_COLORS[item.type]} style={{ fontSize: 10 }}>
                        {item.icon} {item.type === 'call' ? '通話' : item.type === 'visit' ? '拜訪' : item.type === 'line' ? 'LINE' : '備忘'}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 11 }}>{item.timeLabel}</Text>
                    </Space>
                  </div>

                  {/* Customer & description */}
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>{item.customer}</Text>
                  </div>
                  <Paragraph
                    type="secondary"
                    style={{ fontSize: 12, margin: '4px 0 0', lineHeight: 1.5 }}
                    ellipsis={!isExpanded ? { rows: 2 } : false}
                  >
                    {item.description}
                  </Paragraph>

                  {/* Expandable details */}
                  {isExpanded && (
                    <div style={{
                      marginTop: 8,
                      padding: '8px 12px',
                      background: '#f8f9fa',
                      borderRadius: 8,
                      borderLeft: `3px solid ${TYPE_COLORS[item.type]}`,
                    }}>
                      {item.details.map((d, i) => (
                        <div key={i} style={{ fontSize: 12, lineHeight: 1.8, color: '#555' }}>
                          · {d}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ),
            };
          })}
        />
      </Card>
    </div>
  );
}
