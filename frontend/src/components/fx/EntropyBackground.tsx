'use client'

import { useEffect, useRef } from 'react'

// EntropyBackground
//
// mode="fixed"     (default) — covers the viewport, position:fixed.
//                  No effect on page scroll height. Used in the global layout.
//
// mode="page"      — covers the full scrollable page height, position:absolute.
//                  Parent must be position:relative and contain the full content.
//                  Used inside the landing page wrapper.

interface Particle {
  x: number
  y: number
  originalX: number
  originalY: number
  order: boolean
  velocity: { x: number; y: number }
  influence: number
  neighbors: Particle[]
}

function createParticle(x: number, y: number, order: boolean): Particle {
  return {
    x, y, originalX: x, originalY: y, order,
    velocity: { x: (Math.random() - 0.5) * 1.5, y: (Math.random() - 0.5) * 1.5 },
    influence: 0,
    neighbors: [],
  }
}

interface EntropyBackgroundProps {
  mode?: 'fixed' | 'page'
}

export function EntropyBackground({ mode = 'fixed' }: EntropyBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const canvas = canvasRef.current
    if (!canvas) return
    const ctxRaw = canvas.getContext('2d')
    if (!ctxRaw) return

    const cv = canvas
    const cx: CanvasRenderingContext2D = ctxRaw

    let width = 0
    let height = 0
    let particles: Particle[] = []
    let animId = 0
    let time = 0
    let lastFrame = 0

    const COLOR_ORDER = '#c3c0ff'
    const COLOR_CHAOS = '#3cddc7'

    function hexToRgba(hex: string, alpha: number): string {
      const r = parseInt(hex.slice(1, 3), 16)
      const g = parseInt(hex.slice(3, 5), 16)
      const b = parseInt(hex.slice(5, 7), 16)
      return `rgba(${r},${g},${b},${alpha})`
    }

    function buildParticles() {
      particles = []
      const spacing = 44
      const cols = Math.ceil(width / spacing)
      const rows = Math.ceil(height / spacing)
      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const x = i * spacing + spacing / 2 + (Math.random() - 0.5) * 6
          const y = j * spacing + spacing / 2 + (Math.random() - 0.5) * 6
          particles.push(createParticle(x, y, x < width * 0.55))
        }
      }
    }

    function measure() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      if (mode === 'page') {
        // Use the parent's full scrollable height (but don't let the canvas ADD height)
        const parent = cv.parentElement
        if (!parent) return
        // Temporarily hide canvas so scrollHeight is accurate
        cv.style.display = 'none'
        width  = parent.offsetWidth
        height = parent.scrollHeight
        cv.style.display = ''
      } else {
        width  = window.innerWidth
        height = window.innerHeight
      }
      cv.width  = width  * dpr
      cv.height = height * dpr
      cv.style.width  = `${width}px`
      cv.style.height = `${height}px`
      cx.scale(dpr, dpr)
      buildParticles()
    }

    function updateNeighbors() {
      particles.forEach(p => {
        p.neighbors = particles.filter(o =>
          o !== p && Math.hypot(p.x - o.x, p.y - o.y) < 90
        )
      })
    }

    function updateParticle(p: Particle) {
      if (p.order) {
        const dx = p.originalX - p.x
        const dy = p.originalY - p.y
        const chaos = { x: 0, y: 0 }
        p.neighbors.forEach(n => {
          if (!n.order) {
            const dist = Math.hypot(p.x - n.x, p.y - n.y)
            const strength = Math.max(0, 1 - dist / 90)
            chaos.x += n.velocity.x * strength
            chaos.y += n.velocity.y * strength
            p.influence = Math.max(p.influence, strength)
          }
        })
        p.x += dx * 0.04 * (1 - p.influence) + chaos.x * p.influence
        p.y += dy * 0.04 * (1 - p.influence) + chaos.y * p.influence
        p.influence *= 0.985
      } else {
        p.velocity.x += (Math.random() - 0.5) * 0.4
        p.velocity.y += (Math.random() - 0.5) * 0.4
        p.velocity.x *= 0.96
        p.velocity.y *= 0.96
        p.x += p.velocity.x
        p.y += p.velocity.y
        const m = 20
        if (p.x < m || p.x > width  - m) p.velocity.x *= -1
        if (p.y < m || p.y > height - m) p.velocity.y *= -1
        p.x = Math.max(m, Math.min(width  - m, p.x))
        p.y = Math.max(m, Math.min(height - m, p.y))
      }
    }

    function draw(now: number) {
      animId = requestAnimationFrame(draw)
      if (now - lastFrame < 50) return
      lastFrame = now

      if (time % 45 === 0) updateNeighbors()

      cx.clearRect(0, 0, width, height)

      const isLight = document.documentElement.getAttribute('data-theme') === 'light'
      const orderColor = isLight ? '#4f46e5' : COLOR_ORDER
      const chaosColor = isLight ? '#0d9488' : COLOR_CHAOS

      particles.forEach(p => {
        updateParticle(p)
        const color = p.order ? orderColor : chaosColor
        const baseAlpha = isLight ? 0.14 : 0.09

        p.neighbors.forEach(n => {
          const dist = Math.hypot(p.x - n.x, p.y - n.y)
          if (dist < 55) {
            cx.strokeStyle = hexToRgba(color, (isLight ? 0.045 : 0.03) * (1 - dist / 55))
            cx.lineWidth = 0.5
            cx.beginPath()
            cx.moveTo(p.x, p.y)
            cx.lineTo(n.x, n.y)
            cx.stroke()
          }
        })

        const alpha = p.order
          ? (baseAlpha + 0.04) * (1 - p.influence * 0.4)
          : baseAlpha + 0.03
        cx.fillStyle = hexToRgba(color, alpha)
        cx.beginPath()
        cx.arc(p.x, p.y, 1.4, 0, Math.PI * 2)
        cx.fill()
      })

      const divX = width * 0.55
      cx.strokeStyle = isLight ? 'rgba(79,70,229,0.04)' : 'rgba(195,192,255,0.03)'
      cx.lineWidth = 0.5
      cx.setLineDash([4, 10])
      cx.beginPath()
      cx.moveTo(divX, 0)
      cx.lineTo(divX, height)
      cx.stroke()
      cx.setLineDash([])

      time++
    }

    measure()

    const ro = new ResizeObserver(() => measure())
    if (mode === 'page') {
      const parent = cv.parentElement
      if (parent) ro.observe(parent)
    } else {
      ro.observe(document.documentElement)
    }

    animId = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(animId)
      ro.disconnect()
    }
  }, [mode])

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none"
      style={{
        position: mode === 'page' ? 'absolute' : 'fixed',
        top: 0,
        left: 0,
        zIndex: 1,
        // In fixed mode: viewport dimensions are set in JS
        // In page mode: height is set in JS from scrollHeight
      }}
      aria-hidden
    />
  )
}
