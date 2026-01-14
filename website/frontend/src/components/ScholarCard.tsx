import { Link } from 'react-router-dom';
import type { ScholarBasic } from '../types';
import { getPhotoUrl } from '../api';
import './ScholarCard.css';

interface ScholarCardProps {
  scholar: ScholarBasic & {
    paper_count?: number;
    h_index?: number;
    n_citation?: number;
    n_pubs?: number;
    organization?: string;
    organization_zh?: string;
  };
  conferenceId: string;
  showMetrics?: boolean;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export default function ScholarCard({ scholar, conferenceId, showMetrics = false }: ScholarCardProps) {
  const searchParam = scholar.aminer_id
    ? `aminer_id=${scholar.aminer_id}`
    : `name=${encodeURIComponent(scholar.name)}`;

  // Get organization to display (prefer Chinese, fallback to English)
  // Handle multiple organizations: take first one (split by semicolon or comma)
  const getFirstOrg = (org?: string) => {
    if (!org) return undefined;
    return org.split(/[;,]/)[0].trim();
  };

  const displayOrg = getFirstOrg(scholar.organization_zh) || getFirstOrg(scholar.organization);

  return (
    <Link
      to={`/conference/${conferenceId}/scholar?${searchParam}`}
      className="scholar-card"
    >
      <div className="scholar-card-avatar">
        {scholar.photo_url ? (
          <img
            src={getPhotoUrl(scholar.photo_url) || ''}
            alt={scholar.name}
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.style.display = 'none';
              const parent = target.parentElement;
              if (parent) {
                const placeholder = document.createElement('div');
                placeholder.className = 'scholar-card-avatar-placeholder';
                placeholder.textContent = getInitials(scholar.name);
                parent.appendChild(placeholder);
              }
            }}
          />
        ) : (
          <div className="scholar-card-avatar-placeholder">
            {getInitials(scholar.name)}
          </div>
        )}
      </div>
      <div className="scholar-card-content">
        <h3 className="scholar-card-name">{scholar.name}</h3>
        {scholar.roles && scholar.roles.length > 0 && (
          <p className="scholar-card-roles">{scholar.roles.join(', ')}</p>
        )}
        {displayOrg && (
          <p className="scholar-card-affiliation" title={displayOrg}>{displayOrg}</p>
        )}
        {!displayOrg && scholar.affiliation && (
          <p className="scholar-card-affiliation" title={scholar.affiliation}>{scholar.affiliation}</p>
        )}
        {showMetrics && (
          <div className="scholar-card-metrics">
            {scholar.paper_count !== undefined && scholar.paper_count > 0 && (
              <span className="metric" title="Conference Papers">
                Papers: {scholar.paper_count}
              </span>
            )}
            {scholar.n_citation !== undefined && scholar.n_citation > 0 && (
              <span className="metric" title="Total Citations">
                Citations: {scholar.n_citation.toLocaleString()}
              </span>
            )}
            {scholar.h_index !== undefined && scholar.h_index > 0 && (
              <span className="metric" title="H-Index">
                H-Index: {scholar.h_index}
              </span>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}
