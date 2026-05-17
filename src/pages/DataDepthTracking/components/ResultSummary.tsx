/**
 * @file        追蹤結果摘要面板
 * @description 展示追蹤結果的統計數據（節點數、邊數、最大深度、耗時）與資料表類型分布
 * @lastUpdate  2026-05-17
 * @author      Daniel Chung
 * @version     1.0.0
 */
import { useMemo } from 'react';
import { Card, Statistic, Row, Col, Divider, Typography, Tag } from 'antd';
import { DatabaseOutlined, ApartmentOutlined, NodeIndexOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { getTableCategory } from '../../data-agent/schemaGraphUtils';

const { Text } = Typography;

/* =================== 型別定義 =================== */

export interface TraceNodeSummary {
  ragic_id: string;
  table_name: string;
  depth: number;
  fields: Record<string, unknown>;
  table_key?: string;
}

export interface ResultSummaryProps {
  nodeCount: number;
  edgeCount: number;
  maxDepth: number;
  totalTimeMs: number;
  nodes: TraceNodeSummary[];
}

/* =================== 工具函式 =================== */

/** 計算各 table 類型在回傳結果中的分布統計 */
interface TableGroup {
  tableName: string;
  count: number;
  category: string;
}

function groupByTable(nodes: TraceNodeSummary[]): TableGroup[] {
  const map = new Map<string, { count: number; tableName: string }>();
  for (const n of nodes) {
    const key = n.table_name || '未知';
    const existing = map.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      map.set(key, { count: 1, tableName: key });
    }
  }
  return Array.from(map.values())
    .map(item => ({
      tableName: item.tableName,
      count: item.count,
      category: getTableCategory(item.tableName),
    }))
    .sort((a, b) => b.count - a.count);
}

/** Module name → Tag color 映射（使用 Ant Design 預設 Tag 色票） */
const MODULE_TAG_COLORS: Record<string, string> = {
  '基礎資料': 'blue',
  '進銷存': 'cyan',
  '生產製造': 'green',
  '品質/ISO': 'orange',
  'CRM/SCM': 'purple',
  '人資/行政': 'pink',
  '專案/研發': 'geekblue',
  '管理': 'gold',
};

function getModuleTagColor(category: string): string {
  return MODULE_TAG_COLORS[category] ?? 'default';
}

/* =================== 主元件 =================== */

export default function ResultSummary({ nodeCount, edgeCount, maxDepth, totalTimeMs, nodes }: ResultSummaryProps) {
  const tableGroups = useMemo(() => groupByTable(nodes), [nodes]);

  const formatTime = (ms: number): string => {
    if (ms < 1000) return `${ms.toFixed(0)} ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
    const mins = Math.floor(ms / 60000);
    const secs = ((ms % 60000) / 1000).toFixed(0);
    return `${mins}m ${secs}s`;
  };

  const statStyle: React.CSSProperties = { textAlign: 'center' };

  return (
    <Card title="追蹤摘要" size="small">
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Statistic
            title="節點數"
            value={nodeCount}
            prefix={<NodeIndexOutlined />}
            valueStyle={{ ...statStyle, color: '#1677ff' }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="關聯邊數"
            value={edgeCount}
            prefix={<ApartmentOutlined />}
            valueStyle={{ ...statStyle, color: '#52c41a' }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="最大深度"
            value={maxDepth}
            prefix={<DatabaseOutlined />}
            valueStyle={{ ...statStyle, color: '#fa8c16' }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="總耗時"
            value={formatTime(totalTimeMs)}
            prefix={<ThunderboltOutlined />}
            valueStyle={{ ...statStyle, color: '#eb2f96' }}
          />
        </Col>
      </Row>

      {tableGroups.length > 0 && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
            資料表類型分布
          </Text>
          <Row gutter={[8, 8]}>
            {tableGroups.map(g => (
              <Col key={g.tableName}>
                <Tag color={getModuleTagColor(g.category)}>
                  {g.tableName}
                  <span style={{ marginLeft: 6, fontWeight: 600 }}>{g.count}</span>
                </Tag>
              </Col>
            ))}
          </Row>
        </>
      )}
    </Card>
  );
}
