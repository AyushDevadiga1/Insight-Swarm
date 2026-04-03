import React from 'react';
import { useDebateStore } from '../../store/useDebateStore';

export default function SubClaimBanner() {
  const subClaims = useDebateStore(state => state.subClaims);

  if (!subClaims || subClaims.length <= 1) return null;

  return (
    <div className="subclaim-banner animate-fade-in">
      <div className="subclaim-glass-card">
        <div className="subclaim-header">
          <div className="subclaim-icon-wrapper">
             <span className="subclaim-icon">⚙️</span>
             <div className="subclaim-icon-pulse" />
          </div>
          <div className="subclaim-header-text">
            <h4>Claim Decomposition</h4>
            <p>System identified {subClaims.length} independent verifiable components</p>
          </div>
        </div>
        
        <div className="subclaim-grid">
          {subClaims.map((sc, i) => (
            <div key={i} className="subclaim-card animate-slide-in" style={{ animationDelay: `${i * 100}ms` }}>
              <div className="subclaim-card-num">{i + 1}</div>
              <div className="subclaim-card-content">{sc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
