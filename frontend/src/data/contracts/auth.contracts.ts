export type AuthTokenResponse = {
  status: "authenticated";
  access_token: string;
  token_type: "bearer";
};

export type VerificationRequired = {
  status: "verification_required";
  challenge_id: string;
  email: string;
};

export type AuthResult = AuthTokenResponse | VerificationRequired;

export type AuthSessionResponse = {
  authenticated: boolean;
  user_id: string | null;
  email: string | null;
  role: "member" | "admin" | null;
  email_verified: boolean;
};

export type SignUpRequest = {
  email: string;
  password: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};
