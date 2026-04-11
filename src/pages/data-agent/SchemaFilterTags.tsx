/**
 * @file        Data Agent Schema 過濾標籤
 * @description Schema 頁面的分類標籤過濾元件
 * @lastUpdate  2026-04-11 18:13:37
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { theme } from 'antd';
import { CATEGORY_COLOR_MAP } from './schemaConstants';

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

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
      {categoryOptions.map(opt => {
        const isActive = selectedCategory === opt.value;
        const bg = CATEGORY_COLOR_MAP[opt.value] || '#fafafa';
        return (
          <div
            key={opt.value}
            onClick={() => onSelect(opt.value)}
            style={{
              padding: '6px 16px',
              borderRadius: 6,
              cursor: 'pointer',
              fontWeight: isActive ? 600 : 400,
              background: isActive ? antToken.colorPrimary : bg,
              color: isActive ? '#fff' : 'inherit',
              border: '1.5px solid transparent',
              transition: 'all 0.2s',
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
