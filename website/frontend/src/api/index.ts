import type { Conference, ScholarBasic, ScholarDetail, LabelsConfig } from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined
  ? import.meta.env.VITE_API_BASE_URL
  : 'http://localhost:37801';

/**
 * Convert a relative photo URL to absolute URL if needed.
 * In production (API_BASE_URL is empty), relative URLs work via Nginx proxy.
 * In development, we need to prepend the API base URL.
 */
export function getPhotoUrl(photoUrl: string | null | undefined): string | null {
  if (!photoUrl) return null;
  // If it's already an absolute URL, return as-is
  if (photoUrl.startsWith('http://') || photoUrl.startsWith('https://')) {
    return photoUrl;
  }
  // For relative URLs, prepend API_BASE_URL
  return `${API_BASE_URL}${photoUrl}`;
}

async function fetchApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function getConferences(): Promise<Conference[]> {
  return fetchApi<Conference[]>('/api/conferences');
}

export async function getConferenceScholars(conferenceId: string): Promise<ScholarBasic[]> {
  return fetchApi<ScholarBasic[]>(`/api/conferences/${conferenceId}/scholars`);
}

export async function searchScholar(
  conferenceId: string,
  params: { name?: string; aminer_id?: string }
): Promise<ScholarDetail[]> {
  const searchParams = new URLSearchParams();
  if (params.name) searchParams.set('name', params.name);
  if (params.aminer_id) searchParams.set('aminer_id', params.aminer_id);

  return fetchApi<ScholarDetail[]>(
    `/api/conferences/${conferenceId}/scholars/search?${searchParams.toString()}`
  );
}

export async function getLabelsConfig(): Promise<LabelsConfig> {
  return fetchApi<LabelsConfig>('/api/labels');
}

export async function filterScholarsByLabels(
  conferenceId: string,
  labelFilters: Record<string, boolean>
): Promise<ScholarBasic[]> {
  const filterParts = Object.entries(labelFilters)
    .map(([name, value]) => `${name}:${value}`)
    .join(',');

  const searchParams = new URLSearchParams();
  if (filterParts) {
    searchParams.set('labels', filterParts);
  }

  return fetchApi<ScholarBasic[]>(
    `/api/conferences/${conferenceId}/scholars/filter?${searchParams.toString()}`
  );
}

export async function filterPeopleByLabels(
  conferenceId: string,
  labelFilters: Record<string, boolean>
): Promise<any[]> {
  const filterParts = Object.entries(labelFilters)
    .map(([name, value]) => `${name}:${value}`)
    .join(',');

  const searchParams = new URLSearchParams();
  if (filterParts) {
    searchParams.set('labels', filterParts);
  }

  return fetchApi<any[]>(
    `/api/conferences/${conferenceId}/people/filter?${searchParams.toString()}`
  );
}
