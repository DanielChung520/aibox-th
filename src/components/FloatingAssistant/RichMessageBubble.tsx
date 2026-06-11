/**
 * @file        RichMessageBubble.tsx
 * @description 艾企 Tauri 視窗的 Markdown 訊息氣泡：程式碼高亮、Mermaid 圖表、表格、複製按鈕
 * @lastUpdate  2026-04-27 12:00:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useState } from 'react';
import { Button, message } from 'antd';
import { CopyOutlined, CheckOutlined } from '@ant-design/icons';
import CodeBlock from '../CodeBlock';
import MermaidToggle from '../MermaidToggle';
import TableBlock from '../TableBlock';
import { MarkdownContent } from './ChatMarkdown';

interface RichMessageBubbleProps {
  content: string;
  role: 'user' | 'assistant';
}

type Segment =
  | { kind: 'text'; body: string }
  | { kind: 'code'; lang: string; body: string }
  | { kind: 'table'; body: string };

function isTableRow(line: string): boolean {
  const t = line.trim();
  return t.startsWith('|') && t.split('|').filter(Boolean).length >= 2;
}

function isTableSeparator(line: string): boolean {
  const t = line.trim().replace(/\|/g, '');
  return /^[ :-]+$/.test(t);
}

function extractTables(text: string): Segment[] {
  const result: Segment[] = [];
  const lines = text.split('\n');
  let pending: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (isTableRow(trimmed) && !isTableSeparator(trimmed)) {
      pending.push(trimmed);
    } else if (isTableSeparator(trimmed)) {
      if (pending.length > 0) {
        result.push({ kind: 'table', body: pending.join('\n') });
        pending = [];
      }
    } else {
      if (pending.length > 0) {
        result.push({ kind: 'table', body: pending.join('\n') });
        pending = [];
      }
      result.push({ kind: 'text', body: trimmed });
    }
  }
  if (pending.length > 0) result.push({ kind: 'table', body: pending.join('\n') });
  return result;
}

function parseSegments(raw: string): Segment[] {
  const segments: Segment[] = [];
  const re = /```(\w*)\n?([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(raw)) !== null) {
    if (m.index > last) {
      for (const seg of extractTables(raw.slice(last, m.index))) segments.push(seg);
    }
    const lang = m[1] || 'text';
    const body = m[2].trim();
    segments.push({ kind: 'code', lang, body });
    last = re.lastIndex;
  }

  for (const seg of extractTables(raw.slice(last))) segments.push(seg);
  return segments;
}

export default function RichMessageBubble({ content, role }: RichMessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isAssistant = role === 'assistant';
  const segments = parseSegments(content);

  const handleCopyAll = () => {
    void navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      message.success('已複製到剪貼簿');
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.kind === 'code') {
          if (seg.lang === 'mermaid') {
            return <MermaidToggle key={i} code={seg.body} />;
          }
          return <CodeBlock key={i} code={seg.body} language={seg.lang || 'text'} />;
        }
        if (seg.kind === 'table') {
          return <TableBlock key={i} markdown={seg.body} />;
        }
        return (
          <div key={i} style={{ padding: '1px 0' }}>
            <MarkdownContent content={seg.body} />
          </div>
        );
      })}
      {isAssistant && content.trim() && (
        <div style={{ display: 'flex', marginTop: 8, opacity: 0.5 }}>
          <Button
            type="text"
            size="small"
            icon={copied ? <CheckOutlined /> : <CopyOutlined />}
            onClick={handleCopyAll}
            style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', height: 24, padding: '0 4px' }}
          >
            {copied ? '已複製' : '複製'}
          </Button>
        </div>
      )}
    </>
  );
}
