import { useState, useEffect, useMemo } from 'react';

import { format } from 'date-fns';
import { motion } from 'framer-motion';
import { CalendarDays, Droplets } from 'lucide-react';
import { api } from '@/services/api';
import type { PredictionDay, BasinPrediction, WeatherHour } from '@/services/mockData';
import PredictionCard from '@/components/dashboard/PredictionCard';
import PredictionSummary from '@/components/dashboard/PredictionSummary';
import WeatherChart from '@/components/dashboard/WeatherChart';
import BasinMap from '@/components/maps/BasinMap';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Checkbox } from '@/components/ui/checkbox';
import { basinFillColorByModel } from '@/lib/basinMapStyles';

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

const today = new Date();

function dateFromInput(value: string): Date {
  return new Date(`${value}T12:00:00`);
}

function getNearestAvailableDate(value: string, availableDates: string[]): string | null {
  if (availableDates.length === 0) return null;
  return availableDates.filter(date => date <= value).at(-1) ?? availableDates.at(-1) ?? null;
}

function basinRiskMeta(probability: number) {
  if (probability < 25) {
    return { label: 'Normal', color: 'hsl(var(--safe))' };
  }
  if (probability < 50) {
    return { label: 'Atenção', color: 'hsl(var(--moderate))' };
  }
  if (probability < 75) {
    return { label: 'Alerta', color: 'hsl(var(--warning))' };
  }
  return { label: 'Alerta máximo', color: 'hsl(var(--critical))' };
}

