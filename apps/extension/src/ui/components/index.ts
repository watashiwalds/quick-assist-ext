/**
 * Design system (task A05 — owner UI/UX). Mọi màn hình dùng chung các component này để trạng
 * thái loading/empty/error nhất quán (NFR khả năng sử dụng). Màu chỉ lấy từ token trong styles.css;
 * độ tương phản token được kiểm tra tự động (tests/contrast.test.ts — WCAG AA).
 */
export { Button } from './Button'
export { ConfidenceBadge } from './ConfidenceBadge'
export { Field, Input, Select, TextArea } from './Form'
export { GroupSection } from './GroupSection'
export { Icon, type IconName } from './Icon'
export { ConfirmDialog, Modal } from './Modal'
export { PaneHeader } from './PaneHeader'
export { Banner, EmptyState, ErrorState, ProgressBar, Spinner, StatusBadge } from './State'
export { type TabItem, Tabs } from './Tabs'
export { ToastProvider, useToast } from './Toast'
