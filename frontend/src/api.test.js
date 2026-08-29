import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock axios before importing the module under test
vi.mock('axios', () => {
  const mockPost = vi.fn()
  return {
    default: {
      create: () => ({
        post: mockPost,
        defaults: {},
      }),
    },
  }
})

const axios = (await import('axios')).default
const { verifyClaim, submitFeedback } = await import('./api.js')

describe('api helpers', () => {
  beforeEach(() => {
    axios.create().post.mockReset()
  })

  it('verifyClaim returns response data on success', async () => {
    axios.create().post.mockResolvedValue({ data: { verdict: 'TRUE' } })
    const result = await verifyClaim('some claim')
    expect(result.verdict).toBe('TRUE')
  })

  it('verifyClaim throws RATE_LIMITED with object detail spread safely', async () => {
    axios.create().post.mockRejectedValue({
      response: { status: 429, data: { detail: { retry_after: 42, message: 'rate' } } },
    })
    await expect(verifyClaim('x')).rejects.toMatchObject({
      type: 'RATE_LIMITED',
      retry_after: 42,
      message: 'rate',
    })
  })

  it('verifyClaim handles a string detail without crashing (bug fix)', async () => {
    axios.create().post.mockRejectedValue({
      response: { status: 429, data: { detail: 'Too many requests' } },
    })
    await expect(verifyClaim('x')).rejects.toMatchObject({
      type: 'RATE_LIMITED',
      message: 'Too many requests',
    })
  })

  it('submitFeedback returns true on success and false on failure', async () => {
    axios.create().post.mockResolvedValue({})
    await expect(submitFeedback('c', 'TRUE', 'UP')).resolves.toBe(true)

    axios.create().post.mockRejectedValue(new Error('boom'))
    await expect(submitFeedback('c', 'TRUE', 'UP')).resolves.toBe(false)
  })
})
