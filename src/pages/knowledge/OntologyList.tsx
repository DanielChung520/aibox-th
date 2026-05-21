/**
 * @file        知識本體列表頁面
 * @description 知識管理 - 三層式知識本體 (Basic/Domain/Major) 兩層展開式瀏覽、匯入與管理
 * @lastUpdate  2026-03-25 12:21:13
 * @author      Daniel Chung
 * @version     4.0.0
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import { Table, Button, Space, Modal, Tag, Input, Upload, Popconfirm, App, Descriptions, Form, Tabs } from 'antd';
import { ImportOutlined, DeleteOutlined, SettingOutlined, PlusOutlined, SaveOutlined, NodeIndexOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { Ontology, OntologyLayer, ontologyApi } from '../../services/api';
import { useContentTokens } from '../../contexts/AppThemeProvider';
import OntologyGraphViewer from './components/OntologyGraphViewer';
import { useEntityPerception } from '../../hooks/useEntityPerception';
import { pageContextManager } from '../../services/PageContextManager';

interface Basic5W1HItem {
  key: string;
  dimension: string;
  label: string;
  extractionIntent: string;
}

const DIMENSION_DEFAULT_LABEL: Record<string, string> = {
  Who: '人物 / 組織', What: '事物 / 概念', When: '時間 / 週期',
  Where: '地點 / 空間', Why: '原因 / 目的', How: '方法 / 流程',
};

export default function OntologyList() {
  const [ontologies, setOntologies] = useState<Ontology[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [basicModalVisible, setBasicModalVisible] = useState(false);
  const [basicItems, setBasicItems] = useState<Basic5W1HItem[]>([]);
  const [basicLoading, setBasicLoading] = useState(false);
  const [basicSaving, setBasicSaving] = useState(false);
  const basicOntologyKey = 'basic_5w1h';
  const [previewModalVisible, setPreviewModalVisible] = useState(false);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [selectedOntology, setSelectedOntology] = useState<Ontology | null>(null);
  const [importParentDomain, setImportParentDomain] = useState<Ontology | null>(null);
  const [parsedImportData, setParsedImportData] = useState<Partial<Ontology> | null>(null);
  const [importForm] = Form.useForm();
  
  const { message } = App.useApp();
  const tokens = useContentTokens();
  const { dispatchEntity } = useEntityPerception({ defaultEntityType: 'ontology', defaultAction: 'list' });
  void dispatchEntity; // Reserved for future event handler use

  useEffect(() => {
    pageContextManager.report({ component: 'OntologyList', entityType: 'ontology', action: 'list' });
    return () => { pageContextManager.report({ component: undefined, entityType: undefined, action: undefined }); };
  }, []);

  const loadOntologies = useCallback(async () => {
    setLoading(true);
    try {
      const res = await ontologyApi.list();
      setOntologies((res.data.data || []).filter(o => o.type !== 'basic'));
    } catch {
      message.error('載入知識本體列表失敗');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => { loadOntologies(); }, [loadOntologies]);

  // Filters
  const domains = useMemo(() => ontologies.filter(o => o.type === 'domain'), [ontologies]);
  const majors = useMemo(() => ontologies.filter(o => o.type === 'major'), [ontologies]);

  const filteredData = useMemo(() => {
    if (!searchText) return domains;
    const lowerSearch = searchText.toLowerCase();
    
    // Find matching majors
    const matchingMajors = majors.filter(m => 
      m.name.toLowerCase().includes(lowerSearch) || 
      m.ontology_name.toLowerCase().includes(lowerSearch) || 
      m.description.toLowerCase().includes(lowerSearch)
    );

    // Filter domains based on text OR if they have a matching major
    return domains.filter(d => {
      const matchSelf = d.name.toLowerCase().includes(lowerSearch) || 
                        d.ontology_name.toLowerCase().includes(lowerSearch) || 
                        d.description.toLowerCase().includes(lowerSearch);
      
      const hasMatchingMajor = matchingMajors.some(m => 
        m.inherits_from.includes(d.ontology_name) || m.metadata?.domain === d.name
      );

      return matchSelf || hasMatchingMajor;
    });
  }, [domains, majors, searchText]);

  // --- Basic 5W1H API ---
  const loadBasic5W1H = useCallback(async () => {
    setBasicLoading(true);
    try {
      const res = await ontologyApi.get(basicOntologyKey);
      const ont = res.data.data;
      const items: Basic5W1HItem[] = (ont.entity_classes || []).map((ec) => ({
        key: ec.name.toLowerCase(),
        dimension: ec.name,
        label: ec.base_class === 'Dimension' ? (DIMENSION_DEFAULT_LABEL[ec.name] || ec.name) : ec.base_class,
        extractionIntent: ec.description,
      }));
      setBasicItems(items);
    } catch {
      message.error('載入 Basic 5W1H 設定失敗');
    } finally {
      setBasicLoading(false);
    }
  }, [basicOntologyKey, message]);

  const handleBasicSave = async () => {
    const emptyDimension = basicItems.some(item => !item.dimension.trim());
    if (emptyDimension) {
      message.warning('維度名稱不可為空');
      return;
    }
    setBasicSaving(true);
    try {
      const entity_classes = basicItems.map((item) => ({
        name: item.dimension.trim(),
        base_class: item.label.trim(),
        description: item.extractionIntent.trim(),
      }));
      await ontologyApi.update(basicOntologyKey, { entity_classes });
      message.success('Basic 5W1H 設定已儲存');
    } catch {
      message.error('儲存失敗');
    } finally {
      setBasicSaving(false);
    }
  };

  const handleBasicFieldChange = (key: string, field: 'dimension' | 'label' | 'extractionIntent', value: string) => {
    setBasicItems(prev => prev.map(item => item.key === key ? { ...item, [field]: value } : item));
  };

  const handleBasicAdd = () => {
    const newKey = `dim_${Date.now()}`;
    setBasicItems(prev => [...prev, { key: newKey, dimension: '', label: '', extractionIntent: '' }]);
  };

  const handleBasicDelete = (key: string) => {
    setBasicItems(prev => prev.filter(item => item.key !== key));
  };

  const handleOpenBasicModal = () => {
    loadBasic5W1H();
    setBasicModalVisible(true);
  };

  // Handlers
  const handleDelete = async (record: Ontology) => {
    try {
      await ontologyApi.delete(record._key);
      message.success('刪除成功');
      loadOntologies();
    } catch (error: any) {
      const msg = error.response?.data?.message || '刪除失敗';
      message.error(msg);
    }
  };

  const handleImportOpen = (parentDomain?: Ontology) => {
    setImportParentDomain(parentDomain || null);
    setParsedImportData(null);
    importForm.resetFields();
    setImportModalVisible(true);
  };

  const handleImportConfirm = async () => {
    try {
      const values = await importForm.validateFields();
      if (parsedImportData) {
        const payload = { ...parsedImportData, ...values };
        await ontologyApi.importOntology(payload);
        message.success('匯入成功');
        setImportModalVisible(false);
        loadOntologies();
      }
    } catch (error: any) {
      if (error.response?.data?.message) {
        message.error(error.response.data.message);
      }
    }
  };

  const importUploadProps: UploadProps = {
    accept: '.json,application/json',
    showUploadList: false,
    beforeUpload: (file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const content = e.target?.result as string;
          const parsed = JSON.parse(content) as Ontology;
          
          if (!parsed.entity_classes || !parsed.object_properties || !Array.isArray(parsed.entity_classes) || !Array.isArray(parsed.object_properties)) {
            message.error('JSON 格式錯誤: 缺少必要欄位 (entity_classes, object_properties 需為陣列)');
            return;
          }

          if (importParentDomain) {
            parsed.type = 'major';
            parsed.inherits_from = parsed.inherits_from || [];
            if (!parsed.inherits_from.includes(importParentDomain.ontology_name)) {
              parsed.inherits_from.push(importParentDomain.ontology_name);
            }
            parsed.metadata = parsed.metadata || {};
            parsed.metadata.domain = importParentDomain.name;
          } else {
            parsed.type = 'domain';
          }

          setParsedImportData(parsed);
          importForm.setFieldsValue({
            name: parsed.name,
            ontology_name: parsed.ontology_name,
            description: parsed.description,
            version: parsed.version
          });
        } catch (error) {
          message.error('無法解析 JSON 檔案');
        }
      };
      reader.readAsText(file);
      return false; 
    }
  };

  // Renderers
  const getTagColor = (type: OntologyLayer) => {
    switch (type) {
      case 'basic': return 'blue';
      case 'domain': return 'green';
      case 'major': return 'orange';
      default: return 'default';
    }
  };

  const sharedColumns = [
    {
      title: '名稱',
      key: 'name',
      render: (_: any, record: Ontology) => (
        <div>
          <div style={{ fontWeight: 600, color: tokens.colorPrimary }}>{record.ontology_name}</div>
          <div style={{ fontSize: 12, color: tokens.textSecondary }}>{record.name}</div>
        </div>
      )
    },
    {
      title: '說明',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => (
        <div style={{ maxWidth: 300, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={text}>
          {text}
        </div>
      )
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80
    },
    {
      title: '標籤',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[] = []) => (
        <Space size={[0, 4]} wrap>
          {tags.slice(0, 3).map(tag => <Tag key={tag} color="processing">{tag}</Tag>)}
          {tags.length > 3 && <Tag>+{tags.length - 3}</Tag>}
        </Space>
      )
    },
    {
      title: '實體數',
      key: 'entities',
      width: 80,
      render: (_: any, record: Ontology) => record.entity_classes?.length || 0
    },
    {
      title: '關係數',
      key: 'properties',
      width: 80,
      render: (_: any, record: Ontology) => record.object_properties?.length || 0
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
        render: (_: any, record: Ontology) => (
        <Space>
          <Button type="link" icon={<NodeIndexOutlined />} onClick={() => { setSelectedOntology(record); setPreviewModalVisible(true); }}>圖譜視圖</Button>
          {record.type === 'domain' && (
            <Button type="link" icon={<PlusOutlined />} onClick={() => handleImportOpen(record)}>匯入 Major</Button>
          )}
          {record.type !== 'basic' && (
            <Popconfirm title="確定刪除此知識本體嗎？" onConfirm={() => handleDelete(record)}>
              <Button type="link" danger icon={<DeleteOutlined />}>刪除</Button>
            </Popconfirm>
          )}
        </Space>
      )
    }
  ];

  const expandedRowRender = (domainRecord: Ontology) => {
    const childMajors = majors.filter(m => 
      m.inherits_from.includes(domainRecord.ontology_name) || 
      m.metadata?.domain === domainRecord.name
    );
    
    const filteredChildMajors = searchText 
      ? childMajors.filter(m => 
          m.name.toLowerCase().includes(searchText.toLowerCase()) || 
          m.ontology_name.toLowerCase().includes(searchText.toLowerCase()) || 
          m.description.toLowerCase().includes(searchText.toLowerCase())
        )
      : childMajors;

    if (childMajors.length === 0) return <div style={{ padding: '8px 16px', color: tokens.textSecondary }}>無專業知識本體</div>;

    return (
      <div style={{ padding: '12px 16px', background: tokens.tableExpandedRowBg }}>
        <Table 
          columns={sharedColumns} 
          dataSource={filteredChildMajors} 
          rowKey="_key" 
          pagination={false} 
          showHeader={false}
          size="small"
        />
        <div style={{ marginTop: 8 }}>
          <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => handleImportOpen(domainRecord)}>
            匯入 Major Ontology
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div style={{ padding: 24, background: tokens.contentBg, minHeight: '100%', borderRadius: tokens.borderRadius }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Input.Search 
          placeholder="搜尋知識領域..." 
          style={{ width: 300 }} 
          allowClear 
          onChange={(e) => setSearchText(e.target.value)} 
        />
        <Space>
          <Button icon={<SettingOutlined />} onClick={handleOpenBasicModal}>Basic 5W1H 設定</Button>
          <Button type="primary" icon={<ImportOutlined />} onClick={() => handleImportOpen()}>匯入 Domain</Button>
        </Space>
      </div>

      <Table
        columns={sharedColumns}
        dataSource={filteredData}
        rowKey="_key"
        expandable={{ expandedRowRender, expandRowByClick: false }}
        pagination={{ pageSize: 20 }}
        loading={loading}
      />

      {/* Basic 5W1H Modal — 可編輯 label / extractionIntent */}
      <Modal
        title="Basic 5W1H 設定"
        open={basicModalVisible}
        onCancel={() => setBasicModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setBasicModalVisible(false)}>取消</Button>,
          <Button key="save" type="primary" icon={<SaveOutlined />} loading={basicSaving} onClick={handleBasicSave}>儲存</Button>,
        ]}
        width={800}
      >
        <p style={{ color: tokens.textSecondary, marginBottom: 16 }}>
          基礎抽取維度定義，用於知識文件上傳時的 NER / RE / RT 管線指導。可編輯分類名稱與抽取意圖說明。
        </p>
        <Table
          columns={[
            { title: '維度', dataIndex: 'dimension', key: 'dimension', width: 100,
              render: (_: string, record: Basic5W1HItem) => (
                <Input value={record.dimension} onChange={e => handleBasicFieldChange(record.key, 'dimension', e.target.value)}
                  size="small" placeholder="維度名稱" />
              ) },
            { title: '分類', dataIndex: 'label', key: 'label', width: 140,
              render: (_: string, record: Basic5W1HItem) => (
                <Input value={record.label} onChange={e => handleBasicFieldChange(record.key, 'label', e.target.value)} size="small" placeholder="分類標籤" />
              ) },
            { title: '抽取意圖說明', dataIndex: 'extractionIntent', key: 'extractionIntent',
              render: (_: string, record: Basic5W1HItem) => (
                <Input.TextArea value={record.extractionIntent} onChange={e => handleBasicFieldChange(record.key, 'extractionIntent', e.target.value)}
                  autoSize={{ minRows: 1, maxRows: 3 }} size="small" placeholder="描述此維度的抽取意圖" />
              ) },
            { title: '', key: 'action', width: 50, align: 'center' as const,
              render: (_: unknown, record: Basic5W1HItem) => (
                <Popconfirm title="確定刪除此維度？" onConfirm={() => handleBasicDelete(record.key)} okText="刪除" cancelText="取消">
                  <Button type="text" danger icon={<DeleteOutlined />} size="small" />
                </Popconfirm>
              ) },
          ]}
          dataSource={basicItems}
          rowKey="key"
          pagination={false}
          size="small"
          loading={basicLoading}
        />
        <Button type="dashed" icon={<PlusOutlined />} onClick={handleBasicAdd} block style={{ marginTop: 12 }}>
          新增維度
        </Button>
      </Modal>

      {/* Import Modal */}
      <Modal
        title={importParentDomain ? `匯入 Major — ${importParentDomain.name}` : '匯入 Domain Ontology'}
        open={importModalVisible}
        onCancel={() => setImportModalVisible(false)}
        footer={
          parsedImportData ? (
            <Space>
              <Button onClick={() => setParsedImportData(null)}>返回</Button>
              <Button type="primary" onClick={handleImportConfirm}>確認匯入</Button>
            </Space>
          ) : null
        }
      >
        {!parsedImportData ? (
          <Upload.Dragger {...importUploadProps}>
            <p className="ant-upload-drag-icon"><ImportOutlined style={{ fontSize: 32, color: tokens.colorPrimary }} /></p>
            <p className="ant-upload-text">點擊或拖曳 JSON 檔案至此</p>
            <p className="ant-upload-hint">支援匯入 {importParentDomain ? 'Major' : 'Domain'} 類型的知識本體 JSON 檔案</p>
          </Upload.Dragger>
        ) : (
          <Form form={importForm} layout="vertical">
            <Form.Item label="匯入類型">
              <Tag color={importParentDomain ? 'orange' : 'green'}>
                {importParentDomain ? 'Major' : 'Domain'}
              </Tag>
            </Form.Item>
            {importParentDomain && (
              <Form.Item label="所屬領域">
                <Input value={importParentDomain.name} disabled />
              </Form.Item>
            )}
            <Form.Item label="名稱" name="name" rules={[{ required: true, message: '請輸入名稱' }]}>
              <Input />
            </Form.Item>
            <Form.Item label="本體名稱" name="ontology_name" rules={[{ required: true, message: '請輸入本體名稱' }]}>
              <Input />
            </Form.Item>
            <Form.Item label="說明" name="description">
              <Input.TextArea rows={3} />
            </Form.Item>
            <Form.Item label="版本" name="version" rules={[{ required: true, message: '請輸入版本' }]}>
              <Input />
            </Form.Item>
            <div style={{ marginTop: 16, color: tokens.textSecondary, fontSize: 12 }}>
              包含 {parsedImportData.entity_classes?.length || 0} 個實體類型、{parsedImportData.object_properties?.length || 0} 個關係類型
            </div>
          </Form>
        )}
      </Modal>

      {/* Preview Modal */}
      <Modal
        title={`圖譜視圖 — ${selectedOntology?.ontology_name || ''}`}
        open={previewModalVisible}
        onCancel={() => setPreviewModalVisible(false)}
        footer={null}
        width="95vw"
        styles={{ body: { padding: 0, maxHeight: '90vh', overflow: 'hidden' } }}
      >
        {selectedOntology && (
          <div style={{ display: 'grid', gridTemplateColumns: '25% 1fr', height: '100%' }}>
            <div style={{ display: 'flex', flexDirection: 'column', borderRight: '1px solid #e2e8f0', overflow: 'hidden' }}>
              <div style={{ flexShrink: 0, borderBottom: '1px solid #e2e8f0', padding: 12, overflow: 'auto', maxHeight: '40%' }}>
                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label="名稱">
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{selectedOntology.ontology_name}</span>
                  </Descriptions.Item>
                  <Descriptions.Item label="顯示名">{selectedOntology.name}</Descriptions.Item>
                  <Descriptions.Item label="類型">
                    <Tag color={getTagColor(selectedOntology.type)} style={{ fontSize: 11 }}>{selectedOntology.type.toUpperCase()}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="版本">{selectedOntology.version}</Descriptions.Item>
                  <Descriptions.Item label="作者">{selectedOntology.author}</Descriptions.Item>
                  <Descriptions.Item label="實體數">{selectedOntology.entity_classes?.length || 0}</Descriptions.Item>
                  <Descriptions.Item label="關係數">{selectedOntology.object_properties?.length || 0}</Descriptions.Item>
                  <Descriptions.Item label="繼承自">
                    {selectedOntology.inherits_from?.length
                      ? selectedOntology.inherits_from.map(i => <Tag key={i} style={{ fontSize: 10 }}>{i}</Tag>)
                      : '-'}
                  </Descriptions.Item>
                </Descriptions>
              </div>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <Tabs
                  defaultActiveKey="entities"
                  size="small"
                  style={{ height: '100%' }}
                  items={[
                    {
                      key: 'entities',
                      label: `實體 (${selectedOntology.entity_classes?.length || 0})`,
                      children: (
                        <div style={{ overflow: 'auto', height: '100%' }}>
                          <Table
                            columns={[
                              { title: '名稱', dataIndex: 'name', key: 'name', width: 120 },
                              { title: '類別', dataIndex: 'base_class', key: 'base_class', width: 80 },
                              { title: '說明', dataIndex: 'description', key: 'description' },
                            ]}
                            dataSource={selectedOntology.entity_classes}
                            rowKey="name"
                            pagination={{ pageSize: 10 }}
                            size="small"
                          />
                        </div>
                      ),
                    },
                    {
                      key: 'properties',
                      label: `關係 (${selectedOntology.object_properties?.length || 0})`,
                      children: (
                        <div style={{ overflow: 'auto', height: '100%' }}>
                          <Table
                            columns={[
                              { title: '名稱', dataIndex: 'name', key: 'name', width: 120 },
                              { title: '來源', dataIndex: 'domain', key: 'domain', width: 100 },
                              { title: '目標', dataIndex: 'range', key: 'range', width: 100 },
                            ]}
                            dataSource={selectedOntology.object_properties}
                            rowKey="name"
                            pagination={{ pageSize: 10 }}
                            size="small"
                          />
                        </div>
                      ),
                    },
                  ]}
                />
              </div>
            </div>
            <div style={{ overflow: 'hidden', height: '100%', border: '1px solid #cbd5e1', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.06)', margin: 4 }}>
              <OntologyGraphViewer ontology={selectedOntology} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
