import { useEffect, useMemo, useState } from 'react';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { ArrowLeftRight, Minus, TrendingDown, TrendingUp } from 'lucide-react';
import { useChamadosOccurrences } from '@/contexts/ChamadosOccurrencesContext';
import KeplerOccurrenceMap from '@/components/maps/KeplerOccurrenceMap';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import {
  type CompareDateRange,
  defaultCompareRanges,
  distinctIsoDates,
  filterForCompare,
  servicoOptions,
} from '@/lib/occurrenceCompare';
import { mergeIsoRanges, rangesEqual } from '@/lib/chamadosDates';

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35 } },
};

function formatIsoLabel(iso: string): string {
  try {
    return format(parseISO(`${iso}T12:00:00`), 'dd/MM/yyyy', { locale: ptBR });
  } catch {
    return iso;
  }
}

function formatRangeLabel(range: CompareDateRange): string {
  if (!range.start && !range.end) return 'Selecione o período';
  if (range.start && range.end) {
    if (range.start === range.end) return formatIsoLabel(range.start);
    return `${formatIsoLabel(range.start)} – ${formatIsoLabel(range.end)}`;
  }
  if (range.start) return `A partir de ${formatIsoLabel(range.start)}`;
  return `Até ${formatIsoLabel(range.end)}`;
}

function ComparePanel({
  title,
  range,
  occurrences,
  mapId,
  accentClass,
}: {
  title: string;
  range: CompareDateRange;
  occurrences: ReturnType<typeof filterForCompare>;
  mapId: string;
  accentClass: string;
}) {
  return (
    <Card className={`border shadow-sm overflow-hidden ${accentClass}`}>
      <CardHeader className="py-3 border-b border-border/60">
        <CardTitle className="text-sm font-heading">{title}</CardTitle>
        <p className="text-xs text-muted-foreground">{formatRangeLabel(range)}</p>
      </CardHeader>
      <CardContent className="p-0 space-y-0">
        <div className="px-4 py-3 border-b border-border/40">
          <p className="text-3xl font-heading font-bold text-primary">
            {occurrences.length.toLocaleString('pt-BR')}
          </p>
          <p className="text-xs text-muted-foreground">ocorrências no período</p>
        </div>
        <KeplerOccurrenceMap
          occurrences={occurrences}
          height={420}
          mapId={mapId}
          heatmapOnly
        />
      </CardContent>
    </Card>
  );
}

function RangeInputs({
  label,
  range,
  onChange,
  listId,
}: {
  label: string;
  range: CompareDateRange;
  onChange: (next: CompareDateRange) => void;
  listId: string;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{label}</p>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label className="text-xs font-medium text-muted-foreground">Início</Label>
          <Input
            type="date"
            value={range.start}
            onChange={e => onChange({ ...range, start: e.target.value })}
            className="h-9 text-xs mt-1"
            list={listId}
          />
        </div>
        <div>
          <Label className="text-xs font-medium text-muted-foreground">Fim</Label>
          <Input
            type="date"
            value={range.end}
            onChange={e => onChange({ ...range, end: e.target.value })}
            className="h-9 text-xs mt-1"
            list={listId}
          />
        </div>
      </div>
    </div>
  );
}

