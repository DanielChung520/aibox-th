/**
 * @file        ChatMarkdown.tsx
 * @description Mermaid 圖表渲染與 Markdown 內容展示元件
 * @lastUpdate  2026-04-18 22:45:00
 * @author      AI Agent
 * @version     1.0.0
 */

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  fontFamily: 'var(--ant-font-family, sans-serif)',
  securityLevel: 'strict',
});

function MermaidBlock({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;

    mermaid.render(id, code).then(
      ({ svg: rendered }) => {
        if (!cancelled) setSvg(rendered);
      },
      (err) => {
        if (!cancelled) setError(String(err));
      }
    );

    return () => { cancelled = true; };
  }, [code]);

  if (error) {
    return (
      <pre className="mermaid-error" style={{ color: '#f87171', fontSize: 12, whiteSpace: 'pre-wrap' }}>
        {`Mermaid render error:\n${error}`}
      </pre>
    );
  }

  if (svg) {
    return <div ref={containerRef} className="mermaid-container" dangerouslySetInnerHTML={{ __html: svg }} />;
  }

  return <pre className="mermaid">{code}</pre>;
}

export function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          const codeString = String(children).replace(/\n$/, '');

          if (match && match[1] === 'mermaid') {
            return <MermaidBlock code={codeString} />;
          }

          return (
            <code className={className} {...props}>
              {children}
            </code>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export { MermaidBlock };
