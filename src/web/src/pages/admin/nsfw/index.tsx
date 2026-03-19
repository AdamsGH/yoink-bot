import { useEffect, useState } from 'react'
import { Plus, Trash2, ShieldAlert } from 'lucide-react'
import type { AxiosError } from 'axios'

import { apiClient } from '@/lib/api-client'
import { formatDate } from '@/lib/utils'
import type { NsfwDomain, NsfwKeyword, NsfwCheckResponse } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from '@/components/ui/toast'

// ── Add dialog ────────────────────────────────────────────────────────────────

interface AddDialogProps {
  open: boolean
  title: string
  fieldLabel: string
  fieldPlaceholder: string
  onClose: () => void
  onAdd: (value: string, note: string) => Promise<void>
}

function AddDialog({ open, title, fieldLabel, fieldPlaceholder, onClose, onAdd }: AddDialogProps) {
  const [value, setValue] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  const handleAdd = async () => {
    if (!value.trim()) return
    setSaving(true)
    try {
      await onAdd(value.trim(), note.trim())
      setValue('')
      setNote('')
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o: boolean) => { if (!o) { setValue(''); setNote(''); onClose() } }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>{fieldLabel}</Label>
            <Input
              placeholder={fieldPlaceholder}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label>Note (optional)</Label>
            <Input
              placeholder="e.g. added manually"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleAdd} disabled={saving || !value.trim()}>
            {saving ? 'Adding…' : 'Add'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Check panel ───────────────────────────────────────────────────────────────

function CheckPanel() {
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [result, setResult] = useState<NsfwCheckResponse | null>(null)
  const [checking, setChecking] = useState(false)

  const check = async () => {
    if (!url.trim()) return
    setChecking(true)
    setResult(null)
    try {
      const res = await apiClient.post<NsfwCheckResponse>('/nsfw/check', {
        url: url.trim(),
        title: title.trim(),
        description: description.trim(),
      })
      setResult(res.data)
    } catch {
      toast.error('Check failed')
    } finally {
      setChecking(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4" />
          Detection check
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="check-url">URL</Label>
          <Input
            id="check-url"
            placeholder="https://example.com/video/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && check()}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="check-title">Title (optional)</Label>
            <Input id="check-title" placeholder="Video title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="check-desc">Description snippet</Label>
            <Input id="check-desc" placeholder="…" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={check} disabled={checking || !url.trim()}>
            {checking ? 'Checking…' : 'Check'}
          </Button>
          {result && (
            <div className="flex items-center gap-2 text-sm">
              <Badge variant={result.is_nsfw ? 'destructive' : 'success'}>
                {result.is_nsfw ? 'NSFW' : 'clean'}
              </Badge>
              {result.reason && (
                <span className="font-mono text-xs text-muted-foreground">{result.reason}</span>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminNsfwPage() {
  const [domains, setDomains] = useState<NsfwDomain[]>([])
  const [keywords, setKeywords] = useState<NsfwKeyword[]>([])
  const [loadingD, setLoadingD] = useState(true)
  const [loadingK, setLoadingK] = useState(true)
  const [deletingD, setDeletingD] = useState<number | null>(null)
  const [deletingK, setDeletingK] = useState<number | null>(null)
  const [addDomainOpen, setAddDomainOpen] = useState(false)
  const [addKeywordOpen, setAddKeywordOpen] = useState(false)

  const loadDomains = () => {
    setLoadingD(true)
    apiClient.get<{ items: NsfwDomain[]; total: number }>('/nsfw/domains')
      .then((r) => setDomains(r.data.items))
      .catch(() => toast.error('Failed to load domains'))
      .finally(() => setLoadingD(false))
  }

  const loadKeywords = () => {
    setLoadingK(true)
    apiClient.get<{ items: NsfwKeyword[]; total: number }>('/nsfw/keywords')
      .then((r) => setKeywords(r.data.items))
      .catch(() => toast.error('Failed to load keywords'))
      .finally(() => setLoadingK(false))
  }

  useEffect(() => { loadDomains(); loadKeywords() }, [])

  const removeDomain = async (id: number) => {
    if (!confirm('Remove this domain?')) return
    setDeletingD(id)
    try {
      await apiClient.delete(`/nsfw/domains/${id}`)
      toast.success('Domain removed')
      loadDomains()
    } catch {
      toast.error('Failed to remove domain')
    } finally {
      setDeletingD(null)
    }
  }

  const removeKeyword = async (id: number) => {
    if (!confirm('Remove this keyword?')) return
    setDeletingK(id)
    try {
      await apiClient.delete(`/nsfw/keywords/${id}`)
      toast.success('Keyword removed')
      loadKeywords()
    } catch {
      toast.error('Failed to remove keyword')
    } finally {
      setDeletingK(null)
    }
  }

  const addDomain = async (domain: string, note: string) => {
    try {
      await apiClient.post('/nsfw/domains', { domain, note: note || null })
      toast.success(`Domain ${domain} added`)
      loadDomains()
    } catch (err) {
      const detail = (err as AxiosError<{ detail?: string }>)?.response?.data?.detail
      toast.error(detail ?? 'Failed to add domain')
      throw err
    }
  }

  const addKeyword = async (keyword: string, note: string) => {
    try {
      await apiClient.post('/nsfw/keywords', { keyword, note: note || null })
      toast.success(`Keyword "${keyword}" added`)
      loadKeywords()
    } catch (err) {
      const detail = (err as AxiosError<{ detail?: string }>)?.response?.data?.detail
      toast.error(detail ?? 'Failed to add keyword')
      throw err
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">NSFW</h1>

      <CheckPanel />

      {/* Domains */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>{loadingD ? '…' : domains.length} domain{domains.length !== 1 ? 's' : ''}</CardTitle>
          <Button size="sm" onClick={() => setAddDomainOpen(true)}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add domain
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {loadingD ? (
            <div className="flex justify-center py-10 text-muted-foreground">Loading…</div>
          ) : domains.length === 0 ? (
            <div className="flex justify-center py-10 text-muted-foreground">No domains</div>
          ) : (
            <>
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Domain</TableHead>
                      <TableHead>Note</TableHead>
                      <TableHead>Added</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {domains.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="font-mono text-sm">{d.domain}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{d.note ?? ' -'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{formatDate(d.created_at)}</TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive"
                            disabled={deletingD === d.id} onClick={() => removeDomain(d.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="md:hidden divide-y divide-border">
                {domains.map((d) => (
                  <div key={d.id} className="flex items-center justify-between px-4 py-3 gap-3">
                    <div className="min-w-0">
                      <p className="font-mono text-sm">{d.domain}</p>
                      {d.note && <p className="text-xs text-muted-foreground">{d.note}</p>}
                      <p className="text-xs text-muted-foreground">{formatDate(d.created_at)}</p>
                    </div>
                    <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive shrink-0"
                      disabled={deletingD === d.id} onClick={() => removeDomain(d.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Keywords */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>{loadingK ? '…' : keywords.length} keyword{keywords.length !== 1 ? 's' : ''}</CardTitle>
          <Button size="sm" onClick={() => setAddKeywordOpen(true)}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add keyword
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {loadingK ? (
            <div className="flex justify-center py-10 text-muted-foreground">Loading…</div>
          ) : keywords.length === 0 ? (
            <div className="flex justify-center py-10 text-muted-foreground">No keywords</div>
          ) : (
            <>
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Keyword</TableHead>
                      <TableHead>Note</TableHead>
                      <TableHead>Added</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {keywords.map((k) => (
                      <TableRow key={k.id}>
                        <TableCell className="font-mono text-sm">{k.keyword}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{k.note ?? ' -'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{formatDate(k.created_at)}</TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive"
                            disabled={deletingK === k.id} onClick={() => removeKeyword(k.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="md:hidden divide-y divide-border">
                {keywords.map((k) => (
                  <div key={k.id} className="flex items-center justify-between px-4 py-3 gap-3">
                    <div className="min-w-0">
                      <p className="font-mono text-sm">{k.keyword}</p>
                      {k.note && <p className="text-xs text-muted-foreground">{k.note}</p>}
                      <p className="text-xs text-muted-foreground">{formatDate(k.created_at)}</p>
                    </div>
                    <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive shrink-0"
                      disabled={deletingK === k.id} onClick={() => removeKeyword(k.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <AddDialog
        open={addDomainOpen}
        title="Add NSFW domain"
        fieldLabel="Domain"
        fieldPlaceholder="pornhub.com"
        onClose={() => setAddDomainOpen(false)}
        onAdd={addDomain}
      />
      <AddDialog
        open={addKeywordOpen}
        title="Add NSFW keyword"
        fieldLabel="Keyword"
        fieldPlaceholder="e.g. nude"
        onClose={() => setAddKeywordOpen(false)}
        onAdd={addKeyword}
      />
    </div>
  )
}
