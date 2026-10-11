// @vitest-environment jsdom
import { act, useEffect, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DisplayErrorBoundary } from './ErrorBoundary'

let root: Root | null = null
let container: HTMLDivElement | null = null

function render(ui: ReactNode) {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  act(() => root?.render(ui))
  return container
}

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
  vi.restoreAllMocks()
})

describe('DisplayErrorBoundary', () => {
  it('catches a child rendering exception and shows an operator-friendly fallback', () => {
    const expectedError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    function BrokenDisplay(): never { throw new Error('render failure') }

    const screen = render(<DisplayErrorBoundary scope="3D digital twin"><BrokenDisplay /></DisplayErrorBoundary>)

    expect(screen.querySelector('[role="alert"]')?.textContent).toContain('3D digital twin could not be displayed')
    expect(screen.querySelector('[role="alert"]')?.textContent).toContain('may still be operating')
    expect(expectedError).toHaveBeenCalled()
  })

  it('provides labeled keyboard-accessible recovery controls and moves focus to the fallback', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    function BrokenDisplay(): never { throw new Error('render failure') }

    const screen = render(<DisplayErrorBoundary scope="Traffic analytics dashboard"><BrokenDisplay /></DisplayErrorBoundary>)
    const retry = screen.querySelector('button')
    const reload = screen.querySelector('button.secondary')
    const heading = screen.querySelector('h2')

    expect(retry?.textContent).toBe('Retry display')
    expect(reload?.textContent).toBe('Reload application')
    expect(heading?.tabIndex).toBe(-1)
    expect(document.activeElement).toBe(heading)
  })

  it('recovers by remounting the failed display only after Retry display is chosen', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    let shouldThrow = true
    function RecoverableDisplay() {
      if (shouldThrow) throw new Error('render failure')
      return <p>Recovered display</p>
    }

    const screen = render(<DisplayErrorBoundary scope="2D traffic map"><RecoverableDisplay /></DisplayErrorBoundary>)
    shouldThrow = false
    act(() => screen.querySelector('button')?.dispatchEvent(new MouseEvent('click', { bubbles: true })))

    expect(screen.textContent).toContain('Recovered display')
    expect(screen.querySelector('[role="alert"]')).toBeNull()
  })

  it('keeps a healthy sibling display mounted when another boundary fails', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    function BrokenDisplay(): never { throw new Error('map failure') }
    let healthyMounts = 0
    function HealthyDisplay() { useEffect(() => { healthyMounts += 1 }, []); return <p>Healthy analytics</p> }

    const screen = render(<><DisplayErrorBoundary scope="2D traffic map"><BrokenDisplay /></DisplayErrorBoundary><DisplayErrorBoundary scope="Traffic analytics dashboard"><HealthyDisplay /></DisplayErrorBoundary></>)

    expect(screen.textContent).toContain('2D traffic map could not be displayed')
    expect(screen.textContent).toContain('Healthy analytics')
    expect(healthyMounts).toBe(1)
  })

  it('does not invoke a control request while handling or retrying a display failure', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const controlRequest = vi.fn()
    let shouldThrow = true
    function RecoverableDisplay() {
      if (shouldThrow) throw new Error('render failure')
      return <button onClick={controlRequest}>Apply signal timing</button>
    }

    const screen = render(<DisplayErrorBoundary scope="3D digital twin"><RecoverableDisplay /></DisplayErrorBoundary>)
    shouldThrow = false
    act(() => screen.querySelector('button')?.dispatchEvent(new MouseEvent('click', { bubbles: true })))

    expect(controlRequest).not.toHaveBeenCalled()
  })

  it('keeps the enclosing connection owner mounted through a child recovery', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    let ownerMounts = 0
    let ownerCleanups = 0
    let shouldThrow = true
    function ConnectionOwner({ children }: { children: ReactNode }) {
      useEffect(() => { ownerMounts += 1; return () => { ownerCleanups += 1 } }, [])
      return <>{children}</>
    }
    function RecoverableDisplay() {
      if (shouldThrow) throw new Error('render failure')
      return <p>Recovered display</p>
    }

    const screen = render(<ConnectionOwner><DisplayErrorBoundary scope="3D digital twin"><RecoverableDisplay /></DisplayErrorBoundary></ConnectionOwner>)
    shouldThrow = false
    act(() => screen.querySelector('button')?.dispatchEvent(new MouseEvent('click', { bubbles: true })))

    expect(ownerMounts).toBe(1)
    expect(ownerCleanups).toBe(0)
  })

  it('cleans up a failed child before remounting it after retry', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    let shouldThrow = false
    let mounts = 0
    let cleanups = 0
    function RecoverableDisplay() {
      useEffect(() => { mounts += 1; return () => { cleanups += 1 } }, [])
      if (shouldThrow) throw new Error('render failure')
      return <p>Healthy display</p>
    }

    const screen = render(<DisplayErrorBoundary scope="Traffic analytics dashboard"><RecoverableDisplay /></DisplayErrorBoundary>)
    shouldThrow = true
    act(() => root?.render(<DisplayErrorBoundary scope="Traffic analytics dashboard"><RecoverableDisplay /></DisplayErrorBoundary>))
    shouldThrow = false
    act(() => screen.querySelector('button')?.dispatchEvent(new MouseEvent('click', { bubbles: true })))

    expect(mounts).toBe(2)
    expect(cleanups).toBe(1)
  })
})
