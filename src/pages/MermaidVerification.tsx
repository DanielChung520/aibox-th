import { useEffect, useState } from 'react';
import { Button, message, Tag } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, CopyOutlined, ReloadOutlined } from '@ant-design/icons';
import mermaid from 'mermaid';
import { useContentTokens, useEffectiveTheme } from '../contexts/AppThemeProvider';

const TEST_CASES = [
  {
    id: 'flowchart-basic',
    name: '基本流程圖（Flowchart TB）',
    source: 'sd-sa-ontology-spec.md §1.1',
    code: `flowchart TB
    subgraph BASE["Base Layer (5W1H Base)"]
        B1["5W1H_Base_Ontology_OWL"]
    end
    subgraph DOMAIN["Domain Layer"]
        D1["System_Development_Domain_Ontology"]
    end
    B1 --> D1
    style BASE fill:#276749,color:#fff,stroke:#1a5632,stroke-width:3px
    style DOMAIN fill:#2b6cb0,color:#fff,stroke:#1a4a8a,stroke-width:3px
    style B1 fill:#48bb78,color:#fff,stroke:#276749,stroke-width:2px
    style D1 fill:#4299e1,color:#fff,stroke:#2b6cb0,stroke-width:2px`,
    expected: 'should render with colored subgraphs',
  },
  {
    id: 'er-diagram',
    name: 'ER 關係圖',
    source: 'sd-sa-ontology-spec.md §2.3',
    code: `erDiagram
    SYSTEM ||--o{ SOFTWARE_COMPONENT : decomposes
    SYSTEM ||--o{ REQUIREMENT : has
    SYSTEM ||--o{ TEST_CASE : has
    REQUIREMENT ||--o{ FUNCTIONAL_REQUIREMENT : is_type
    REQUIREMENT ||--o{ NON_FUNCTIONAL_REQUIREMENT : is_type`,
    expected: 'should render ER relationships',
  },
  {
    id: 'pie-chart',
    name: '圓餅圖',
    source: 'sd-sa-ontology-spec.md §2.4',
    code: `pie title Department Annual ROI
    "R&D 1,400h" : 1400
    "Sales 4,248h" : 4248
    "QA 1,043h" : 1043
    "HR 898h" : 898
    "Engineering 763h" : 763`,
    expected: 'should render pie chart with departments',
  },
  {
    id: 'gantt-chart',
    name: '甘特圖',
    source: 'sd-sa-ontology-spec.md §10',
    code: `gantt
    title Ontology Extension Roadmap
    dateFormat YYYY-MM
    section Phase 1
    SD Domain and SA Major v1.0    :done, p1, 2026-04-04, 2026-04-04
    section Phase 2
    DevOps Engineering Major v1.0   :done, p2, 2026-04-04, 2026-04-04
    section Phase 3
    Security Engineering Major v1.0  :done, p3, 2026-04-04, 2026-04-04`,
    expected: 'should render gantt with 3 phases',
  },
  {
    id: 'mindmap',
    name: '心智圖',
    source: 'sd-sa-ontology-spec.md §3.1',
    code: `mindmap
    root((System_Analysis))
      FEASIBILITY
        Feasibility_Study
        Technical_Feasibility
        Economic_Feasibility
      REQUIREMENT
        Requirement_Elicitation
        Requirement_Analysis
        Stakeholder
      MODELING
        System_Modeling
        Use_Case_Diagram
        Class_Diagram`,
    expected: 'should render mindmap with branches',
  },
  {
    id: 'sequence-diagram',
    name: '時序圖',
    source: 'sd-sa-ontology-spec.md (reference)',
    code: `sequenceDiagram
    participant U as User
    participant KA as KnowledgeAgent
    participant RAG as RAG_Pipeline
    participant LLM as Generation_Model
    U->>KA: Upload Document
    KA->>RAG: Chunk and Embed
    RAG-->>KA: Store in VectorDB
    U->>KA: Query
    KA->>RAG: Retrieve Context
    RAG-->>KA: Relevant Chunks
    KA->>LLM: Generate Answer
    LLM-->>KA: Answer
    KA-->>U: Response`,
    expected: 'should render sequence diagram',
  },
  {
    id: 'flowchart-lr',
    name: '水平流程圖',
    source: 'sd-sa-ontology-spec.md §2.4',
    code: `flowchart LR
    subgraph AI["AI Requirements"]
        AI1["Meeting_Record_AI"]
        AI2["Knowledge_Base_QA"]
        AI3["Form_AI_Review"]
    end
    subgraph ONT["Ontology Mapping"]
        OM1["Technical_Documentation"]
        OM2["Knowledge_Asset"]
        OM3["Requirement_Analysis"]
    end
    AI1 --> OM1
    AI2 --> OM2
    AI3 --> OM3
    style AI fill:#2b6cb0,color:#fff,stroke:#1a4a8a,stroke-width:2px
    style ONT fill:#702459,color:#fff,stroke:#4a1a3a,stroke-width:2px`,
    expected: 'should render horizontal flowchart',
  },
  {
    id: 'quadrant-chart',
    name: '象限圖（優先級矩陣）',
    source: 'sd-sa-ontology-spec.md §5.1 (reference)',
    code: `quadrantChart
    title Priority Matrix
    x-axis Low Risk --> High Risk
    y-axis Low ROI --> High ROI
    quadrant-1 Q1 Critical
    quadrant-2 Q2 Important
    quadrant-3 Q3 Low
    quadrant-4 Q4 Normal
    "AI Image Recognition" [0.95, 0.90]
    "AI Quote" [0.90, 0.95]
    "ECN-SAP Integration" [0.95, 0.80]
    "Patent Search" [0.90, 0.75]`,
    expected: 'should render quadrant chart with data points',
  },
  {
    id: 'state-diagram',
    name: '狀態圖',
    source: 'sd-sa-ontology-spec.md (reference)',
    code: `stateDiagram-v2
    [*] --> Pending
    Pending --> Processing : Submit
    Processing --> Success : Complete
    Processing --> Failed : Error
    Success --> [*]
    Failed --> Pending : Retry`,
    expected: 'should render state diagram',
  },
  {
    id: 'class-diagram-sample',
    name: '類別圖（精簡）',
    source: 'sd-sa-ontology-spec.md (reference)',
    code: `classDiagram
    class System {
        +String name
        +System_Architecture architecture
        +addComponent()
        +deploy()
    }
    class Software_Component {
        +String component_id
        +implements()
        +satisfies_requirement()
    }
    System "1" *--> "n" Software_Component : decomposes`,
    expected: 'should render class diagram',
  },
];

