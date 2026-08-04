import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, AreaChart, Area,
  ScatterChart, Scatter, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

const PALETTE = ['#2dd4a7', '#38bdf8', '#f0b429', '#ef5350', '#a78bfa', '#43e8bc', '#fb923c', '#8fb3a0'];

const tooltipStyle = {
  background: 'rgba(7,22,16,0.97)',
  border: '1px solid rgba(45,212,167,0.30)',
  borderRadius: '8px',
  fontSize: '11.5px',
  padding: '6px 10px',
  color: '#e9f6ef',
  boxShadow: '0 4px 16px rgba(0,0,0,0.45)',
};

export default function DynamicChart({ spec }) {
  if (!spec || !spec.type || !spec.data) return null;

  const {
    type, title, subtitle, data,
    xKey = 'name',
    yKeys = [{ key: 'value', label: 'Value', color: PALETTE[0] }],
    annotations = [],
    height = 260,
    yAxisLabel = '',
    footnote,
  } = spec;

  return (
    <div className="mt-2 rounded-xl p-3.5 animate-fade-up" dir="ltr"
      style={{ background: 'rgba(9,28,20,0.72)', border: '1px solid rgba(45,212,167,0.16)', boxShadow: 'var(--glass-shadow)' }}>
      {(title || subtitle) && (
        <div className="mb-2">
          {title && <div className="text-[12.5px] font-semibold" style={{ color: 'var(--text)' }}>{title}</div>}
          {subtitle && <div className="text-[10.5px] mt-0.5" style={{ color: 'var(--text-dim)' }}>{subtitle}</div>}
        </div>
      )}
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          {renderChart(type, data, xKey, yKeys, annotations, yAxisLabel)}
        </ResponsiveContainer>
      </div>
      {footnote && (
        <div className="text-[10.5px] mt-2" style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>{footnote}</div>
      )}
    </div>
  );
}

function renderChart(type, data, xKey, yKeys, annotations, yAxisLabel) {
  if (type === 'bar') {
    const longestLabel = Math.max(...data.map(d => String(d[xKey] ?? '').length));
    const shouldRotate = data.length > 3 || longestLabel > 10;
    const axisHeight = shouldRotate ? (longestLabel > 18 ? 80 : 60) : 25;
    const truncate = (s) => {
      const str = String(s ?? '');
      return str.length > 16 ? str.slice(0, 15) + '…' : str;
    };
    return (
      <BarChart data={data} margin={{ top: 8, right: 14, left: -8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(45,212,167,0.10)" vertical={false} />
        <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: '#8fb3a0' }}
          axisLine={{ stroke: 'rgba(45,212,167,0.20)' }} tickLine={false}
          interval={0}
          angle={shouldRotate ? -30 : 0}
          textAnchor={shouldRotate ? 'end' : 'middle'}
          height={axisHeight}
          tickFormatter={truncate} />
        <YAxis tick={{ fontSize: 10, fill: '#8fb3a0' }} axisLine={false} tickLine={false}
          label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', fontSize: 10, offset: 12 } : null} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(45,212,167,0.06)' }} />
        {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 10 }} />}
        {annotations.filter(a => a.type === 'reference').map((a, i) => (
          <ReferenceLine key={i} y={a.value}
            stroke={a.color || '#f0b429'} strokeDasharray="4 4"
            label={{ value: a.label, fontSize: 9, fill: a.color || '#f0b429', position: 'right' }} />
        ))}
        {yKeys.map((yk, i) => (
          <Bar key={yk.key} dataKey={yk.key} name={yk.label || yk.key}
            fill={yk.color || PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]}>
            {yk.colorByRow && data.map((entry, idx) => (
              <Cell key={idx} fill={entry._color || PALETTE[idx % PALETTE.length]} />
            ))}
          </Bar>
        ))}
      </BarChart>
    );
  }

  if (type === 'line') return (
    <LineChart data={data} margin={{ top: 8, right: 14, left: -8, bottom: 4 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(45,212,167,0.10)" vertical={false} />
      <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: '#8fb3a0' }} tickLine={false} />
      <YAxis tick={{ fontSize: 10, fill: '#8fb3a0' }} axisLine={false} tickLine={false}
        domain={annotations.find(a => a.type === 'reference') ? ['auto', 'auto'] : [0, 'auto']} />
      <Tooltip contentStyle={tooltipStyle} />
      {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 10 }} />}
      {annotations.filter(a => a.type === 'reference').map((a, i) => (
        <ReferenceLine key={i} y={a.value} stroke={a.color || '#f0b429'} strokeDasharray="4 4"
          label={{ value: a.label, fontSize: 9, fill: a.color || '#f0b429' }} />
      ))}
      {yKeys.map((yk, i) => (
        <Line key={yk.key} type="monotone" dataKey={yk.key} name={yk.label || yk.key}
          stroke={yk.color || PALETTE[i % PALETTE.length]} strokeWidth={2}
          dot={{ r: 2.5 }} activeDot={{ r: 4 }} />
      ))}
    </LineChart>
  );

  if (type === 'area') return (
    <AreaChart data={data} margin={{ top: 8, right: 14, left: -8, bottom: 4 }}>
      <defs>
        {yKeys.map((yk, i) => (
          <linearGradient key={yk.key} id={`grad-${yk.key}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={yk.color || PALETTE[i % PALETTE.length]} stopOpacity={0.6} />
            <stop offset="95%" stopColor={yk.color || PALETTE[i % PALETTE.length]} stopOpacity={0.05} />
          </linearGradient>
        ))}
      </defs>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(45,212,167,0.10)" vertical={false} />
      <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: '#8fb3a0' }} tickLine={false} />
      <YAxis tick={{ fontSize: 10, fill: '#8fb3a0' }} axisLine={false} tickLine={false} />
      <Tooltip contentStyle={tooltipStyle} />
      {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 10 }} />}
      {yKeys.map((yk, i) => (
        <Area key={yk.key} type="monotone" dataKey={yk.key} name={yk.label || yk.key}
          stroke={yk.color || PALETTE[i % PALETTE.length]} strokeWidth={2}
          fill={`url(#grad-${yk.key})`} />
      ))}
    </AreaChart>
  );

  if (type === 'pie') return (
    <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
      <Tooltip contentStyle={tooltipStyle} />
      <Legend wrapperStyle={{ fontSize: 10 }} />
      <Pie data={data} dataKey={yKeys[0].key} nameKey={xKey} cx="50%" cy="50%"
        innerRadius="35%" outerRadius="70%" paddingAngle={2}
        label={(e) => `${e[xKey]}: ${e[yKeys[0].key]}`}
        labelLine={false} style={{ fontSize: 10 }}>
        {data.map((entry, idx) => (
          <Cell key={idx} fill={entry._color || PALETTE[idx % PALETTE.length]} />
        ))}
      </Pie>
    </PieChart>
  );

  if (type === 'scatter') return (
    <ScatterChart margin={{ top: 8, right: 14, left: 0, bottom: 4 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(45,212,167,0.10)" />
      <XAxis dataKey={xKey} type="number" tick={{ fontSize: 10, fill: '#8fb3a0' }} />
      <YAxis dataKey={yKeys[0].key} type="number" tick={{ fontSize: 10, fill: '#8fb3a0' }} />
      <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: '3 3' }} />
      <Scatter data={data} fill={yKeys[0].color || PALETTE[0]} />
    </ScatterChart>
  );

  return <div />;
}
