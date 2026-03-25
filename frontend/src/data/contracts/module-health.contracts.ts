export interface ModuleHealthResponse<TDetails = unknown> {
  module: string;
  status: string;
  details?: TDetails;
}