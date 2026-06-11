/**
 * @file        formatAgentResult.ts
 * @description 代理結果格式化工具，將 API 回應轉換為可讀的 Markdown 表格與訊息
 * @lastUpdate  2026-04-18 22:45:00
 * @author      AI Agent
 * @version     1.0.0
 */

export const ROUTABLE_STRATEGIES = new Set(['route_to_data', 'knowledge_search']);

export function formatAgentResult(action: string, result: Record<string, unknown>): string {
  const clarification = result.clarification as Record<string, unknown> | undefined;
  if (clarification?.needs_clarification) {
    const questions = (clarification.questions as Array<Record<string, string>>) || [];
    const reason = String(clarification.reason || '');
    const qList = questions.map((q) => `- ${q.question}`).join('\n');
    return `需要進一步確認：\n\n${reason}\n\n${qList}\n\n請補充資訊後再次提問。`;
  }

  const errorExplanation = result.error_explanation as Record<string, unknown> | undefined;
  if (errorExplanation) {
    const suggestions = (errorExplanation.suggestions as string[]) || [];
    const sugList = suggestions.length > 0 ? `\n\n建議：\n${suggestions.map((s) => `- ${s}`).join('\n')}` : '';
    return `查詢失敗：${String(errorExplanation.explanation || result.error || '未知錯誤')}${sugList}`;
  }

  if (result.error) {
    return `查詢失敗：${String(result.error)}`;
  }

  const executionResult = result.execution_result as Record<string, unknown> | undefined;
  if (!executionResult) {
    return action === 'knowledge_search' ? '未找到相關知識。' : '查詢未返回結果。';
  }

  const rows = (executionResult.rows as Array<Record<string, unknown>>) || [];
  const columns = (executionResult.columns as string[]) || [];
  const rowCount = Number(executionResult.row_count || rows.length);
  const sql = String(result.generated_sql || '');

  if (rows.length === 0) return '查詢成功，但沒有符合條件的資料。';

  const header = `| ${columns.join(' | ')} |`;
  const separator = `| ${columns.map(() => '---').join(' | ')} |`;
  const body = rows.slice(0, 20).map((row) => `| ${columns.map((col) => String(row[col] ?? '')).join(' | ')} |`).join('\n');
  const overflow = rowCount > 20 ? `\n\n> 共 ${rowCount} 筆，僅顯示前 20 筆` : '';
  const sqlNote = sql ? `\n\n<details><summary>SQL</summary>\n\n\`\`\`sql\n${sql}\n\`\`\`\n</details>` : '';

  return `${header}\n${separator}\n${body}${overflow}${sqlNote}`;
}
