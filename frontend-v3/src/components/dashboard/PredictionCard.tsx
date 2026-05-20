import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import type { PredictionDay } from '@/services/mockData';

interface PredictionCardProps {
  prediction: PredictionDay;
  isSelected?: boolean;
  onClick?: () => void;
}

const periodLabels = {
  madrugada: 'Madrugada',
  manha: 'Manhã',
  tarde: 'Tarde',
  noite: 'Noite',
};

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function interpolate(start: number, end: number, amount: number): number {
  return Math.round(start + (end - start) * amount);
}

function periodColor(value: number): string {
  const p = clamp01(value);
  const green = [59, 184, 112];
  const yellow = [245, 158, 11];
  const red = [220, 38, 38];
  const start = p < 0.5 ? green : yellow;
  const end = p < 0.5 ? yellow : red;
  const amount = p < 0.5 ? p * 2 : (p - 0.5) * 2;
  const [r, g, b] = start.map((channel, index) => interpolate(channel, end[index], amount));

  return `rgb(${r}, ${g}, ${b})`;
}

export default function PredictionCard({ prediction, isSelected, onClick }: PredictionCardProps) {
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={cn(
        'w-full rounded-xl border-2 p-4 text-left transition-colors',
        isSelected
          ? 'border-secondary bg-secondary/5 shadow-md'
          : 'border-border bg-card hover:border-secondary/40'
      )}
    >
      <p className="font-heading font-bold text-foreground text-sm capitalize">
        {prediction.dayOfWeek}
      </p>
      <p className="text-lg font-heading font-bold text-primary">
        {prediction.date}
      </p>

      <div className="grid grid-cols-4 gap-2 mt-3">
        {(Object.entries(prediction.periods) as [keyof typeof periodLabels, number][]).map(
          ([period, value]) => (
            <div key={period} className="flex flex-col items-center gap-1">
              <span className="text-[10px] text-muted-foreground leading-tight text-center">
                {periodLabels[period]}
              </span>
              <div
                className="h-6 w-6 rounded-full shadow-sm ring-1 ring-white/10"
                style={{ backgroundColor: periodColor(value) }}
                title={`${periodLabels[period]}: ${(clamp01(value) * 100).toFixed(0)}%`}
              />
            </div>
          )
        )}
      </div>
    </motion.button>
  );
}
