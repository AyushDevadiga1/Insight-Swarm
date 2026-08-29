import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useApiStatusStore, STATUS_META, PROVIDER_META } from './useApiStatusStore'

describe('useApiStatusStore', () => {
  beforeEach(() => {
    useApiStatusStore.setState({
      providers: {},
      lastChecked: null,
      isLoading: false,
      error: null,
      _pollTimer: null,
      _consecutiveFailures: 0,
    })
  })

  afterEach(() => {
    useApiStatusStore.getState().stopPolling()
  })

  it('has status and provider metadata', () => {
    expect(STATUS_META.healthy.label).toBe('Healthy')
    expect(PROVIDER_META.groq.displayName).toBe('Groq')
  })

  it('getErrorContext summarises broken providers only', () => {
    useApiStatusStore.setState({
      providers: {
        groq: { status: 'healthy' },
        gemini: { status: 'rate_limited' },
        tavily: { status: 'no_key' },
      },
    })
    const ctx = useApiStatusStore.getState().getErrorContext()
    expect(ctx).toContain('Gemini: Rate Limited')
    expect(ctx).not.toContain('Tavily')
    expect(ctx).not.toContain('Groq')
  })

  it('hasPrimaryProvider is true when groq or gemini is healthy', () => {
    useApiStatusStore.setState({ providers: { gemini: { status: 'healthy' } } })
    expect(useApiStatusStore.getState().hasPrimaryProvider()).toBe(true)
    useApiStatusStore.setState({ providers: { gemini: { status: 'no_key' } } })
    expect(useApiStatusStore.getState().hasPrimaryProvider()).toBe(false)
  })

  it('fetchStatus updates providers on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ groq: { status: 'healthy' } }),
    })
    await useApiStatusStore.getState().fetchStatus()
    const s = useApiStatusStore.getState()
    expect(s.providers.groq.status).toBe('healthy')
    expect(s.isLoading).toBe(false)
    expect(s._consecutiveFailures).toBe(0)
  })

  it('fetchStatus records an error on failure and stops on HTTP error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 })
    await useApiStatusStore.getState().fetchStatus()
    const s = useApiStatusStore.getState()
    expect(s.error).toContain('500')
    expect(s._consecutiveFailures).toBe(1)
  })
})
