import { useEffect, useState } from 'react'

import { apiClient } from '@/lib/api-client'
import { formatDate } from '@/lib/utils'
import type { PaginatedResponse, User, UserRole, UserUpdateRequest } from '@/types/api'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from '@/components/ui/toast'

const ROLES: UserRole[] = ['owner', 'admin', 'moderator', 'user', 'restricted', 'banned']
const PAGE_SIZE = 30
type StatusFilter = 'all' | 'active' | 'restricted' | 'banned'

function roleBadgeVariant(role: UserRole): BadgeProps['variant'] {
  if (role === 'owner') return 'default'
  if (role === 'admin') return 'secondary'
  if (role === 'moderator') return 'outline'
  if (role === 'banned') return 'destructive'
  if (role === 'restricted') return 'warning'
  return 'outline'
}

export default function AdminUsersPage() {
  const [items, setItems] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ search: '', role: 'all' as UserRole | 'all', status: 'all' as StatusFilter })
  const [appliedFilters, setAppliedFilters] = useState(filters)
  const [selected, setSelected] = useState<User | null>(null)
  const [editRole, setEditRole] = useState<UserRole>('user')
  const [banUntil, setBanUntil] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }
    if (appliedFilters.search) params.search = appliedFilters.search
    if (appliedFilters.role !== 'all') params.role = appliedFilters.role
    if (appliedFilters.status !== 'all') params.status = appliedFilters.status

    apiClient
      .get<PaginatedResponse<User>>('/users', { params })
      .then((res) => { setItems(res.data.items); setTotal(res.data.total) })
      .catch(() => toast.error('Failed to load users'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, appliedFilters])

  const apply = () => { setPage(1); setAppliedFilters(filters) }
  const resetFilters = () => {
    const d = { search: '', role: 'all' as const, status: 'all' as const }
    setFilters(d); setPage(1); setAppliedFilters(d)
  }

  const openEdit = (user: User) => { setSelected(user); setEditRole(user.role); setBanUntil('') }

  const saveUser = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const body: UserUpdateRequest = { role: editRole }
      if (banUntil) body.ban_until = new Date(banUntil).toISOString()
      await apiClient.patch(`/users/${selected.id}`, body)
      toast.success('User updated')
      setSelected(null)
      load()
    } catch {
      toast.error('Failed to update user')
    } finally {
      setSaving(false)
    }
  }

  const quickBan = async (user: User) => {
    if (!confirm(`Ban ${user.username ?? user.id}?`)) return
    try {
      await apiClient.patch(`/users/${user.id}`, { role: 'banned' })
      toast.success('User banned')
      load()
    } catch { toast.error('Failed to ban user') }
  }

  const quickUnban = async (user: User) => {
    try {
      await apiClient.patch(`/users/${user.id}`, { role: 'user', ban_until: null })
      toast.success('User unbanned')
      load()
    } catch { toast.error('Failed to unban user') }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const hasActive = appliedFilters.search || appliedFilters.role !== 'all' || appliedFilters.status !== 'all'

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Users</h1>

      <Card>
        <CardContent className="pt-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Search by username / ID</Label>
              <Input placeholder="@username or 12345678" value={filters.search}
                onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
                onKeyDown={(e) => e.key === 'Enter' && apply()} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Role</Label>
              <Select value={filters.role} onValueChange={(v: string) => setFilters((f) => ({ ...f, role: v as UserRole | 'all' }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All roles</SelectItem>
                  {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Status</Label>
              <Select value={filters.status} onValueChange={(v: string) => setFilters((f) => ({ ...f, status: v as StatusFilter }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="restricted">Restricted</SelectItem>
                  <SelectItem value="banned">Banned</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <Button size="sm" onClick={apply}>Apply</Button>
            {hasActive && <Button size="sm" variant="outline" onClick={resetFilters}>Clear</Button>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            {total.toLocaleString()} user{total !== 1 ? 's' : ''}
            {hasActive && <span className="ml-2 text-sm font-normal text-muted-foreground">(filtered)</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-12 text-muted-foreground">Loading…</div>
          ) : items.length === 0 ? (
            <div className="flex justify-center py-12 text-muted-foreground">No users found</div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>ID</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Joined</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <p className="text-sm font-medium">{user.first_name ?? ' -'}</p>
                          {user.username && <p className="text-xs text-muted-foreground">@{user.username}</p>}
                        </TableCell>
                        <TableCell className="font-mono text-xs">{user.id}</TableCell>
                        <TableCell><Badge variant={roleBadgeVariant(user.role)}>{user.role}</Badge></TableCell>
                        <TableCell className="text-xs text-muted-foreground">{formatDate(user.created_at)}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" onClick={() => openEdit(user)}>Edit</Button>
                            {user.role === 'banned' ? (
                              <Button variant="ghost" size="sm" className="text-green-600 hover:text-green-700" onClick={() => quickUnban(user)}>Unban</Button>
                            ) : user.role !== 'owner' ? (
                              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => quickBan(user)}>Ban</Button>
                            ) : null}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden divide-y divide-border">
                {items.map((user) => (
                  <div key={user.id} className="px-4 py-3 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{user.first_name ?? ' -'}</p>
                        <p className="text-xs text-muted-foreground font-mono">{user.id}{user.username && ` · @${user.username}`}</p>
                      </div>
                      <Badge variant={roleBadgeVariant(user.role)} className="shrink-0">{user.role}</Badge>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" className="flex-1" onClick={() => openEdit(user)}>Edit</Button>
                      {user.role === 'banned' ? (
                        <Button variant="outline" size="sm" className="flex-1 text-green-600 border-green-600/30" onClick={() => quickUnban(user)}>Unban</Button>
                      ) : user.role !== 'owner' ? (
                        <Button variant="outline" size="sm" className="flex-1 text-destructive border-destructive/30" onClick={() => quickBan(user)}>Ban</Button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
          </div>
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={(open: boolean) => !open && setSelected(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit user #{selected?.id}</DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium">{selected.first_name}</p>
                {selected.username && <p className="text-xs text-muted-foreground">@{selected.username}</p>}
              </div>
              <div className="space-y-1.5">
                <Label>Role</Label>
                <Select value={editRole} onValueChange={(v: string) => setEditRole(v as UserRole)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ban-until">Temporary ban until (optional)</Label>
                <Input id="ban-until" type="datetime-local" value={banUntil} onChange={(e) => setBanUntil(e.target.value)} />
                <p className="text-xs text-muted-foreground">Leave blank to use role only.</p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>Cancel</Button>
            <Button onClick={saveUser} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
