import { useEffect, useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { getConferences, getConferenceScholars, getLabelsConfig, filterScholarsByLabels } from '../api';
import ScholarCard from '../components/ScholarCard';
import type { Conference, ScholarBasic, LabelDefinition } from '../types';
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

type FilterValue = 'any' | 'true' | 'false';

function parseFiltersFromUrl(searchParams: URLSearchParams): Record<string, FilterValue> {
  const filters: Record<string, FilterValue> = {};
  const labelsParam = searchParams.get('labels');
  if (labelsParam) {
    labelsParam.split(',').forEach(item => {
      const [name, value] = item.split(':');
      if (name && (value === 'true' || value === 'false')) {
        filters[name] = value as FilterValue;
      }
    });
  }
  return filters;
}

function filtersToUrlParam(filters: Record<string, FilterValue>): string {
  const parts = Object.entries(filters)
    .filter(([, value]) => value !== 'any')
    .map(([name, value]) => `${name}:${value}`);
  return parts.join(',');
}

function hasActiveFilters(filters: Record<string, FilterValue>): boolean {
  return Object.values(filters).some(v => v !== 'any');
}

export default function ConferenceDetail() {
  const { conferenceId } = useParams<{ conferenceId: string }>();
  const [, setSearchParams] = useSearchParams();
  const [conference, setConference] = useState<Conference | null>(null);
  const [scholars, setScholars] = useState<ScholarBasic[]>([]);
  const [filteredScholars, setFilteredScholars] = useState<ScholarBasic[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterLoading, setFilterLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [labelDefinitions, setLabelDefinitions] = useState<LabelDefinition[]>([]);
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [filters, setFilters] = useState<Record<string, FilterValue>>({});
  const [tempFilters, setTempFilters] = useState<Record<string, FilterValue>>({});

  const applyFilters = async (newFilters: Record<string, FilterValue>, allScholars: ScholarBasic[]) => {
    if (!conferenceId) return;

    // Update URL (use replace to avoid adding to history for filter changes)
    const urlParam = filtersToUrlParam(newFilters);
    if (urlParam) {
      setSearchParams({ labels: urlParam }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }

    setFilters(newFilters);

    // If no active filters, show all scholars
    if (!hasActiveFilters(newFilters)) {
      setFilteredScholars(allScholars);
      return;
    }

    // Convert filters to API format
    const apiFilters: Record<string, boolean> = {};
    Object.entries(newFilters).forEach(([name, value]) => {
      if (value === 'true') apiFilters[name] = true;
      else if (value === 'false') apiFilters[name] = false;
    });

    setFilterLoading(true);
    try {
      const filtered = await filterScholarsByLabels(conferenceId, apiFilters);
      setFilteredScholars(filtered);
    } catch (err) {
      console.error('Error filtering scholars:', err);
      setFilteredScholars(allScholars);
    } finally {
      setFilterLoading(false);
    }
  };

  // Initial data load - only depends on conferenceId
  useEffect(() => {
    async function fetchData() {
      if (!conferenceId) return;

      setLoading(true);
      try {
        const [conferencesData, scholarsData, labelsData] = await Promise.all([
          getConferences(),
          getConferenceScholars(conferenceId),
          getLabelsConfig().catch(() => ({ version: '1.0', labels: [] })),
        ]);

        const conf = conferencesData.find(c => c.id === conferenceId);
        if (!conf) {
          throw new Error('Conference not found');
        }

        setConference(conf);
        setScholars(scholarsData);
        setLabelDefinitions(labelsData.labels);

        // Initialize filters with label names
        const initialFilters: Record<string, FilterValue> = {};
        labelsData.labels.forEach(label => {
          initialFilters[label.name] = 'any';
        });

        // Apply URL filters (read current searchParams)
        const currentSearchParams = new URLSearchParams(window.location.search);
        const urlFilters = parseFiltersFromUrl(currentSearchParams);
        Object.entries(urlFilters).forEach(([name, value]) => {
          if (name in initialFilters) {
            initialFilters[name] = value;
          }
        });

        setTempFilters(initialFilters);

        // Apply initial filters with the freshly loaded scholars
        await applyFilters(initialFilters, scholarsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conferenceId]);

  const openFilterModal = () => {
    setTempFilters({ ...filters });
    setShowFilterModal(true);
  };

  const handleApplyFilter = () => {
    applyFilters(tempFilters, scholars);
    setShowFilterModal(false);
  };

  const handleResetFilter = () => {
    const resetFilters: Record<string, FilterValue> = {};
    labelDefinitions.forEach(label => {
      resetFilters[label.name] = 'any';
    });
    setTempFilters(resetFilters);
  };

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
              <Link
                to={`/conference/${conferenceId}/people`}
                className="conference-link scholars-link"
              >
                Scholars
              </Link>
            </div>
          )}
          {!(conference.urls && conference.urls.length > 0) && (
            <div className="conference-links">
              <Link
                to={`/conference/${conferenceId}/people`}
                className="conference-link scholars-link"
              >
                Scholars
              </Link>
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
        <div className="scholars-header">
          <h2>Conference Participants ({scholars.length})</h2>
          <button
            className={`filter-button ${hasActiveFilters(filters) ? 'active' : ''}`}
            onClick={openFilterModal}
            title="Filter participants"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
            </svg>
            Filter
          </button>
        </div>
        {filterLoading ? (
          <div className="loading">Filtering...</div>
        ) : (
          <>
            <div className="scholars-grid">
              {filteredScholars.map((scholar, index) => (
                <ScholarCard
                  key={scholar.aminer_id || `${scholar.name}-${index}`}
                  scholar={scholar}
                  conferenceId={conferenceId!}
                />
              ))}
            </div>
            {filteredScholars.length === 0 && (
              <div className="empty-state">
                {hasActiveFilters(filters)
                  ? 'No participants match the current filters.'
                  : 'No participants found.'}
              </div>
            )}
          </>
        )}
      </section>

      {showFilterModal && (
        <div className="modal-overlay" onClick={() => setShowFilterModal(false)}>
          <div className="filter-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Filter Participants</h3>
              <button className="modal-close" onClick={() => setShowFilterModal(false)}>
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
            <div className="modal-body">
              {labelDefinitions.map(label => (
                <div key={label.name} className="filter-row">
                  <label className="filter-label" title={label.description}>
                    {label.name}
                  </label>
                  <select
                    className="filter-select"
                    value={tempFilters[label.name] || 'any'}
                    onChange={e => setTempFilters(prev => ({
                      ...prev,
                      [label.name]: e.target.value as FilterValue
                    }))}
                  >
                    <option value="any">Any</option>
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                </div>
              ))}
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={handleResetFilter}>
                Reset
              </button>
              <button className="btn-primary" onClick={handleApplyFilter}>
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