export default function ChamadosCompareView() {
  const { occurrences, loading, error, loadForRange, loadedRange } = useChamadosOccurrences();

  const availableDates = useMemo(() => distinctIsoDates(occurrences), [occurrences]);
  const servicos = useMemo(() => servicoOptions(occurrences), [occurrences]);

  const [servico, setServico] = useState('todos');
  const [rangeA, setRangeA] = useState<CompareDateRange>({ start: '', end: '' });
  const [rangeB, setRangeB] = useState<CompareDateRange>({ start: '', end: '' });

  useEffect(() => {
    if (availableDates.length && !rangeA.start && !rangeB.start) {
      const defaults = defaultCompareRanges(availableDates);
      setRangeA(defaults.rangeA);
      setRangeB(defaults.rangeB);
    }
  }, [availableDates, rangeA.start, rangeB.start]);

  const unionRange = useMemo(
    () => mergeIsoRanges(rangeA, rangeB),
    [rangeA, rangeB],
  );

  useEffect(() => {
    if (!unionRange) return;
    if (rangesEqual(loadedRange, unionRange)) return;

    const timer = window.setTimeout(() => {
      void loadForRange(unionRange);
    }, 400);

    return () => window.clearTimeout(timer);
  }, [unionRange, loadForRange, loadedRange]);

  const left = useMemo(
    () => filterForCompare(occurrences, rangeA, servico),
    [occurrences, rangeA, servico],
  );
  const right = useMemo(
    () => filterForCompare(occurrences, rangeB, servico),
    [occurrences, rangeB, servico],
  );

  const mergedBairros = useMemo(() => {
    const map = new Map<string, { name: string; countA: number; countB: number }>();
    for (const o of left) {
      const row = map.get(o.bairro) ?? { name: o.bairro, countA: 0, countB: 0 };
      row.countA += 1;
      map.set(o.bairro, row);
    }
    for (const o of right) {
      const row = map.get(o.bairro) ?? { name: o.bairro, countA: 0, countB: 0 };
      row.countB += 1;
      map.set(o.bairro, row);
    }
    return Array.from(map.values())
      .sort((a, b) => (b.countA + b.countB) - (a.countA + a.countB))
      .slice(0, 12);
  }, [left, right]);

  const delta = right.length - left.length;
  const deltaPct = left.length > 0 ? ((delta / left.length) * 100) : (right.length > 0 ? 100 : 0);

  if (loading || error) {
    return null;
  }


  return (
    <div className="space-y-4">
      <div>
        <Card className="border border-border">
          <CardContent className="py-4 space-y-4">
            <div>
              <Label className="text-xs font-medium text-muted-foreground">Serviço executado</Label>
              <Select value={servico} onValueChange={setServico}>
                <SelectTrigger className="h-9 text-xs mt-1 max-w-xl">
                  <SelectValue placeholder="Todos os serviços" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="todos" className="text-xs">
                    Todos os serviços
                  </SelectItem>
                  {servicos.map(s => (
                    <SelectItem key={s} value={s} className="text-xs">
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <RangeInputs
                label="Período A"
                range={rangeA}
                onChange={setRangeA}
                listId="chamados-dates-a"
              />
              <RangeInputs
                label="Período B"
                range={rangeB}
                onChange={setRangeB}
                listId="chamados-dates-b"
              />
            </div>
            <datalist id="chamados-dates-a">
              {availableDates.map(d => (
                <option key={d} value={d} />
              ))}
            </datalist>
            <datalist id="chamados-dates-b">
              {availableDates.map(d => (
                <option key={d} value={d} />
              ))}
            </datalist>
          </CardContent>
        </Card>
      </div>

      <div>
        <Card className="border border-border">
          <CardContent className="py-4 flex flex-wrap items-center gap-4 justify-center">
            <div className="text-center min-w-[120px]">
              <p className="text-xs text-muted-foreground">Período A</p>
              <p className="text-2xl font-bold text-primary">{left.length.toLocaleString('pt-BR')}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">{formatRangeLabel(rangeA)}</p>
            </div>
            <ArrowLeftRight className="h-5 w-5 text-muted-foreground shrink-0" />
            <div className="text-center min-w-[120px]">
              <p className="text-xs text-muted-foreground">Período B</p>
              <p className="text-2xl font-bold text-primary">{right.length.toLocaleString('pt-BR')}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">{formatRangeLabel(rangeB)}</p>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/50">
              {delta > 0 ? (
                <TrendingUp className="h-4 w-4 text-amber-600" />
              ) : delta < 0 ? (
                <TrendingDown className="h-4 w-4 text-emerald-600" />
              ) : (
                <Minus className="h-4 w-4 text-muted-foreground" />
              )}
              <div>
                <p className="text-xs text-muted-foreground">Variação (B − A)</p>
                <p className="text-sm font-semibold">
                  {delta >= 0 ? '+' : ''}{delta.toLocaleString('pt-BR')}
                  {left.length > 0 && (
                    <span className="text-muted-foreground font-normal">
                      {' '}({deltaPct >= 0 ? '+' : ''}{deltaPct.toFixed(1)}%)
                    </span>
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ComparePanel
          title="Período A"
          range={rangeA}
          occurrences={left}
          mapId="compare-map-a"
          accentClass="border-l-4 border-l-secondary"
        />
        <ComparePanel
          title="Período B"
          range={rangeB}
          occurrences={right}
          mapId="compare-map-b"
          accentClass="border-l-4 border-l-primary"
        />
      </div>

      {mergedBairros.length > 0 && rangeA.start && rangeB.start && (
        <div>
          <Card className="border border-border shadow-sm">
            <CardHeader className="py-3">
              <CardTitle className="text-sm font-heading">
                Bairros — comparação lado a lado
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mergedBairros} margin={{ top: 8, right: 8, left: 0, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    angle={-35}
                    textAnchor="end"
                    height={56}
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 9 }} />
                  <Tooltip contentStyle={{ fontSize: 11 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar
                    dataKey="countA"
                    name={`Período A (${formatRangeLabel(rangeA)})`}
                    fill="hsl(var(--secondary))"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="countB"
                    name={`Período B (${formatRangeLabel(rangeB)})`}
                    fill="hsl(var(--primary))"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
