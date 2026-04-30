import { useState, useEffect } from 'react';
import Markdown from 'markdown-to-jsx';
import { Button, message as antdMsg } from 'antd';
import { CaretRightOutlined, LoadingOutlined, CopyOutlined } from '@ant-design/icons';
import CodeBlock from './CodeBlock';
import MermaidToggle from './MermaidToggle';
import TableBlock from './TableBlock';
import MessageActions from './MessageActions';
import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';
import type { ChatMessage } from '../services/api';

interface MessageBubbleProps {
  message: ChatMessage;
  streamingContent?: string;
  streamingThinking?: string;
  onCopyToInput?: (content: string) => void;
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
      // skip separator row, but close table if we have content
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

function renderTextWithLinks(text: string, tokens: Record<string, string>): React.ReactNode {
  const urlRegex = /(https?:\/\/[^\s<]+)/g;
  const parts = text.split(urlRegex);
  const children = parts.map((part, i) => {
    if (/^https?:\/\//.test(part)) {
      return (
        <a key={i} href={part} target="_blank" rel="noopener noreferrer"
          style={{ color: tokens.primaryColor, textDecoration: 'underline', cursor: 'pointer', wordBreak: 'break-all' }}>
          {part}
        </a>
      );
    }
    // 非 URL 部分直接回傳字串
    return part;
  });
  // 包在 span 中讓 React 正確渲染混合字串與元件
  return <span>{children}</span>;
}

function TextRenderer({ body, tokens }: { body: string; tokens: Record<string, string> }) {
  // 使用 renderTextWithLinks 直接渲染 URL 為 <a> 標籤
  // 其餘 markdown 語法（bold, italic, code, blockquote）仍由 markdown-to-jsx 處理
  const options = {
    overrides: {
      code: {
        component: ({ children }: { children: React.ReactNode }) => (
          <code style={{ background: tokens.codeBg, padding: '0.15em 0.4em', borderRadius: 4, fontFamily: 'monospace', fontSize: '0.9em' }}>
            {children}
          </code>
        ),
      },
      table: {
        component: ({ children }: { children: React.ReactNode }) => (
          <div className="msg-table-wrapper">
            <table className="msg-table">
              {children}
            </table>
          </div>
        ),
      },
      thead: {
        component: ({ children }: { children: React.ReactNode }) => (
          <thead style={{ background: tokens.tableHeaderBg, borderBottom: `2px solid ${tokens.borderColor}` }}>
            {children}
          </thead>
        ),
      },
      th: {
        component: ({ children }: { children: React.ReactNode }) => (
          <th style={{ border: `1px solid ${tokens.borderColor}`, padding: '0.5em 0.85em', textAlign: 'left', fontWeight: 700, fontSize: '0.9em', color: tokens.textColor }}>
            {children}
          </th>
        ),
      },
      td: {
        component: ({ children }: { children: React.ReactNode }) => (
          <td style={{ border: `1px solid ${tokens.borderColor}`, padding: '0.4em 0.85em', color: tokens.textColor, fontSize: '0.9em' }}>
            {children}
          </td>
        ),
      },
      tr: {
        component: ({ children }: { children: React.ReactNode }) => (
          <tr>{children}</tr>
        ),
      },
      h1: {
        component: ({ children }: { children: React.ReactNode }) => (
          <h1 style={{ fontSize: '1.2em', fontWeight: 700, margin: '0.75em 0 0.3em', color: tokens.textColor }}>{children}</h1>
        ),
      },
      h2: {
        component: ({ children }: { children: React.ReactNode }) => (
          <h2 style={{ fontSize: '1.05em', fontWeight: 700, margin: '0.75em 0 0.25em', color: tokens.textColor }}>{children}</h2>
        ),
      },
      h3: {
        component: ({ children }: { children: React.ReactNode }) => (
          <h3 style={{ fontSize: '0.95em', fontWeight: 700, margin: '0.6em 0 0.2em', color: tokens.textColor }}>{children}</h3>
        ),
      },
      p: {
        component: ({ children }: { children: React.ReactNode }) => (
          <p style={{ margin: '0 0 0.5em', lineHeight: 1.7, color: tokens.textColor }}>{children}</p>
        ),
      },
      blockquote: {
        component: ({ children }: { children: React.ReactNode }) => (
          <blockquote style={{ borderLeft: `3px solid ${tokens.blockquoteBorder}`, margin: '0.5em 0', paddingLeft: '0.75em', color: tokens.textSecondary, fontStyle: 'italic' }}>
            {children}
          </blockquote>
        ),
      },
      a: {
        component: ({ children, href }: { children: React.ReactNode; href?: string }) => {
          const text = typeof children === 'string' ? children : '';
          const isInlineRef = /^\[\d+\]$/.test(text.trim());
          if (isInlineRef) {
            return (
              <sup>
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={href}
                  style={{
                    color: tokens.primaryColor,
                    textDecoration: 'none',
                    fontSize: '0.75em',
                    fontWeight: 600,
                    cursor: 'pointer',
                    padding: '0 1px',
                  }}
                >
                  {text}
                </a>
              </sup>
            );
          }
          return (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              title={href}
              style={{
                color: tokens.primaryColor,
                textDecoration: 'underline',
                cursor: 'pointer',
              }}
            >
              {children}
            </a>
          );
        },
      },
      ul: {
        component: ({ children }: { children: React.ReactNode }) => (
          <ul style={{ margin: '0.25em 0', paddingLeft: '1.5em', listStyleType: 'disc', color: tokens.textColor }}>{children}</ul>
        ),
      },
      ol: {
        component: ({ children }: { children: React.ReactNode }) => (
          <ol style={{ margin: '0.25em 0', paddingLeft: '1.5em', listStyleType: 'decimal', color: tokens.textColor }}>{children}</ol>
        ),
      },
      li: {
        component: ({ children }: { children: React.ReactNode }) => (
          <li style={{ margin: '0.2em 0', lineHeight: 1.6, color: tokens.textColor }}>{children}</li>
        ),
      },
      hr: {
        component: () => (
          <hr style={{ border: 'none', borderTop: `1px solid ${tokens.borderColor}`, margin: '0.75em 0' }} />
        ),
      },
      strong: {
        component: ({ children }: { children: React.ReactNode }) => (
          <strong style={{ fontWeight: 700, color: tokens.textColor }}>{children}</strong>
        ),
      },
      em: {
        component: ({ children }: { children: React.ReactNode }) => (
          <em style={{ fontStyle: 'italic', color: tokens.textSecondary }}>{children}</em>
        ),
      },
    },
  };

  return <Markdown options={options}>{linkified}</Markdown>;
}

export default function MessageBubble({ message, streamingContent, streamingThinking, onCopyToInput }: MessageBubbleProps) {
  const [thinkingExpanded, setThinkingExpanded] = useState(false);
  const contentTokens = useContentTokens();
  const effectiveTheme = useEffectiveTheme();
  const isUser = message.role === 'user';
  const content = streamingContent ?? message.content ?? '';
  const thinking = streamingThinking ?? message.thinking ?? null;

  const hasThinking = Boolean(thinking?.trim());
  const isStreaming = streamingContent !== undefined;

  const isDark = effectiveTheme === 'dark';
  const textColor = contentTokens.colorTextBase;
  const textSecondary = contentTokens.textSecondary;
  const primaryColor = contentTokens.colorPrimary;
  const borderColor = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
  const tableHeaderBg = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
  const tableRowBorder = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)';
  const blockquoteBorder = isDark ? 'rgba(59,130,246,0.6)' : 'rgba(59,130,246,0.5)';
  const thinkingBg = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)';
  const thinkingBorder = isDark ? 'rgba(168,85,247,0.6)' : 'rgba(168,85,247,0.4)';
  const codeBg = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';

  const tokens = { textColor, textSecondary, borderColor, tableHeaderBg, tableRowBorder, blockquoteBorder, primaryColor, codeBg };
  const segments = parseSegments(content);

  const zebraBg = isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)';

  useEffect(() => {
    const styleId = 'msg-bubble-table-styles';
    if (document.getElementById(styleId)) return;
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .msg-table-wrapper { border-radius: 8px; border: 1px solid ${borderColor}; overflow: hidden; margin: 0.75em 0; }
      .msg-table { border-collapse: collapse; width: 100%; font-size: 0.875em; min-width: 200; }
      .msg-table tbody tr:nth-child(even) { background: ${zebraBg}; }
      .msg-table tbody tr:hover { background: ${isDark ? 'rgba(59,130,246,0.08)' : 'rgba(59,130,246,0.06)'}; }
    `;
    document.head.appendChild(style);
    return () => {
      const el = document.getElementById(styleId);
      if (el) el.remove();
    };
  }, [borderColor, zebraBg, isDark]);

  const handleUserCopy = () => {
    if (onCopyToInput) {
      onCopyToInput(content);
      antdMsg.success('已複製到輸入框');
    }
  };

  return (
    <div style={{ marginBottom: 16 }}>
      {isUser ? (
        <div style={{ maxWidth: '70%', marginLeft: 'auto' }}>
          <div
            style={{
              background: contentTokens.chatUserBubble,
              borderRadius: 8,
              borderRight: `3px solid ${primaryColor}`,
              padding: '10px 12px 6px',
              fontSize: 14,
              lineHeight: 1.7,
              color: textColor,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {content}
          </div>
          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 4,
            marginTop: 4,
            opacity: 0.6,
          }}>
            <Button type="text" size="small" icon={<CopyOutlined />} onClick={handleUserCopy} style={{ fontSize: 11, color: textSecondary, height: 24, padding: '0 4px' }}>
              複製
            </Button>
          </div>
        </div>
      ) : (
        <div>
          {hasThinking && (
            <div style={{ marginBottom: 8 }}>
              <button
                onClick={() => setThinkingExpanded(!thinkingExpanded)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: textSecondary,
                  fontSize: 12,
                  padding: '2px 4px',
                  borderRadius: 4,
                }}
              >
                <CaretRightOutlined
                  style={{
                    transition: 'transform 0.2s',
                    transform: thinkingExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                    fontSize: 10,
                  }}
                />
                <LoadingOutlined style={{ fontSize: 10 }} />
                Thinking...
              </button>
              {thinkingExpanded && (
                <div
                  style={{
                    marginTop: 6,
                    padding: '8px 12px',
                    background: thinkingBg,
                    borderRadius: 6,
                    borderLeft: `2px solid ${thinkingBorder}`,
                    fontSize: 12,
                    lineHeight: 1.6,
                    color: textSecondary,
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {thinking}
                </div>
              )}
            </div>
          )}

          <div style={{ maxWidth: '85%' }}>
            <div style={{ fontSize: 14, lineHeight: 1.7, color: textColor }}>
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
                  <div key={i} style={{ padding: '2px 0' }}>
                    {renderTextWithLinks(seg.body, tokens)}
                  </div>
                );
              })}
            </div>
            {!isStreaming && <MessageActions messageId={message._key} messageContent={content} />}
          </div>
        </div>
      )}
    </div>
  );
}
