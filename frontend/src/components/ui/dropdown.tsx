import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

export function DropdownMenu({
  trigger,
  children,
  align = 'end',
}: {
  trigger: ReactNode
  children: ReactNode | ((close: () => void) => ReactNode)
  align?: 'start' | 'end'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current?.contains(e.target as Node) || triggerRef.current?.contains(e.target as Node)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <>
      <div ref={triggerRef} onClick={() => setOpen((o) => !o)} className="inline-flex">
        {trigger}
      </div>
      {open &&
        createPortal(
          <div className="fixed inset-0 z-40" onMouseDown={() => setOpen(false)} />,
          document.body,
        )}
      {open &&
        createPortal(
          <div
            ref={ref}
            role="menu"
            className={cn(
              'fixed z-50 min-w-44 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg',
              align === 'end' ? 'right-2' : 'left-2',
            )}
            style={{
              top: (triggerRef.current?.getBoundingClientRect().bottom ?? 0) + 4,
            }}
          >
            {typeof children === 'function' ? children(() => setOpen(false)) : children}
          </div>,
          document.body,
        )}
    </>
  )
}

export function DropdownItem({
  onClick,
  children,
  danger,
  className,
}: {
  onClick?: () => void
  children: ReactNode
  danger?: boolean
  className?: string
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm hover:bg-accent',
        danger && 'text-destructive hover:bg-destructive/10',
        className,
      )}
    >
      {children}
    </button>
  )
}