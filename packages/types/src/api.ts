/** Cross-stack API contracts shared by frontend (and documented for backend). */

export type AppMode = "ecommerce" | "explainer";

export interface ModuleHealth {
  status: string;
  module: string;
  stage: number;
  ready: boolean;
  source: string;
  checks: Record<string, unknown>;
  message?: string;
  provider?: string;
}

export interface GlobalHealth {
  status: string;
  stage: number;
  modules: {
    ecommerce: ModuleHealth;
    explainer_vision: ModuleHealth;
    explainer_generate: ModuleHealth;
  };
}

export interface ApiErrorBody {
  code: string;
  message: string;
  detail?: unknown;
}

export interface ApiErrorResponse {
  error: ApiErrorBody;
}
