/**
 * @file        儲存報表模態對話框
 * @description 提供表單讓使用者輸入報表名稱與標籤，儲存資料深度追蹤結果
 * @lastUpdate  2026-05-17
 * @author      Daniel Chung
 * @version     1.0.0
 */
import { Modal, Form, Input, Select, Typography } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { useContentTokens } from '../../../contexts/AppThemeProvider';

/* =================== 型別定義 =================== */

export interface SaveReportParams {
  name: string;
  tags: string[];
}

interface ReportSaveModalProps {
  /** 是否顯示對話框 */
  open: boolean;
  /** 關閉對話框 */
  onClose: () => void;
  /** 儲存報表回呼 */
  onSave: (params: SaveReportParams) => void;
  /** 當前場景識別碼（僅供顯示） */
  scenario: string | null;
  /** 儲存中狀態 */
  loading?: boolean;
}

const { Text } = Typography;

/* =================== 主元件 =================== */

export default function ReportSaveModal({
  open,
  onClose,
  onSave,
  scenario,
  loading,
}: ReportSaveModalProps) {
  const tokens = useContentTokens();
  const [form] = Form.useForm();

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      onSave({
        name: values.name,
        tags: values.tags || [],
      });
      form.resetFields();
    } catch {
      // validation failed — Ant Design shows inline messages
    }
  };

  const handleClose = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title="儲存報表"
      open={open}
      onOk={handleOk}
      onCancel={handleClose}
      confirmLoading={loading}
      okText="儲存"
      cancelText="取消"
      okButtonProps={{ icon: <SaveOutlined /> }}
      destroyOnClose
      width={480}
      style={{ borderRadius: tokens.borderRadius }}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ name: '', tags: [] }}
      >
        {scenario && (
          <Text
            type="secondary"
            style={{
              display: 'block',
              marginBottom: 16,
              fontSize: 12,
              color: tokens.textSecondary,
            }}
          >
            當前場景：{scenario}
          </Text>
        )}

        <Form.Item
          name="name"
          label="報表名稱"
          rules={[{ required: true, message: '請輸入報表名稱' }]}
        >
          <Input
            placeholder="請輸入報表名稱"
            style={{ borderRadius: tokens.borderRadius }}
          />
        </Form.Item>

        <Form.Item
          name="tags"
          label="標籤"
        >
          <Select
            mode="tags"
            placeholder="輸入標籤後按 Enter"
            style={{ borderRadius: tokens.borderRadius }}
            tokenSeparators={[',', '，']}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
