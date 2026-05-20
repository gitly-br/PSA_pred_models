import { motion } from 'framer-motion';

interface FloodGaugeProps {
  label: string;
  percentage: number;
  size?: number;
  color?: string;
}

export default function FloodGauge({ label, percentage, size = 160, color }: FloodGaugeProps) {
  const clampedPct = Math.max(0, Math.min(100, percentage));
  const radius = 60;
  const circumference = Math.PI * radius;
  const offset = circumference - (clampedPct / 100) * circumference;

  const getRiskColor = (pct: number) => {
    if (pct < 30) return 'hsl(var(--safe))';
    if (pct < 60) return 'hsl(var(--moderate))';
    return 'hsl(var(--critical))';
  };
  const gaugeColor = color ?? getRiskColor(clampedPct);

  return (
    <div className="flex flex-col items-center p-4 rounded-xl bg-card border border-border shadow-sm hover:shadow-md transition-shadow">
      <p className="text-xs font-medium text-muted-foreground text-center mb-3 leading-tight min-h-[2rem] flex items-center">
        <span className="inline-block h-2.5 w-2.5 rounded-full mr-2" style={{ backgroundColor: gaugeColor }} />
        {label}
      </p>
      <div className="relative" style={{ width: size, height: size * 0.6 }}>
        <svg
          viewBox="0 0 140 80"
          className="w-full h-full"
        >
          {/* Background arc */}
          <path
            d="M 10 70 A 60 60 0 0 1 130 70"
            fill="none"
            stroke="hsl(var(--gauge-track))"
            strokeWidth="10"
            strokeLinecap="round"
          />
          {/* Filled arc */}
          <motion.path
            d="M 10 70 A 60 60 0 0 1 130 70"
            fill="none"
            stroke={gaugeColor}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
          {/* Labels */}
          <text x="10" y="78" className="text-[7px] fill-muted-foreground" textAnchor="middle">0%</text>
          <text x="70" y="15" className="text-[7px] fill-muted-foreground" textAnchor="middle">50%</text>
          <text x="130" y="78" className="text-[7px] fill-muted-foreground" textAnchor="middle">100%</text>
          {/* Center value */}
          <text
            x="70"
            y="65"
            textAnchor="middle"
            className="font-heading font-bold text-[22px]"
            fill={gaugeColor}
          >
            {clampedPct}%
          </text>
        </svg>
      </div>
    </div>
  );
}
