/**
 * ARGO Layer 1 공통 타입 정의
 * 모든 서비스에서 사용하는 공통 타입들을 정의
 */

// 기본 응답 인터페이스
export interface BaseResponse {
  success: boolean;
  message: string;
  timestamp: Date;
  executionTime?: number;
}

// 검색 관련 타입
export interface SearchResult {
  id: string;
  path: string;
  name: string;
  content?: string;
  relevanceScore: number;
  snippet?: string;
  reasoning?: string;
  source: 'local' | 'drive' | 'hybrid';
  similarity?: number;
}

export interface CommandResult extends BaseResponse {
  data?: any;
  suggestions?: string[];
}

// 파일 관련 타입
export interface FileMetadata {
  size: number;
  type: string;
  encoding: string;
  tags: string[];
  importance: number;
  lastModified: Date;
  checksum?: string;
}

export interface FileContent {
  path: string;
  content: string;
  metadata: FileMetadata;
  lastModified: Date;
}

// 태깅 관련 타입
export interface Tag {
  name: string;
  weight: number;
  type: 'topic' | 'technology' | 'project' | 'person' | 'concept' | 'action';
  source: 'ai' | 'pattern' | 'manual' | 'inherited';
}

export interface Category {
  name: string;
  confidence: number;
  subcategory?: string;
}

export type ContentType = 
  | 'documentation' 
  | 'code' 
  | 'design' 
  | 'meeting_notes' 
  | 'planning' 
  | 'research' 
  | 'personal' 
  | 'reference'
  | 'unknown';

// 검색 쿼리 타입
export interface SearchQuery {
  query: string;
  maxResults?: number;
  minConfidence?: number;
  contentTypes?: ContentType[];
  dateRange?: {
    from: Date;
    to: Date;
  };
}

export interface SemanticSearchQuery extends SearchQuery {
  // semantic search specific options
  includeContext?: boolean;
  expandQuery?: boolean;
  maxResults?: number;
  searchMode?: 'semantic' | 'hybrid' | 'local';
}

// 동기화 관련 타입
export interface SyncEvent {
  type: 'file_added' | 'file_modified' | 'file_deleted' | 'file_moved';
  filePath: string;
  driveId?: string;
  timestamp: Date;
  checksum?: string;
}

export interface SyncConflict {
  filePath: string;
  driveId: string;
  conflictType: 'content_diff' | 'timestamp_mismatch' | 'both_modified';
  localTimestamp: Date;
  driveTimestamp: Date;
  localChecksum: string;
  driveChecksum: string;
}

// 서비스 상태 관련 타입
export type ServiceStatus = 'initializing' | 'ready' | 'error' | 'shutdown' | 'degraded';

export interface ServiceHealth {
  status: ServiceStatus;
  uptime: number;
  errors: string[];
  lastCheck: Date;
}

// 성능 메트릭 타입
export interface PerformanceMetrics {
  responseTime: number;
  throughput: number;
  errorRate: number;
  cacheHitRate: number;
}

// 분석 결과 타입
export interface AnalysisResult {
  filePath: string;
  tags: Tag[];
  contentType: ContentType;
  categories: Category[];
  confidence: number;
  embedding?: boolean;
  synchronized: boolean;
  timestamp: Date;
}

// API 응답 타입
export interface APIResponse<T = any> extends BaseResponse {
  data?: T;
  error?: string;
}

// 설정 타입
export interface Layer1Config {
  openaiApiKey?: string;
  googleCredentials?: string;
  enableWebInterface?: boolean;
  enableRealtimeSync?: boolean;
  webPort?: number;
  dataDir?: string;
}

// 에러 타입
export class Layer1Error extends Error {
  constructor(
    message: string,
    public code: string,
    public service?: string,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'Layer1Error';
  }
}

// 네트워크 관련 타입 (미래 확장용)
export interface IntelligentNode {
  id: string;
  address: string;
  status: 'active' | 'inactive' | 'syncing';
  lastSeen: Date;
}

export interface InteractionQuality {
  score: number;
  feedback: string;
  timestamp: Date;
}

// 드라이브 파일 타입
export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime: string;
  size?: string;
  content?: string;
  source: 'local' | 'drive';
}

// 유틸리티 타입
export type Nullable<T> = T | null;
export type Optional<T> = T | undefined;
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};