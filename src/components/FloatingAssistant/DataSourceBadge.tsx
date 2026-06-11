/**
 * @file        DataSourceBadge.tsx
 * @description 顯示 AI 回應過程中所調閱的資料來源（知識庫、資料庫、工具）
 * @lastUpdate  2026-04-27 12:30:00
 * @author      AI Agent
 * @version     1.0.0
 */

import type { DataSourceRecord } from '../../stores/chatStoreTypes';
import { DatabaseOutlined, BookOutlined, ToolOutlined } from '@ant-design/icons';

interface DataSourceBadgeProps {
  sources: DataSourceRecord[];
}

const iconMap = {
  knowledge: BookOutlined,
  database: DatabaseOutlined,
  tool: ToolOutlined,
};

const labelMap = {
  knowledge: '知識庫',
  database: '資料庫',
  tool: '工具',
};

export default function DataSourceBadge({ sources }: DataSourceBadgeProps) {
  if (sources.length === 0) return null;

  const deduped = sources.filter(
    (s, i, arr) => arr.findIndex((x) => x.label === s.label && x.type === s.type) === i
  );

  return (
    <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {deduped.map((s, i) => {
        const Icon = iconMap[s.type];
        return (
          <span
            key={i}
            title={s.detail}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              fontSize: 11,
              color: s.success ? 'rgba(255,255,255,0.45)' : '#ef4444',
              background: 'rgba(255,255,255,0.06)',
              borderRadius: 4,
              padding: '1px 6px',
              lineHeight: '18px',
            }}
          >
            <Icon style={{ fontSize: 10 }} />
            {labelMap[s.type]}：{s.label}
            {s.row_count !== undefined ? ` (${s.row_count} 筆)` : ''}
            {s.duration_ms !== undefined ? ` ${s.duration_ms}ms` : ''}
          </span>
        );
      })}
    </div>
  );
}
