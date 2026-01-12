import { useEffect, useState } from 'react';
import { getConferences } from '../api';
import ConferenceCard from '../components/ConferenceCard';
import type { Conference } from '../types';
import './ConferenceList.css';

export default function ConferenceList() {
  const [conferences, setConferences] = useState<Conference[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchConferences() {
      try {
        const data = await getConferences();
        setConferences(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load conferences');
      } finally {
        setLoading(false);
      }
    }
    fetchConferences();
  }, []);

  // Group conferences by year and sort
  const conferencesByYear = conferences.reduce<Record<number, Conference[]>>((acc, conf) => {
    const year = conf.year || new Date().getFullYear();
    if (!acc[year]) {
      acc[year] = [];
    }
    acc[year].push(conf);
    return acc;
  }, {});

  // Sort conferences within each year by start date (descending)
  Object.values(conferencesByYear).forEach(yearConfs => {
    yearConfs.sort((a, b) => {
      const dateA = a.dates?.start ? new Date(a.dates.start).getTime() : 0;
      const dateB = b.dates?.start ? new Date(b.dates.start).getTime() : 0;
      return dateB - dateA;
    });
  });

  // Get sorted years (descending)
  const sortedYears = Object.keys(conferencesByYear)
    .map(Number)
    .sort((a, b) => b - a);

  if (loading) {
    return (
      <div className="conference-list-page">
        <div className="loading">Loading conferences...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="conference-list-page">
        <div className="error">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="conference-list-page">
      <header className="page-header">
        <h1>Academic Conferences</h1>
        <p>Browse conferences and discover researchers</p>
      </header>

      {sortedYears.map(year => (
        <section key={year} className="year-section">
          <h2 className="year-heading">{year}</h2>
          <div className="conference-grid">
            {conferencesByYear[year].map(conference => (
              <ConferenceCard key={conference.id} conference={conference} />
            ))}
          </div>
        </section>
      ))}

      {conferences.length === 0 && (
        <div className="empty-state">No conferences found.</div>
      )}
    </div>
  );
}
