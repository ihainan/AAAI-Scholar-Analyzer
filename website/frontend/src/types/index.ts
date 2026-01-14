export interface ConferenceLocation {
  venue?: string;
  city?: string;
  country?: string;
}

export interface ConferenceDates {
  start?: string;
  end?: string;
}

export interface ConferenceUrl {
  url: string;
  name?: string;
  description?: string;
}

export interface Conference {
  id: string;
  name: string;
  shortName?: string;
  edition?: number;
  year?: number;
  dates?: ConferenceDates;
  location?: ConferenceLocation;
  description?: string;
  logo_url?: string;
  urls?: ConferenceUrl[];
  timezone?: string;
  tags?: string[];
}

export interface ScholarBasic {
  name: string;
  affiliation?: string;
  roles: string[];
  aminer_id?: string;
  photo_url?: string;
  description?: string;
}

export interface AminerValidation {
  status?: string;
  is_same_person?: boolean;
  reason?: string;
}

export interface Honor {
  award: string;
  year?: number;
  reason?: string;
}

export interface ResearchInterest {
  name: string;
  order?: number;
}

export interface LabelResult {
  name: string;
  value?: boolean | null;
  confidence?: string;
  reason?: string;
}

export interface ScholarLabels {
  last_updated?: string;
  results: LabelResult[];
}

export interface LabelDefinition {
  name: string;
  description: string;
}

export interface LabelsConfig {
  version: string;
  labels: LabelDefinition[];
}

export interface ConferencePaperAuthor {
  name: string;
  aminer_id?: string;
  in_conference: boolean;
}

export interface ConferencePaper {
  paper_id: string;
  title: string;
  track?: string;
  session?: string;
  room?: string;
  date?: string;
  presentation_type?: string;
  coauthors: ConferencePaperAuthor[];
  abstract?: string;
}

export interface AcademicIndices {
  hindex?: number;
  gindex?: number;
  citations?: number;
  pubs?: number;
  activity?: number;
  diversity?: number;
  sociability?: number;
}

export interface ScholarDetail {
  name: string;
  aliases?: string[];
  affiliation?: string;
  roles: string[];
  description?: string;
  sources?: string[];
  source_urls?: string[];
  aminer_id?: string;
  aminer_validation?: AminerValidation;
  photo_url?: string;
  bio?: string;
  education?: string;
  position?: string;
  organizations?: string[];
  honors?: Honor[];
  research_interests?: ResearchInterest[];
  homepage?: string;
  google_scholar?: string;
  dblp?: string;
  linkedin?: string;
  twitter?: string;
  email?: string;
  orcid?: string;
  semantic_scholar?: string;
  additional_info?: string;
  labels?: ScholarLabels;
  indices?: AcademicIndices;
  conference_papers?: ConferencePaper[];
}
