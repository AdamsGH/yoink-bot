import { Refine } from '@refinedev/core'
import { NavigateToResource } from '@refinedev/react-router'
import { Navigate, Route, Routes, BrowserRouter } from 'react-router'
import { Toaster } from 'sonner'

import { authProvider } from '@/lib/auth-provider'
import { dataProvider } from '@/lib/data-provider'
import { Button } from '@/components/ui/button'
import { AppLayout } from '@/layout/AppLayout'
import { useTelegram } from '@/layout/TelegramProvider'
import SettingsPage from '@/pages/settings'
import HistoryPage from '@/pages/history'
import AdminUsersPage from '@/pages/admin/users'
import AdminGroupsPage from '@/pages/admin/groups'
import AdminCookiesPage from '@/pages/admin/cookies'
import AdminStatsPage from '@/pages/admin/stats'
import AdminNsfwPage from '@/pages/admin/nsfw'
import AdminBotSettingsPage from '@/pages/admin/bot-settings'
import UnauthorizedPage from '@/pages/unauthorized'

function AuthGate({ children }: { children: React.ReactNode }) {
  const { authState, isTelegramApp } = useTelegram()

  if (authState === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-border border-t-primary" />
          <span className="text-sm">Signing in…</span>
        </div>
      </div>
    )
  }

  if (authState === 'error') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <p className="text-base font-medium text-foreground">
            {isTelegramApp ? 'Authentication failed' : 'Open in Telegram'}
          </p>
          <p className="max-w-xs text-sm text-muted-foreground">
            {isTelegramApp
              ? 'Could not sign in. Please close and reopen the app.'
              : 'This app must be launched from the Telegram bot as a Mini App.'}
          </p>
          {isTelegramApp && (
            <Button className="mt-3" onClick={() => window.location.reload()}>
              Retry
            </Button>
          )}
        </div>
      </div>
    )
  }

  return <>{children}</>
}

function RefineApp() {
  return (
    <BrowserRouter>
      <Refine
        dataProvider={dataProvider}
        authProvider={authProvider}
        resources={[
          { name: 'settings', list: '/settings' },
          { name: 'downloads', list: '/history' },
          {
            name: 'users',
            list: '/admin/users',
            meta: { label: 'Users', roles: ['admin', 'owner'] },
          },
          {
            name: 'groups',
            list: '/admin/groups',
            meta: { label: 'Groups', roles: ['admin', 'owner'] },
          },
          {
            name: 'cookies',
            list: '/admin/cookies',
            meta: { label: 'Cookies', roles: ['admin', 'moderator', 'owner'] },
          },
          {
            name: 'stats',
            list: '/admin/stats',
            meta: { label: 'Stats', roles: ['admin', 'owner'] },
          },
          {
            name: 'nsfw',
            list: '/admin/nsfw',
            meta: { label: 'NSFW', roles: ['admin', 'owner'] },
          },
          {
            name: 'bot-settings',
            list: '/admin/bot-settings',
            meta: { label: 'Bot Settings', roles: ['admin', 'owner'] },
          },
        ]}
        options={{
          syncWithLocation: true,
          warnWhenUnsavedChanges: true,
          disableTelemetry: true,
        }}
      >
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/settings" replace />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/groups" element={<AdminGroupsPage />} />
            <Route path="/admin/cookies" element={<AdminCookiesPage />} />
            <Route path="/admin/stats" element={<AdminStatsPage />} />
            <Route path="/admin/nsfw" element={<AdminNsfwPage />} />
            <Route path="/admin/bot-settings" element={<AdminBotSettingsPage />} />
          </Route>
          <Route path="/unauthorized" element={<UnauthorizedPage />} />
          <Route path="*" element={<NavigateToResource resource="settings" />} />
        </Routes>
      </Refine>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <>
      <AuthGate>
        <RefineApp />
      </AuthGate>
      <Toaster position="top-right" richColors />
    </>
  )
}
