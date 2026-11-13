/**
 * Lịch sử hội thoại theo phiên cho tab "Hỏi AI" (X02) — bọc quanh `useChat` (giữ nguyên in-memory).
 *
 * Chiến lược ghi (điểm dễ sai):
 *  - KHÔNG ghi mỗi delta khi stream. Chỉ ghi khi "mốc" hội thoại đổi: gửi câu hỏi (thêm 2 tin nhắn),
 *    câu trả lời kết thúc (done/stopped/error), và flush qua `pagehide` khi đóng panel.
 *  - `signature` = độ dài mảng + id/status tin nhắn cuối; delta chỉ đổi text nên không kích hoạt ghi.
 *  - Đóng panel giữa stream: lần flush cuối lưu phần text đã nhận; khi khôi phục → `stopped`.
 *
 * Tầng dữ liệu (kiểu + hàm thuần ở `shared/chat`, storage ở `shared/storage/chat-sessions`) dùng lại
 * được cho vòng redesign UI sau; view chỉ cần gọi `switchSession`/`newSession`. UI đọc/ghi qua RPC
 * `chatSessions/*` — background sở hữu key (luật phân tầng extension).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChatMessageItem, ChatSession } from '@/shared/chat'
import { capMessages, evictSessions, firstQuestion, newSessionId, normalizeRestored, sessionTitle } from '@/shared/chat'
import { rpc } from '@/shared/messaging/client'
import { type ChatState, useChat } from './useChat'

export interface ChatSessionsState extends ChatState {
  /** Mới nhất đứng đầu; phiên đang mở luôn ở đầu sau mỗi lần ghi. */
  sessions: ChatSession[]
  activeId: string | null
  /** Đã đọc xong storage chưa — tránh ghi đè bằng mảng rỗng lúc mount. */
  ready: boolean
  switchSession: (id: string) => void
  newSession: () => void
  /** Đổi tên phiên (gộp khoảng trắng, cắt `SESSION_TITLE_MAX`); phiên đang mở vẫn giữ tên mới khi ghi. */
  renameSession: (id: string, title: string) => void
  /** Xoá một phiên; xoá phiên đang mở → mở phiên mới nhất còn lại (hoặc "Cuộc trò chuyện mới"). */
  deleteSession: (id: string) => void
  /** Xoá toàn bộ lịch sử lưu trên máy này (đưa về hội thoại mới). */
  clearSessions: () => void
  /** Ghi ngay hội thoại hiện tại (gọi từ `pagehide` khi đóng panel). */
  flush: () => void
}

/** Mốc thay đổi cấu trúc hội thoại — delta không làm đổi chuỗi này. */
function signatureOf(messages: ChatMessageItem[]): string {
  const last = messages.at(-1)
  return `${messages.length}:${last?.id ?? ''}:${last?.status ?? ''}`
}

