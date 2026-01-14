import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, PolarRadiusAxis, Tooltip } from 'recharts';
import type { AcademicIndices } from '../types';
import './AcademicRadarChart.css';

interface AcademicRadarChartProps {
  indices: AcademicIndices;
}

// Normalize function to map values to 0-100 scale
function normalizeValue(value: number, max: number): number {
  if (max === 0) return 0;
  return Math.min(100, (value / max) * 100);
}

// Custom tooltip component
function CustomTooltip({ active, payload }: any) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="radar-tooltip">
        <p className="tooltip-label">{data.fullName}</p>
        <p className="tooltip-value">{data.actualValue}</p>
      </div>
    );
  }
  return null;
}

export default function AcademicRadarChart({ indices }: AcademicRadarChartProps) {
  // Define max values for normalization (based on typical academic metrics)
  const maxValues = {
    hindex: 100,      // H-Index rarely exceeds 100
    gindex: 150,      // G-Index is typically higher than H-Index
    citations: 20000, // Citations can be very high
    pubs: 500,        // Publications
    activity: 600,    // Activity score
    diversity: 10,    // Diversity (typically 0-10)
    sociability: 10,  // Sociability (typically 0-10)
  };

  // Build radar data with actual values for tooltip
  const data = [
    {
      metric: 'H-Idx',
      fullName: 'H-Index',
      value: indices.hindex ? normalizeValue(indices.hindex, maxValues.hindex) : 0,
      actualValue: indices.hindex || 0,
      fullMark: 100,
    },
    {
      metric: 'G-Idx',
      fullName: 'G-Index',
      value: indices.gindex ? normalizeValue(indices.gindex, maxValues.gindex) : 0,
      actualValue: indices.gindex || 0,
      fullMark: 100,
    },
    {
      metric: 'Cites',
      fullName: 'Citations',
      value: indices.citations ? normalizeValue(indices.citations, maxValues.citations) : 0,
      actualValue: indices.citations ? indices.citations.toLocaleString() : 0,
      fullMark: 100,
    },
    {
      metric: 'Pubs',
      fullName: 'Publications',
      value: indices.pubs ? normalizeValue(indices.pubs, maxValues.pubs) : 0,
      actualValue: indices.pubs || 0,
      fullMark: 100,
    },
    {
      metric: 'Act',
      fullName: 'Activity',
      value: indices.activity ? normalizeValue(indices.activity, maxValues.activity) : 0,
      actualValue: indices.activity ? indices.activity.toFixed(1) : 0,
      fullMark: 100,
    },
    {
      metric: 'Div',
      fullName: 'Diversity',
      value: indices.diversity ? normalizeValue(indices.diversity, maxValues.diversity) : 0,
      actualValue: indices.diversity ? indices.diversity.toFixed(1) : 0,
      fullMark: 100,
    },
    {
      metric: 'Soc',
      fullName: 'Sociability',
      value: indices.sociability ? normalizeValue(indices.sociability, maxValues.sociability) : 0,
      actualValue: indices.sociability ? indices.sociability.toFixed(1) : 0,
      fullMark: 100,
    },
  ];

  return (
    <div className="academic-radar-chart">
      <h3>Academic Metrics</h3>
      <ResponsiveContainer width="100%" height={180}>
        <RadarChart
          data={data}
          cx="50%"
          cy="50%"
          outerRadius="65%"
          margin={{ top: 5, right: 5, bottom: 5, left: 5 }}
        >
          <PolarGrid stroke="#e0e0e0" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: '#666', fontSize: 10 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={false}
            axisLine={false}
          />
          <Radar
            name="Metrics"
            dataKey="value"
            stroke="#4CAF50"
            fill="#4CAF50"
            fillOpacity={0.5}
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
