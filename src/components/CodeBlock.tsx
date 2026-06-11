import { useRef, useEffect, useState } from 'react';
import { Button, message } from 'antd';
import hljs from 'highlight.js';
import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';

interface CodeBlockProps {
  code: string;
  language?: string;
}

const LANGUAGE_LABELS: Record<string, string> = {
  python: 'Python',
  javascript: 'JavaScript',
  typescript: 'TypeScript',
  jsx: 'JSX',
  tsx: 'TSX',
  rust: 'Rust',
  go: 'Go',
  java: 'Java',
  cpp: 'C++',
  c: 'C',
  bash: 'Bash',
  shell: 'Shell',
  sql: 'SQL',
  json: 'JSON',
  yaml: 'YAML',
  yml: 'YAML',
  xml: 'XML',
  html: 'HTML',
  css: 'CSS',
  markdown: 'Markdown',
  mermaid: 'Mermaid',
  text: '純文字',
};

export default function CodeBlock({ code, language = 'text' }: CodeBlockProps) {
  const codeRef = useRef<HTMLElement>(null);
  const [copied, setCopied] = useState(false);
  const contentTokens = useContentTokens();
  const effectiveTheme = useEffectiveTheme();
  const isDark = effectiveTheme === 'dark';

  const handleCopy = () => {
    void navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      message.success('已複製到剪貼簿');
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const label = LANGUAGE_LABELS[language.toLowerCase()] ?? language.toUpperCase();

  useEffect(() => {
    if (!codeRef.current) return;
    const lang = language.toLowerCase();
    try {
      if (lang && lang !== 'text' && hljs.getLanguage(lang)) {
        const result = hljs.highlight(code, { language: lang, ignoreIllegals: true });
        codeRef.current.innerHTML = result.value;
      } else {
        codeRef.current.textContent = code;
      }
    } catch {
      if (codeRef.current) codeRef.current.textContent = code;
    }
  }, [code, language]);

  useEffect(() => {
    const linkId = 'hljs-theme';
    const existing = document.getElementById(linkId);
    if (existing) existing.remove();
    const link = document.createElement('link');
    link.id = linkId;
    link.rel = 'stylesheet';
    link.href = isDark
      ? 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github-dark.min.css'
      : 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github.min.css';
    document.head.appendChild(link);
  }, [isDark]);

  const borderColor = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
  const labelColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)';
  const copyColor = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.45)';
  const copySuccessColor = '#22c55e';
  const headerBg = isDark ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.06)';

  return (
    <div style={{
      borderRadius: 8,
      overflow: 'hidden',
      marginTop: 8,
      marginBottom: 8,
      border: `1px solid ${borderColor}`,
      background: contentTokens.chatAssistantBubble,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '4px 12px',
        background: headerBg,
        borderBottom: `1px solid ${borderColor}`,
      }}>
        <span style={{ fontSize: 11, color: labelColor, fontFamily: 'monospace' }}>
          {label}
        </span>
        <Button
          type="text"
          size="small"
          icon={copied ? <CheckOutlined /> : <CopyOutlined />}
          onClick={handleCopy}
          style={{ color: copied ? copySuccessColor : copyColor, fontSize: 12 }}
        >
          {copied ? '已複製' : '複製'}
        </Button>
      </div>
      <pre style={{
        margin: 0,
        padding: '12px 16px',
        background: 'transparent',
        overflow: 'auto',
        fontSize: 13,
        lineHeight: 1.6,
        fontFamily: '"Fira Code", "Cascadia Code", "JetBrains Mono", Consolas, monospace',
        maxHeight: 400,
      }}>
        <code ref={codeRef} className={`language-${language}`} style={{ fontFamily: 'inherit' }}>
          {code}
        </code>
      </pre>
    </div>
  );
}
