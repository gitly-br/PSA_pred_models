import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { WeatherHour } from '@/services/mockData';

interface WeatherChartProps {
  data: WeatherHour[];
}

export default function WeatherChart({ data }: WeatherChartProps) {
  const totalPrecipitation = data.reduce((sum, item) => sum + item.precipitation, 0);
  const averageTemperature = data.length
    ? data.reduce((sum, item) => sum + item.temperature, 0) / data.length
    : 0;
  const maxPrecipitation = Math.max(0, ...data.map(item => item.precipitation));
  const rainyHours = data.filter(item => item.precipitation > 0.05).length;
  const forecastDescription = totalPrecipitation < 1
    ? 'Sem chuva relevante prevista para Santo André no período selecionado.'
    : totalPrecipitation < 5
      ? 'Chuva fraca e localizada prevista para Santo André, com baixo volume acumulado.'
      : 'Há previsão de chuva acumulada mais relevante; acompanhar pontos de atenção do município.';

  return (
    <Card className="border border-border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="font-heading text-base">Previsão do Tempo</CardTitle>
        <p className="text-xs text-muted-foreground">
          Dados climáticos de Santo André fornecidos por OpenWeather.
        </p>
      </CardHeader>
      <CardContent>
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-4">
          <div className="rounded-lg border border-border bg-muted/35 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Temperatura média</p>
            <p className="mt-1 text-lg font-heading font-bold text-foreground">{averageTemperature.toFixed(1)}°C</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/35 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Chuva acumulada</p>
            <p className="mt-1 text-lg font-heading font-bold text-foreground">{totalPrecipitation.toFixed(1)} mm</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/35 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Pico horário</p>
            <p className="mt-1 text-lg font-heading font-bold text-foreground">{maxPrecipitation.toFixed(2)} mm</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/35 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Horas com chuva</p>
            <p className="mt-1 text-lg font-heading font-bold text-foreground">{rainyHours}h</p>
          </div>
        </div>
        <p className="mb-4 rounded-lg border border-secondary/25 bg-secondary/10 px-3 py-2 text-sm text-foreground">
          {forecastDescription}
        </p>
        <div className="w-full h-[300px] md:h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="hour"
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                interval={1}
              />
              <YAxis
                yAxisId="temp"
                orientation="left"
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                label={{
                  value: 'Temperatura (°C)',
                  angle: -90,
                  position: 'insideLeft',
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
              />
              <YAxis
                yAxisId="precip"
                orientation="right"
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                label={{
                  value: 'Volume de chuva (mm)',
                  angle: 90,
                  position: 'insideRight',
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
              />
              <Tooltip
                contentStyle={{
                  background: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: '12px' }}
              />
              <Bar
                yAxisId="precip"
                dataKey="precipitation"
                name="Precipitação horária"
                fill="hsl(var(--chart-5))"
                opacity={0.6}
                radius={[2, 2, 0, 0]}
              />
              <Line
                yAxisId="temp"
                type="monotone"
                dataKey="temperature"
                name="Temperatura"
                stroke="hsl(var(--destructive))"
                strokeWidth={2}
                dot={{ r: 2, fill: 'hsl(var(--destructive))' }}
                activeDot={{ r: 4 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
