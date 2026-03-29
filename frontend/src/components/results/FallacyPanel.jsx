import React from 'react';

export default function FallacyPanel({ result }) {
  if (!result || !result.metrics) return null;

  const proFallacies = result.metrics.pro_fallacies || [];
  const conFallacies = result.metrics.con_fallacies || [];

  if (proFallacies.length === 0 && conFallacies.length === 0) return null;

  return (
    <div className="panel fallacy-panel">
      <div className="panel-header">
        <span className="panel-icon">⚠️</span>
        <span className="panel-title">Logical Fallacies Detected</span>
      </div>
      
      <div className="fallacy-columns">
        {proFallacies.length > 0 && (
          <div className="fallacy-column fallacy-pro">
            <h4 className="fallacy-column-title">ProAgent Fallacies</h4>
            <ul className="fallacy-list">
              {proFallacies.map((f, i) => (
                <li key={`pro-${i}`}>{f}</li>
              ))}
            </ul>
          </div>
        )}

        {conFallacies.length > 0 && (
          <div className="fallacy-column fallacy-con">
            <h4 className="fallacy-column-title">ConAgent Fallacies</h4>
            <ul className="fallacy-list">
              {conFallacies.map((f, i) => (
                <li key={`con-${i}`}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