export function useChatSessions(): ChatSessionsState {
  const chat = useChat()
  const chatRef = useRef(chat)
  chatRef.current = chat

  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const sessionsRef = useRef(sessions)
  sessionsRef.current = sessions
  const activeIdRef = useRef(activeId)
  activeIdRef.current = activeId
  const signatureRef = useRef('')
  /** Đọc kho thất bại → tạm khoá ghi để không xoá mất lịch sử cũ bằng mảng rỗng. */
  const persistRef = useRef(true)

  /** Cập nhật state + ref đồng bộ rồi ghi storage (ref đồng bộ để lần ghi kế tiếp không dùng dữ liệu cũ). */
  const apply = useCallback((nextSessions: ChatSession[], nextActiveId: string | null) => {
    const capped = evictSessions(nextSessions)
    sessionsRef.current = capped
    activeIdRef.current = nextActiveId
    setSessions(capped)
    setActiveId(nextActiveId)
    if (persistRef.current) void rpc('chatSessions/save', { sessions: capped, activeId: nextActiveId }).catch(() => undefined)
  }, [])

  /**
   * Gộp hội thoại đang mở vào danh sách phiên (không ghi storage — để switch/new ghi đúng 1 lần).
   * Phiên chưa có id (vừa "Cuộc trò chuyện mới") được tạo ở lần ghi đầu tiên — không sinh phiên rỗng.
   */
  const merge = useCallback((messages: ChatMessageItem[], folderId: string | null, sessionId: string | null) => {
    const msgs = capMessages(messages)
    let next = sessionsRef.current
    let nextActive = sessionId

    if (msgs.length > 0) {
      const now = Date.now()
      const existing = nextActive ? next.find((s) => s.id === nextActive) : undefined
      if (!nextActive) nextActive = newSessionId()
      const updated: ChatSession = {
        id: nextActive,
        title: existing?.title || sessionTitle(firstQuestion(msgs)),
        messages: msgs,
        folderId,
        createdAt: existing?.createdAt ?? now,
        updatedAt: now,
      }
      next = [updated, ...next.filter((s) => s.id !== nextActive)]
    }

    return { sessions: next, activeId: nextActive }
  }, [])

  /** Chốt hội thoại đang mở vào danh sách phiên rồi ghi storage. */
  const commit = useCallback(
    (messages = chatRef.current.messages, folderId = chatRef.current.folderId) => {
      const merged = merge(messages, folderId, activeIdRef.current)
      apply(merged.sessions, merged.activeId)
    },
    [apply, merge],
  )

  // Nạp lịch sử một lần lúc mount. Không ghi lại ngay sau khi nạp (signatureRef = mốc vừa nạp).
  useEffect(() => {
    let cancelled = false
    void rpc('chatSessions/load')
      .then((store) => {
        if (cancelled) return
        const active = store.sessions.find((s) => s.id === store.activeId)
        sessionsRef.current = store.sessions
        activeIdRef.current = store.activeId
        setSessions(store.sessions)
        setActiveId(store.activeId)
        if (active) {
          const restored = normalizeRestored(active.messages)
          signatureRef.current = signatureOf(restored)
          chatRef.current.replace(restored, active.folderId)
        }
        setReady(true)
      })
      .catch(() => {
        if (cancelled) return
        persistRef.current = false
        setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Ghi ở các mốc: gửi câu hỏi (mảng +2, tin cuối streaming), kết thúc trả lời (status đổi).
  const signature = signatureOf(chat.messages)
  useEffect(() => {
    if (!ready || signature === signatureRef.current) return
    signatureRef.current = signature
    commit()
  }, [signature, ready, commit])

  const flush = useCallback(() => {
    if (!ready) return
    commit()
  }, [commit, ready])

  const switchSession = useCallback(
    (id: string) => {
      if (!ready || id === activeIdRef.current) return
      const target = sessionsRef.current.find((s) => s.id === id)
      if (!target) return

      // Chốt phần đã nhận vào phiên cũ; `replace()` dừng stream đang chạy trước khi nạp phiên mới.
      const streaming = chatRef.current.streaming
      const frozen = streaming ? normalizeRestored(chatRef.current.messages) : chatRef.current.messages
      const merged = merge(frozen, chatRef.current.folderId, activeIdRef.current)

      const restored = normalizeRestored(target.messages)
      chatRef.current.replace(restored, target.folderId)
      signatureRef.current = signatureOf(restored)
      apply(merged.sessions, id)
    },
    [apply, merge, ready],
  )

  const newSession = useCallback(() => {
    if (!ready) return
    // `reset()` dừng stream đang chạy; chốt phần đã nhận vào phiên cũ trước khi xoá hội thoại.
    const streaming = chatRef.current.streaming
    const frozen = streaming ? normalizeRestored(chatRef.current.messages) : chatRef.current.messages
    const merged = merge(frozen, chatRef.current.folderId, activeIdRef.current)

    chatRef.current.reset()
    signatureRef.current = signatureOf([])
    apply(merged.sessions, null)
  }, [apply, merge, ready])

  /**
   * Đổi tên phiên. Chỉ sửa state cục bộ rồi ghi qua `chatSessions/save` (một đường ghi duy nhất);
   * `merge()` giữ `existing.title` nên lần ghi kế tiếp của phiên đang mở không trả lại tên cũ.
   * Tên rỗng bị bỏ qua — UI đã khoá nút Lưu, đây là chốt chặn ở tầng dữ liệu.
   */
  const renameSession = useCallback(
    (id: string, title: string) => {
      if (!ready || !title.trim()) return
      if (!sessionsRef.current.some((s) => s.id === id)) return
      const clean = sessionTitle(title)
      apply(
        sessionsRef.current.map((s) => (s.id === id ? { ...s, title: clean } : s)),
        activeIdRef.current,
      )
    },
    [apply, ready],
  )

  /**
   * Xoá một phiên. Xoá phiên đang mở: dừng stream (nếu có), mở phiên mới nhất còn lại hoặc về
   * "Cuộc trò chuyện mới" — không tự gửi lại câu hỏi.
   */
  const deleteSession = useCallback(
    (id: string) => {
      if (!ready) return
      const remaining = sessionsRef.current.filter((s) => s.id !== id)
      if (remaining.length === sessionsRef.current.length) return

      if (id !== activeIdRef.current) {
        apply(remaining, activeIdRef.current)
        return
      }

      const next = remaining[0]
      if (next) {
        const restored = normalizeRestored(next.messages)
        chatRef.current.replace(restored, next.folderId)
        signatureRef.current = signatureOf(restored)
        apply(remaining, next.id)
      } else {
        chatRef.current.reset()
        signatureRef.current = signatureOf([])
        apply([], null)
      }
    },
    [apply, ready],
  )

  /** Xoá toàn bộ lịch sử trên máy này: dừng stream, đưa hội thoại về trạng thái mới, ghi mảng rỗng. */
  const clearSessions = useCallback(() => {
    if (!ready) return
    chatRef.current.reset()
    signatureRef.current = signatureOf([])
    apply([], null)
  }, [apply, ready])

  return { ...chat, sessions, activeId, ready, switchSession, newSession, renameSession, deleteSession, clearSessions, flush }
}
