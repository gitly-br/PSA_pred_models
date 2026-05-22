import { HelpCircle } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { PredictionDay } from '@/services/mockData';

interface PredictionSummaryProps {
  prediction: PredictionDay;
}

export default function PredictionSummary({ prediction }: PredictionSummaryProps) {
  const getStatusColor = (prob: number) => {
    if (prob < 30) return 'text-safe';
    if (prob < 60) return 'text-moderate';
    return 'text-critical';
  };

  const summaryText = prediction.message;
  const analiseCompleta = prediction.longExplanation;

  return (
    <Card className="border border-border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-heading">
          <span className={cn('text-lg font-bold', getStatusColor(prediction.probability))}>
            {prediction.probability}% de possibilidade
          </span>
          {' '}em {prediction.date}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-start gap-2">
          <p
            className={cn(
              'text-sm text-muted-foreground flex-1 leading-snug',
              !summaryText && 'italic',
            )}
          >
            {summaryText}
          </p>
          {analiseCompleta ? (
            <Dialog>
              <DialogTrigger asChild>
                <button
                  type="button"
                  className="shrink-0 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Ver explicação completa da predição"
                >
                  <HelpCircle className="h-5 w-5" aria-hidden />
                </button>
              </DialogTrigger>
              <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
                <DialogHeader>
                  <DialogTitle>Análise operacional</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                  {analiseCompleta}
                </p>
              </DialogContent>
            </Dialog>
          ) : null}
        </div>

      </CardContent>
    </Card>
  );
}
