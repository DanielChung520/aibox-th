/**
 * @file        ActionScriptDetail.tsx
 * @description 行動腳本規格書頁面 — Tab 分頁檢視技能詳細規格
 * @lastUpdate  2026-06-22
 * @author      Sisyphus
 * @version     1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Tabs, Tag, Spin, Button, Typography, App, Input, Space } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import { actionApi } from '../../services/api';
import mermaid from 'mermaid';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface ActionScript {
  _key: string;
  skill_no: string;
  name: string;
  title?: string;
  description?: string;
  version?: string;
  status?: string;
  skill_type?: string;
  tags?: string[];
  steps?: string[];
  guardrails?: string[];
  linked_intents?: string[];
  linked_agents?: string[];
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  developed_by?: string;
  spec_version?: string;
  code_language?: string;
  data_scope?: Record<string, unknown>;
  raw_requirement?: string;
  estimated_hours?: number;
}

export default function ActionScriptDetail() {
  const { skill_no } = useParams<{ skill_no: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [skill, setSkill] = useState<ActionScript | null>(null);
  const [loading, setLoading] = useState(true);
  const [mermaidSvg, setMermaidSvg] = useState('');
  const [mermaidCode, setMermaidCode] = useState('');
  const [mermaidError, setMermaidError] = useState('');

  const loadSkill = useCallback(async () => {
    if (!skill_no) return;
    setLoading(true);
    try {
      const res = await actionApi.getByNo(skill_no);
      const data = res.data?.data;
      setSkill(data);
      // 從 steps 生成 Mermaid code
      if (data?.steps && data.steps.length > 0) {
        const steps = data.steps.map((s: string) => {
          try { return JSON.parse(s); } catch { return { title: s, type: 'manual' }; }
        });
        const code = generateMermaidCode(steps);
        setMermaidCode(code);
        renderMermaid(code);
      }
    } catch { message.error('載入失敗'); }
    setLoading(false);
  }, [skill_no, message]);

  useEffect(() => { loadSkill(); }, [loadSkill]);

  const renderMermaid = useCallback(async (code: string) => {
    setMermaidError('');
    try {
      await mermaid.initialize({ startOnLoad: false });
      const { svg } = await mermaid.render('mermaid-chart', code);
      setMermaidSvg(svg);
    } catch (e: any) {
      setMermaidError(e?.message || '渲染失敗');
      setMermaidSvg('');
    }
  }, []);

  const handleRefreshMermaid = () => {
    if (mermaidCode) renderMermaid(mermaidCode);
  };

  const parseSteps = (): any[] => {
    if (!skill?.steps) return [];
    return skill.steps.map((s: string) => {
      try { return JSON.parse(s); } catch { return { title: s, type: 'manual' }; }
    });
  };

  const tabItems = [
    {
      key: 'requirement',
      label: '原始需求',
      children: (
        <div style={{ padding: '16px 0' }}>
          <TextArea rows={10} value={skill?.raw_requirement || '（尚未填寫原始需求）'} readOnly
            style={{ fontSize: 13, color: '#333', background: '#fafafa' }} />
        </div>
      ),
    },
    {
      key: 'steps',
      label: '執行步驟',
      children: (
        <div style={{ padding: '16px 0' }}>
          {parseSteps().length === 0 ? (
            <Text type="secondary">（無步驟定義）</Text>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {parseSteps().map((step, i) => (
                <Card key={i} size="small"
                  style={{ borderLeft: `4px solid ${step.type === 'condition' ? '#faad14' : step.type === 'llm_prompt' ? '#1677ff' : '#52c41a'}` }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <Tag color={step.type === 'condition' ? 'gold' : step.type === 'llm_prompt' ? 'blue' : 'green'}
                      style={{ flexShrink: 0, marginTop: 2 }}>
                      {step.type === 'condition' ? '◆ 條件' : step.type === 'llm_prompt' ? '🤖 LLM' : step.type === 'script' ? '📜 Script' : step.type === 'manual' ? '👤 Manual' : '🔧 Tool'}
                    </Tag>
                    <div style={{ flex: 1 }}>
                      <Text strong style={{ fontSize: 13 }}>{step.title}</Text>
                      {step.description && <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>{step.description}</div>}
                      {step.type === 'condition' && step.branches && (
                        <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {step.branches.map((br: any, bi: number) => (
                            <Tag key={bi} color="processing">{br.label}</Tag>
                          ))}
                        </div>
                      )}
                      {step.prompt && (
                        <div style={{ marginTop: 4, background: '#f5f5f5', padding: '6px 8px', borderRadius: 4, fontSize: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                          {step.prompt.substring(0, 200)}{step.prompt.length > 200 ? '...' : ''}
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'mermaid',
      label: 'Mermaid 流程',
      children: (
        <div style={{ padding: '16px 0' }}>
          <Space style={{ marginBottom: 12 }}>
            <Button size="small" icon={<ReloadOutlined />} onClick={handleRefreshMermaid}>重新渲染</Button>
            <Button size="small" icon={<CopyOutlined />} onClick={() => { navigator.clipboard.writeText(mermaidCode); message.success('已複製'); }}>
              複製 Mermaid 碼
            </Button>
          </Space>
          {mermaidError ? (
            <div style={{ padding: 20, background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 6, marginBottom: 12 }}>
              <Text type="danger">渲染失敗：{mermaidError}</Text>
            </div>
          ) : mermaidSvg ? (
            <div style={{ background: '#fff', borderRadius: 8, padding: 24, border: '1px solid #f0f0f0', overflow: 'auto', marginBottom: 12 }}
              dangerouslySetInnerHTML={{ __html: mermaidSvg }} />
          ) : (
            <div style={{ padding: 20, textAlign: 'center', color: '#ccc' }}>載入中...</div>
          )}
          <div style={{ marginTop: 8 }}>
            <Text strong style={{ fontSize: 12 }}>Mermaid 原始碼</Text>
            <TextArea rows={6} value={mermaidCode} readOnly
              style={{ fontFamily: 'monospace', fontSize: 12, marginTop: 4 }} />
          </div>
        </div>
      ),
    },
    {
      key: 'params',
      label: '參數變數',
      children: (
        <div style={{ padding: '16px 0' }}>
          {skill?.data_scope ? (
            <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, fontSize: 13 }}>
              {JSON.stringify(skill.data_scope, null, 2)}
            </pre>
          ) : (
            <Text type="secondary">（無定義參數變數）</Text>
          )}
        </div>
      ),
    },
    {
      key: 'rules',
      label: '規則說明',
      children: (
        <div style={{ padding: '16px 0' }}>
          {skill?.guardrails && skill.guardrails.length > 0 ? (
            <ul style={{ fontSize: 13, lineHeight: 2 }}>
              {skill.guardrails.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          ) : (
            <Text type="secondary">（無規則說明）</Text>
          )}
        </div>
      ),
    },
    {
      key: 'hours',
      label: '預估工時',
      children: (
        <div style={{ padding: '16px 0' }}>
          <Text strong style={{ fontSize: 24 }}>
            {skill?.estimated_hours ? `${skill.estimated_hours} 小時` : '—'}
          </Text>
        </div>
      ),
    },
  ];

  if (loading) return <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>;
  if (!skill) return <div style={{ textAlign: 'center', padding: 60, color: '#ccc' }}>找不到此技能</div>;

  const statusColors: Record<string, string> = { enabled: 'green', disabled: 'default', draft: 'orange' };

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
      {/* Header */}
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate('/app/knowledge/skills')}
        style={{ marginBottom: 12, padding: 0 }}>
        返回技能列表
      </Button>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <Title level={4} style={{ margin: 0 }}>{skill.name || skill.skill_no}</Title>
              {skill.version && <Tag>{skill.version}</Tag>}
              <Tag color={statusColors[skill.status || ''] || 'default'}>{skill.status}</Tag>
              {skill.skill_type && <Tag color="geekblue">{skill.skill_type}</Tag>}
            </div>
            {skill.title && <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>{skill.title}</Text>}
            {skill.description && <Paragraph style={{ fontSize: 13, color: '#555', marginBottom: 0 }}>{skill.description}</Paragraph>}
          </div>
          <div style={{ textAlign: 'right', fontSize: 12, color: '#888', whiteSpace: 'nowrap' }}>
            <div>SKL: {skill.skill_no}</div>
            <div>建立：{skill.created_at?.substring(0, 10) || '—'}</div>
            <div>更新：{skill.updated_at?.substring(0, 10) || '—'}</div>
            <div>{skill.developed_by ? `作者：${skill.developed_by}` : ''}</div>
          </div>
        </div>

        {skill.tags && skill.tags.length > 0 && (
          <div style={{ marginTop: 8, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {skill.tags.map((t, i) => <Tag key={i} style={{ fontSize: 11 }}>{t}</Tag>)}
          </div>
        )}
      </Card>

      {/* Tabs */}
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}

// Mermaid code generator (copied from SkillsManagement.tsx with condition support)
function generateMermaidCode(steps: any[]): string {
  const typeColors: Record<string, { fill: string; stroke: string; color: string }> = {
    llm_prompt: { fill: '#e6f4ff', stroke: '#1677ff', color: '#135200' },
    script: { fill: '#fff7e6', stroke: '#fa8c16', color: '#873800' },
    manual: { fill: '#f6ffed', stroke: '#52c41a', color: '#135200' },
    agent: { fill: '#f9f0ff', stroke: '#722ed1', color: '#391063' },
    tool: { fill: '#fff0f6', stroke: '#eb2f96', color: '#9c0e5c' },
    condition: { fill: '#fffbe6', stroke: '#faad14', color: '#874d00' },
  };

  let code = 'flowchart TD\n';
  let condIndex = 0;

  steps.forEach((step, i) => {
    const id = `step${i}`;
    const typeLabel = step.type === 'llm_prompt' ? 'LLM' : step.type === 'script' ? 'Script' : step.type === 'manual' ? 'Manual' : step.type === 'agent' ? 'Agent' : step.type === 'condition' ? '條件' : 'Tool';
    const label = `${i + 1}. ${step.title} (${typeLabel})`.replace(/"/g, '#quot;');

    if (step.type === 'condition') {
      code += `    ${id}{"${label}"}\n`;
      const nextNonBranch = (() => { for (let j = i + 1; j < steps.length; j++) { if (steps[j].type !== 'condition') return j; } return -1; })();
      if (step.branches && step.branches.length > 0) {
        step.branches.forEach((br: any, bi: number) => {
          const bid = `cond${condIndex}_${bi}`;
          const blabel = br.label.replace(/"/g, '#quot;');
          code += `    ${bid}["${blabel}"]\n`;
          code += `    ${id} -->|${blabel}| ${bid}\n`;
          const target = br.target !== undefined ? br.target : (nextNonBranch >= 0 ? nextNonBranch : -1);
          if (target >= 0 && target < steps.length) {
            const hasCondBetween = steps.slice(i + 1, target).some((s: any) => s.type === 'condition');
            if (!hasCondBetween) code += `    ${bid} --> step${target}\n`;
            else code += `    ${bid} --> done["✅ 完成"]\n`;
          } else if (nextNonBranch >= 0) { code += `    ${bid} --> step${nextNonBranch}\n`; }
          else { code += `    ${bid} --> done["✅ 完成"]\n`; }
        });
        condIndex++;
      } else { code += `    ${id}["${label}"]\n`; }
    } else { code += `    ${id}["${label}"]\n`; }
  });

  const nonCondIndices = steps.map((s: any, i: number) => s.type !== 'condition' ? i : -1).filter((i: number) => i >= 0);
  for (let ci = 0; ci < nonCondIndices.length - 1; ci++) {
    const from = nonCondIndices[ci];
    const to = nonCondIndices[ci + 1];
    const hasCondBetween = steps.slice(from + 1, to).some((s: any) => s.type === 'condition');
    if (!hasCondBetween) code += `    step${from} --> step${to}\n`;
  }
  if (nonCondIndices.length > 0) code += `    step${nonCondIndices[nonCondIndices.length - 1]} --> done["✅ 完成"]\n`;
  code += `    style done fill:#f6ffed,stroke:#52c41a,color:#135200\n`;
  steps.forEach((step: any, i: number) => {
    const colors = typeColors[step.type]; if (colors) code += `    style step${i} fill:${colors.fill},stroke:${colors.stroke},color:${colors.color}\n`;
  });
  return code;
}
