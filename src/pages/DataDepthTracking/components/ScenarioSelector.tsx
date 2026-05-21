/**
 * @file        場景選擇器
 * @description 8 大追蹤場景的卡片式選擇網格，支援選中高亮與懸浮陰影效果
 * @lastUpdate  2026-05-17
 */
import React from 'react';
import { Card, Row, Col } from 'antd';
import {
  ExportOutlined,
  ImportOutlined,
  BranchesOutlined,
  FileTextOutlined,
  WarningOutlined,
  ClockCircleOutlined,
  BugOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import { SCENARIO_DEFINITIONS } from '../scenarioConfig';
import { useContentTokens } from '../../../contexts/AppThemeProvider';

interface ScenarioSelectorProps {
  selectedScenario: string | null;
  onSelect: (scenarioId: string) => void;
}

const ICON_MAP: Record<string, React.ComponentType<{ style?: React.CSSProperties }>> = {
  ExportOutlined,
  ImportOutlined,
  BranchesOutlined,
  FileTextOutlined,
  WarningOutlined,
  ClockCircleOutlined,
  BugOutlined,
  ShopOutlined,
};

const ScenarioSelector: React.FC<ScenarioSelectorProps> = ({ selectedScenario, onSelect }) => {
  const tokens = useContentTokens();

  return (
    <Row gutter={[16, 16]}>
      {SCENARIO_DEFINITIONS.map((scenario) => {
        const isSelected = selectedScenario === scenario.id;
        const IconComponent = ICON_MAP[scenario.icon];

        return (
          <Col xs={12} md={12} key={scenario.id}>
            <Card
              hoverable
              size="small"
              onClick={() => onSelect(scenario.id)}
              style={{
                borderRadius: tokens.borderRadius,
                cursor: 'pointer',
                border: isSelected
                  ? `2px solid ${tokens.colorPrimary}`
                  : '1px solid transparent',
                background: isSelected
                  ? `${tokens.colorPrimary}15`
                  : tokens.containerBg,
                boxShadow: isSelected
                  ? `0 0 0 1px ${tokens.colorPrimary}22, ${tokens.cardShadow}`
                  : tokens.cardShadow,
                transition: 'all 0.25s ease',
              }}
              styles={{
                body: {
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column' as const,
                  alignItems: 'center',
                  textAlign: 'center' as const,
                  gap: 8,
                },
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.boxShadow = tokens.cardShadowHover;
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.boxShadow = tokens.cardShadow;
                  e.currentTarget.style.transform = 'translateY(0)';
                }
              }}
            >
              {IconComponent && (
                <IconComponent
                  style={{
                    fontSize: 28,
                    color: isSelected ? tokens.colorPrimary : tokens.iconDefault,
                    transition: 'color 0.25s ease',
                  }}
                />
              )}
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  color: isSelected ? tokens.colorPrimary : tokens.colorTextBase,
                  transition: 'color 0.25s ease',
                }}
              >
                {scenario.name}
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: tokens.textSecondary,
                  lineHeight: 1.4,
                }}
              >
                {scenario.description}
              </div>
            </Card>
          </Col>
        );
      })}
    </Row>
  );
};

export default ScenarioSelector;
