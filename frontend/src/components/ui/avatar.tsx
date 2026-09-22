import { type HTMLAttributes } from 'react'
import { initials } from '@/lib/format'
import { cn } from '@/lib/utils'

const palettes = [
  'bg-violet-500/15 text-violet-600',
  'bg-emerald-500/15 text-emerald-600',
  'bg-amber-500/15 text-amber-600',
  'bg-rose-500/15 text-rose-600',
  'bg-sky-500/15 text-sky-600',
  'bg-fuchsia-500/15 text-fuchsia-600',
]

export function Avatar({
  name,
  src,
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { name?: string | null; src?: string | null }) {
  const paletteIdx = (name ?? '').split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % palettes.length
  return (
    <span
      className={cn(
        'inline-flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full text-sm font-semibold',
        !src && palettes[paletteIdx],
        className,
      )}
      {...props}
    >
      {src ? <img src={src} alt={name ?? ''} className="size-full object-cover" /> : <span>{initials(name ?? '?')}</span>}
    </span>
  )
}