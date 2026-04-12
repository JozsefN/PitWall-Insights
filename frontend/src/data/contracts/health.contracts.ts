export interface DatabaseHealthResponse {
  status: string;
  driver: string;
  error?: string;
}

export interface RootHealthResponse {
  status: string;
  service: string;
}

export interface ApiHealthResponse {
  status: string;
  service: string;
  db: DatabaseHealthResponse;
}
