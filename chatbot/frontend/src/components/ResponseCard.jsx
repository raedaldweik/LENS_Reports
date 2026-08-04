import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DynamicChart from './DynamicChart';
import ReasoningTrace from './ReasoningTrace';

export default function ResponseCard({ data }) {
  if (!data) return null;

  const markdownComponents = {
    p: ({node, ...props}) => <p className="my-1 leading-[1.75]" {...props} />,
    strong: ({node, ...props}) => <strong style={{ color: 'var(--gold)', fontWeight: 700 }} {...props} />,
    em: ({node, ...props}) => <em style={{ color: 'var(--gold-lo)' }} {...props} />,
    ul: ({node, ...props}) => <ul className="my-1.5 space-y-0.5 pl-5 list-disc" {...props} />,
    ol: ({node, ...props}) => <ol className="my-1.5 space-y-0.5 pl-5 list-decimal" {...props} />,
    li: ({node, ...props}) => <li className="leading-[1.7]" {...props} />,
    h1: ({node, ...props}) => <h1 className="text-[15px] font-bold my-2" style={{ color: 'var(--gold)' }} {...props} />,
    h2: ({node, ...props}) => <h2 className="text-[14px] font-bold my-2" style={{ color: 'var(--gold)' }} {...props} />,
    h3: ({node, ...props}) => <h3 className="text-[13px] font-semibold my-1.5" style={{ color: 'var(--gold-lo)' }} {...props} />,
    table: ({node, ...props}) => (
      <div className="my-2 overflow-x-auto">
        <table className="border-collapse text-[12px] w-full" style={{ border: '1px solid rgba(185,28,44,0.15)' }} {...props} />
      </div>
    ),
    thead: ({node, ...props}) => <thead style={{ background: 'rgba(185,28,44,0.06)' }} {...props} />,
    th: ({node, ...props}) => <th className="px-2 py-1.5 text-left font-semibold" style={{ border: '1px solid rgba(185,28,44,0.15)', color: 'var(--gold)' }} {...props} />,
    td: ({node, ...props}) => <td className="px-2 py-1.5" style={{ border: '1px solid rgba(185,28,44,0.10)' }} {...props} />,
    code: ({node, inline, ...props}) => inline
      ? <code className="px-1 py-0.5 rounded text-[12px]" style={{ background: 'rgba(185,28,44,0.08)', color: 'var(--gold)' }} {...props} />
      : <code className="block p-2 rounded my-1 text-[12px]" style={{ background: 'rgba(0,0,0,0.04)' }} {...props} />,
    blockquote: ({node, ...props}) => <blockquote className="pl-3 my-2 italic" style={{ borderLeft: '2px solid var(--gold-lo)', color: 'var(--text-md)' }} {...props} />,
  };

  return (
    <div className="animate-slide-up space-y-2.5 max-w-[640px]">
      {/* Answer bubble */}
      <div className="msg-bot-bubble px-4 py-3">
        <div className="text-[13px]" style={{ color: 'var(--text)' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {data.answer}
          </ReactMarkdown>
        </div>
      </div>

      {/* Dynamic charts from the agent */}
      {data.charts && data.charts.length > 0 && (
        <div className="space-y-2">
          {data.charts.map((chart, i) => <DynamicChart key={i} spec={chart} />)}
        </div>
      )}

      {/* Collapsible agent reasoning */}
      <ReasoningTrace trace={data.trace} />
    </div>
  );
}