export default function Home() {
  const [selectedDate, setSelectedDate] = useState(today);
  const [predictions, setPredictions] = useState<PredictionDay[]>([]);
  const [basins, setBasins] = useState<BasinPrediction[]>([]);
  const [weather, setWeather] = useState<WeatherHour[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const [visibleBasinIds, setVisibleBasinIds] = useState<Record<string, boolean>>({});
  const [availableDates, setAvailableDates] = useState<string[]>([]);

  useEffect(() => {
    let ignore = false;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const dates = await api.getAvailableDates();
        if (!ignore) {
          setAvailableDates(dates);
        }

        const selectedDateValue = format(selectedDate, 'yyyy-MM-dd');
        const availableDateValue = getNearestAvailableDate(selectedDateValue, dates);
        if (availableDateValue && availableDateValue !== selectedDateValue) {
          if (!ignore) {
            setSelectedDate(dateFromInput(availableDateValue));
          }
          return;
        }

        const [preds, bsns, wth] = await Promise.all([
          api.getPredictions(selectedDate),
          api.getBasinPredictions(selectedDate),
          api.getWeatherData(selectedDate),
        ]);
        if (ignore) return;
        setPredictions(preds);
        setBasins(bsns);
        setVisibleBasinIds(prev => {
          if (Object.keys(prev).length > 0) return prev;
          return Object.fromEntries(bsns.map(b => [b.id, true]));
        });
        setWeather(wth);
      } catch (err) {
        if (ignore) return;
        console.error('Failed to load dashboard data:', err);
        setPredictions([]);
        setBasins([]);
        setWeather([]);
        setError('Não foi possível carregar os dados da API local agora.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();

    return () => {
      ignore = true;
    };
  }, [selectedDate]);

  const visibleIds = useMemo(
    () => basins.filter(b => visibleBasinIds[b.id] !== false).map(b => b.id),
    [basins, visibleBasinIds],
  );
  const selectedDateInputValue = format(selectedDate, 'yyyy-MM-dd');
  const minDateInputValue = availableDates.at(0);
  const maxDateInputValue = availableDates.at(-1) ?? format(today, 'yyyy-MM-dd');

  const handleDateChange = (value: string) => {
    if (!value) return;
    const nearestDate = getNearestAvailableDate(value, availableDates);
    setSelectedDate(dateFromInput(nearestDate ?? value));
    setSelectedDayIndex(0);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-3/4" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
        <Skeleton className="h-[300px]" />
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

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
      {/* Header */}
      <motion.div variants={item} className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-heading font-bold text-primary">
            Sistema de Predição de Alagamentos e Inundações
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <CalendarDays className="h-4 w-4" />
              Previsão feita em: {format(selectedDate, 'dd/MM/yyyy')}
            </span>
            <span className="hidden md:inline">•</span>
            <span>Todas as previsões são feitas a partir das 0h do dia selecionado.</span>
          </div>
        </div>
        <label className="flex w-full flex-col gap-1 text-xs font-medium text-muted-foreground md:w-auto">
          Data escolhida
          <input
            type="date"
            value={selectedDateInputValue}
            min={minDateInputValue}
            max={maxDateInputValue}
            onChange={event => handleDateChange(event.target.value)}
            className="h-10 rounded-md border border-input bg-card px-3 text-sm font-semibold text-foreground shadow-sm outline-none transition-colors focus:border-secondary focus:ring-2 focus:ring-secondary/20"
          />
        </label>
      </motion.div>

      {/* Modelo de Santo André */}
      <motion.div variants={item}>
        <h2 className="text-xl font-heading font-semibold text-secondary mb-4">
          Modelo de Santo André:
        </h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Day cards */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {predictions.map((pred, i) => (
              <PredictionCard
                key={pred.date}
                prediction={pred}
                isSelected={selectedDayIndex === i}
                onClick={() => setSelectedDayIndex(i)}
              />
            ))}
          </div>
          {/* Summaries */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1">
            {predictions.map(pred => (
              <PredictionSummary key={pred.date} prediction={pred} />
            ))}
          </div>
        </div>
      </motion.div>

      <Separator />

      {/* Basin model section */}
      <motion.div variants={item}>
        <h2 className="text-xl font-heading font-semibold text-secondary mb-4 flex items-center gap-2">
          <Droplets className="h-5 w-5" />
          Modelo de Bacias:
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Map */}
          <div className="rounded-xl overflow-hidden border border-border shadow-sm p-3 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              {basins.map(basin => (
                <label key={basin.id} className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
                  <Checkbox
                    checked={visibleBasinIds[basin.id] !== false}
                    onCheckedChange={checked =>
                      setVisibleBasinIds(prev => ({ ...prev, [basin.id]: checked === true }))
                    }
                  />
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: basinFillColorByModel(basin.id) }}
                  />
                  <span className="truncate">{basin.name}</span>
                </label>
              ))}
            </div>
            <BasinMap className="h-[360px] w-full" basins={basins} visibleBasinIds={visibleIds} />
          </div>
          {/* Basin risk cards */}
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h3 className="text-sm font-heading font-semibold uppercase tracking-wide text-muted-foreground">
                Modelos de Bacias - Risco de Alagamento
              </h3>
              <span className="text-xs font-semibold text-secondary">
                {format(selectedDate, 'dd/MM/yyyy')}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {basins.map(basin => {
                const risk = basinRiskMeta(basin.probability);

                return (
                  <article
                    key={basin.id}
                    className="rounded-lg border border-border bg-muted/35 p-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="text-sm font-heading font-bold text-foreground">
                        {basin.name}
                      </h4>
                      <span className="text-sm font-bold" style={{ color: risk.color }}>
                        {basin.probability}%
                      </span>
                    </div>
                    <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-gauge-track">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${basin.probability}%`,
                          backgroundColor: risk.color,
                        }}
                      />
                    </div>
                    <p className="mt-3 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Estado: {risk.label}
                    </p>
                  </article>
                );
              })}
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Possibilidade de Alagamento ou Inundação
              calculada para as bacias monitoradas em Santo André.
            </p>
          </div>
        </div>
      </motion.div>

      <Separator />

      {/* Weather chart */}
      <motion.div variants={item}>
        <WeatherChart data={weather} />
      </motion.div>
    </motion.div>
  );
}
