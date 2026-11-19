export type F1Connection = {
  status: "not_connected" | "connected" | "reconnect_required";
  connected: boolean;
  persistent: boolean;
  expires_at: string | null;
  connected_at?: string;
  verified_at?: string;
  auth_method?: "password" | "browser";
};

export type Profile = {
  user_id: string;
  email: string;
  name: string | null;
  nickname: string | null;
  phone_number: string | null;
  subscription: { plan: "free"; billing_available: boolean; upgrade_status: string };
};

export type F1Credentials = {
  email: string;
  password: string;
  personal_use_acknowledged: boolean;
  remember_credentials: true;
};
