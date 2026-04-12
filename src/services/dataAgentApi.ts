/**
 * @file        Data Agent API 服務層
 * @description DA 的 Schema、Intents、Query 等 API 接口定義
 * @lastUpdate  2026-04-12 08:50:59
 * @author      Daniel Chung
 */

export type {
  TableInfo,
  FieldInfo,
  TableRelation,
  QueryRequest,
  IntentSummary,
  QueryResponse,
  OllamaModel,
  IntentCatalogEntry,
  NL2SqlPhaseResult,
  NL2SqlIntentMatch,
  NL2SqlQueryPlan,
  NL2SqlValidation,
  NL2SqlExecution,
  ClarificationQuestion,
  ClarificationResponse,
  ErrorExplanation,
  NL2SqlResponse,
  RagicImportResult,
  RagicGraphRelation,
  RagicGraphQueryResult,
  RagicStepResult,
  RagicMultiStepResult,
  RagicIntentItem,
  RagicNLQueryOptions,
  RagicNLQueryRequest,
  RagicNLWhereClause,
  RagicNLTranslatedParams,
  RagicNLRecord,
  RagicNLPagination,
  RagicNLClarification,
  RagicNLResultStats,
  RagicNLResultSet,
  RagicNLIntentMatch,
  RagicNLPostError,
  RagicNLQueryMetadata,
  RagicNLQueryResponse,
} from './dataAgentApi_types';

import { dataAgentApi_endpoints } from './dataAgentApi_endpoints';

export const dataAgentApi = { ...dataAgentApi_endpoints };

export default dataAgentApi;
