import { Link } from 'react-router-dom';
import type { Conference } from '../types';
import './ConferenceCard.css';

interface ConferenceCardProps {
  conference: Conference;
}

function formatDateRange(dates?: { start?: string; end?: string }): string {
  if (!dates?.start) return '';
  const start = new Date(dates.start);
  const end = dates.end ? new Date(dates.end) : null;

  const options: Intl.DateTimeFormatOptions = {
    month: 'short',
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
  const parts = [location.city, location.country].filter(Boolean);
  return parts.join(', ');
}

export default function ConferenceCard({ conference }: ConferenceCardProps) {
  return (
    <Link to={`/conference/${conference.id}`} className="conference-card">
      <div className="conference-card-image">
        {conference.logo_url ? (
          <img src={conference.logo_url} alt={conference.name} />
        ) : (
          <div className="conference-card-placeholder">
            {conference.shortName || conference.name.slice(0, 4)}
          </div>
        )}
      </div>
      <div className="conference-card-content">
        <h3 className="conference-card-title">
          {conference.shortName || conference.name}
        </h3>
        <p className="conference-card-name">{conference.name}</p>
        {conference.location && (
          <p className="conference-card-location">
            {formatLocation(conference.location)}
          </p>
        )}
        {conference.dates && (
          <p className="conference-card-dates">
            {formatDateRange(conference.dates)}
          </p>
        )}
      </div>
    </Link>
  );
}
