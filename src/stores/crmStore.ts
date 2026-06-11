export interface CRMContext {
  currentAgentId?: string;
}

export function useCrmStore(): { context: CRMContext } {
  return { context: {} };
}
