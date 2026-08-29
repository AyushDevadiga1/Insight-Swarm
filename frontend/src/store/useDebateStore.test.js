import { describe, it, expect, beforeEach } from 'vitest'
import { useDebateStore, STAGES } from './useDebateStore'

describe('useDebateStore', () => {
  beforeEach(() => {
    useDebateStore.getState().reset()
  })

  it('has required stage metadata', () => {
    expect(STAGES.decomposing.label).toBe('Decomposing Claim')
    expect(STAGES.complete.pct).toBe(1.0)
    expect(STAGES.error.icon).toBe('❌')
  })

  it('startRun initialises stream state with the run id', () => {
    useDebateStore.getState().startRun('run-123')
    const s = useDebateStore.getState()
    expect(s.isRunning).toBe(true)
    expect(s.threadId).toBe('run-123')
    expect(s.agentMessages).toEqual({})
    expect(s.result).toBeNull()
    expect(s.activeStage).toBe('idle')
  })

  it('pushStage appends unique stages and updates activeStage', () => {
    useDebateStore.getState().startRun('run-1')
    const store = useDebateStore
    store.getState().pushStage({ stage: 'searching', message: 'Searching', progress: 0.1 })
    store.getState().pushStage({ stage: 'fact_checking', message: 'Checking', progress: 0.88 })
    const s = store.getState()
    expect(s.activeStage).toBe('fact_checking')
    expect(s.stageHistory.map((h) => h.stage)).toEqual(['searching', 'fact_checking'])
  })

  it('pushStage deduplicates consecutive identical stages', () => {
    useDebateStore.getState().startRun('run-2')
    const store = useDebateStore
    store.getState().pushStage({ stage: 'decomposing' })
    store.getState().pushStage({ stage: 'decomposing' }) // duplicate
    expect(store.getState().stageHistory).toHaveLength(1)
    expect(store.getState().activeStage).toBe('decomposing')
  })

  it('appendStreamChunk accumulates text per agent round and ignores empties', () => {
    useDebateStore.getState().startRun('run-3')
    const store = useDebateStore
    store.getState().appendStreamChunk('PRO', 1, 'hello ')
    store.getState().appendStreamChunk('PRO', 1, 'world')
    store.getState().appendStreamChunk('CON', 1, 'no')
    store.getState().appendStreamChunk('PRO', 2, '') // empty ignored
    const s = store.getState()
    expect(s.agentMessages['PRO_1']).toBe('hello world')
    expect(s.agentMessages['CON_1']).toBe('no')
    expect(s.agentMessages['PRO_2']).toBeUndefined()
    expect(s.streamingAgent).toBe('CON')
  })

  it('setResult marks the run complete and records history', () => {
    useDebateStore.getState().startRun('run-4')
    const store = useDebateStore
    store.getState().setResult({ claim: 'X', verdict: 'TRUE' })
    const s = store.getState()
    expect(s.isRunning).toBe(false)
    expect(s.activeStage).toBe('complete')
    expect(s.result.verdict).toBe('TRUE')
    expect(s.history[0]).toMatchObject({ claim: 'X', verdict: 'TRUE' })
  })

  it('setError moves to error stage and clears running state', () => {
    useDebateStore.getState().startRun('run-5')
    const store = useDebateStore
    store.getState().setError({ type: 'NETWORK_ERROR', message: 'Lost' })
    const s = store.getState()
    expect(s.isRunning).toBe(false)
    expect(s.activeStage).toBe('error')
    expect(s.error.type).toBe('NETWORK_ERROR')
    expect(s.result).toBeNull()
  })
})
