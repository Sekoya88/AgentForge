'use client'

import { useScrollReveal } from '@/hooks/useScrollReveal'
import { useReducedMotion } from '@/hooks/useReducedMotion'

interface ScrollRevealProps {
  children: React.ReactNode
  className?: string
  delay?: number
  direction?: 'up' | 'left' | 'none'
}

export function ScrollReveal({
  children,
  className = '',
  delay = 0,
  direction = 'up',
}: ScrollRevealProps) {
  const [ref, visible] = useScrollReveal<HTMLDivElement>({ threshold: 0.12 })
  const reduced = useReducedMotion()

  const baseStyle: React.CSSProperties = {
    transitionDelay: delay ? `${delay}ms` : undefined,
  }

  if (reduced) {
    return <div className={className}>{children}</div>
  }

  const hiddenTransform =
    direction === 'up' ? 'translateY(24px)' :
    direction === 'left' ? 'translateX(-16px)' :
    'none'

  const style: React.CSSProperties = {
    ...baseStyle,
    opacity: visible ? 1 : 0,
    transform: visible ? 'none' : hiddenTransform,
    transition: `opacity 0.55s cubic-bezier(0.22,1,0.36,1), transform 0.55s cubic-bezier(0.22,1,0.36,1)`,
    willChange: visible ? 'auto' : 'opacity, transform',
  }

  return (
    <div ref={ref} className={className} style={style}>
      {children}
    </div>
  )
}
