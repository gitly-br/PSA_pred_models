import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { motion } from 'framer-motion';
import { api } from '@/services/api';
import type { ModelDetail } from '@/services/mockData';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function DetailedModels() {
  const [models, setModels] = useState<ModelDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const today = new Date();
  const dayName = format(today, 'EEEE', { locale: ptBR });
  const dateStr = format(today, 'yyyy-MM-dd');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const data = await api.getModelDetails();
        setModels(data);
      } catch (err) {
        console.error('Failed to load model details:', err);
        setModels([]);
        setError('Não foi possível carregar os detalhes dos modelos pela API local.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-3/4" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  const getStatusDot = (value: number) => {
    if (value < 30) return 'bg-safe';
    if (value < 60) return 'bg-moderate';
    return 'bg-critical';
  };

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={item}>
        <h1 className="text-2xl md:text-3xl font-heading font-bold text-primary capitalize">
          Previsões detalhadas de {dayName} ({dateStr})
        </h1>
      </motion.div>

      {models.map((region) => (
        <motion.div key={region.regionName} variants={item}>
          <Card className="border border-border shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="font-heading text-lg">{region.regionName}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {region.models.map((model) => (
                <div key={model.name} className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full flex-shrink-0 ${getStatusDot(model.value)}`}
                  />
                  <span className="text-sm font-medium text-foreground">
                    {model.name}:
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {model.value}%
                  </span>
                  {/* Progress bar */}
                  <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden max-w-[200px]">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ backgroundColor: model.color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${model.value}%` }}
                      transition={{ duration: 1, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </motion.div>
  );
}
