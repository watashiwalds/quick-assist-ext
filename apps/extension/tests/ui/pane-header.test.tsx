// @vitest-environment happy-dom
/** Phase 5 — PaneHeader dùng chung: tiêu đề/phụ đề (aria-live) + hành động, không đổi cấu trúc a11y. */
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { PaneHeader } from '../../src/ui/components'

afterEach(cleanup)

describe('PaneHeader', () => {
  it('render h2, phụ đề aria-live và cụm hành động', () => {
    render(
      <PaneHeader
        title="Tất cả ghi chú"
        subtitle="12 ghi chú"
        actions={<button type="button">Chọn</button>}
      >
        <p>Banner</p>
      </PaneHeader>,
    )
    expect(screen.getByRole('heading', { level: 2, name: 'Tất cả ghi chú' })).toBeTruthy()
    expect(screen.getByText('12 ghi chú').getAttribute('aria-live')).toBe('polite')
    expect(screen.getByRole('button', { name: 'Chọn' })).toBeTruthy()
    expect(screen.getByText('Banner')).toBeTruthy()
  })

  it('không render phụ đề rỗng; subtitleLive=false tắt aria-live', () => {
    const { rerender } = render(<PaneHeader title="A" subtitle="" />)
    expect(screen.queryByText('', { selector: 'p' })).toBeNull()
    rerender(<PaneHeader title="A" subtitle="ổn định" subtitleLive={false} />)
    expect(screen.getByText('ổn định').hasAttribute('aria-live')).toBe(false)
  })

  it('footer nằm sau hàng tiêu đề (hint của Tìm trong trang)', () => {
    render(<PaneHeader title="Kết quả" footer={<p>Hint</p>} />)
    const headingRow = screen.getByRole('heading', { level: 2 }).parentElement!.parentElement!
    expect(headingRow.nextElementSibling?.textContent).toBe('Hint')
  })
})
