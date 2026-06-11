/**
 * @file        DemandTab.tsx
 * @description 需求管理 Tab 元件，根據狀態 render 不同內容（草稿/已提交/開發中/待驗收/已上線）
 * @lastUpdate  2026-04-22 00:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Button, Space, Form, Input, Tag, Divider, App, InputNumber, Upload, Image, Modal, Alert, theme } from 'antd';
import type { Demand, DemandStatus, UploadedFile, AIReview } from '../services/api';
import { agentApi, demandApi } from '../services/api';
import { authStore } from '../stores/auth';
import { InboxOutlined, FileOutlined } from '@ant-design/icons';
import type { UploadProps, UploadFile } from 'antd/es/upload/interface';
import { trackDemandAction } from '../utils/analytics';

const SEAWEED_URL = import.meta.env.VITE_SEAWEED_URL || 'http://localhost:8888';
const SEAWEED_USER = import.meta.env.VITE_SEAWEED_USER || 'admin';
const SEAWEED_PASS = import.meta.env.VITE_SEAWEED_PASS || 'admin123';

interface DemandTabProps {
  agentKey: string;
  demandKey?: string | null;
  onStatusChange?: (color: string) => void;
  onDemandChange?: (demand: Demand | null) => void;
}

const statusConfig: Record<DemandStatus, { label: string; badgeColor: string; tagColor: string; icon: string }> = {
  draft: { label: '草稿', badgeColor: '#fa8c16', tagColor: 'orange', icon: '📝' },
  submitted: { label: '等待接單', badgeColor: '#1890ff', tagColor: 'blue', icon: '⏳' },
  accepted: { label: '已承接', badgeColor: '#13c2c2', tagColor: 'cyan', icon: '✅' },
  in_development: { label: '開發中', badgeColor: '#fa8c16', tagColor: 'orange', icon: '🔧' },
  pending_acceptance: { label: '待驗收', badgeColor: '#722ed1', tagColor: 'purple', icon: '⏳' },
  online: { label: '已上線', badgeColor: '#52c41a', tagColor: 'green', icon: '🎉' },
  cancelled: { label: '已取消', badgeColor: '#ff4d4f', tagColor: 'red', icon: '❌' },
};

export default function DemandTab({ agentKey, demandKey, onStatusChange, onDemandChange }: DemandTabProps) {
  const { message: antMessage } = App.useApp();
  const { token } = theme.useToken();
  const [demand, setDemand] = useState<Demand | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [aiReview, setAiReview] = useState<AIReview | null>(null);
  const [reviewModalVisible, setReviewModalVisible] = useState(false);
  const [form] = Form.useForm();
  const user = authStore.getState().user;

  useEffect(() => {
    if (demandKey) {
      loadDemand();
    }
  }, [demandKey]);

  const loadDemand = async () => {
    if (!demandKey) return;
    setLoading(true);
    try {
      const res = await agentApi.getDemand(agentKey, demandKey);
      const loadedDemand = res.data.data;
      setDemand(loadedDemand);
      form.setFieldsValue(loadedDemand);
      onDemandChange?.(loadedDemand);
    } catch {
      antMessage.error('載入需求失敗');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!demandKey) return;
    setSaving(true);
    try {
      const values = await form.validateFields();
      await agentApi.updateDemand(agentKey, demandKey, values);
      antMessage.success('草稿已保存');
      await loadDemand();
    } catch {
      antMessage.error('保存失敗');
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async () => {
    if (!demandKey) return;
    try {
      await form.validateFields();
    } catch {
      antMessage.error('請填寫必填欄位');
      return;
    }

    setReviewing(true);
    antMessage.loading({ content: '🤖 AI 審查中...請稍候', key: 'review', duration: 0 });

    try {
      const values = await form.getFieldsValue();
      const reviewRes = await demandApi.reviewDemand(values as Demand);
      const review = reviewRes.data.data;
      setAiReview(review);
      trackDemandAction('review', demandKey || '', demand?.goal, { score: review?.score });
      antMessage.destroy('review');
      setReviewModalVisible(true);
    } catch {
      antMessage.error('AI 審查失敗，請稍後再試');
    } finally {
      setReviewing(false);
    }
  };

  const handleConfirmSubmit = async () => {
    if (!demandKey || !aiReview) return;
    setSubmitting(true);
    setReviewModalVisible(false);
    try {
      const values = await form.getFieldsValue();
      await agentApi.updateDemand(agentKey, demandKey, values);
      await agentApi.updateDemandStatus(agentKey, demandKey, { status: 'submitted', ai_review: aiReview });
      
      // 建立 agent_requirements 記錄
      try {
        const agentRes = await agentApi.get(agentKey);
        const agentName = (agentRes.data as any)?.data?.name || (agentRes.data as any)?.name || agentKey;
        await fetch('/api/v1/agent-requirements', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authStore.getState().token}` },
          body: JSON.stringify({
            agent_key: agentKey,
            demand_key: demandKey,
            agent_name: agentName,
            account: user?.username || 'anonymous',
            version: demand?.version || 'v1.0',
            status: 'pending_accept',
            goal: values.goal,
            expected_effect: values.expected_effect,
            problem_description: values.problem_description,
            ai_review: aiReview,
            submitted_at: new Date().toISOString(),
          }),
        });
      } catch (e) { console.warn('Failed to create requirement record:', e); }
      
      trackDemandAction('submit', demandKey, demand?.goal);
      antMessage.success('需求已提交，等待團隊接單');
      setAiReview(null);
      await loadDemand();
    } catch {
      antMessage.error('提交失敗');
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async () => {
    if (!demandKey) return;
    try {
      await agentApi.updateDemandStatus(agentKey, demandKey, { status: 'draft' });
      trackDemandAction('withdraw', demandKey, demand?.goal);
      antMessage.success('已撤回');
      await loadDemand();
    } catch {
      antMessage.error('撤回失敗');
    }
  };

  const handleReactivate = async () => {
    if (!demandKey) return;
    try {
      await agentApi.updateDemandStatus(agentKey, demandKey, { status: 'draft' });
      trackDemandAction('create', demandKey, demand?.goal);
      antMessage.success('已重新開啟');
      await loadDemand();
    } catch {
      antMessage.error('操作失敗');
    }
  };

  const handleStatusChange = async (newStatus: string, reason?: string) => {
    if (!demandKey) return;
    try {
      await agentApi.updateDemandStatus(agentKey, demandKey, { status: newStatus, reason });
      trackDemandAction(newStatus as 'approve' | 'reject' | 'cancel', demandKey, demand?.goal, { reason });
      antMessage.success('狀態已更新');
      await loadDemand();
    } catch {
      antMessage.error('狀態更新失敗');
    }
  };

  const status = demand?.status as DemandStatus | undefined;
  const cfg = status ? statusConfig[status] : null;
  const isEditable = status === 'draft';

  useEffect(() => {
    if (cfg?.badgeColor && onStatusChange) {
      onStatusChange(cfg.badgeColor);
    }
  }, [cfg?.badgeColor]);

  if (loading) return <div style={{ padding: 20 }}>載入中...</div>;

  if (!demand) return <div style={{ padding: 20 }}>尚無需求</div>;

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>需求 {demand.version}</span>
          {cfg && <Tag color={cfg.tagColor}>{cfg.icon} {cfg.label}</Tag>}
        </div>
        {isEditable && (
          <Space>
            <Button onClick={handleSaveDraft} loading={saving}>保存草稿</Button>
            <Button type="primary" onClick={handleSubmit} loading={submitting || reviewing}>提交需求</Button>
          </Space>
        )}
      </div>

      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: token.colorTextSecondary, marginBottom: 16, padding: '8px 12px', background: token.colorFillAlter, borderRadius: 6 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#fa8c16' }}></span>
          草稿
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#1890ff' }}></span>
          開發中
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#52c41a' }}></span>
          待驗收/已上線
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff4d4f' }}></span>
          已取消
        </span>
      </div>

      {isEditable ? (
        <Form form={form} layout="vertical" initialValues={demand}>
          <Form.Item name="goal" label="需求目標" rules={[{ required: true, message: '請輸入需求目標' }]}>
            <Input.TextArea rows={2} placeholder="例如：做一個內部 IT 客服，幫員工快速解決 IT 問題" />
          </Form.Item>
          <Form.Item name="expected_effect" label="預期效果" rules={[{ required: true, message: '請輸入預期效果' }]}>
            <Input.TextArea rows={2} placeholder="例如：員工問題能在 5 分鐘內得到回覆，80% 問題能自動回答" />
          </Form.Item>
          <Form.Item name="problem_description" label="問題描述" rules={[{ required: true, message: '請輸入問題描述' }]}>
            <Input.TextArea rows={3} placeholder="描述現有的問題或痛點..." />
          </Form.Item>
          <Space style={{ width: '100%' }}>
            <Form.Item name="target_users" label="目標用戶" style={{ flex: 1 }}>
              <Input placeholder="例如：公司內部員工約 200 人" />
            </Form.Item>
            <Form.Item name="scope" label="服務範圍" style={{ flex: 1 }}>
              <Input placeholder="例如：密碼重設、軟體安裝、網路問題" />
            </Form.Item>
          </Space>
          <Space style={{ width: '100%' }}>
            <Form.Item name="excluded_scope" label="不包含範圍" style={{ flex: 1 }}>
              <Input placeholder="例如：不處理財務系統問題、不執行刪除動作" />
            </Form.Item>
            <Form.Item name="conversation_style" label="對話風格" style={{ flex: 1 }}>
              <Input placeholder="例如：繁體中文、禮貌親切、專業但不冷淡" />
            </Form.Item>
          </Space>

          <Divider>📥 輸入</Divider>
          <Form.Item name="input_description" label="輸入說明">
            <Input.TextArea rows={2} placeholder="描述使用者會輸入什麼內容..." />
          </Form.Item>
          <Space style={{ width: '100%' }}>
            <Form.Item name="input_format" label="建議格式" style={{ flex: 1 }}>
              <Input placeholder="例如：JSON、純文字、Markdown、圖片檔案" />
            </Form.Item>
          </Space>
          <Form.Item label="範例文件" name="example_documents">
            <FileUpload
              listType="text"
              accept=".pdf,.doc,.docx,.txt,.md"
              bucket="demands"
              fileType="documents"
              agentKey={agentKey}
              demandKey={demandKey || ''}
            />
          </Form.Item>
          <Form.Item label="範例圖片" name="example_images">
            <FileUpload
              listType="picture"
              accept="image/*"
              bucket="demands"
              fileType="images"
              agentKey={agentKey}
              demandKey={demandKey || ''}
            />
          </Form.Item>

          <Divider>📤 輸出</Divider>
          <Form.Item name="output_description" label="輸出說明">
            <Input.TextArea rows={2} placeholder="描述系統會輸出什麼內容..." />
          </Form.Item>
          <Space style={{ width: '100%' }}>
            <Form.Item name="output_format" label="輸出格式" style={{ flex: 1 }}>
              <Input placeholder="例如：JSON、純文字、回覆訊息、圖表" />
            </Form.Item>
          </Space>
          <Form.Item label="輸出範例" name="output_examples">
            <FileUpload
              listType="text"
              accept=".pdf,.doc,.docx,.txt,.md,.json,.csv"
              bucket="demands"
              fileType="outputs"
              agentKey={agentKey}
              demandKey={demandKey || ''}
            />
          </Form.Item>

          <Divider>⏱️ 工時估計</Divider>
          <Form.Item name="estimated_hours" label="預估工時（小時）">
            <InputNumber min={1} max={1000} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      ) : (
        <DemandSummary demand={demand} />
      )}

      <Divider />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          {status === 'submitted' && (
            <Button onClick={handleWithdraw}>撤回需求</Button>
          )}
          {status === 'in_development' && (
            <span style={{ color: token.colorTextTertiary }}>開發中，請等待團隊完成...</span>
          )}
          {status === 'accepted' && (
            <span style={{ color: token.colorTextTertiary }}>已承接，開發中...</span>
          )}
          {status === 'pending_acceptance' && (
            <>
              <Button onClick={() => handleStatusChange('in_development', prompt('請說明驗收不通過的原因：') || '')}>驗收不通過</Button>
              <Button type="primary" onClick={() => handleStatusChange('online')}>驗收通過 ✓</Button>
            </>
          )}
          {status === 'online' && (
            <Button onClick={() => handleStatusChange('draft')}>需求變更</Button>
          )}
          {status === 'cancelled' && (
            <>
              <Button danger onClick={() => agentApi.deleteDemand(agentKey, demandKey!)}>刪除需求</Button>
              <Button onClick={handleReactivate}>重新開啟</Button>
            </>
          )}
        </Space>
        <div style={{ color: token.colorTextTertiary, fontSize: 12 }}>
          提交時間：{demand.submitted_at ? new Date(demand.submitted_at).toLocaleString('zh-TW') : '-'}
        </div>
      </div>

      <Modal
        title="🤖 AI 需求審查"
        open={reviewModalVisible}
        onCancel={() => setReviewModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setReviewModalVisible(false)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={submitting}
            onClick={handleConfirmSubmit}
            disabled={aiReview ? aiReview.score < 70 : false}
          >
            {aiReview && aiReview.score < 70 ? '評分過低，無法提交' : '確認提交'}
          </Button>,
        ]}
        width={600}
      >
        {aiReview && (
          <div style={{ maxHeight: '60vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <Alert
                message={aiReview.summary}
                type="info"
                showIcon
                style={{ flex: 1, marginRight: 8 }}
              />
              <div style={{
                background: aiReview.score >= 70 ? token.colorSuccessBg : token.colorErrorBg,
                border: `1px solid ${aiReview.score >= 70 ? token.colorSuccessBorder : token.colorErrorBorder}`,
                borderRadius: 8,
                padding: '12px 20px',
                textAlign: 'center',
                minWidth: 80,
              }}>
                <div style={{ fontSize: 24, fontWeight: 'bold', color: aiReview.score >= 70 ? token.colorSuccess : token.colorError }}>
                  {aiReview.score}
                </div>
                <div style={{ fontSize: 12, color: token.colorTextTertiary }}>綜合評分</div>
              </div>
            </div>

            {aiReview.score < 70 && (
              <Alert
                message="評分低於 70 分，不建議開發。請參考建議改善需求後再提交。"
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            <div style={{ display: 'grid', gap: 12 }}>
              <div style={{ background: token.colorFillAlter, padding: 12, borderRadius: 8 }}>
                <strong>📝 完整性：</strong>
                <div style={{ marginTop: 4 }}>{aiReview.completeness}</div>
              </div>

              <div style={{ background: token.colorFillAlter, padding: 12, borderRadius: 8 }}>
                <strong>✅ 合理性：</strong>
                <div style={{ marginTop: 4 }}>{aiReview.reasonableness}</div>
              </div>

              <div style={{ background: token.colorFillAlter, padding: 12, borderRadius: 8 }}>
                <strong>⚡ 可行性：</strong>
                <div style={{ marginTop: 4 }}>{aiReview.feasibility}</div>
              </div>

              <div style={{ background: token.colorInfoBg, padding: 12, borderRadius: 8 }}>
                <strong>⏱️ AI 預估工時：</strong>
                <span style={{ fontSize: 20, marginLeft: 8 }}>{aiReview.estimated_hours}</span>
                <span style={{ color: token.colorTextTertiary, marginLeft: 4 }}>小時</span>
                <Tag color={aiReview.confidence === 'high' ? 'green' : aiReview.confidence === 'medium' ? 'orange' : 'red'} style={{ marginLeft: 8 }}>
                  信心度：{aiReview.confidence}
                </Tag>
                {aiReview.hour_breakdown && (
                  <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 12 }}>
                    <span>🔍 顧問：{aiReview.hour_breakdown.consulting}h</span>
                    <span>💻 開發：{aiReview.hour_breakdown.development}h</span>
                    <span>🧪 測試：{aiReview.hour_breakdown.testing}h</span>
                    <span>✅ 審查：{aiReview.hour_breakdown.review}h</span>
                  </div>
                )}
              </div>

              {aiReview.suggestions && aiReview.suggestions.length > 0 && (
                <div style={{ background: token.colorWarningBg, padding: 12, borderRadius: 8 }}>
                  <strong>💡 改進建議：</strong>
                  <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                    {aiReview.suggestions.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function DemandSummary({ demand }: { demand: Demand }) {
  const { token } = theme.useToken();
  return (
    <div style={{ background: token.colorFillAlter, padding: 16, borderRadius: 8 }}>
      <h4 style={{ marginBottom: 12 }}>📋 需求摘要</h4>
      <div style={{ display: 'grid', gap: 8 }}>
        <div><strong>目標：</strong>{demand.goal || '-'}</div>
        <div><strong>預期效果：</strong>{demand.expected_effect || '-'}</div>
        <div><strong>問題描述：</strong>{demand.problem_description || '-'}</div>
        {demand.target_users && <div><strong>目標用戶：</strong>{demand.target_users}</div>}
        {demand.scope && <div><strong>服務範圍：</strong>{demand.scope}</div>}
        {demand.excluded_scope && <div><strong>不包含：</strong>{demand.excluded_scope}</div>}
        {demand.conversation_style && <div><strong>對話風格：</strong>{demand.conversation_style}</div>}
        {demand.estimated_hours && (
          <div><strong>預估工時：</strong>{demand.estimated_hours} 小時</div>
        )}

        {demand.input_description && (
          <>
            <Divider style={{ margin: '8px 0' }} />
            <div><strong>📥 輸入說明：</strong>{demand.input_description}</div>
            {demand.input_format && <div><strong>輸入格式：</strong>{demand.input_format}</div>}
            {demand.example_documents && demand.example_documents.length > 0 && (
              <div>
                <strong>範例文件：</strong>
                <FileListDisplay files={demand.example_documents} />
              </div>
            )}
            {demand.example_images && demand.example_images.length > 0 && (
              <div>
                <strong>範例圖片：</strong>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
                  {demand.example_images.map((img, i) => (
                    <Image key={i} src={img.url} width={80} height={80} style={{ objectFit: 'cover', borderRadius: 4 }} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {demand.output_description && (
          <>
            <Divider style={{ margin: '8px 0' }} />
            <div><strong>📤 輸出說明：</strong>{demand.output_description}</div>
            {demand.output_format && <div><strong>輸出格式：</strong>{demand.output_format}</div>}
            {demand.output_examples && demand.output_examples.length > 0 && (
              <div>
                <strong>輸出範例：</strong>
                <FileListDisplay files={demand.output_examples} />
              </div>
            )}
          </>
        )}

        {demand.ai_review && (
          <>
            <Divider style={{ margin: '8px 0' }} />
            <div style={{ background: token.colorInfoBg, padding: 12, borderRadius: 8, marginTop: 8 }}>
              <h4 style={{ marginBottom: 8 }}>🤖 AI 審查結果</h4>
              <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
                <div><strong>完整性：</strong>{demand.ai_review.completeness}</div>
                <div><strong>合理性：</strong>{demand.ai_review.reasonableness}</div>
                <div><strong>可行性：</strong>{demand.ai_review.feasibility}</div>
                {demand.ai_review.estimated_hours > 0 && (
                  <div><strong>AI 預估工時：</strong>{demand.ai_review.estimated_hours} 小時</div>
                )}
                {demand.ai_review.suggestions && demand.ai_review.suggestions.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <strong>💡 建議：</strong>
                    <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                      {demand.ai_review.suggestions.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function FileListDisplay({ files }: { files: UploadedFile[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
      {files.map((file, i) => (
        <a key={i} href={file.url} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <FileOutlined /> {file.name}
        </a>
      ))}
    </div>
  );
}

interface FileUploadProps {
  listType?: 'text' | 'picture';
  accept?: string;
  bucket: string;
  fileType: string;
  agentKey: string;
  demandKey: string;
}

function FileUpload({ listType = 'text', accept, bucket, fileType, agentKey, demandKey }: FileUploadProps) {
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  const uploadPath = `${bucket}/${agentKey}/${demandKey}/${fileType}`;

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    accept,
    listType,
    fileList,
    customRequest: async (options) => {
      const { file, onSuccess, onError } = options;
      const formData = new FormData();
      formData.append('file', file as File);

      try {
        const response = await fetch(`${SEAWEED_URL}/${uploadPath}/${(file as File).name}`, {
          method: 'PUT',
          headers: {
            'Authorization': 'Basic ' + btoa(`${SEAWEED_USER}:${SEAWEED_PASS}`),
          },
          body: formData,
        });

        if (response.ok) {
          const url = `${SEAWEED_URL}/${uploadPath}/${(file as File).name}`;
          const uploadFile: UploadFile = {
            uid: (file as File).name,
            name: (file as File).name,
            status: 'done',
            url,
          };
          setFileList(prev => [...prev, uploadFile]);
          onSuccess?.(uploadFile);
        } else {
          onError?.(new Error(`Upload failed: ${response.statusText}`));
        }
      } catch (err) {
        onError?.(err as Error);
      }
    },
    onRemove: (file) => {
      setFileList(prev => prev.filter(f => f.uid !== file.uid));
      return true;
    },
  };

  return (
    <Upload.Dragger {...uploadProps} style={{ padding: listType === 'picture' ? 0 : undefined }}>
      <p className="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p className="ant-upload-text">點擊或拖曳上傳檔案</p>
      <p className="ant-upload-hint" style={{ fontSize: 12, color: '#888' }}>
        支援：{accept || '所有檔案'}
      </p>
    </Upload.Dragger>
  );
}
