import { useEffect, useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { Coffee, Ghost, Moon, Sun } from 'lucide-react'

import { apiClient } from '@/lib/api-client'
import { cn } from '@/lib/utils'
import type { UserSettings } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { toast } from '@/components/ui/toast'
import { useTelegram, type CatppuccinFlavor } from '@/layout/TelegramProvider'

type FormValues = Omit<UserSettings, 'user_id' | 'args_json' | 'theme'>

const THEME_OPTIONS: { value: CatppuccinFlavor; label: string; icon: React.ReactNode; dark: boolean }[] = [
  { value: 'latte',     label: 'Latte',     icon: <Sun className="h-3.5 w-3.5" />,    dark: false },
  { value: 'frappe',    label: 'Frappé',    icon: <Coffee className="h-3.5 w-3.5" />,  dark: true  },
  { value: 'macchiato', label: 'Macchiato', icon: <Moon className="h-3.5 w-3.5" />,   dark: true  },
  { value: 'mocha',     label: 'Mocha',     icon: <Ghost className="h-3.5 w-3.5" />,  dark: true  },
]

const QUALITY_OPTIONS = [
  { value: 'best',  label: 'Best available' },
  { value: 'ask',   label: 'Ask every time' },
  { value: '4320',  label: '8K (4320p)' },
  { value: '2160',  label: '4K (2160p)' },
  { value: '1440',  label: '1440p' },
  { value: '1080',  label: '1080p' },
  { value: '720',   label: '720p' },
  { value: '480',   label: '480p' },
  { value: '360',   label: '360p' },
]

const CODEC_OPTIONS = [
  { value: 'avc1', label: 'H.264 (avc1)  - most compatible' },
  { value: 'av01', label: 'AV1 (av01)  - best compression' },
  { value: 'vp9',  label: 'VP9  - good compression' },
  { value: 'any',  label: 'Any  - let yt-dlp choose' },
]

const CONTAINER_OPTIONS = [
  { value: 'mp4',  label: 'MP4' },
  { value: 'mkv',  label: 'MKV' },
  { value: 'webm', label: 'WebM' },
]

const SPLIT_OPTIONS = [
  { value: String(500 * 1024 * 1024),  label: '500 MB' },
  { value: String(1000 * 1024 * 1024), label: '1 GB' },
  { value: String(1500 * 1024 * 1024), label: '1.5 GB' },
  { value: String(2000 * 1024 * 1024), label: '2 GB (Telegram limit)' },
]

const KEYBOARD_OPTIONS = [
  { value: 'OFF',  label: 'Off  - no reply keyboard' },
  { value: '1x3',  label: '1×3  - single column' },
  { value: '2x3',  label: '2×3  - grid (default)' },
  { value: 'FULL', label: 'Full width buttons' },
]

const LANG_OPTIONS = [
  { value: 'en', label: 'English' },
  { value: 'ru', label: 'Русский' },
  { value: 'uk', label: 'Українська' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'es', label: 'Español' },
]

const SUBS_LANG_OPTIONS = ['en', 'ru', 'de', 'fr', 'es', 'it', 'pt', 'ja', 'zh', 'ko']

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  )
}

