import { Link } from 'react-router-dom';
import type { ScholarBasic } from '../types';
import { getPhotoUrl } from '../api';
import './ScholarCard.css';

interface ScholarCardProps {
  scholar: ScholarBasic;
  conferenceId: string;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export default function ScholarCard({ scholar, conferenceId }: ScholarCardProps) {
  const searchParam = scholar.aminer_id
    ? `aminer_id=${scholar.aminer_id}`
    : `name=${encodeURIComponent(scholar.name)}`;

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
        {scholar.roles.length > 0 && (
          <p className="scholar-card-roles">{scholar.roles.join(', ')}</p>
        )}
        {scholar.affiliation && (
          <p className="scholar-card-affiliation">{scholar.affiliation}</p>
        )}
      </div>
    </Link>
  );
}
