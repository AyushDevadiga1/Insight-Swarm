import React from 'react';

export default function LoadingOrb({ message = "Processing..." }) {
  return (
    <div className="loading-orb-container">
      <div className="loading-orb">
        <div className="orb-ring orb-ring-1" />
        <div className="orb-ring orb-ring-2" />
        <div className="orb-ring orb-ring-3" />
        <div className="orb-core" />
      </div>
      <div className="loading-orb-message">{message}</div>
    </div>
  );
}
