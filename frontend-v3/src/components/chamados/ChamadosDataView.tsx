import { useState, useMemo, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useChamadosOccurrences } from '@/contexts/ChamadosOccurrencesContext';
import KeplerOccurrenceMap from '@/components/maps/KeplerOccurrenceMap';
import { MAP_POINT_LIMIT } from '@/lib/occurrenceMapSample';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { filterOccurrences, bairroStatsFromOccurrences } from '@/lib/occurrenceFilters';
import { getTodayIso, rangesEqual } from '@/lib/chamadosDates';

const TABLE_PREVIEW_LIMIT = 50;

export default function ChamadosDataView() {
  const { occurrences, loading, error, refetching, loadForRange, loadedRange } = useChamadosOccurrences();
  const bairroStats = useMemo(
    () => bairroStatsFromOccurrences(occurrences),
    [occurrences],
  );
  const todayIso = getTodayIso();
  const [filters, setFilters] = useState({
    dateStart: todayIso,
    dateEnd: todayIso,
    servico: 'todos',
    bairro: 'todos',
    interdicao: 'todos',
    tipoArea: 'todos',
  });

  const filteredOccurrences = useMemo(
    () => filterOccurrences(occurrences, filters),
    [occurrences, filters],
  );

  const displayBairroStats = useMemo(() => {
    if (!occurrences.length) return bairroStats;
    return bairroStatsFromOccurrences(filteredOccurrences);
  }, [occurrences.length, filteredOccurrences, bairroStats]);

  const totalChamados = filteredOccurrences.length;

  const servicoOptions = useMemo(
    () => Array.from(new Set(
      occurrences
        .map(occ => occ.servico?.trim())
        .filter((servico): servico is string => Boolean(servico)),
    )).sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [occurrences],
  );

  const tipoOptions = useMemo(
    () => Array.from(new Set(
      occurrences
        .map(occ => occ.tipo?.trim())
        .filter((tipo): tipo is string => Boolean(tipo)),
    )).sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [occurrences],
  );

  const tableRows = useMemo(
    () => filteredOccurrences.slice(0, TABLE_PREVIEW_LIMIT),
    [filteredOccurrences],
  );

  useEffect(() => {
    if (!filters.dateStart || !filters.dateEnd) return;
    const query = { dateStart: filters.dateStart, dateEnd: filters.dateEnd };
    if (rangesEqual(loadedRange, query)) return;

    const timer = window.setTimeout(() => {
      void loadForRange(query);
    }, 400);

    return () => window.clearTimeout(timer);
  }, [filters.dateStart, filters.dateEnd, loadForRange, loadedRange]);

  if (loading || error) {
    return null;
  }


  return (
    <div className="space-y-6">
      {occurrences.length === 0 && (
        <p
          className="rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground"
        >
          Nenhum chamado retornado pela API. Confirme a origem CSV (mesma do painel Power BI) em{' '}
          <code className="text-xs">CHAMADOS_CSV_PATH</code> ou MinIO.
        </p>
      )}

      <div>
        <Card className="border border-secondary/30 bg-secondary/5">
          <CardContent className="py-4">
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Data Início</Label>
                <Input
                  type="date"
                  value={filters.dateStart}
                  onChange={e => setFilters(f => ({ ...f, dateStart: e.target.value }))}
                  className="h-9 text-xs"
                />
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Data Fim</Label>
                <Input
                  type="date"
                  value={filters.dateEnd}
                  onChange={e => setFilters(f => ({ ...f, dateEnd: e.target.value }))}
                  className="h-9 text-xs"
                />
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Serviço Executado</Label>
                <Select value={filters.servico} onValueChange={v => setFilters(f => ({ ...f, servico: v }))}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todos">Todos</SelectItem>
                    {servicoOptions.map(servico => (
                      <SelectItem key={servico} value={servico}>{servico}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Bairro Afetado</Label>
                <Select value={filters.bairro} onValueChange={v => setFilters(f => ({ ...f, bairro: v }))}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todos">Todos</SelectItem>
                    {bairroStats.map(b => (
                      <SelectItem key={b.name} value={b.name}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Interdição?</Label>
                <Select value={filters.interdicao} onValueChange={v => setFilters(f => ({ ...f, interdicao: v }))}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todos">Todos</SelectItem>
                    <SelectItem value="sim">Sim</SelectItem>
                    <SelectItem value="nao">Não</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Tipo de ocorrência</Label>
                <Select value={filters.tipoArea} onValueChange={v => setFilters(f => ({ ...f, tipoArea: v }))}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todos">Todos</SelectItem>
                    {tipoOptions.map(t => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Mostrando <strong>{totalChamados}</strong> de {occurrences.length} ocorrências carregadas.
            </p>
          </CardContent>
        </Card>
      </div>

      <div>
        <Card className="border border-border shadow-sm overflow-hidden">
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-heading">Visualização Geoespacial</CardTitle>
            {filteredOccurrences.length > MAP_POINT_LIMIT && (
              <p className="text-[10px] text-muted-foreground mt-1">
                Mapa com amostra de até {MAP_POINT_LIMIT.toLocaleString('pt-BR')} pontos para manter o desempenho.
              </p>
            )}
          </CardHeader>
          <CardContent className="p-0 relative">
            {refetching && (
              <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 bg-background/70 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Atualizando período…
              </div>
            )}
            <KeplerOccurrenceMap occurrences={filteredOccurrences} height={460} />
          </CardContent>
        </Card>
      </div>

      <div>
        <Card className="border border-border shadow-sm">
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-heading">Estatísticas</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Total de Chamados (filtrado)</p>
                <p className="text-4xl font-heading font-bold text-primary">
                  {totalChamados.toLocaleString('pt-BR')}
                </p>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground mb-3">Bairros Afetados</h4>
                <div className="w-full h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={displayBairroStats.slice(0, 10)}
                      layout="vertical"
                      margin={{ top: 0, right: 10, left: 0, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis type="number" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                        width={90}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                          fontSize: '11px',
                        }}
                      />
                      <Bar dataKey="count" name="Ocorrências" fill="hsl(var(--secondary))" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div>
        <Card className="border border-border shadow-sm">
          <CardHeader className="py-3 flex flex-row items-center justify-between gap-2">
            <CardTitle className="text-sm font-heading">Lista de chamados</CardTitle>
            {filteredOccurrences.length > TABLE_PREVIEW_LIMIT && (
              <span className="text-xs text-muted-foreground">
                Exibindo os primeiros {TABLE_PREVIEW_LIMIT} registros
              </span>
            )}
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Data</TableHead>
                  <TableHead className="text-xs">Bairro</TableHead>
                  <TableHead className="text-xs">Tipo</TableHead>
                  <TableHead className="text-xs">Serviço</TableHead>
                  <TableHead className="text-xs">Interdição</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tableRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-8">
                      Nenhum registro para os filtros selecionados.
                    </TableCell>
                  </TableRow>
                ) : (
                  tableRows.map(row => (
                    <TableRow key={row.id}>
                      <TableCell className="text-xs">{row.date || '—'}</TableCell>
                      <TableCell className="text-xs">{row.bairro}</TableCell>
                      <TableCell className="text-xs">{row.tipo}</TableCell>
                      <TableCell className="text-xs capitalize">{row.servico || '—'}</TableCell>
                      <TableCell className="text-xs">{row.interdicao ? 'Sim' : 'Não'}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
