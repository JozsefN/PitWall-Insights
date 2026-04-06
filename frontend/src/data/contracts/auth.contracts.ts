export type AuthTokenResponse = {
  access_token: string;
  token_type: "bearer";
};

export type AuthSessionResponse = {
  authenticated: boolean;
  user_id: string | null;
  email: string | null;
};

export type SignUpRequest = {
  email: string;
  password: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};