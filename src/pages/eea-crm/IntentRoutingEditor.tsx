/**
 * @file        IntentRoutingEditor.tsx
 * @description 業務助理意圖路由表 — 列表式維護介面
 *              編輯 routing rules JSON 不需手寫 JSON，表單欄位各自獨立
 * @lastUpdate  2026-06-14
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import {
  Table, Button, Switch, Tag, Modal, Form, Input, Select, Slider,
  App, Space, Typography, Tooltip, Alert,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import { paramsApi } from '../../services/api';

const { Text } = Typography;

/* ─── Types ────────────────────────────────────────────── */

interface IntentRoute {
  intent_id: string;
  name: string;
  description: string;
  enabled: boolean;
  priority: number;
  stage1: { keywords: string[]; match_mode: 'any' | 'all' };
  stage2: { classification_prompt: string; few_shot_examples: { role: string; content: string }[] };
  target: { type: 'skill' | 'direct_answer'; skill_name?: string; response_template?: string; direct_params?: Record<string, string> };
  parameter_extraction: { extraction_prompt: string; required_fields: string[]; optional_fields: string[] };
  permissions: { scenarios: string[]; min_level: string };
}

interface IntentRoutingData {
  rules: IntentRoute[];
  model: string;
  fallback: string;
}

const SCENARIO_OPTIONS = [
  { label: '客戶端', value: 'customer_bot' },
  { label: '內部助理', value: 'internal_assistant' },
];

const LEVEL_OPTIONS = [
  { label: 'L0', value: 'L0' },
  { label: 'L1', value: 'L1' },
  { label: 'L2', value: 'L2' },
  { label: 'L3', value: 'L3' },
  { label: 'L4', value: 'L4' },
];

const TARGET_TYPE_OPTIONS = [
  { label: 'Skill 呼叫', value: 'skill' },
  { label: '直接回覆', value: 'direct_answer' },
];

const MATCH_MODE_OPTIONS = [
  { label: '任一關鍵詞命中', value: 'any' },
  { label: '全部關鍵詞命中', value: 'all' },
];

const EMPTY_INTENT: IntentRoute = {
  intent_id: '', name: '', description: '', enabled: true, priority: 50,
  stage1: { keywords: [], match_mode: 'any' },
  stage2: { classification_prompt: '', few_shot_examples: [] },
  target: { type: 'skill', skill_name: '' },
  parameter_extraction: { extraction_prompt: '', required_fields: [], optional_fields: [] },
  permissions: { scenarios: ['customer_bot'], min_level: 'L0' },
};

/* ─── Scenario Badge ───────────────────────────────────── */

function ScenarioBadge({ scenarios }: { scenarios: string[] }) {
  const hasCus = scenarios.includes('customer_bot');
  const hasInt = scenarios.includes('internal_assistant');
  if (hasCus && hasInt) return <Tag color="blue">雙場景</Tag>;
  if (hasCus) return <Tag color="green">客戶端</Tag>;
  if (hasInt) return <Tag color="orange">內部</Tag>;
  return null;
}

/* ─── Main Component ───────────────────────────────────── */

