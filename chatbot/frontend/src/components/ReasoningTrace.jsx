import { useState } from 'react';

const AGENT_LABELS = {
  fleet_agent:     'Fleet Data Agent',
  analytics_agent: 'Analytics Agent',
  forecast_engine: 'Forecast Engine',
  process_mining:  'Process Mining Engine',
  risk_model:      'Driver Risk Model',
  model_engine:    'Model Engine',
};

export default function ReasoningTrace({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace || trace.length === 0) return null;

  return (
    <div className="trace-panel mt-2">
      <div className="trace-header" onClick={() => setOpen(!open)}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 3" />
        </svg>
        <span>Agent reasoning · {trace.length} step{trace.length !== 1 ? 's' : ''}</span>
        <div className="flex-1" />
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && (
        <div className="animate-slide-up">
          {trace.map((step, i) => (
            <div key={i} className="trace-step">
              <div className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5"
                style={{ background: 'rgba(14,116,144,0.15)', color: 'var(--teal)' }}>
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-0.5">
                  <span className="text-[10.5px] font-semibold" style={{ color: 'var(--teal)' }}>
                    {AGENT_LABELS[step.agent] || step.agent}
                  </span>
                  {step.tool && <span className="trace-step-tool">{step.tool}</span>}
                  {step.duration_ms !== undefined && (
                    <span className="text-[9.5px] font-mono" style={{ color: 'var(--text-faint)' }}>
                      {step.duration_ms}ms
                    </span>
                  )}
                </div>
                <div className="text-[11.5px] leading-relaxed" style={{ color: 'var(--text-md)' }}>
                  {step.description}
                </div>
                {step.detail && (
                  <div className="mt-1 text-[10.5px] px-2 py-1 rounded font-mono"
                    style={{ background: 'rgba(14,116,144,0.04)', color: 'var(--text-dim)', border: '1px solid rgba(14,116,144,0.08)' }}>
                    {step.detail}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
