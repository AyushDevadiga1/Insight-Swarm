/**
 * DebateArena.jsx — v3
 * Renders the debate as a full-width alternating message thread.
 * Pro rows on the left (lighter bg), Con rows on the right (darker bg).
 */

import React from 'react';
import AgentBubble from './AgentBubble';
import { useDebateStore } from '../../store/useDebateStore';

export default function DebateArena({ result }) {
  const { isRunning, activeStage, agentMessages } = useDebateStore();

  // Build the ordered list of messages to render
  const messages = [];

  if (result) {
    // Post-completion: render from result object
    const proArgs = result.pro_arguments || [];
    const conArgs = result.con_arguments || [];
    const rounds = Math.max(proArgs.length, conArgs.length);

    for (let r = 1; r <= rounds; r++) {
      if (proArgs[r - 1]) {
        messages.push({ agent: 'PRO', round: r, text: proArgs[r - 1], isStreaming: false, sources: (result.pro_sources || [])[r - 1] || [] });
      }
      if (conArgs[r - 1]) {
        messages.push({ agent: 'CON', round: r, text: conArgs[r - 1], isStreaming: false, sources: (result.con_sources || [])[r - 1] || [] });
      }
    }
  } else {
    // During streaming: render from agentMessages store
    const keys = Object.keys(agentMessages).sort();
    for (const key of keys) {
      const [agent, roundStr] = key.split('_');
      const round = parseInt(roundStr, 10);
      if (!agent || isNaN(round)) continue;

      const isStreaming = isRunning && activeStage === `round_${round}_${agent.toLowerCase()}`;
      messages.push({
        agent,
        round,
        text:        agentMessages[key],
        isStreaming,
        sources:     [],
      });
    }

    // Add a thinking bubble for the agent currently starting up (no text yet)
    if (isRunning && activeStage) {
      const match = activeStage.match(/^round_(\d+)_(pro|con)$/);
      if (match) {
        const round  = parseInt(match[1], 10);
        const agent  = match[2].toUpperCase();
        const key    = `${agent}_${round}`;
        const hasMsg = agentMessages[key];
        if (!hasMsg) {
          messages.push({ agent, round, text: '', isStreaming: true, sources: [] });
        }
      }
    }
  }

  if (messages.length === 0 && !isRunning) return null;

  return (
    <div className="debate-thread">
      {messages.map((msg, i) => (
        <AgentBubble
          key={`${msg.agent}-${msg.round}-${i}`}
          agent={msg.agent}
          round={msg.round}
          text={msg.text}
          isStreaming={msg.isStreaming}
          sources={msg.sources}
        />
      ))}
    </div>
  );
}
