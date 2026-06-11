/**
 * @file        Data Agent Schema 過濾標籤
 * @description Schema 頁面的分類標籤過濾元件
 * @lastUpdate  2026-04-11 18:13:37
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { theme } from 'antd';
import { CATEGORY_COLOR_MAP, CATEGORY_COLOR_MAP_DARK } from './schemaConstants';

interface SchemaFilterTagsProps {
  categoryOptions: { label: string; value: string }[];
  selectedCategory: string;
  onSelect: (value: string) => void;
}

export default function SchemaFilterTags({
  categoryOptions,
  selectedCategory,
  onSelect,
}: SchemaFilterTagsProps) {
  const { token: antToken } = theme.useToken();
  const isDark = antToken.colorBgBase === '#0f172a' || antToken.colorBgContainer === 'rgb(30, 41, 59)';

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
      {categoryOptions.map(opt => {
        const isActive = selectedCategory === opt.value;
        const colorMap = isDark ? CATEGORY_COLOR_MAP_DARK : CATEGORY_COLOR_MAP;
        const bg = colorMap[opt.value] || (isDark ? '#2a2a2a' : '#f0f0f0');
        const textColor = isActive ? '#fff' : (isDark ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.85)');
        return (
          <div
            key={opt.value}
            onClick={() => onSelect(opt.value)}
            onMouseEnter={e => {
              if (!isActive) {
                (e.currentTarget as HTMLElement).style.background = isDark
                  ? 'rgba(255,255,255,0.12)'
                  : 'rgba(0,0,0,0.06)';
              }
            }}
            onMouseLeave={e => {
              if (!isActive) {
                (e.currentTarget as HTMLElement).style.background = bg;
              }
            }}
            style={{
              padding: '6px 16px',
              borderRadius: 6,
              cursor: 'pointer',
              fontWeight: isActive ? 600 : 400,
              background: isActive ? antToken.colorPrimary : bg,
              color: textColor,
              border: '1.5px solid transparent',
              transition: 'background 0.15s',
              fontSize: 14,
            }}
          >
            {opt.label}
          </div>
        );
      })}
    </div>
  );
}
