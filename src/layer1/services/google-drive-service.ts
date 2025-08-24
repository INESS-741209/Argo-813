/**
 * ARGO Layer 1 Phase 1: Google Drive API 연동
 * 블루프린트: "Director의 모든 지식 소스를 단일 네트워크로 통합"
 * 목표: 로컬 파일과 클라우드 파일의 완전한 시맨틱 통합
 */

import { google, drive_v3 } from 'googleapis';
import { GoogleAuth } from 'google-auth-library';
import * as fs from 'fs/promises';
import * as path from 'path';
import { EmbeddingService } from './embedding-service.js';

interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  parents?: string[];
  modifiedTime: string;
  size?: string;
  webViewLink: string;
  content?: string;
  localPath?: string;
}

interface SyncManifest {
  lastSync: Date;
  syncedFiles: {
    [driveId: string]: {
      localPath: string;
      lastModified: Date;
      checksum: string;
    };
  };
}

interface DriveSearchQuery {
  query: string;
  mimeTypes?: string[];
  folders?: string[];
  modifiedAfter?: Date;
  maxResults?: number;
}

/**
 * Google Drive Integration Service
 * Phase 1 핵심: 클라우드와 로컬의 완전한 시맨틱 통합
 */
class GoogleDriveService {
  private drive!: drive_v3.Drive;
  private auth!: GoogleAuth;
  private embeddingService: EmbeddingService;
  private syncManifest!: SyncManifest;
  private manifestFile: string;
  private localSyncDir: string;
  private supportedMimeTypes: Set<string>;

  constructor(embeddingService: EmbeddingService) {
    this.embeddingService = embeddingService;
    this.manifestFile = 'C:\\Argo-813\\data\\drive-sync-manifest.json';
    this.localSyncDir = 'C:\\Argo-813\\data\\drive-sync';
    
    // 지원하는 MIME 타입들
    this.supportedMimeTypes = new Set([
      'text/plain',
      'text/markdown',
      'application/vnd.google-apps.document',
      'application/vnd.google-apps.presentation',
      'application/vnd.google-apps.spreadsheet',
      'application/pdf',
      'application/json'
    ]);

    this.initializeAuth();
    this.loadSyncManifest();
  }

  /**
   * Google Drive 인증 초기화
   */
  private async initializeAuth(): Promise<void> {
    try {
      this.auth = new GoogleAuth({
        keyFile: process.env.GOOGLE_APPLICATION_CREDENTIALS,
        scopes: [
          'https://www.googleapis.com/auth/drive.readonly',
          'https://www.googleapis.com/auth/drive.metadata.readonly'
        ]
      });

      this.drive = google.drive({ version: 'v3', auth: this.auth });
      console.log('✅ Google Drive API 인증 완료');

    } catch (error) {
      console.warn('⚠️  Google Drive 인증 실패, 로컬 전용 모드로 전환:', error);
    }
  }

  /**
   * Drive에서 파일 검색 (시맨틱 + 메타데이터)
   */
  async searchFiles(searchQuery: DriveSearchQuery): Promise<DriveFile[]> {
    if (!this.drive) {
      console.warn('Google Drive 연결 없음, 로컬 캐시에서 검색');
      return this.searchFromCache(searchQuery.query);
    }

    try {
      console.log(`🔍 Google Drive에서 검색 중: "${searchQuery.query}"`);

      // Google Drive Query DSL 구성
      const driveQuery = this.buildDriveQuery(searchQuery);
      
      const response = await this.drive.files.list({
        q: driveQuery,
        fields: 'nextPageToken, files(id, name, mimeType, parents, modifiedTime, size, webViewLink)',
        pageSize: searchQuery.maxResults || 100,
        orderBy: 'modifiedTime desc'
      });

      const files = response.data.files || [];
      console.log(`📁 ${files.length}개 파일 발견`);

      // 각 파일의 콘텐츠 가져오기 및 시맨틱 분석
      const enrichedFiles = await Promise.all(
        files.map(file => this.enrichFileWithContent(file))
      );

      // 시맨틱 유사도 기반 재정렬
      if (searchQuery.query.trim()) {
        return await this.rankBySemanticSimilarity(enrichedFiles, searchQuery.query);
      }

      return enrichedFiles;

    } catch (error) {
      console.error('❌ Google Drive 검색 오류:', error);
      return this.searchFromCache(searchQuery.query);
    }
  }

