import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";
import { trend } from "../data/mockData";
export function TrendChart({
  data = trend,
}: {
  data?: { date: string; high: number; medium: number }[];
}) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 16, right: 12, left: -28, bottom: 0 }}
        >
          <defs>
            <linearGradient id="teal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#bd9556" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#bd9556" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="4 5"
            vertical={false}
            stroke="#e8eef1"
          />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#8a99a8", fontSize: 12 }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#8a99a8", fontSize: 12 }}
            allowDecimals={false}
          />
          <Tooltip />
          <Area
            type="monotone"
            dataKey="medium"
            name="中风险"
            stroke="#bd9556"
            strokeWidth={2.5}
            fill="url(#teal)"
          />
          <Area
            type="monotone"
            dataKey="high"
            name="高风险"
            stroke="#c47c77"
            strokeWidth={2}
            fill="transparent"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Distribution({
  data,
  bar = false,
}: {
  data: { name: string; value: number }[];
  bar?: boolean;
}) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        {bar ? (
          <BarChart data={data}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" name="事件数" radius={[6, 6, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={["#c47c77", "#bd9556", "#76a18a"][i % 3]} />
              ))}
            </Bar>
          </BarChart>
        ) : (
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={52}
              outerRadius={80}
              paddingAngle={4}
              label={({ name, value }) => `${name} ${value}`}
            >
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={
                    ["#6e8faf", "#96adc2", "#b7c5d1", "#c9b493", "#d2d6dc"][
                      i % 5
                    ]
                  }
                />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}


