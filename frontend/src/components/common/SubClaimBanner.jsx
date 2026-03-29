import React from 'react';
import { useDebateStore } from '../../store/useDebateStore';

export default function SubClaimBanner() {
  const subClaims = useDebateStore(state => state.subClaims);

  // Only show if there are actual sub-claims resulting from decomposition
  if (!subClaims || subClaims.length <= 1) return null;

  return (
    <div className="subclaim-banner">
      <div className="subclaim-header">
        <span className="subclaim-icon">🔀</span>
        <span className="subclaim-title">Claim decomposed into verifiable parts:</span>
      </div>
      <ul className="subclaim-list">
        {subClaims.map((sc, i) => (
          <li key={i} className="subclaim-item">{sc}</li>
        ))}
      </ul>
    </div>
  );
}
