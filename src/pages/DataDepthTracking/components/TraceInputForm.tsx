/**
 * @file        追蹤輸入表單
 * @description 根據選擇的場景動態渲染輸入欄位（批號、日期、深度、扇出等）
 * @lastUpdate  2026-05-17
 */
import React, { useEffect } from 'react';
import { Form, Input, DatePicker, Slider, Button, Collapse, Space, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { getScenarioById } from '../scenarioConfig';
import { useContentTokens } from '../../../contexts/AppThemeProvider';

export interface TraceParams {
  scenario: string;
  entry_batch: string;
  depth: number;
  max_fan_out: number;
  from_date?: string;
  to_date?: string;
}

interface TraceInputFormProps {
  scenario: string | null;
  onTrace: (params: TraceParams) => void;
  loading: boolean;
}

const { Text } = Typography;
const { RangePicker } = DatePicker;

const depthMarks: Record<number, string> = {
  1: '1',
  3: '3',
  5: '5',
  7: '7',
  10: '10',
};

const fanOutMarks: Record<number, string> = {
  1: '1',
  10: '10',
  25: '25',
  50: '50',
};

const TraceInputForm: React.FC<TraceInputFormProps> = ({ scenario, onTrace, loading }) => {
  const tokens = useContentTokens();
  const [form] = Form.useForm();

  useEffect(() => {
    if (scenario) {
      const def = getScenarioById(scenario as any);
      if (def) {
        form.setFieldsValue({
          depth: def.defaultDepth,
          max_fan_out: 10,
        });
      }
    }
  }, [scenario, form]);

  const handleFinish = (values: any) => {
    if (!scenario) return;

    const params: TraceParams = {
      scenario,
      entry_batch: values.entry_batch || '',
      depth: values.depth ?? 3,
      max_fan_out: values.max_fan_out ?? 10,
    };

    if (values.date_range && values.date_range.length === 2) {
      params.from_date = values.date_range[0].format('YYYY-MM-DD');
      params.to_date = values.date_range[1].format('YYYY-MM-DD');
    }

    onTrace(params);
  };

  if (!scenario) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: 'center',
          color: tokens.textSecondary,
          background: tokens.containerBg,
          borderRadius: tokens.borderRadius,
        }}
      >
        <Text type="secondary">請先選擇一個追蹤場景</Text>
      </div>
    );
  }

  const scenarioDef = getScenarioById(scenario as any);
  if (!scenarioDef) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: 'center',
          color: tokens.textSecondary,
          background: tokens.containerBg,
          borderRadius: tokens.borderRadius,
        }}
      >
        <Text type="secondary">未知場景：{scenario}</Text>
      </div>
    );
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        depth: scenarioDef.defaultDepth,
        max_fan_out: 10,
      }}
    >
      <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
        <Form.Item
          name="entry_batch"
          label={scenarioDef.inputLabel}
          rules={[{ required: true, message: `請輸入${scenarioDef.inputLabel}` }]}
          style={{ marginBottom: 0 }}
        >
          <Input.Search
            placeholder={scenarioDef.inputPlaceholder}
            enterButton={<SearchOutlined />}
            size="middle"
            onSearch={() => form.submit()}
          />
        </Form.Item>

        {scenarioDef.hasDateRange && (
          <Form.Item name="date_range" label="效期範圍" style={{ marginBottom: 0 }}>
            <RangePicker
              style={{ width: '100%' }}
              placeholder={['起始日期', '結束日期']}
            />
          </Form.Item>
        )}

        {scenarioDef.hasSupplierInput && (
          <Form.Item name="supplier_code" label="供應商代碼" style={{ marginBottom: 0 }}>
            <Input placeholder="請輸入供應商代碼（選填）" />
          </Form.Item>
        )}

        <Collapse
          ghost
          size="small"
          items={[
            {
              key: 'advanced',
              label: '進階設定',
              children: (
                <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
                  <Form.Item
                    name="depth"
                    label="追蹤深度"
                    tooltip="控制追蹤鏈條的最大層數"
                    style={{ marginBottom: 0 }}
                  >
                    <Slider
                      min={1}
                      max={10}
                      marks={depthMarks}
                      defaultValue={scenarioDef.defaultDepth}
                    />
                  </Form.Item>
                  <Form.Item
                    name="max_fan_out"
                    label="最大扇出數"
                    tooltip="控制每層展開的最大節點數"
                    style={{ marginBottom: 0 }}
                  >
                    <Slider
                      min={1}
                      max={50}
                      marks={fanOutMarks}
                      defaultValue={10}
                    />
                  </Form.Item>
                </Space>
              ),
            },
          ]}
        />

        <Button
          type="primary"
          htmlType="submit"
          loading={loading}
          size="large"
          block
          style={{
            background: tokens.colorPrimary,
            borderColor: tokens.colorPrimary,
            borderRadius: tokens.borderRadius,
          }}
        >
          開始追蹤
        </Button>
      </Space>
    </Form>
  );
};

export default TraceInputForm;
