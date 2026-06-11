import { useState } from 'react';
import { Button, message as antdMsg } from 'antd';
import { CopyOutlined, CheckOutlined } from '@ant-design/icons';
import Markdown from 'markdown-to-jsx';
import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';

interface TableBlockProps {
  markdown: string;
}

interface Cell {
  text: string;
  align?: 'left' | 'center' | 'right';
}

interface Row {
  cells: Cell[];
}

function parseMarkdownTable(raw: string): { headers: Cell[]; rows: Row[]; colCount: number } {
  const lines = raw.trim().split('\n').filter((l) => l.trim());
  if (lines.length < 2) return { headers: [], rows: [], colCount: 0 };

  const headers = parseRow(lines[0]);
  const alignLine = lines.find((l) => l.trim().startsWith('|') && l.includes('---'));
  const alignMap: Record<number, 'left' | 'center' | 'right'> = {};
  if (alignLine) {
    const parts = alignLine.split('|').filter(Boolean);
    parts.forEach((p, i) => {
      const t = p.trim();
      if (t.startsWith(':') && t.endsWith(':')) alignMap[i] = 'center';
      else if (t.endsWith(':')) alignMap[i] = 'right';
      else alignMap[i] = 'left';
    });
  }

  const rows: Row[] = [];
  for (let i = alignLine ? 1 : 1; i < lines.length; i++) {
    const cells = parseRow(lines[i]);
    rows.push({ cells: cells.map((c, i) => ({ ...c, align: alignMap[i] })) });
  }

  return { headers: headers.map((c, i) => ({ ...c, align: alignMap[i] })), rows, colCount: headers.length };
}

function parseRow(line: string): Cell[] {
  return line
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((c) => ({ text: c.trim() }));
}

export default function TableBlock({ markdown }: TableBlockProps) {
  const [copied, setCopied] = useState(false);
  const contentTokens = useContentTokens();
  const effectiveTheme = useEffectiveTheme();
  const isDark = effectiveTheme === 'dark';

  const borderColor = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
  const headerBg = isDark ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.06)';
  const labelColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)';
  const btnColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)';
  const successColor = '#22c55e';

  const { headers, rows, colCount } = parseMarkdownTable(markdown);
  const textColor = contentTokens.colorTextBase;
  const codeBg = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';

  const cellOptions = {
    overrides: {
      p: { component: ({ children }: { children: React.ReactNode }) => <>{children}</> },
      strong: { component: ({ children }: { children: React.ReactNode }) => <strong style={{ fontWeight: 700 }}>{children}</strong> },
      em: { component: ({ children }: { children: React.ReactNode }) => <em>{children}</em> },
      code: { component: ({ children }: { children: React.ReactNode }) => <code style={{ background: codeBg, padding: '0.1em 0.3em', borderRadius: 3, fontSize: '0.88em' }}>{children}</code> },
      a: { component: ({ children, href }: { children: React.ReactNode; href?: string }) => <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: contentTokens.colorPrimary, textDecoration: 'underline' }}>{children}</a> },
    },
  };

  const handleCopy = () => {
    void navigator.clipboard.writeText(markdown).then(() => {
      setCopied(true);
      antdMsg.success('已複製到剪貼簿');
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div
      style={{
        borderRadius: 8,
        overflow: 'hidden',
        marginTop: 8,
        marginBottom: 8,
        border: `1px solid ${borderColor}`,
        background: contentTokens.chatAssistantBubble,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 12px',
          background: headerBg,
          borderBottom: `1px solid ${borderColor}`,
        }}
      >
        <span style={{ fontSize: 11, color: labelColor, fontFamily: 'monospace' }}>表格</span>
        <Button
          type="text"
          size="small"
          icon={copied ? <CheckOutlined /> : <CopyOutlined />}
          onClick={handleCopy}
          style={{ color: copied ? successColor : btnColor, fontSize: 12 }}
        >
          {copied ? '已複製' : '複製'}
        </Button>
      </div>

      <div style={{ overflowX: 'auto', padding: '12px 16px' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.875em', minWidth: colCount * 80 }}>
            <thead>
            <tr style={{ borderBottom: `2px solid ${borderColor}` }}>
              {headers.map((h, i) => (
                <th
                  key={i}
                  style={{
                    padding: '0.5em 0.85em',
                    textAlign: h.align ?? 'left',
                    fontWeight: 700,
                    color: textColor,
                    whiteSpace: 'nowrap',
                  }}
                >
                  <Markdown options={cellOptions}>{h.text}</Markdown>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                style={{ borderBottom: `1px solid ${borderColor}` }}
              >
                {row.cells.map((c, ci) => (
                  <td
                    key={ci}
                    style={{
                      padding: '0.4em 0.85em',
                      textAlign: c.align ?? 'left',
                      color: textColor,
                    }}
                  >
                    <Markdown options={cellOptions}>{c.text}</Markdown>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
