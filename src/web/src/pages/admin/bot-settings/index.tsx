import { useEffect, useState } from 'react'

import { apiClient } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from '@/components/ui/toast'

const ROLES = [
  { value: 'owner',      label: 'Owner only' },
  { value: 'admin',      label: 'Admin and above' },
  { value: 'moderator',  label: 'Moderator and above' },
  { value: 'user',       label: 'All users' },
]

export default function AdminBotSettingsPage() {
  const [settings, setSettings] = useState<Record<string, string | null>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient
      .get<{ settings: Record<string, string | null> }>('/bot-settings')
      .then((r) => setSettings(r.data.settings))
      .catch(() => toast.error('Failed to load bot settings'))
      .finally(() => setLoading(false))
  }, [])

  const update = async (key: string, value: string) => {
    try {
      const r = await apiClient.patch<{ settings: Record<string, string | null> }>(
        `/bot-settings/${key}`,
        { value },
      )
      setSettings(r.data.settings)
      toast.success('Saved')
    } catch {
      toast.error('Failed to save')
    }
  }

  if (loading) return <div className="flex justify-center py-24 text-muted-foreground">Loading…</div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Bot Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Access Mode</CardTitle>
          <CardDescription>
            Controls who can use the bot in private chats.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label>Private chat access</Label>
            <Select
              value={settings['bot_access_mode'] ?? 'open'}
              onValueChange={(v) => update('bot_access_mode', v)}
            >
              <SelectTrigger className="w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="open">Open  - anyone can use the bot</SelectItem>
                <SelectItem value="approved_only">Approved only  - new users get restricted role</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              In <strong>approved only</strong> mode, new users receive the <code>restricted</code> role
              (no access) until manually upgraded to <code>user</code> or above.
              Existing users are not affected.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Browser Cookies</CardTitle>
          <CardDescription>
            Who can use the shared browser profile (Chromium) for cookie-authenticated downloads.
            The owner always has access regardless of this setting.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label>Minimum role required</Label>
            <Select
              value={settings['browser_cookies_min_role'] ?? 'owner'}
              onValueChange={(v) => update('browser_cookies_min_role', v)}
            >
              <SelectTrigger className="w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Users with this role or higher will automatically use the shared
              Chromium profile cookies when no personal cookie is uploaded.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
