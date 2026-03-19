import { useRef, useEffect, useState } from 'react'
import { Trash2, Upload } from 'lucide-react'
import type { AxiosError } from 'axios'
import { useGetIdentity } from '@refinedev/core'

import { apiClient } from '@/lib/api-client'
import { formatDate } from '@/lib/utils'
import type { Cookie } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from '@/components/ui/toast'

type Identity = { id: number; role: string }

function parseDomainFromNetscape(content: string): string | null {
  for (const line of content.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const parts = trimmed.split('\t')
    if (parts.length >= 7) {
      // field 0 is the domain, strip leading dot
      return parts[0].replace(/^\./, '')
    }
  }
  return null
}

export default function AdminCookiesPage() {
  const { data: identity } = useGetIdentity<Identity>()

  const [items, setItems] = useState<Cookie[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<number | null>(null)

  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadContent, setUploadContent] = useState('')
  const [uploadDomain, setUploadDomain] = useState('')
  const [uploadUserId, setUploadUserId] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setLoading(true)
    apiClient
      .get<{ items: Cookie[] }>('/cookies/all')
      .then((res) => setItems(res.data.items))
      .catch(() => toast.error('Failed to load cookies'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  // Pre-fill user_id from JWT when dialog opens
  useEffect(() => {
    if (uploadOpen && identity?.id && !uploadUserId) {
      setUploadUserId(String(identity.id))
    }
  }, [uploadOpen, identity])

  const remove = async (id: number) => {
    if (!confirm('Delete this cookie?')) return
    setDeleting(id)
    try {
      await apiClient.delete(`/cookies/${id}`)
      toast.success('Cookie deleted')
      load()
    } catch {
      toast.error('Failed to delete cookie')
    } finally {
      setDeleting(null)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadFile(file)

    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result as string
      setUploadContent(text)
      const domain = parseDomainFromNetscape(text)
      if (domain) setUploadDomain(domain)
    }
    reader.readAsText(file)
  }

  const handleUpload = async () => {
    if (!uploadContent) { toast.error('Select a file first'); return }
    if (!uploadDomain) { toast.error('Domain is required'); return }
    const uid = parseInt(uploadUserId, 10)
    if (!uid) { toast.error('User ID is required'); return }

    setUploading(true)
    try {
      await apiClient.post('/cookies', {
        user_id: uid,
        domain: uploadDomain,
        content: uploadContent,
      })
      toast.success(`Cookie uploaded for ${uploadDomain}`)
      setUploadOpen(false)
      resetUpload()
      load()
    } catch (err) {
      const detail = (err as AxiosError<{ detail?: string }>)?.response?.data?.detail
      toast.error(detail ?? 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const resetUpload = () => {
    setUploadFile(null)
    setUploadContent('')
    setUploadDomain('')
    setUploadUserId(identity?.id ? String(identity.id) : '')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Cookies</h1>
        <Button onClick={() => setUploadOpen(true)}>
          <Upload className="mr-2 h-4 w-4" />
          Upload cookie
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{items.length} cookie{items.length !== 1 ? 's' : ''}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-12 text-muted-foreground">Loading…</div>
          ) : items.length === 0 ? (
            <div className="flex justify-center py-12 text-muted-foreground">No cookies stored</div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Domain</TableHead>
                      <TableHead>User ID</TableHead>
                      <TableHead>Valid</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((cookie) => (
                      <TableRow key={cookie.id}>
                        <TableCell className="font-medium">{cookie.domain}</TableCell>
                        <TableCell className="font-mono text-xs">{cookie.user_id}</TableCell>
                        <TableCell>
                          <Badge variant={cookie.is_valid ? 'success' : 'destructive'}>
                            {cookie.is_valid ? 'valid' : 'invalid'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(cookie.updated_at)}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost" size="icon"
                            className="text-destructive hover:text-destructive"
                            disabled={deleting === cookie.id}
                            onClick={() => remove(cookie.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden divide-y divide-border">
                {items.map((cookie) => (
                  <div key={cookie.id} className="flex items-center justify-between px-4 py-3 gap-3">
                    <div className="min-w-0 space-y-0.5">
                      <p className="text-sm font-medium">{cookie.domain}</p>
                      <p className="font-mono text-xs text-muted-foreground">uid: {cookie.user_id}</p>
                      <div className="flex items-center gap-2 pt-0.5">
                        <Badge variant={cookie.is_valid ? 'success' : 'destructive'} className="text-xs">
                          {cookie.is_valid ? 'valid' : 'invalid'}
                        </Badge>
                        <span className="text-xs text-muted-foreground">{formatDate(cookie.updated_at)}</span>
                      </div>
                    </div>
                    <Button
                      variant="ghost" size="icon"
                      className="text-destructive hover:text-destructive shrink-0"
                      disabled={deleting === cookie.id}
                      onClick={() => remove(cookie.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={uploadOpen} onOpenChange={(open: boolean) => { setUploadOpen(open); if (!open) resetUpload() }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Upload Netscape cookie file</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* File picker */}
            <div className="space-y-1.5">
              <Label>Cookie file (.txt)</Label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,text/plain"
                className="hidden"
                onChange={handleFileChange}
              />
              <div
                className="flex cursor-pointer items-center gap-3 rounded-md border border-dashed px-4 py-3 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4 shrink-0" />
                {uploadFile ? uploadFile.name : 'Click to select file…'}
              </div>
            </div>

            {/* Domain  - auto-filled from file */}
            <div className="space-y-1.5">
              <Label htmlFor="cookie-domain">Domain</Label>
              <Input
                id="cookie-domain"
                placeholder="youtube.com"
                value={uploadDomain}
                onChange={(e) => setUploadDomain(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Auto-detected from the file. Edit if incorrect.
              </p>
            </div>

            {/* User ID */}
            <div className="space-y-1.5">
              <Label htmlFor="cookie-uid">User ID</Label>
              <Input
                id="cookie-uid"
                type="number"
                placeholder="123456789"
                value={uploadUserId}
                onChange={(e) => setUploadUserId(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Telegram user ID this cookie belongs to.
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={uploading || !uploadFile}
            >
              {uploading ? 'Uploading…' : 'Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
