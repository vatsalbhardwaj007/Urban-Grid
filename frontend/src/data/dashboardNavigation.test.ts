import { describe, expect, it } from 'vitest'
import { dashboardHash, dashboardScreenFromHash } from './dashboardNavigation'

describe('analytics navigation', () => {
  it('uses a URL hash for back-navigation without a routing dependency', () => {
    expect(dashboardScreenFromHash('#analytics')).toBe('analytics')
    expect(dashboardScreenFromHash('')).toBe('live')
    expect(dashboardHash('analytics')).toBe('#analytics')
  })
})