const DEFAULT_RULES: IntentRoute[] = [
  // ═══ 場景一：客戶端 LINE Bot ═══
  {
    intent_id:"greeting_basic", name:"基本問候", description:"早安、哈囉、嗨等日常打招呼，模板回覆即可",
    enabled:true, priority:101,
    stage1:{keywords:["早安","你好","哈囉","嗨","午安","晚安","hello","hi"],match_mode:"any"},
    stage2:{classification_prompt:"使用者正在日常打招呼，語氣友善，無特定節日",few_shot_examples:[
      {role:"user",content:"早安"},{role:"assistant",content:'{"intent":"greeting_basic","confidence":0.98}'}]},
    target:{type:"direct_answer",response_template:"{{greeting_time}}您好！祝您有美好的一天。"},
    parameter_extraction:{extraction_prompt:"",required_fields:[],optional_fields:[]},
    permissions:{scenarios:["customer_bot","internal_assistant"],min_level:"L0"} },
  {
    intent_id:"greeting_celebration", name:"節日祝福", description:"新年、生日、中秋等慶祝性祝福，需 LLM 生成有變化的賀詞",
    enabled:true, priority:100,
    stage1:{keywords:["新年快樂","生日快樂","中秋節","聖誕快樂","母親節","過年","恭喜發財","佳節愉快"],match_mode:"any"},
    stage2:{classification_prompt:"使用者表達節日或慶祝性祝福，需生成有溫度、有變化的賀詞回覆",few_shot_examples:[
      {role:"user",content:"新年快樂"},{role:"assistant",content:'{"intent":"greeting_celebration","confidence":0.97}'}]},
    target:{type:"skill",skill_name:"greeting_engine",direct_params:{greeting_type:"auto"}},
    parameter_extraction:{extraction_prompt:"提取祝福類型(event_type: new_year/birthday/mid_autumn/xmas)",required_fields:[],optional_fields:["event_type"]},
    permissions:{scenarios:["customer_bot","internal_assistant"],min_level:"L0"} },
  {
    intent_id:"greeting_image", name:"問候圖片回覆", description:"客戶傳送問候圖片（賀卡、早安圖等）",
    enabled:true, priority:96,
    stage1:{keywords:[],match_mode:"any"},
    stage2:{classification_prompt:"使用者傳送了一張圖片，內容為節日賀卡、早安圖等問候性質圖片",few_shot_examples:[]},
    target:{type:"skill",skill_name:"image_processor",direct_params:{mode:"greeting"}},
    parameter_extraction:{extraction_prompt:"",required_fields:[],optional_fields:[]},
    permissions:{scenarios:["customer_bot","internal_assistant"],min_level:"L0"} },
  {
    intent_id:"faq_question", name:"產品FAQ查詢", description:"詢問產品/服務的一般性問題",
    enabled:true, priority:90,
    stage1:{keywords:["什麼是","有什麼","怎麼用","多少錢","價格","費用","介紹","說明","服務","產品"],match_mode:"any"},
    stage2:{classification_prompt:"使用者想了解產品或服務的基本資訊，非訂購意圖",few_shot_examples:[
      {role:"user",content:"你們的產品有哪些"},{role:"assistant",content:'{"intent":"faq_question","confidence":0.95}'}]},
    target:{type:"skill",skill_name:"knowledge_agent",direct_params:{}},
    parameter_extraction:{extraction_prompt:"提取產品或主題關鍵字(topic)",required_fields:["topic"],optional_fields:[]},
    permissions:{scenarios:["customer_bot","internal_assistant"],min_level:"L0"} },
  {
    intent_id:"timeline_query", name:"客戶互動歷程查詢", description:"查詢客戶的互動歷史記錄",
    enabled:true, priority:80,
    stage1:{keywords:["歷程","互動記錄","歷史","活動記錄","timeline","Timeline"],match_mode:"any"},
    stage2:{classification_prompt:"使用者想查看客戶的互動時間線或歷史活動",few_shot_examples:[]},
    target:{type:"skill",skill_name:"timeline_engine",direct_params:{action:"query",level:"{permission_level}"}},
    parameter_extraction:{extraction_prompt:"（客戶端：自動綁定本人 LINE ID，無需提取）提取客戶名稱(customer_name)或客戶編號(customer_id) — 限內部使用",required_fields:[],optional_fields:["customer_name","customer_id"]},
    permissions:{scenarios:["customer_bot","internal_assistant"],min_level:"L0"} },
  {
    intent_id:"confidential_q", name:"機密問題拒答", description:"客戶詢問報價金額、成本、合約細節等機密資訊",
    enabled:true, priority:100,
    stage1:{keywords:["多少錢","報價","金額","成本","合約","價格","費用","利潤","折扣"],match_mode:"any"},
    stage2:{classification_prompt:"使用者詢問涉及商業機密的具體數字或合約細節，必須委婉拒答。同時觸發 BusinessNotificationSkill 通知業務",few_shot_examples:[]},
    target:{type:"direct_answer",response_template:"感謝您的詢問，關於{{topic}}的詳細資訊，已通知業務同仁直接與您聯繫說明。"},
    parameter_extraction:{extraction_prompt:"提取客戶詢問的主題(topic)",required_fields:["topic"],optional_fields:[]},
    permissions:{scenarios:["customer_bot"],min_level:"L0"} },
  {
    intent_id:"business_card", name:"名片掃描（客戶）", description:"客戶傳送名片圖片要求掃描",
    enabled:true, priority:85,
    stage1:{keywords:[],match_mode:"any"},
    stage2:{classification_prompt:"使用者傳送了一張名片或聯絡資訊卡片的圖片",few_shot_examples:[]},
    target:{type:"skill",skill_name:"image_processor",direct_params:{mode:"business_card"}},
    parameter_extraction:{extraction_prompt:"",required_fields:[],optional_fields:[]},
    permissions:{scenarios:["customer_bot"],min_level:"L0"} },
  // ═══ 場景二：內部工作助理 ═══
  {
    intent_id:"erp_query", name:"ERP資料查詢", description:"查詢ERP中的報價、訂單、出貨、退貨記錄",
    enabled:true, priority:75,
    stage1:{keywords:["ERP","報價單","訂單","出貨","退貨","查詢訂單","銷貨","應收","帳款"],match_mode:"any"},
    stage2:{classification_prompt:"使用者想查詢ERP後台的業務資料（訂單、報價、出貨等），透過 Data Agent NL2SQL 查詢",few_shot_examples:[]},
    target:{type:"skill",skill_name:"data_agent",direct_params:{}},
    parameter_extraction:{extraction_prompt:"提取查詢條件：客戶名稱(customer_name)、單號(doc_number)、日期範圍(date_from,date_to)",required_fields:[],optional_fields:["customer_name","doc_number","date_from","date_to"]},
    permissions:{scenarios:["internal_assistant"],min_level:"L2"} },
  {
    intent_id:"crm_query", name:"CRM客戶查詢", description:"查詢CRM中的客戶詳情、聯絡人資訊",
    enabled:true, priority:74,
    stage1:{keywords:["客戶資料","聯絡人","電話","地址","查客戶","客戶詳情"],match_mode:"any"},
    stage2:{classification_prompt:"使用者想查詢CRM系統中的客戶基本資料或聯絡人資訊",few_shot_examples:[]},
    target:{type:"skill",skill_name:"data_agent",direct_params:{}},
    parameter_extraction:{extraction_prompt:"提取客戶名稱(customer_name)或電話(phone)",required_fields:["customer_name"],optional_fields:["phone"]},
    permissions:{scenarios:["internal_assistant"],min_level:"L1"} },
  {
    intent_id:"greeting_customer", name:"代理客戶問候", description:"代替業務傳送個人化問候給指定客戶",
    enabled:true, priority:73,
    stage1:{keywords:["代發問候","幫我問候","發送祝福","發早安","代傳","問候客戶"],match_mode:"any"},
    stage2:{classification_prompt:"使用者想代替系統發送個人化問候給特定客戶，需查CRM職稱決定尊稱",few_shot_examples:[]},
    target:{type:"skill",skill_name:"greeting_engine",direct_params:{greeting_type:"auto"}},
    parameter_extraction:{extraction_prompt:"提取目標客戶名稱(customer_name)和問候類型(greeting_type: morning/holiday/birthday)",required_fields:["customer_name"],optional_fields:["greeting_type"]},
    permissions:{scenarios:["internal_assistant"],min_level:"L1"} },
  {
    intent_id:"broadcast", name:"群發訊息", description:"群發公告或促銷訊息給客戶",
    enabled:true, priority:72,
    stage1:{keywords:["群發","廣播","公告","通知全部","發給所有","全體客戶","broadcast"],match_mode:"any"},
    stage2:{classification_prompt:"使用者想一次發送訊息給多個客戶（群發、廣播）",few_shot_examples:[]},
    target:{type:"skill",skill_name:"push_engine",direct_params:{action:"create_task"}},
    parameter_extraction:{extraction_prompt:"提取群發內容(content)、目標對象(target_group: all/vip/region)",required_fields:["content"],optional_fields:["target_group"]},
    permissions:{scenarios:["internal_assistant"],min_level:"L2"} },
  {
    intent_id:"schedule_visit", name:"行程安排", description:"安排客戶拜訪行程、估路程、設提醒",
    enabled:true, priority:71,
    stage1:{keywords:["安排拜訪","預約行程","約客戶","拜訪計劃","安排時間","排行程"],match_mode:"any"},
    stage2:{classification_prompt:"使用者想安排或查詢客戶拜訪行程",few_shot_examples:[]},
    target:{type:"direct_answer",response_template:"已記錄{{customer_name}}的拜訪行程（{{visit_date}}），屆時將自動提醒。"},
    parameter_extraction:{extraction_prompt:"提取客戶名稱(customer_name)、日期(visit_date)、地點(location)",required_fields:["customer_name","visit_date"],optional_fields:["location"]},
    permissions:{scenarios:["internal_assistant"],min_level:"L1"} },
  {
    intent_id:"business_card_internal", name:"名片掃描（內部）", description:"業務人員傳送名片圖片直接寫入CRM",
    enabled:true, priority:70,
    stage1:{keywords:[],match_mode:"any"},
    stage2:{classification_prompt:"業務人員傳送了一張名片圖片，需要直接寫入CRM聯絡人",few_shot_examples:[]},
    target:{type:"skill",skill_name:"image_processor",direct_params:{mode:"business_card"}},
    parameter_extraction:{extraction_prompt:"",required_fields:[],optional_fields:[]},
    permissions:{scenarios:["internal_assistant"],min_level:"L1"} },
];

