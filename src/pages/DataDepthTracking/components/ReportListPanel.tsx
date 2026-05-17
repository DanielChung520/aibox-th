/**
 * @file        報表列表面板
 * @description 顯示已儲存的資料深度追蹤報表清單，支援場景篩選、名稱搜尋、載入與刪除
 * @lastUpdate  2026-05-17
 * @author      Daniel Chung
 * @version     1.0.0
 */
import { useMemo, useState } from 'react';
import {
  List,
  Card,
  Tag,
  Empty,
  Button,
  Select,
  Input,
  Typography,
  Space,
  Popconfirm,
  Tooltip,
} from 'antd';
import {
  DeleteOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useContentTokens } from '../../../contexts/AppThemeProvider';
import { SCENARIO_DEFINITIONS } from '../scenarioConfig';

/* =================== 型別定義 =================== */

export interface ReportItem {
  id: string;
  name: string;
  scenario: string;
  created_at: string;
  tags: string[];
}

export interface ReportListPanelProps {
  /** 報表資料陣列 */
  reports: ReportItem[];
  /** 點擊載入報表 */
  onLoadReport: (reportId: string) => void;
  /** 刪除報表 */
  onDeleteReport: (reportId: string) => void;
  /** 載入中狀態 */
  loading?: boolean;
}

const { Text } = Typography;

/* =================== 工具函式 =================== */

/** 從 scenarioConfig 查詢場景顯示名稱 */
function getScenarioDisplayName(scenarioId: string): string {
  const def = SCENARIO_DEFINITIONS.find(s => s.id === scenarioId);
  return def?.name ?? scenarioId;
}

/** 格式化 ISO 日期字串 */
function formatDateTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

/** Select 場景篩選選項 */
const SCENARIO_FILTER_OPTIONS = SCENARIO_DEFINITIONS.map(s => ({
  value: s.id,
  label: s.name,
}));

/* =================== 主元件 =================== */

export default function ReportListPanel({
  reports,
  onLoadReport,
  onDeleteReport,
  loading,
}: ReportListPanelProps) {
  const tokens = useContentTokens();
  const [searchText, setSearchText] = useState('');
  const [scenarioFilter, setScenarioFilter] = useState<string | undefined>(undefined);

  const filteredReports = useMemo(() => {
    return reports.filter(r => {
      if (searchText && !r.name.toLowerCase().includes(searchText.toLowerCase())) {
        return false;
      }
      if (scenarioFilter && r.scenario !== scenarioFilter) {
        return false;
      }
      return true;
    });
  }, [reports, searchText, scenarioFilter]);

  return (
    <div>
      {/* 篩選工具列 */}
      <Space
        style={{
          marginBottom: 16,
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <Input.Search
          placeholder="搜尋報表名稱..."
          allowClear
          prefix={<SearchOutlined />}
          onSearch={setSearchText}
          onChange={e => setSearchText(e.target.value)}
          style={{
            width: 240,
            borderRadius: tokens.borderRadius,
          }}
        />
        <Select
          placeholder="篩選場景"
          allowClear
          onChange={value => setScenarioFilter(value)}
          options={SCENARIO_FILTER_OPTIONS}
          style={{
            width: 180,
            borderRadius: tokens.borderRadius,
          }}
        />
      </Space>

      {/* 報表卡片列表 */}
      <List
        dataSource={filteredReports}
        loading={loading}
        locale={{
          emptyText: (
            <Empty
              description="尚無已儲存的報表"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ),
        }}
        renderItem={item => (
          <List.Item style={{ border: 'none', padding: 0, marginBottom: 12 }}>
            <Card
              hoverable
              size="small"
              style={{
                width: '100%',
                borderRadius: tokens.borderRadius,
                background: tokens.containerBg,
                boxShadow: tokens.cardShadow,
                transition: 'all 0.25s ease',
              }}
              styles={{ body: { padding: 16 } }}
              onMouseEnter={e => {
                e.currentTarget.style.boxShadow = tokens.cardShadowHover;
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.boxShadow = tokens.cardShadow;
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <div
                role="button"
                tabIndex={0}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  cursor: 'pointer',
                }}
                onClick={() => onLoadReport(item.id)}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onLoadReport(item.id);
                  }
                }}
              >
                {/* 報表資訊 */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <Text
                    strong
                    style={{
                      fontSize: 14,
                      color: tokens.colorTextBase,
                      display: 'block',
                      marginBottom: 4,
                    }}
                  >
                    {item.name}
                  </Text>

                  <div
                    style={{
                      fontSize: 12,
                      color: tokens.textSecondary,
                      marginBottom: 6,
                    }}
                  >
                    {getScenarioDisplayName(item.scenario)} · {formatDateTime(item.created_at)}
                  </div>

                  {item.tags && item.tags.length > 0 && (
                    <Space size={[4, 4]} wrap>
                      {item.tags.map(tag => (
                        <Tag key={tag} style={{ fontSize: 11, borderRadius: tokens.borderRadius }}>
                          {tag}
                        </Tag>
                      ))}
                    </Space>
                  )}
                </div>

                {/* 刪除按鈕 */}
                <Popconfirm
                  title="刪除報表"
                  description="確定要刪除此報表嗎？此操作無法復原。"
                  onConfirm={() => onDeleteReport(item.id)}
                  okText="刪除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                >
                  <Tooltip title="刪除報表">
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={e => e.stopPropagation()}
                      style={{ flexShrink: 0 }}
                    />
                  </Tooltip>
                </Popconfirm>
              </div>
            </Card>
          </List.Item>
        )}
      />
    </div>
  );
}
