export type UserRole = 'owner' | 'admin' | 'moderator' | 'user' | 'restricted' | 'banned'

export interface User {
  id: number
  username: string | null
  first_name: string | null
  role: UserRole
  created_at: string
}

export interface UserSettings {
  user_id: number
  language: string
  quality: string
  codec: string
  container: string
  proxy_enabled: boolean
  proxy_url: string | null
  subs_enabled: boolean
  subs_auto: boolean
  subs_always_ask: boolean
  subs_lang: string
  split_size: number
  nsfw_blur: boolean
  mediainfo: boolean
  send_as_file: boolean
  theme: string
  keyboard: string
  args_json: Record<string, unknown>
}

export interface DownloadLog {
  id: number
  user_id: number
  url: string
  domain: string | null
  title: string | null
  quality: string | null
  file_size: number | null
  duration: number | null
  status: string
  error_msg: string | null
  group_id: number | null
  group_title: string | null
  thread_id: number | null
  message_id: number | null
  clip_start: number | null
  clip_end: number | null
  created_at: string
}

export interface Cookie {
  id: number
  user_id: number
  domain: string
  is_valid: boolean
  created_at: string
  updated_at: string
}

export interface Group {
  id: number
  title: string | null
  enabled: boolean
  auto_grant_role: UserRole
  allow_pm: boolean
  nsfw_allowed: boolean
  created_at: string
}

export interface NsfwDomain {
  id: number
  domain: string
  note: string | null
  created_at: string
}

export interface NsfwKeyword {
  id: number
  keyword: string
  note: string | null
  created_at: string
}

export interface NsfwCheckRequest {
  url: string
  title?: string
  description?: string
  tags?: string[]
}

export interface NsfwCheckResponse {
  is_nsfw: boolean
  reason: string
}

export interface ThreadPolicy {
  id: number
  group_id: number
  thread_id: number | null
  name: string | null
  enabled: boolean
}

export interface StatsOverview {
  total_downloads: number
  downloads_today: number
  cache_hits_today: number
  errors_today: number
  top_domains: Array<{ domain: string; count: number }>
  downloads_by_day: Array<{ date: string; count: number }>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: number
  role: string
}

export interface UserUpdateRequest {
  role?: UserRole
  ban_until?: string | null
}

export interface RetryResponse {
  url: string
  queued: boolean
}

export interface GroupCreateRequest {
  id: number
  title?: string | null
  enabled?: boolean
  auto_grant_role?: UserRole
  allow_pm?: boolean
  nsfw_allowed?: boolean
}

export interface GroupUpdateRequest {
  title?: string | null
  enabled?: boolean
  auto_grant_role?: UserRole
  allow_pm?: boolean
  nsfw_allowed?: boolean
}
