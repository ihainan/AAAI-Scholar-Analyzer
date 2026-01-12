import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getConferences, getConferenceScholars } from '../api';
import ScholarCard from '../components/ScholarCard';
import type { Conference, ScholarBasic } from '../types';
import './ConferenceDetail.css';

function formatDateRange(dates?: { start?: string; end?: string }): string {
  if (!dates?.start) return '';
  const start = new Date(dates.start);
  const end = dates.end ? new Date(dates.end) : null;

  const options: Intl.DateTimeFormatOptions = {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  };

  if (end) {
    return `${start.toLocaleDateString('en-US', options)} - ${end.toLocaleDateString('en-US', options)}`;
  }
  return start.toLocaleDateString('en-US', options);
}

function formatLocation(location?: { venue?: string; city?: string; country?: string }): string {
  if (!location) return '';
  const parts = [location.venue, location.city, location.country].filter(Boolean);
  return parts.join(', ');
}

export default function ConferenceDetail() {
  const { conferenceId } = useParams<{ conferenceId: string }>();
  const [conference, setConference] = useState<Conference | null>(null);
  const [scholars, setScholars] = useState<ScholarBasic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      if (!conferenceId) return;

      try {
        const [conferencesData, scholarsData] = await Promise.all([
          getConferences(),
          getConferenceScholars(conferenceId),
        ]);

        const conf = conferencesData.find(c => c.id === conferenceId);
        if (!conf) {
          throw new Error('Conference not found');
        }

        setConference(conf);
        setScholars(scholarsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [conferenceId]);

  if (loading) {
    return (
      <div className="conference-detail-page">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (error || !conference) {
    return (
      <div className="conference-detail-page">
        <div className="error">Error: {error || 'Conference not found'}</div>
        <Link to="/" className="back-link">Back to Conferences</Link>
      </div>
    );
  }

  return (
    <div className="conference-detail-page">
      <nav className="breadcrumb">
        <Link to="/">Conferences</Link>
        <span className="separator">/</span>
        <span>{conference.shortName || conference.name}</span>
      </nav>

      <header className="conference-header">
        {conference.logo_url && (
          <div className="conference-logo">
            <img src={conference.logo_url} alt={conference.name} />
          </div>
        )}
        <div className="conference-info">
          <h1>{conference.name}</h1>
          {conference.dates && (
            <p className="conference-dates">{formatDateRange(conference.dates)}</p>
          )}
          {conference.location && (
            <p className="conference-location">{formatLocation(conference.location)}</p>
          )}
          {conference.description && (
            <p className="conference-description">{conference.description}</p>
          )}
          {conference.urls && conference.urls.length > 0 && (
            <div className="conference-links">
              {conference.urls.map((urlInfo, index) => (
                <a
                  key={index}
                  href={urlInfo.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="conference-link"
                >
                  {urlInfo.name || 'Link'}
                </a>
              ))}
            </div>
          )}
          {conference.tags && conference.tags.length > 0 && (
            <div className="conference-tags">
              {conference.tags.map((tag, index) => (
                <span key={index} className="tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </header>

      <section className="scholars-section">
        <h2>Conference Participants ({scholars.length})</h2>
        <div className="scholars-grid">
          {scholars.map((scholar, index) => (
            <ScholarCard
              key={scholar.aminer_id || `${scholar.name}-${index}`}
              scholar={scholar}
              conferenceId={conferenceId!}
            />
          ))}
        </div>
        {scholars.length === 0 && (
          <div className="empty-state">No participants found.</div>
        )}
      </section>
    </div>
  );
}
