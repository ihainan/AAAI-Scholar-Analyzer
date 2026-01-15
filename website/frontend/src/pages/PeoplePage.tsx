import { useEffect, useState, useMemo } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { getConferences, API_BASE_URL } from '../api';
import type { Conference, ScholarBasic } from '../types';
import ScholarCard from '../components/ScholarCard';
import './PeoplePage.css';

interface Person extends ScholarBasic {
  paper_count?: number;
  h_index?: number;
  n_citation?: number;
  n_pubs?: number;
  organization?: string;
  organization_zh?: string;
}

type SortOption = 'citations' | 'papers' | 'hindex' | 'pubs' | 'name';

const ITEMS_PER_PAGE = 24;

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

export default function PeoplePage() {
  const { conferenceId } = useParams<{ conferenceId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const [conference, setConference] = useState<Conference | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [searchTerm, setSearchTerm] = useState(searchParams.get('search') || '');
  const [sortBy, setSortBy] = useState<SortOption>((searchParams.get('sort') as SortOption) || 'citations');
  const [displayCount, setDisplayCount] = useState(ITEMS_PER_PAGE);

  const debouncedSearchTerm = useDebounce(searchTerm, 300);

  // Load data
  useEffect(() => {
    async function fetchData() {
      if (!conferenceId) return;

      try {
        setLoading(true);

        // Load conference info
        const conferencesData = await getConferences();
        const conf = conferencesData.find(c => c.id === conferenceId);
        setConference(conf || null);

        // Load authors data from API
        const authorsResponse = await fetch(`${API_BASE_URL}/api/conferences/${conferenceId}/authors`);
        const authorsData = await authorsResponse.json();
        const authors: Person[] = authorsData.authors || [];

        // Load scholars data from API
        const scholarsResponse = await fetch(`${API_BASE_URL}/api/conferences/${conferenceId}/data/scholars`);
        const scholarsData = await scholarsResponse.json();
        const scholars: Person[] = scholarsData.talents || [];

        // Merge and deduplicate by aminer_id
        const mergedMap = new Map<string, Person>();

        // Add scholars first (they might have more complete info)
        scholars.forEach(scholar => {
          if (scholar.aminer_id) {
            mergedMap.set(scholar.aminer_id, {
              name: scholar.name,
              name_zh: scholar.name_zh,
              aminer_id: scholar.aminer_id,
              affiliation: scholar.affiliation,
              roles: scholar.roles || [],
              photo_url: scholar.photo_url,
              description: scholar.description,
            });
          }
        });

        // Merge with authors (authors have metrics)
        authors.forEach(author => {
          if (author.aminer_id) {
            const existing = mergedMap.get(author.aminer_id);
            if (existing) {
              // Merge data, preserving name_zh from existing if available
              mergedMap.set(author.aminer_id, {
                ...existing,
                paper_count: author.paper_count,
                h_index: author.h_index,
                n_citation: author.n_citation,
                n_pubs: author.n_pubs,
                affiliation: existing.affiliation || author.affiliation,
                organization: (author as any).organization,
                organization_zh: (author as any).organization_zh,
                name_zh: existing.name_zh || (author as any).name_zh,
              });
            } else {
              mergedMap.set(author.aminer_id, {
                ...author,
                roles: author.roles || [],
              });
            }
          }
        });

        const merged = Array.from(mergedMap.values());
        setPeople(merged);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [conferenceId]);

  // Update URL when search/sort changes
  useEffect(() => {
    const params = new URLSearchParams();
    if (debouncedSearchTerm) {
      params.set('search', debouncedSearchTerm);
    }
    if (sortBy !== 'citations') {
      params.set('sort', sortBy);
    }
    setSearchParams(params, { replace: true });
  }, [debouncedSearchTerm, sortBy, setSearchParams]);

  // Filter and sort people
  const filteredAndSortedPeople = useMemo(() => {
    let result = [...people];

    // Filter by search term (search in both English and Chinese names)
    if (debouncedSearchTerm) {
      const term = debouncedSearchTerm.toLowerCase();
      result = result.filter(person =>
        person.name.toLowerCase().includes(term) ||
        (person.name_zh && person.name_zh.includes(debouncedSearchTerm))
      );
    }

    // Sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'citations':
          return (b.n_citation || 0) - (a.n_citation || 0);
        case 'papers':
          return (b.paper_count || 0) - (a.paper_count || 0);
        case 'hindex':
          return (b.h_index || 0) - (a.h_index || 0);
        case 'pubs':
          return (b.n_pubs || 0) - (a.n_pubs || 0);
        case 'name':
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    });

    return result;
  }, [people, debouncedSearchTerm, sortBy]);

  const displayedPeople = filteredAndSortedPeople.slice(0, displayCount);
  const hasMore = displayCount < filteredAndSortedPeople.length;

  const handleLoadMore = () => {
    setDisplayCount(prev => prev + ITEMS_PER_PAGE);
  };

  const handleClearSearch = () => {
    setSearchTerm('');
    setDisplayCount(ITEMS_PER_PAGE);
  };

  const handleSortChange = (newSort: SortOption) => {
    setSortBy(newSort);
    setDisplayCount(ITEMS_PER_PAGE);
  };

  if (loading) {
    return (
      <div className="people-page">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="people-page">
        <div className="error">Error: {error}</div>
        <Link to="/" className="back-link">
          Back to Conferences
        </Link>
      </div>
    );
  }

  return (
    <div className="people-page">
      <nav className="breadcrumb">
        <Link to="/">Conferences</Link>
        <span className="separator">/</span>
        <Link to={`/conference/${conferenceId}`}>
          {conference?.shortName || conference?.name || conferenceId}
        </Link>
        <span className="separator">/</span>
        <span>People</span>
      </nav>

      <header className="people-header">
        {conference?.logo_url && (
          <img src={conference.logo_url} alt={conference.name} className="conference-logo" />
        )}
        <div className="conference-info">
          <h1>{conference?.name || conferenceId}</h1>
          {conference?.location && (
            <p className="location">
              {conference.location.city && conference.location.country &&
                `${conference.location.city}, ${conference.location.country}`}
            </p>
          )}
        </div>
      </header>

      <div className="search-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search by name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
          {searchTerm && (
            <button onClick={handleClearSearch} className="clear-button">
              Clear
            </button>
          )}
        </div>

        <div className="controls-right">
          <div className="sort-control">
            <label htmlFor="sort-select">Sort by:</label>
            <select
              id="sort-select"
              value={sortBy}
              onChange={(e) => handleSortChange(e.target.value as SortOption)}
              className="sort-select"
            >
              <option value="citations">Citations</option>
              <option value="papers">Conference Papers</option>
              <option value="hindex">H-Index</option>
              <option value="pubs">Total Publications</option>
              <option value="name">Name</option>
            </select>
          </div>

          <div className="result-count">
            {filteredAndSortedPeople.length.toLocaleString()} people
          </div>
        </div>
      </div>

      {filteredAndSortedPeople.length === 0 ? (
        <div className="empty-state">
          <p>No people found matching your search.</p>
        </div>
      ) : (
        <>
          <div className="people-grid">
            {displayedPeople.map((person) => (
              <ScholarCard
                key={person.aminer_id}
                scholar={person}
                conferenceId={conferenceId!}
                showMetrics={true}
                fromPage="people"
              />
            ))}
          </div>

          {hasMore && (
            <div className="load-more-container">
              <button onClick={handleLoadMore} className="load-more-button">
                Load More ({filteredAndSortedPeople.length - displayCount} remaining)
              </button>
            </div>
          )}

          {!hasMore && displayedPeople.length > ITEMS_PER_PAGE && (
            <div className="end-message">
              Showing all {filteredAndSortedPeople.length} people
            </div>
          )}
        </>
      )}
    </div>
  );
}