const DARK_THEME = {
  primaryColor: '#3b82f6',
  primaryTextColor: '#f1f5f9',
  background: '#1e293b',
  mainBkg: '#1e293b',
  nodeBorder: '#3b82f6',
  clusterBkg: '#0f172a',
};

const LIGHT_THEME = {
  primaryColor: '#3b82f6',
  primaryTextColor: '#1e293b',
  background: '#ffffff',
  mainBkg: '#f8fafc',
  nodeBorder: '#3b82f6',
  clusterBkg: '#f1f5f9',
};

interface TestResult {
  id: string;
  status: 'pending' | 'ok' | 'error';
  svg?: string;
  error?: string;
}

export default function MermaidVerificationPage() {
  const [results, setResults] = useState<TestResult[]>([]);
  const [isDark, setIsDark] = useState(false);
  const contentTokens = useContentTokens();
  const effectiveTheme = useEffectiveTheme();

  useEffect(() => {
    setIsDark(effectiveTheme === 'dark');
  }, [effectiveTheme]);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      themeVariables: isDark ? DARK_THEME : LIGHT_THEME,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    });
  }, [isDark]);

  const runTest = async (testCase: (typeof TEST_CASES)[number]): Promise<TestResult> => {
    const id = `test-${testCase.id}-${Date.now()}`;
    try {
      await mermaid.parse(testCase.code.trim());
      const { svg } = await mermaid.render(id, testCase.code.trim());
      return { id: testCase.id, status: 'ok', svg };
    } catch (e: any) {
      const errorMsg = e?.message?.split('\n')[0] || String(e);
      return { id: testCase.id, status: 'error', error: errorMsg };
    }
  };

  const runAllTests = async () => {
    setResults(TEST_CASES.map((t) => ({ id: t.id, status: 'pending' })));
    for (const tc of TEST_CASES) {
      const result = await runTest(tc);
      setResults((prev) => prev.map((r) => (r.id === tc.id ? result : r)));
    }
    message.success('全部測試完成');
  };

  const copyCode = (code: string) => {
    void navigator.clipboard.writeText(code).then(() => {
      message.success('已複製');
    });
  };

  const getStatusIcon = (status: TestResult['status']) => {
    if (status === 'ok') return <CheckCircleOutlined style={{ color: '#22c55e' }} />;
    if (status === 'error') return <CloseCircleOutlined style={{ color: '#ef4444' }} />;
    return <span style={{ color: '#94a3b8' }}>●</span>;
  };

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Mermaid 語法渲染驗證</h2>
        <p style={{ color: '#64748b', margin: '4px 0 0' }}>
          測試 Mermaid v11.13.0 對 System_Development Ontology spec 文件的語法支援
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={() => { void runAllTests(); }}>
          執行全部測試
        </Button>
        <Tag color="blue">Mermaid v11.13.0</Tag>
        <Tag color={isDark ? 'default' : 'gold'}>{isDark ? 'Dark' : 'Light'} Theme</Tag>
      </div>

      {TEST_CASES.map((tc) => {
        const result = results.find((r) => r.id === tc.id);
        const status = result?.status ?? 'pending';

        return (
          <div key={tc.id} style={{
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
            borderRadius: 8,
            marginBottom: 16,
            overflow: 'hidden',
            background: contentTokens.chatAssistantBubble,
          }}>
            <div style={{
              padding: '8px 16px',
              borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: isDark ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.04)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {getStatusIcon(status)}
                <strong>{tc.name}</strong>
                <Tag style={{ fontSize: 11 }}>{tc.source}</Tag>
              </div>
              <Button
                type="text" size="small" icon={<CopyOutlined />}
                onClick={() => copyCode(tc.code)}
              >
                複製
              </Button>
            </div>

            {status === 'error' && result?.error && (
              <div style={{ padding: 12, color: '#ef4444', fontFamily: 'monospace', fontSize: 12 }}>
                解析錯誤：{result.error}
              </div>
            )}

            {status === 'ok' && result?.svg && (
              <div style={{ padding: 16, overflowX: 'auto' }} dangerouslySetInnerHTML={{ __html: result.svg }} />
            )}

            {status === 'pending' && (
              <div style={{ padding: 16, color: '#94a3b8', fontSize: 13 }}>
                點擊「執行全部測試」以開始驗證
              </div>
            )}
          </div>
        );
      })}

      {results.length > 0 && (
        <div style={{ padding: 12, background: isDark ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.04)', borderRadius: 8 }}>
          <strong>測試摘要：</strong>
          {results.filter(r => r.status === 'ok').length} / {results.length} 通過
          {' '}
          {results.filter(r => r.status === 'error').length > 0 && (
            <span style={{ color: '#ef4444' }}>
              {results.filter(r => r.status === 'error').length} 失敗
            </span>
          )}
        </div>
      )}
    </div>
  );
}
