/** Hook dùng chung cho UI: gọi RPC với trạng thái loading/error/data chuẩn. */
import { useCallback, useEffect, useRef, useState } from 'react'
import { type SerializedError, toSerialized } from '@/shared/errors'
import { onBroadcast } from '@/shared/messaging/client'
import type { BroadcastEvent } from '@/shared/messaging/protocol'

export interface AsyncState<T> {
  data: T | undefined
  error: SerializedError | undefined
  loading: boolean
  reload: () => Promise<void>
  setData: (d: T) => void
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<SerializedError>()
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn
  const seq = useRef(0)

  const reload = useCallback(async () => {
    const my = ++seq.current // bỏ kết quả của lần gọi cũ về muộn (đổi thư mục nhanh)
    setLoading(true)
    setError(undefined)
    try {
      const d = await fnRef.current()
      if (my === seq.current) setData(d)
    } catch (e) {
      if (my === seq.current) setError(toSerialized(e))
    } finally {
      if (my === seq.current) setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => void reload(), deps)
  return { data, error, loading, reload, setData }
}

/** Thao tác ghi (lưu/xoá…): busy + lỗi chuẩn hoá; trả undefined nếu lỗi. */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<SerializedError>()
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true)
    setError(undefined)
    try {
      return await fn()
    } catch (e) {
      setError(toSerialized(e))
      return undefined
    } finally {
      setBusy(false)
    }
  }, [])
  return { busy, error, run, clearError: () => setError(undefined) }
}

export function useBroadcast(handler: (e: BroadcastEvent) => void): void {
  const ref = useRef(handler)
  ref.current = handler
  useEffect(() => onBroadcast((e) => ref.current(e)), [])
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}
