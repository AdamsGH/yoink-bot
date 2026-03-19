import { ShieldOff } from 'lucide-react'

import { Button } from '@/components/ui/button'

export default function UnauthorizedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 text-center">
      <ShieldOff className="h-16 w-16 text-muted-foreground" />
      <div>
        <h1 className="text-3xl font-bold">403 - Access Denied</h1>
        <p className="mt-2 text-muted-foreground">
          You don&apos;t have permission to view this page.
        </p>
      </div>
      <Button variant="outline" onClick={() => window.history.back()}>
        Go back
      </Button>
    </div>
  )
}