function FieldRow({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-none">{label}</p>
        {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

interface ControlledSelectProps {
  name: keyof FormValues
  options: { value: string; label: string }[]
  control: ReturnType<typeof useForm<FormValues>>['control']
}

function ControlledSelect({ name, options, control }: ControlledSelectProps) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <Select
          value={String(field.value ?? '')}
          onValueChange={(v: string) => field.onChange(name === 'split_size' ? Number(v) : v)}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    />
  )
}

interface ControlledSwitchProps {
  name: keyof FormValues
  label: string
  hint?: string
  control: ReturnType<typeof useForm<FormValues>>['control']
}

function ControlledSwitch({ name, label, hint, control }: ControlledSwitchProps) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <FieldRow label={label} hint={hint}>
          <Switch
            checked={!!field.value}
            onCheckedChange={field.onChange}
          />
        </FieldRow>
      )}
    />
  )
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const { flavor, setFlavor } = useTelegram()
  const { handleSubmit, reset, watch, control, formState: { isSubmitting, isDirty } } =
    useForm<FormValues>()

  const subsEnabled = watch('subs_enabled')
  const proxyEnabled = watch('proxy_enabled')

  useEffect(() => {
    apiClient
      .get<UserSettings>('/settings')
      .then((res) => {
        const { user_id: _uid, args_json: _args, ...rest } = res.data
        reset(rest)
      })
      .catch(() => toast.error('Failed to load settings'))
      .finally(() => setLoading(false))
  }, [reset])

  const onSubmit = async (values: FormValues) => {
    try {
      await apiClient.patch('/settings', values)
      toast.success('Settings saved')
      reset(values)
    } catch {
      toast.error('Failed to save settings')
    }
  }

  if (loading) {
    return <div className="flex justify-center py-24 text-muted-foreground">Loading…</div>
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Section title="Video quality">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Resolution</Label>
            <ControlledSelect name="quality" options={QUALITY_OPTIONS} control={control} />
          </div>
          <div className="space-y-1.5">
            <Label>Codec</Label>
            <ControlledSelect name="codec" options={CODEC_OPTIONS} control={control} />
          </div>
          <div className="space-y-1.5">
            <Label>Container</Label>
            <ControlledSelect name="container" options={CONTAINER_OPTIONS} control={control} />
          </div>
        </div>
      </Section>

      <Section title="Delivery">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Split large files at</Label>
            <ControlledSelect name="split_size" options={SPLIT_OPTIONS} control={control} />
          </div>
          <div className="space-y-1.5">
            <Label>Reply keyboard layout</Label>
            <ControlledSelect name="keyboard" options={KEYBOARD_OPTIONS} control={control} />
          </div>
        </div>

        <div className="space-y-3 border-t pt-3">
          <ControlledSwitch name="send_as_file" label="Send as document" hint="Skip streaming player, send raw file" control={control} />
          <ControlledSwitch name="nsfw_blur" label="NSFW blur" hint="Apply spoiler overlay on adult content" control={control} />
          <ControlledSwitch name="mediainfo" label="Mediainfo report" hint="Send technical details after each download" control={control} />
        </div>
      </Section>

      <Section title="Subtitles">
        <ControlledSwitch name="subs_enabled" label="Download subtitles" hint="Embed subtitles into the video when available" control={control} />

        {subsEnabled && (
          <div className="space-y-3 border-t pt-3">
            <div className="space-y-1.5">
              <Label>Preferred language</Label>
              <ControlledSelect name="subs_lang" options={SUBS_LANG_OPTIONS.map((c) => ({ value: c, label: c }))} control={control} />
            </div>
            <ControlledSwitch name="subs_auto" label="Auto-generated subtitles" hint="Include YouTube auto-translated captions" control={control} />
            <ControlledSwitch name="subs_always_ask" label="Ask language every time" control={control} />
          </div>
        )}
      </Section>

      <Section title="Network">
        <ControlledSwitch
          name="proxy_enabled"
          label="Use proxy"
          hint="Route your downloads through a proxy server"
          control={control}
        />
        {proxyEnabled && (
          <div className="space-y-1.5 border-t pt-3">
            <Label htmlFor="proxy_url">Proxy URL</Label>
            <Controller
              name="proxy_url"
              control={control}
              render={({ field }) => (
                <Input
                  id="proxy_url"
                  placeholder="socks5://user:pass@host:port or http://host:port"
                  value={field.value ?? ''}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => field.onChange(e.target.value || null)}
                />
              )}
            />
            <p className="text-xs text-muted-foreground">
              Leave blank to use the server's default proxy (if configured).
              Your URL takes priority.
            </p>
          </div>
        )}
      </Section>

      <Section title="Interface">
        <div className="space-y-3">
          <div className="space-y-2">
            <Label>Theme</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {THEME_OPTIONS.map((t) => (
                <Button
                  key={t.value}
                  variant="outline"
                  type="button"
                  onClick={() => setFlavor(t.value)}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-all h-auto',
                    flavor === t.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-muted/30 text-muted-foreground hover:border-primary/50 hover:text-foreground'
                  )}
                >
                  {t.icon}
                  {t.label}
                </Button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Saved automatically. All four variants are Catppuccin.
            </p>
          </div>

          <div className="space-y-1.5 border-t pt-3">
            <Label>Bot language</Label>
            <ControlledSelect name="language" options={LANG_OPTIONS} control={control} />
          </div>
        </div>
      </Section>

      <div className={cn(
        'sticky bottom-0 z-10 border-t bg-background/95 p-3 shadow-sm backdrop-blur transition-opacity',
        isDirty ? 'opacity-100' : 'pointer-events-none opacity-0',
      )}>
        <Button type="submit" disabled={isSubmitting || !isDirty} className="w-full sm:w-auto sm:float-right">
          {isSubmitting ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </form>
  )
}
