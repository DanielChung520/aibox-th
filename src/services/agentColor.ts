/**
 * @file        Agent color utility
 * @description Stable, unique identification colors for agents
 * @lastUpdate  2026-06-16 12:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

export const AGENT_COLORS: string[] = [
  '#3b82f6', // blue-500
  '#10b981', // emerald-500
  '#8b5cf6', // violet-500
  '#f59e0b', // amber-500
  '#ef4444', // red-500
  '#06b6d4', // cyan-500
  '#ec4899', // pink-500
  '#84cc16', // lime-500
];

export interface ColorableAgent {
  name: string;
  color?: string;
  _key?: string;
}

export function getAgentColor(agent: ColorableAgent): string {
  if (agent.color) return agent.color;
  const hash = agent.name.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  return AGENT_COLORS[hash % AGENT_COLORS.length];
}

export function getColorWithAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
