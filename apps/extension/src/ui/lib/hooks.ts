/** Hook dùng chung cho UI: gọi RPC với trạng thái loading/error/data chuẩn. */
import { useCallback, useEffect, useRef, useState } from 'react'
import { onBroadcast } from '@/shared/messaging/client'
import type { BroadcastEvent } from '@/shared/messaging/protocol'
import { AppError, type SerializedError } from '@/shared/errors'

export interface AsyncState<T> {
  data: T | undefined
  error: SerializedError | undefined
  loading: boolean
  reload: () => Promise<void>
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<SerializedError>()
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setData(await fnRef.current())
    } catch (e) {
      setError(e instanceof AppError ? e.toJSON() : { code: 'UNKNOWN', message: String(e), status: 0 })
    } finally {
      setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => void reload(), deps)
  return { data, error, loading, reload }
}

export function useBroadcast(handler: (e: BroadcastEvent) => void): void {
  const ref = useRef(handler)
  ref.current = handler
  useEffect(() => onBroadcast((e) => ref.current(e)), [])
}