export default function IntentRoutingEditor() {
  const { message } = App.useApp();
  const contentTokens = useContentTokens();

  const [data, setData] = useState<IntentRoutingData>({ rules: DEFAULT_RULES, model: 'qwen3', fallback: 'general_chat' });
  const [saving, setSaving] = useState(false);

  // 啟動時從 system_params 載入（若已有資料則取代預設值）
  useEffect(() => {
    (async () => {
      try {
        const res = await paramsApi.get('welfare.intent.routing.rules');
        const raw = res?.data?.data?.param_value;
        if (raw) {
          const parsed = JSON.parse(raw);
          const model = parsed.model || 'qwen3';
          const fallback = parsed.fallback || 'general_chat';
          const rules = parsed.rules || parsed;
          setData({ rules, model, fallback });
        }
      } catch {
        // 不存在則用預設值
      }
    })();
  }, []);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<IntentRoute | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [form] = Form.useForm();

  /* ─── CRUD ─────────────────────────────────── */

  const openCreate = () => {
    setEditing(EMPTY_INTENT);
    setEditingIndex(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (record: IntentRoute, index: number) => {
    setEditing(record);
    setEditingIndex(index);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleDelete = (index: number) => {
    const next = [...data.rules];
    next.splice(index, 1);
    setData(prev => ({ ...prev, rules: next }));
    message.success('已刪除');
  };

  const handleSave = () => {
    form.validateFields().then(values => {
      const route: IntentRoute = {
        intent_id: values.intent_id,
        name: values.name,
        description: values.description || '',
        enabled: values.enabled ?? true,
        priority: values.priority ?? 50,
        stage1: {
          keywords: values.stage1_keywords || [],
          match_mode: values.stage1_match_mode || 'any',
        },
        stage2: {
          classification_prompt: values.classification_prompt || '',
          few_shot_examples: [],
        },
        target: {
          type: values.target_type || 'skill',
          skill_name: values.target_type === 'skill' ? values.skill_name : undefined,
          response_template: values.target_type === 'direct_answer' ? values.response_template : undefined,
          direct_params: {},
        },
        parameter_extraction: {
          extraction_prompt: values.extraction_prompt || '',
          required_fields: values.required_fields || [],
          optional_fields: values.optional_fields || [],
        },
        permissions: {
          scenarios: values.scenarios || ['customer_bot'],
          min_level: values.min_level || 'L0',
        },
      };

      const next = [...data.rules];
      if (editingIndex !== null) {
        next[editingIndex] = route;
      } else {
        next.push(route);
      }
      setData(prev => ({ ...prev, rules: next }));
      setModalOpen(false);
      message.success(editingIndex !== null ? '已更新' : '已新增');
    });
  };

  /* ─── Columns ───────────────────────────────── */

  const columns = [
    {
      title: '', dataIndex: 'enabled', key: 'enabled', width: 48,
      render: (v: boolean, _: IntentRoute, i: number) => (
        <Switch size="small" checked={v} onChange={c => {
          const next = [...data.rules];
          next[i] = { ...next[i], enabled: c };
          setData(prev => ({ ...prev, rules: next }));
        }} />
      ),
    },
    { title: 'ID', dataIndex: 'intent_id', key: 'intent_id', width: 120,
      render: (v: string) => <Text code style={{ fontSize: 11 }}>{v}</Text>,
    },
    { title: '名稱', dataIndex: 'name', key: 'name', width: 120,
      render: (v: string, r: IntentRoute) => (
        <Tooltip title={r.description}><Text style={{ fontSize: 12 }}>{v}</Text></Tooltip>
      ),
    },
    { title: '優先級', dataIndex: 'priority', key: 'priority', width: 72,
      render: (v: number) => <Tag>{v}</Tag>,
    },
    { title: '場景', key: 'scenarios', width: 80,
      render: (_: unknown, r: IntentRoute) => <ScenarioBadge scenarios={r.permissions.scenarios} />,
    },
    { title: '目標', key: 'target', width: 120,
      render: (_: unknown, r: IntentRoute) => (
        <Text style={{ fontSize: 11 }}>{r.target.skill_name || r.target.response_template?.slice(0, 20) || '-'}</Text>
      ),
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: unknown, __: IntentRoute, i: number) => (
        <Space size={0}>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEdit(data.rules[i], i)} />
          <Button size="small" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(i)} />
        </Space>
      ),
    },
  ];

  /* ─── Render ─────────────────────────────────── */

  return (
    <div>
      {/* LLM 設定列 */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16,
        padding: '12px 16px', background: contentTokens.contentBg, borderRadius: 8, border: '1px solid #f0f0f0' }}>
        <Text strong style={{ fontSize: 13, whiteSpace: 'nowrap' }}>⚙️ LLM 設定</Text>
        <span style={{ fontSize: 12, color: '#888' }}>模型：</span>
        <Select value={data.model} onChange={v => setData(prev => ({ ...prev, model: v }))}
          size="small" style={{ width: 140 }}
          options={[{ label: 'qwen3', value: 'qwen3' }, { label: 'gpt-4o', value: 'gpt-4o' }]} />
        <span style={{ fontSize: 12, color: '#888' }}>Fallback：</span>
        <Select value={data.fallback} onChange={v => setData(prev => ({ ...prev, fallback: v }))}
          size="small" style={{ width: 180 }}
          options={[{ label: 'LLM 直接回覆 (general_chat)', value: 'general_chat' },
                    { label: '安全拒絕 (safe_reject)', value: 'safe_reject' }]} />
        <Alert type="info" showIcon style={{ fontSize: 11, padding: '4px 8px', margin: 0, flex: 1 }}
          message="變更後須點擊下方「儲存至系統」才生效" />
      </div>

      {/* 意圖列表 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Text strong style={{ fontSize: 14 }}>意圖列表（{data.rules.length}）</Text>
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增意圖</Button>
      </div>

      <Table
        dataSource={data.rules.map((r, i) => ({ ...r, _index: i }))}
        columns={columns}
        rowKey="_index"
        pagination={false}
        size="middle"
        scroll={{ x: 700 }}
      />

      {/* 儲存按鈕 */}
      <div style={{ marginTop: 16, textAlign: 'right' }}>
        <Button type="primary" loading={saving} onClick={async () => {
          setSaving(true);
          try {
            const payload = JSON.stringify({
              rules: data.rules,
              model: data.model,
              fallback: data.fallback,
            });
            await paramsApi.update('welfare.intent.routing.rules', payload);
            message.success('路由表已寫入 system_params');
          } catch (e: any) {
            message.error(e?.response?.data?.message || '儲存失敗');
          } finally {
            setSaving(false);
          }
        }}>儲存至系統</Button>
      </div>

      {/* ─── Edit Modal ───────────────────────── */}
      <Modal
        title={editingIndex !== null ? '編輯意圖' : '新增意圖'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        okText="儲存"
        width={700}
      >
        <Form form={form} layout="vertical" size="small" initialValues={editing || EMPTY_INTENT}>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="enabled" label="啟用" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="intent_id" label="ID" rules={[{ required: true, message: '必填' }]} style={{ flex: 1 }}>
              <Input placeholder="greeting" disabled={editingIndex !== null} />
            </Form.Item>
            <Form.Item name="name" label="名稱" rules={[{ required: true, message: '必填' }]} style={{ flex: 2 }}>
              <Input placeholder="客戶問候" />
            </Form.Item>
          </div>

          <Form.Item name="description" label="說明">
            <Input.TextArea rows={1} placeholder="客戶打招呼、早安、節日祝福等" />
          </Form.Item>

          <Form.Item name="priority" label="優先級">
            <Slider min={1} max={100} marks={{ 1: '1', 50: '50', 100: '100' }} />
          </Form.Item>

          <Alert message="Stage 1：關鍵詞比對（零成本，命中直接路由）" type="info" showIcon style={{ marginBottom: 8, fontSize: 11, padding: '4px 8px' }} />
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="stage1_keywords" label="關鍵詞" style={{ flex: 1 }}>
              <Select mode="tags" placeholder="輸入後 Enter" open={false} />
            </Form.Item>
            <Form.Item name="stage1_match_mode" label="比對模式">
              <Select options={MATCH_MODE_OPTIONS} style={{ width: 140 }} />
            </Form.Item>
          </div>

          <Alert message="Stage 2：LLM 分類提示（Stage 1 未命中時使用）" type="info" showIcon style={{ marginBottom: 8, fontSize: 11, padding: '4px 8px' }} />
          <Form.Item name="classification_prompt" label="分類提示">
            <Input.TextArea rows={2} placeholder="使用者正在打招呼，語氣友善，無特定業務需求" />
          </Form.Item>

          <Alert message="目標設定" type="info" showIcon style={{ marginBottom: 8, fontSize: 11, padding: '4px 8px' }} />
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="target_type" label="類型" initialValue="skill">
              <Select options={TARGET_TYPE_OPTIONS} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, cur) => prev.target_type !== cur.target_type}>
              {({ getFieldValue }) => {
                const type = getFieldValue('target_type');
                return type === 'skill' ? (
                  <Form.Item name="skill_name" label="Skill 名稱" style={{ flex: 1 }} rules={[{ required: true }]}>
                    <Select options={[
                      { label: 'greeting_engine', value: 'greeting_engine' },
                      { label: 'image_processor', value: 'image_processor' },
                      { label: 'timeline_engine', value: 'timeline_engine' },
                      { label: 'knowledge_agent', value: 'knowledge_agent' },
                      { label: 'data_agent', value: 'data_agent' },
                      { label: 'ragic_timeline_poller', value: 'ragic_timeline_poller' },
                      { label: 'push_engine', value: 'push_engine' },
                    ]} />
                  </Form.Item>
                ) : (
                  <Form.Item name="response_template" label="回覆模板" style={{ flex: 1 }} rules={[{ required: true }]}>
                    <Input placeholder="感謝您的詢問，關於{{topic}}..." />
                  </Form.Item>
                );
              }}
            </Form.Item>
          </div>

          <Alert message="參數提取（選填，從對話中提取 skill 需要的參數）" type="info" showIcon style={{ marginBottom: 8, fontSize: 11, padding: '4px 8px' }} />
          <Form.Item name="extraction_prompt" label="提取提示">
            <Input.TextArea rows={1} placeholder="提取客戶名稱(customer_name)或客戶編號(customer_id)" />
          </Form.Item>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="required_fields" label="必填欄位" style={{ flex: 1 }}>
              <Select mode="tags" placeholder="輸入後 Enter" open={false} />
            </Form.Item>
            <Form.Item name="optional_fields" label="選填欄位" style={{ flex: 1 }}>
              <Select mode="tags" placeholder="輸入後 Enter" open={false} />
            </Form.Item>
          </div>

          <Alert message="權限控制" type="warning" showIcon style={{ marginBottom: 8, fontSize: 11, padding: '4px 8px' }} />
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="scenarios" label="適用場景">
              <Select mode="multiple" options={SCENARIO_OPTIONS} style={{ width: 240 }} />
            </Form.Item>
            <Form.Item name="min_level" label="最低等級">
              <Select options={LEVEL_OPTIONS} style={{ width: 100 }} />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