  /**
   * 특정 파일의 전체 콘텐츠 가져오기
   */
  async getFileContent(fileId: string): Promise<string | null> {
    if (!this.drive) return null;

    try {
      const fileInfo = await this.drive.files.get({
        fileId,
        fields: 'id, name, mimeType'
      });

      const mimeType = fileInfo.data.mimeType;

      if (mimeType === 'application/vnd.google-apps.document') {
        // Google Docs를 텍스트로 내보내기
        const response = await this.drive.files.export({
          fileId,
          mimeType: 'text/plain'
        });
        return response.data as string;

      } else if (mimeType === 'application/vnd.google-apps.presentation') {
        // Google Slides를 텍스트로 내보내기
        const response = await this.drive.files.export({
          fileId,
          mimeType: 'text/plain'
        });
        return response.data as string;

      } else if (this.supportedMimeTypes.has(mimeType || '')) {
        // 일반 파일 다운로드
        const response = await this.drive.files.get({
          fileId,
          alt: 'media'
        });
        return response.data as string;
      }

      return null;

    } catch (error) {
      console.warn(`파일 콘텐츠 가져오기 실패 (${fileId}):`, error);
      return null;
    }
  }

  /**
   * 전체 Drive 동기화 (백그라운드)
   */
  async syncDriveFiles(): Promise<{
    synced: number;
    updated: number;
    errors: number;
  }> {
    if (!this.drive) {
      return { synced: 0, updated: 0, errors: 0 };
    }

    console.log('🔄 Google Drive 전체 동기화 시작...');

    const stats = { synced: 0, updated: 0, errors: 0 };

    try {
      // 모든 지원 파일 검색
      const allFiles = await this.searchFiles({
        query: '',
        mimeTypes: Array.from(this.supportedMimeTypes),
        maxResults: 1000
      });

      // 로컬 동기화 디렉터리 생성
      await fs.mkdir(this.localSyncDir, { recursive: true });

      for (const file of allFiles) {
        try {
          const localPath = await this.syncFileToLocal(file);
          if (localPath) {
            if (this.syncManifest.syncedFiles[file.id]) {
              stats.updated++;
            } else {
              stats.synced++;
            }

            // 동기화 매니페스트 업데이트
            this.syncManifest.syncedFiles[file.id] = {
              localPath,
              lastModified: new Date(file.modifiedTime),
              checksum: this.generateChecksum(file.content || '')
            };
          }

        } catch (error) {
          console.warn(`파일 동기화 실패 (${file.name}):`, error);
          stats.errors++;
        }
      }

      this.syncManifest.lastSync = new Date();
      await this.saveSyncManifest();

      console.log(`✅ 동기화 완료: ${stats.synced}개 신규, ${stats.updated}개 업데이트, ${stats.errors}개 오류`);

    } catch (error) {
      console.error('❌ 전체 동기화 실패:', error);
      stats.errors++;
    }

    return stats;
  }

  /**
   * 실시간 변경사항 감지 및 동기화
   */
  async watchForChanges(): Promise<void> {
    if (!this.drive) return;

    console.log('👁️  Google Drive 변경사항 감지 시작...');

    try {
      // Drive의 변경사항 페이지 토큰 가져오기
      const response = await this.drive.changes.getStartPageToken();
      const pageToken = response.data.startPageToken;

      if (!pageToken) return;

      // 변경사항 폴링 (5분 간격)
      setInterval(async () => {
        try {
          const changes = await this.drive.changes.list({
            pageToken,
            includeItemsFromAllDrives: false,
            fields: 'nextPageToken, changes(fileId, file(id, name, mimeType, modifiedTime))'
          });

          const changedFiles = changes.data.changes || [];
          
          if (changedFiles.length > 0) {
            console.log(`📱 ${changedFiles.length}개 파일 변경사항 감지`);
            
            // 변경된 파일들 재동기화
            for (const change of changedFiles) {
              if (change.file && change.fileId) {
                const fileInfo = await this.enrichFileWithContent(change.file);
                await this.syncFileToLocal(fileInfo);
              }
            }
          }

        } catch (error) {
          console.warn('변경사항 감지 오류:', error);
        }
      }, 5 * 60 * 1000); // 5분

    } catch (error) {
      console.error('변경사항 감지 초기화 실패:', error);
    }
  }

