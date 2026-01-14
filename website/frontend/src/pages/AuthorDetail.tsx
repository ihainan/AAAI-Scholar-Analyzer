import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAuthorDetail, getConferences, getPhotoUrl } from '../api';
import type { AuthorDetail as AuthorDetailType, Conference } from '../types';
import './AuthorDetail.css';

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function cleanBio(bio: string): string {
  return bio.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '');
}

function parseEducation(edu: string): string[] {
  return edu
    .split(/<br\s*\/?>/gi)
    .map(entry => entry.replace(/<[^>]*>/g, '').trim())
    .filter(entry => entry.length > 0);
}

export default function AuthorDetail() {
  const { conferenceId, authorName } = useParams<{ conferenceId: string; authorName: string }>();
  const [author, setAuthor] = useState<AuthorDetailType | null>(null);
  const [conference, setConference] = useState<Conference | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    async function fetchData() {
      if (!conferenceId || !authorName) return;

      setLoading(true);
      try {
        const [conferencesData, authorData] = await Promise.all([
          getConferences(),
          getAuthorDetail(conferenceId, decodeURIComponent(authorName)),
        ]);

        const conf = conferencesData.find(c => c.id === conferenceId);
        if (!conf) {
          throw new Error('Conference not found');
        }

        setConference(conf);
        setAuthor(authorData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load author details');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [conferenceId, authorName]);

  if (loading) {
    return (
      <div className="scholar-detail-page">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (error || !author || !conference) {
    return (
      <div className="scholar-detail-page">
        <div className="error">Error: {error || 'Author not found'}</div>
        <Link to={`/conference/${conferenceId}?tab=authors`} className="back-link">
          Back to Authors
        </Link>
      </div>
    );
  }

  const externalLinks = [
    { url: author.homepage, label: 'Homepage' },
    { url: author.google_scholar, label: 'Google Scholar' },
    { url: author.aminer_id ? `https://www.aminer.cn/profile/${author.aminer_id}` : undefined, label: 'AMiner' },
    { url: author.dblp, label: 'DBLP' },
    { url: author.semantic_scholar, label: 'Semantic Scholar' },
    { url: author.orcid, label: 'ORCID' },
    { url: author.linkedin, label: 'LinkedIn' },
    { url: author.twitter, label: 'Twitter' },
  ].filter(link => link.url);

  // Filter out "Unknown Track Author" role
  const displayRoles = author.roles?.filter(role => !role.includes('Unknown')) || [];

  return (
    <div className="scholar-detail-page">
      <nav className="breadcrumb">
        <Link to="/">Conferences</Link>
        <span className="separator">/</span>
        <Link to={`/conference/${conferenceId}`}>
          {conference?.shortName || conference?.name || conferenceId}
        </Link>
        <span className="separator">/</span>
        <Link to={`/conference/${conferenceId}?tab=authors`}>Authors</Link>
        <span className="separator">/</span>
        <span>{author.name}</span>
      </nav>

      <div className="scholar-content">
        <aside className="scholar-sidebar">
          <div className="scholar-avatar-large">
            {author.photo_url && !imageError ? (
              <img
                src={getPhotoUrl(author.photo_url) || ''}
                alt={author.name}
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="avatar-placeholder-large">
                {getInitials(author.name)}
              </div>
            )}
          </div>

          {externalLinks.length > 0 && (
            <div className="external-links">
              <h3>Links</h3>
              <ul>
                {externalLinks.map((link, index) => (
                  <li key={index}>
                    <a href={link.url} target="_blank" rel="noopener noreferrer">
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {author.email && (
            <div className="contact-info">
              <h3>Contact</h3>
              <p>
                <a href={`mailto:${author.email}`}>{author.email}</a>
              </p>
            </div>
          )}
        </aside>

        <main className="scholar-main">
          <header className="scholar-header">
            <h1>{author.name}</h1>
            {author.labels && author.labels.results.length > 0 && (
              <div className="scholar-labels">
                {author.labels.results
                  .filter(label => label.value === true && (label.confidence === 'high' || label.confidence === 'medium'))
                  .map((label, index) => (
                    <span key={index} className="scholar-label-wrapper">
                      <span className="scholar-label">
                        {label.name}
                      </span>
                      {label.reason && (
                        <span className="scholar-label-tooltip">
                          {label.reason}
                        </span>
                      )}
                    </span>
                  ))}
              </div>
            )}
            {author.position && (
              <p className="position">{author.position}</p>
            )}
            {author.organizations && author.organizations.length > 0 && (
              <p className="affiliation">{author.organizations.join(', ')}</p>
            )}
          </header>

          {displayRoles.length > 0 && (
            <section className="section">
              <h2>Conference Roles</h2>
              <ul className="roles-list">
                {displayRoles.map((role, index) => (
                  <li key={index}>{role}</li>
                ))}
              </ul>
            </section>
          )}

          {/* Papers section - unique to authors */}
          {author.papers && author.papers.length > 0 && (
            <section className="section">
              <h2>Papers at {conference.shortName || conference.name} ({author.papers.length})</h2>
              <div className="papers-list">
                {author.papers.map((paper, index) => (
                  <div key={paper.paper_id || index} className="paper-item">
                    <h3 className="paper-title">{paper.title}</h3>
                    <div className="paper-metadata">
                      <span className="paper-id">{paper.paper_id}</span>
                      {paper.track && !paper.track.includes('Unknown') && (
                        <span className="paper-track">{paper.track}</span>
                      )}
                    </div>
                    {paper.session && (
                      <p className="paper-session">{paper.session}</p>
                    )}
                    {(paper.date || paper.room) && (
                      <p className="paper-schedule">
                        {paper.date && <span>{paper.date}</span>}
                        {paper.date && paper.room && <span className="separator"> • </span>}
                        {paper.room && <span>{paper.room}</span>}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Collaborators section - unique to authors */}
          {author.collaborators && author.collaborators.length > 0 && (
            <section className="section">
              <h2>Collaborators ({author.collaborators.length})</h2>
              <div className="collaborators-tags">
                {author.collaborators.map((collaborator, index) => (
                  <span key={index} className="collaborator-tag">
                    {collaborator}
                  </span>
                ))}
              </div>
            </section>
          )}

          {author.bio && (
            <section className="section">
              <h2>Biography</h2>
              <p className="bio">{cleanBio(author.bio)}</p>
            </section>
          )}

          {author.description && !author.bio && (
            <section className="section">
              <h2>About</h2>
              <p className="bio">{author.description}</p>
            </section>
          )}

          {author.additional_info && (
            <section className="section">
              <h2>Additional Information</h2>
              <p className="bio">{author.additional_info}</p>
            </section>
          )}

          {author.education && (
            <section className="section">
              <h2>Education</h2>
              <ul className="education-list">
                {parseEducation(author.education).map((entry, index) => (
                  <li key={index}>{entry}</li>
                ))}
              </ul>
            </section>
          )}

          {author.honors && author.honors.length > 0 && (
            <section className="section">
              <h2>Honors & Awards</h2>
              <ul className="honors-list">
                {author.honors.map((honor, index) => (
                  <li key={index}>
                    <span className="honor-award">{honor.award}</span>
                    {honor.year && <span className="honor-year">({honor.year})</span>}
                    {honor.reason && <p className="honor-reason">{honor.reason}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {author.research_interests && author.research_interests.length > 0 && (
            <section className="section">
              <h2>Research Interests</h2>
              <div className="interests-tags">
                {author.research_interests
                  .sort((a, b) => (a.order || 999) - (b.order || 999))
                  .slice(0, 20)
                  .map((interest, index) => (
                    <span key={index} className="interest-tag">
                      {interest.name}
                    </span>
                  ))}
              </div>
            </section>
          )}

          {author.source_urls && author.source_urls.length > 0 && (
            <section className="section sources-section">
              <h2>Sources</h2>
              <ul className="sources-list">
                {author.source_urls.map((url, index) => (
                  <li key={index}>
                    <a href={url} target="_blank" rel="noopener noreferrer">
                      {url}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
