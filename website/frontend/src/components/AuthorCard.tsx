import { Link } from 'react-router-dom';
import type { AuthorBasic } from '../types';
import { getPhotoUrl } from '../api';
import './AuthorCard.css';

interface AuthorCardProps {
  author: AuthorBasic;
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

export default function AuthorCard({ author, conferenceId }: AuthorCardProps) {
  // Filter out "Unknown Track Author" role
  const displayRoles = author.roles.filter(role => !role.includes('Unknown'));

  return (
    <Link
      to={`/conference/${conferenceId}/author/${encodeURIComponent(author.name)}`}
      className="author-card"
    >
      <div className="author-card-avatar">
        {author.photo_url ? (
          <img
            src={getPhotoUrl(author.photo_url) || ''}
            alt={author.name}
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.style.display = 'none';
              const parent = target.parentElement;
              if (parent) {
                const placeholder = document.createElement('div');
                placeholder.className = 'author-card-avatar-placeholder';
                placeholder.textContent = getInitials(author.name);
                parent.appendChild(placeholder);
              }
            }}
          />
        ) : (
          <div className="author-card-avatar-placeholder">
            {getInitials(author.name)}
          </div>
        )}
      </div>
      <div className="author-card-content">
        <h3 className="author-card-name">{author.name}</h3>
        {displayRoles.length > 0 && (
          <p className="author-card-roles">{displayRoles.join(', ')}</p>
        )}
        <div className="author-card-stats">
          <span className="stat-item">
            {author.statistics.total_papers} {author.statistics.total_papers === 1 ? 'paper' : 'papers'}
          </span>
        </div>
      </div>
    </Link>
  );
}
