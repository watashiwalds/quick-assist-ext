// @vitest-environment happy-dom
/** Phase 5 — GroupSection là button thật: mở/đóng được bằng bàn phím, có aria-expanded/controls. */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { GroupSection } from '../../src/ui/components'

afterEach(cleanup)

const renderGroup = (collapsed = false, onToggle = vi.fn()) =>
  render(
    <GroupSection label="a.vn" count={2} summary="Tóm tắt nhóm" collapsed={collapsed} onToggle={onToggle}>
      <p>Nội dung nhóm</p>
    </GroupSection>,
  )

describe('GroupSection', () => {
  it('header là <button> có aria-expanded/aria-controls trỏ đúng body', () => {
    renderGroup()
    const toggle = screen.getByRole('button', { name: /a\.vn/ })
    expect(toggle.tagName).toBe('BUTTON')
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    const bodyId = toggle.getAttribute('aria-controls')
    expect(bodyId).toBeTruthy()
    expect(screen.getByText('Nội dung nhóm').parentElement?.id).toBe(bodyId)
    expect(screen.getByText('Tóm tắt nhóm')).toBeTruthy()
  })

  it('bấm header gọi onToggle; khi collapsed body bị ẩn và aria-expanded=false', () => {
    const onToggle = vi.fn()
    const { rerender } = renderGroup(false, onToggle)
    fireEvent.click(screen.getByRole('button', { name: /a\.vn/ }))
    expect(onToggle).toHaveBeenCalledTimes(1)

    rerender(
      <GroupSection label="a.vn" count={2} collapsed onToggle={onToggle}>
        <p>Nội dung nhóm</p>
      </GroupSection>,
    )
    const toggle = screen.getByRole('button', { name: /a\.vn/ })
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(screen.getByText('Nội dung nhóm').parentElement?.hidden).toBe(true)
  })

  it('section có tên truy cập theo nguồn (role region)', () => {
    renderGroup()
    expect(screen.getByRole('region', { name: 'Nguồn a.vn' })).toBeTruthy()
  })
})
