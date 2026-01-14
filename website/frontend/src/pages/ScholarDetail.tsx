import { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { searchScholar, getConferences, getPhotoUrl } from '../api';
import type { ScholarDetail as ScholarDetailType, Conference, ConferencePaperAuthor } from '../types';
import AcademicRadarChart from '../components/AcademicRadarChart';
import './ScholarDetail.css';

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function cleanBio(bio: string): string {
  // Remove HTML tags like <br>
  return bio.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '');
}

function parseEducation(edu: string): string[] {
  // Split by <br> tags and filter out empty entries
  return edu
    .split(/<br\s*\/?>/gi)
    .map(entry => entry.replace(/<[^>]*>/g, '').trim())
    .filter(entry => entry.length > 0);
}

function parseAdditionalInfo(info: string): string[] {
  // Split by periods (sentences) and filter out empty entries
  return info
    .split(/\.\s+/)
    .map(entry => entry.trim())
    .filter(entry => entry.length > 0)
    .map(entry => entry.endsWith('.') ? entry : entry + '.');
}

export default function ScholarDetail() {
  const { conferenceId } = useParams<{ conferenceId: string }>();
  const [searchParams] = useSearchParams();
  const [scholar, setScholar] = useState<ScholarDetailType | null>(null);
  const [conference, setConference] = useState<Conference | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);

  const fromPage = searchParams.get('from');

  useEffect(() => {
    async function fetchData() {
      if (!conferenceId) return;

      const name = searchParams.get('name');
      const aminerId = searchParams.get('aminer_id');

      if (!name && !aminerId) {
        setError('No scholar identifier provided');
        setLoading(false);
        return;
      }

      try {
        const [scholarsData, conferencesData] = await Promise.all([
          searchScholar(conferenceId, { name: name || undefined, aminer_id: aminerId || undefined }),
          getConferences(),
        ]);

        if (scholarsData.length === 0) {
          throw new Error('Scholar not found');
        }

        setScholar(scholarsData[0]);
        const conf = conferencesData.find(c => c.id === conferenceId);
        setConference(conf || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [conferenceId, searchParams]);

  if (loading) {
    return (
      <div className="scholar-detail-page">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (error || !scholar) {
    return (
      <div className="scholar-detail-page">
        <div className="error">Error: {error || 'Scholar not found'}</div>
        <Link to={`/conference/${conferenceId}`} className="back-link">
          Back to Conference
        </Link>
      </div>
    );
  }

  const externalLinks = [
    { url: scholar.homepage, label: 'Homepage' },
    { url: scholar.google_scholar, label: 'Google Scholar' },
    { url: scholar.aminer_id ? `https://www.aminer.cn/profile/${scholar.aminer_id}` : undefined, label: 'AMiner' },
    { url: scholar.dblp, label: 'DBLP' },
    { url: scholar.semantic_scholar, label: 'Semantic Scholar' },
    { url: scholar.orcid, label: 'ORCID' },
    { url: scholar.linkedin, label: 'LinkedIn' },
    { url: scholar.twitter, label: 'Twitter' },
  ].filter(link => link.url);

  return (
    <div className="scholar-detail-page">
      <nav className="breadcrumb">
        <Link to="/">Conferences</Link>
        <span className="separator">/</span>
        <Link to={`/conference/${conferenceId}`}>
          {conference?.shortName || conference?.name || conferenceId}
        </Link>
        <span className="separator">/</span>
        {fromPage === 'people' ? (
          <>
            <Link to={`/conference/${conferenceId}/people`}>Scholars</Link>
            <span className="separator">/</span>
          </>
        ) : null}
        <span>{scholar.name}</span>
      </nav>

      <div className="scholar-content">
        <aside className="scholar-sidebar">
          <div className="scholar-avatar-large">
            {scholar.photo_url && !imageError ? (
              <img
                src={getPhotoUrl(scholar.photo_url) || ''}
                alt={scholar.name}
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="avatar-placeholder-large">
                {getInitials(scholar.name)}
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

          {scholar.indices && (
            <AcademicRadarChart indices={scholar.indices} />
          )}

          {scholar.email && (() => {
            // Split by semicolon or comma, trim whitespace, and get first email
            const firstEmail = scholar.email.split(/[;,]/)[0].trim();
            return (
              <div className="contact-info">
                <h3>Contact</h3>
                <p>
                  <a href={`mailto:${firstEmail}`}>{firstEmail}</a>
                </p>
              </div>
            );
          })()}
        </aside>

        <main className="scholar-main">
          <header className="scholar-header">
            <h1>{scholar.name}</h1>
            {scholar.labels && scholar.labels.results.length > 0 && (
              <div className="scholar-labels">
                {scholar.labels.results
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
            {scholar.aliases && scholar.aliases.length > 0 && (
              <p className="aliases">Also known as: {scholar.aliases.join(', ')}</p>
            )}
            {scholar.position && (
              <p className="position">{scholar.position}</p>
            )}
            {scholar.affiliation && (
              <p className="affiliation">{scholar.affiliation}</p>
            )}
            {scholar.organizations && scholar.organizations.length > 0 && !scholar.affiliation && (
              <p className="affiliation">{scholar.organizations.join(', ')}</p>
            )}
          </header>

          {scholar.roles && scholar.roles.length > 0 && (
            <section className="section">
              <h2>Conference Roles</h2>
              <ul className="roles-list">
                {scholar.roles.map((role, index) => (
                  <li key={index}>{role}</li>
                ))}
              </ul>
            </section>
          )}

          {scholar.bio && (
            <section className="section">
              <h2>Biography</h2>
              <p className="bio">{cleanBio(scholar.bio)}</p>
            </section>
          )}

          {scholar.description && !scholar.bio && (
            <section className="section">
              <h2>About</h2>
              <p className="bio">{scholar.description}</p>
            </section>
          )}

          {scholar.additional_info && (
            <section className="section">
              <h2>Additional Information</h2>
              <ul className="additional-info-list">
                {parseAdditionalInfo(scholar.additional_info).map((entry, index) => (
                  <li key={index}>{entry}</li>
                ))}
              </ul>
            </section>
          )}

          {scholar.education && (
            <section className="section">
              <h2>Education</h2>
              <ul className="education-list">
                {parseEducation(scholar.education).map((entry, index) => (
                  <li key={index}>{entry}</li>
                ))}
              </ul>
            </section>
          )}

          {scholar.conference_papers && scholar.conference_papers.length > 0 && (
            <section className="section">
              <h2>Conference Papers</h2>
              <div className="conference-papers-list">
                {(() => {
                  // Group papers by title to merge duplicates with different presentation types
                  const papersByTitle = new Map();
                  scholar.conference_papers.forEach(paper => {
                    const existing = papersByTitle.get(paper.title);
                    if (existing) {
                      // Merge presentation types
                      if (paper.presentation_type && !existing.presentation_types.includes(paper.presentation_type)) {
                        existing.presentation_types.push(paper.presentation_type);
                      }
                      // Keep the best author position (lowest number = earlier author)
                      if (paper.author_position !== undefined &&
                          (existing.author_position === undefined || paper.author_position < existing.author_position)) {
                        existing.author_position = paper.author_position;
                      }
                    } else {
                      papersByTitle.set(paper.title, {
                        ...paper,
                        presentation_types: paper.presentation_type ? [paper.presentation_type] : []
                      });
                    }
                  });

                  // Convert map to array and sort by author position
                  return Array.from(papersByTitle.values())
                    .sort((a, b) => {
                      const posA = a.author_position ?? 999;
                      const posB = b.author_position ?? 999;
                      return posA - posB;
                    })
                    .map((paper, index) => (
                      <div key={index} className="paper-card">
                        <div className="paper-header">
                          <h3 className="paper-title">{paper.title}</h3>
                          <div className="paper-badges">
                            {paper.track && (
                              <span className="badge badge-track">{paper.track}</span>
                            )}
                            {paper.presentation_types && paper.presentation_types.length > 0 &&
                              paper.presentation_types.map((type: string, typeIndex: number) => (
                                <span key={typeIndex} className={`badge badge-${type}`}>
                                  {type}
                                </span>
                              ))
                            }
                          </div>
                        </div>

                    {(paper.date || paper.session || paper.room) && (
                      <div className="paper-info">
                        {paper.date && <span className="paper-date">{paper.date}</span>}
                        {paper.session && <span className="paper-session">{paper.session}</span>}
                        {paper.room && <span className="paper-room">{paper.room}</span>}
                      </div>
                    )}

                    {(paper.authors && paper.authors.length > 0) && (
                      <div className="paper-coauthors">
                        <span className="coauthors-label">Authors: </span>
                        {paper.authors.map((author: ConferencePaperAuthor, authorIndex: number) => {
                          // Check if this author is the current scholar
                          const isCurrentScholar =
                            (scholar.aminer_id && author.aminer_id === scholar.aminer_id) ||
                            (!scholar.aminer_id && author.name.toLowerCase() === scholar.name.toLowerCase());

                          return (
                            <span key={authorIndex}>
                              {author.in_conference && author.aminer_id ? (
                                <a
                                  href={`/conference/${conferenceId}/scholar?aminer_id=${author.aminer_id}`}
                                  className={`coauthor-link${isCurrentScholar ? ' current-scholar-author' : ''}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  {author.name}
                                </a>
                              ) : (
                                <span className={`coauthor-name${isCurrentScholar ? ' current-scholar-author' : ''}`}>
                                  {author.name}
                                </span>
                              )}
                              {authorIndex < paper.authors.length - 1 && ', '}
                            </span>
                          );
                        })}
                      </div>
                    )}

                        {paper.abstract && (
                          <details className="paper-abstract">
                            <summary>Abstract</summary>
                            <p>{paper.abstract}</p>
                          </details>
                        )}
                      </div>
                    ));
                })()}
              </div>
            </section>
          )}

          {scholar.honors && scholar.honors.length > 0 && (
            <section className="section">
              <h2>Honors & Awards</h2>
              <ul className="honors-list">
                {scholar.honors.map((honor, index) => (
                  <li key={index}>
                    <span className="honor-award">{honor.award}</span>
                    {honor.year && <span className="honor-year">({honor.year})</span>}
                    {honor.reason && <p className="honor-reason">{honor.reason}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {scholar.research_interests && scholar.research_interests.length > 0 && (
            <section className="section">
              <h2>Research Interests</h2>
              <div className="interests-tags">
                {scholar.research_interests
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

          {scholar.source_urls && scholar.source_urls.length > 0 && (
            <section className="section sources-section">
              <h2>Sources</h2>
              <ul className="sources-list">
                {scholar.source_urls.map((url, index) => (
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