  /**
   * 통합 검색 (로컬 + Drive)
   */
  async hybridSearch(query: string, options?: {
    includeLocal?: boolean;
    includeDrive?: boolean;
    maxResults?: number;
  }): Promise<Array<DriveFile & { source: 'local' | 'drive' }>> {
    const { includeLocal = true, includeDrive = true, maxResults = 20 } = options || {};
    
    const results: Array<DriveFile & { source: 'local' | 'drive' }> = [];

    // 로컬 파일 검색
    if (includeLocal) {
      const localResults = await this.searchFromCache(query);
      results.push(...localResults.map(file => ({ ...file, source: 'local' as const })));
    }

    // Drive 파일 검색
    if (includeDrive) {
      const driveResults = await this.searchFiles({ query, maxResults: maxResults / 2 });
      results.push(...driveResults.map(file => ({ ...file, source: 'drive' as const })));
    }

    // 시맨틱 유사도 기반 통합 정렬
    if (query.trim()) {
      const rankedResults = await this.rankBySemanticSimilarity(results, query);
      return rankedResults.map(file => ({ ...file, source: 'local' as const }));
    }

    return results.slice(0, maxResults);
  }

  // ======= Private Methods =======

  private buildDriveQuery(searchQuery: DriveSearchQuery): string {
    const clauses: string[] = [];

    // 기본 필터: 휴지통이 아닌 파일만
    clauses.push('trashed=false');

    // MIME 타입 필터
    if (searchQuery.mimeTypes && searchQuery.mimeTypes.length > 0) {
      const mimeTypeClauses = searchQuery.mimeTypes.map(type => `mimeType='${type}'`);
      clauses.push(`(${mimeTypeClauses.join(' or ')})`);
    } else {
      // 기본적으로 지원하는 타입들만
      const supportedTypes = Array.from(this.supportedMimeTypes);
      const mimeTypeClauses = supportedTypes.map(type => `mimeType='${type}'`);
      clauses.push(`(${mimeTypeClauses.join(' or ')})`);
    }

    // 텍스트 검색 (제목과 내용)
    if (searchQuery.query.trim()) {
      const escaped = searchQuery.query.replace(/'/g, "\\'");
      clauses.push(`(name contains '${escaped}' or fullText contains '${escaped}')`);
    }

    // 수정 날짜 필터
    if (searchQuery.modifiedAfter) {
      const isoDate = searchQuery.modifiedAfter.toISOString();
      clauses.push(`modifiedTime > '${isoDate}'`);
    }

    return clauses.join(' and ');
  }

  private async enrichFileWithContent(file: any): Promise<DriveFile> {
    const driveFile: DriveFile = {
      id: file.id,
      name: file.name,
      mimeType: file.mimeType,
      parents: file.parents,
      modifiedTime: file.modifiedTime,
      size: file.size,
      webViewLink: file.webViewLink
    };

    // 텍스트 콘텐츠 가져오기 (비동기)
    try {
      const content = await this.getFileContent(file.id);
      driveFile.content = content || undefined;
    } catch (error) {
      console.warn(`콘텐츠 가져오기 실패 (${file.name}):`, error);
    }

    return driveFile;
  }

  private async rankBySemanticSimilarity(files: DriveFile[], query: string): Promise<DriveFile[]> {
    if (!query.trim() || files.length === 0) return files;

    try {
      // 쿼리 임베딩 생성
      const queryEmbedding = await this.embeddingService.getEmbedding({ text: query });

      // 각 파일의 유사도 계산
      const rankedFiles = await Promise.all(
        files.map(async (file) => {
          let similarity = 0;

          if (file.content) {
            try {
              const fileEmbedding = await this.embeddingService.getEmbedding({ 
                text: file.content.substring(0, 8000) // 토큰 제한
              });
              
              similarity = this.embeddingService.cosineSimilarity(
                queryEmbedding.embedding,
                fileEmbedding.embedding
              );
            } catch (error) {
              // 임베딩 실패시 제목 기반 유사도 사용
              similarity = this.calculateTitleSimilarity(file.name, query);
            }
          } else {
            // 콘텐츠 없으면 제목 기반 유사도만 사용
            similarity = this.calculateTitleSimilarity(file.name, query);
          }

          return { ...file, similarity };
        })
      );

      // 유사도 순 정렬
      return rankedFiles
        .sort((a, b) => b.similarity - a.similarity)
        .map(({ similarity, ...file }) => file);

    } catch (error) {
      console.warn('시맨틱 유사도 계산 실패, 기본 정렬 사용:', error);
      return files;
    }
  }

  private calculateTitleSimilarity(title: string, query: string): number {
    const titleWords = title.toLowerCase().split(/\s+/);
    const queryWords = query.toLowerCase().split(/\s+/);
    
    let matches = 0;
    for (const queryWord of queryWords) {
      if (titleWords.some(titleWord => titleWord.includes(queryWord))) {
        matches++;
      }
    }
    
    return queryWords.length > 0 ? matches / queryWords.length : 0;
  }

  private async syncFileToLocal(file: DriveFile): Promise<string | null> {
    if (!file.content) return null;

    try {
      // 안전한 파일명 생성
      const safeFileName = this.sanitizeFileName(file.name);
      const localPath = path.join(this.localSyncDir, `${file.id}_${safeFileName}`);

      // 로컬에 저장
      await fs.writeFile(localPath, file.content, 'utf-8');
      
      file.localPath = localPath;
      return localPath;

    } catch (error) {
      console.warn(`로컬 저장 실패 (${file.name}):`, error);
      return null;
    }
  }

  private sanitizeFileName(fileName: string): string {
    return fileName
      .replace(/[<>:"/\\|?*]/g, '_')
      .replace(/\s+/g, '_')
      .substring(0, 100);
  }

  private generateChecksum(content: string): string {
    const crypto = require('crypto');
    return crypto.createHash('sha256').update(content).digest('hex');
  }

  private async searchFromCache(query: string): Promise<DriveFile[]> {
    // 로컬 캐시된 파일에서 검색
    const cachedFiles: DriveFile[] = [];

    try {
      const syncedFiles = this.syncManifest.syncedFiles;
      
      for (const [driveId, fileInfo] of Object.entries(syncedFiles)) {
        try {
          const content = await fs.readFile(fileInfo.localPath, 'utf-8');
          
          if (content.toLowerCase().includes(query.toLowerCase())) {
            cachedFiles.push({
              id: driveId,
              name: path.basename(fileInfo.localPath),
              mimeType: 'text/plain',
              modifiedTime: fileInfo.lastModified.toISOString(),
              webViewLink: `file://${fileInfo.localPath}`,
              content: content,
              localPath: fileInfo.localPath
            });
          }
        } catch (error) {
          console.warn(`캐시 파일 읽기 실패 (${fileInfo.localPath}):`, error);
        }
      }
    } catch (error) {
      console.warn('캐시 검색 실패:', error);
    }

    return cachedFiles;
  }

  private async loadSyncManifest(): Promise<void> {
    try {
      await fs.mkdir('C:\\Argo-813\\data', { recursive: true });
      
      const data = await fs.readFile(this.manifestFile, 'utf-8');
      this.syncManifest = JSON.parse(data);
      
      // Date 객체 복원
      this.syncManifest.lastSync = new Date(this.syncManifest.lastSync);
      Object.values(this.syncManifest.syncedFiles).forEach(file => {
        file.lastModified = new Date(file.lastModified);
      });
      
      console.log(`📂 동기화 매니페스트 로드: ${Object.keys(this.syncManifest.syncedFiles).length}개 파일`);

    } catch (error) {
      console.log('📝 새로운 동기화 매니페스트 생성');
      this.syncManifest = {
        lastSync: new Date(0),
        syncedFiles: {}
      };
    }
  }

  private async saveSyncManifest(): Promise<void> {
    try {
      await fs.writeFile(
        this.manifestFile,
        JSON.stringify(this.syncManifest, null, 2)
      );
    } catch (error) {
      console.warn('동기화 매니페스트 저장 실패:', error);
    }
  }
}

export {
  GoogleDriveService,
  DriveFile,
  DriveSearchQuery,
  SyncManifest
};