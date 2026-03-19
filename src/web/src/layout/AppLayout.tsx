import { useState } from 'react'
import { usePermissions } from '@refinedev/core'
import {
  BarChart2,
  Cookie,
  Download,
  Moon,
  Palette,
  Settings,
  Settings2,
  Shield,
  ShieldAlert,
  Sun,
  Users,
  UsersRound,
} from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'

import { UserPanel } from '@/components/UserPanel'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { type CatppuccinFlavor, useTelegram } from '@/layout/TelegramProvider'
import { cn } from '@/lib/utils'
import type { UserRole } from '@/types/api'

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  adminOnly?: boolean
  minRole?: UserRole[]
}

interface FlavorOption {
  value: CatppuccinFlavor
  label: string
  color: string
}

const FLAVORS: FlavorOption[] = [
  { value: 'latte',     label: 'Latte',     color: '#df8e1d' },
  { value: 'frappe',    label: 'Frappé',    color: '#85c1dc' },
  { value: 'macchiato', label: 'Macchiato', color: '#c6a0f6' },
  { value: 'mocha',     label: 'Mocha',     color: '#f38ba8' },
]

const NAV_ITEMS: NavItem[] = [
  { label: 'Settings', path: '/settings', icon: <Settings className="h-5 w-5" /> },
  { label: 'History',  path: '/history',  icon: <Download  className="h-5 w-5" /> },
  {
    label: 'Users', path: '/admin/users', icon: <Users className="h-5 w-5" />,
    adminOnly: true, minRole: ['owner', 'admin'],
  },
  {
    label: 'Groups', path: '/admin/groups', icon: <UsersRound className="h-5 w-5" />,
    adminOnly: true, minRole: ['owner', 'admin'],
  },
  {
    label: 'Cookies', path: '/admin/cookies', icon: <Cookie className="h-5 w-5" />,
    adminOnly: true, minRole: ['owner', 'admin', 'moderator'],
  },
  {
    label: 'Stats', path: '/admin/stats', icon: <BarChart2 className="h-5 w-5" />,
    adminOnly: true, minRole: ['owner', 'admin'],
  },
  {
    label: 'NSFW', path: '/admin/nsfw', icon: <ShieldAlert className="h-5 w-5" />,
    adminOnly: true, minRole: ['owner', 'admin'],
  },
  {
    label: 'Bot Settings', path: '/admin/bot-settings', icon: <Settings2 className="h-5 w-5" />,
    adminOnly: true, minRole: ['owner', 'admin'],
  },
]

const ADMIN_ROLES: UserRole[] = ['owner', 'admin', 'moderator']

function canSeeItem(item: NavItem, role: string | null): boolean {
  if (!item.adminOnly) return true
  if (!role) return false
  if (!item.minRole) return ADMIN_ROLES.includes(role as UserRole)
  return item.minRole.includes(role as UserRole)
}

interface ThemePickerProps {
  flavor: CatppuccinFlavor
  colorScheme: 'light' | 'dark'
  setFlavor: (f: CatppuccinFlavor) => void
  toggleDark: () => void
}

function ThemePicker({ flavor, colorScheme, setFlavor, toggleDark }: ThemePickerProps) {
  return (
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleDark}
        aria-label="Toggle light/dark"
        className="h-8 w-8"
      >
        {colorScheme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Choose flavor" className="h-8 w-8">
            <Palette className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuLabel className="text-xs text-muted-foreground">Flavor</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {FLAVORS.map((f) => (
            <DropdownMenuItem
              key={f.value}
              onClick={() => setFlavor(f.value)}
              className={cn('gap-2', flavor === f.value && 'text-primary font-medium')}
            >
              {/* dynamic - runtime hex from FLAVORS array */}
              <span
                className="h-3 w-3 shrink-0 rounded-full border border-border"
                style={{ backgroundColor: f.color }}
              />
              {f.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

interface AdminDrawerProps {
  open: boolean
  onClose: () => void
  items: NavItem[]
  currentPath: string
}

function AdminDrawer({ open, onClose, items, currentPath }: AdminDrawerProps) {
  const navigate = useNavigate()

  const handleNav = (path: string) => {
    void navigate(path)
    onClose()
  }

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="bottom" className="rounded-t-xl pb-8">
        <SheetHeader className="mb-4">
          <SheetTitle>Admin</SheetTitle>
        </SheetHeader>
        <div className="grid grid-cols-2 gap-2">
          {items.map((item) => (
            <Button
              key={item.path}
              variant={currentPath.startsWith(item.path) ? 'default' : 'outline'}
              className="h-auto flex-col gap-2 py-4"
              onClick={() => handleNav(item.path)}
            >
              {item.icon}
              <span className="text-xs font-medium">{item.label}</span>
            </Button>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function AppLayout() {
  const { data: role } = usePermissions<string>({ params: {} })
  const location = useLocation()
  const { colorScheme, flavor, setFlavor, toggleDark, isTelegramApp } = useTelegram()
  const [adminDrawerOpen, setAdminDrawerOpen] = useState(false)

  const visibleItems = NAV_ITEMS.filter((item) => canSeeItem(item, role ?? null))
  const adminItems = visibleItems.filter((item) => item.adminOnly)
  const isAdmin = role && ADMIN_ROLES.includes(role as UserRole)
  const isAdminPath = location.pathname.startsWith('/admin')

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r bg-background md:flex fixed top-0 left-0 h-screen overflow-y-auto z-20">
        <div className="flex h-14 items-center border-b px-4">
          <span className="font-bold text-lg">Yoink</span>
          <div className="ml-auto flex items-center gap-2">
            {!isTelegramApp && (
              <ThemePicker
                flavor={flavor}
                colorScheme={colorScheme}
                setFlavor={setFlavor}
                toggleDark={toggleDark}
              />
            )}
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-2">
          {visibleItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                )
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t p-2">
          <UserPanel />
        </div>
      </aside>

      <main className="flex-1 pb-16 md:pb-0 md:ml-56">
        <div className="mx-auto max-w-4xl px-4 py-6">
          <Outlet />
        </div>
      </main>

      {/* Mobile bottom nav  - max 4 tabs: Settings, History, Admin (drawer), Me */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex border-t bg-background md:hidden">
        {visibleItems.filter((item) => !item.adminOnly).map((item) => {
          const isActive = location.pathname.startsWith(item.path)
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                'flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs transition-colors',
                isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {item.icon}
              <span className="leading-none">{item.label}</span>
            </NavLink>
          )
        })}

        {isAdmin && (
          <Button
            variant="ghost"
            onClick={() => setAdminDrawerOpen(true)}
            className={cn(
              'flex flex-1 flex-col items-center justify-center gap-1 py-2 h-auto rounded-none text-xs transition-colors',
              isAdminPath ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Shield className="h-5 w-5" />
            <span className="leading-none">Admin</span>
          </Button>
        )}

        <UserPanel compact />
      </nav>

      {isAdmin && (
        <AdminDrawer
          open={adminDrawerOpen}
          onClose={() => setAdminDrawerOpen(false)}
          items={adminItems}
          currentPath={location.pathname}
        />
      )}
    </div>
  )
}
