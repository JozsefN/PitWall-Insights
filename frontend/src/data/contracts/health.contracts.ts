export interface RootHealthResponse {
  status: string;
  service: string;
}

export interface ApiHealthResponse {
  status: string;
  service: string;
  db: unknown;
}