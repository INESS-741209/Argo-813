/**
 * ARGO Layer 1 Phase 1: 데이터 소스 통합 서비스
 * 평가 기준표 Level 1 요구사항 구현
 * 목표: 모든 디지털 자산을 ARGO의 단일 의미론적 공간으로 통합
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { EmbeddingService } from './embedding-service.js';
import { GoogleDriveService } from './google-drive-service.js';

interface DataSourceConfig {
  localDirectories: string[];
  googleDriveEnabled: boolean;
  browserHistoryEnabled: boolean;
  calendarEnabled: boolean;
  notionEnabled: boolean;
  slackEnabled: boolean;
  bigQueryProjectId: string;
  bigQueryDatasetId: string;
}

interface FileMetadata {
  fileName: string;
  filePath: string;
  fileSize: number;
  lastModified: Date;
  fileType: string;
  checksum: string;
}

interface IntegrationResult {
  success: boolean;
  processedCount: number;
  errorCount: number;
  errors: string[];
  metadata: {
    startTime: Date;
    endTime: Date;
    totalFiles: number;
    totalSize: number;
  };
}

/**
 * 데이터 소스 통합 서비스
 * Phase 1: 수동 실행 스크립트를 통한 일괄 적재
 */
export class DataSourceIntegrationService {
  private config: DataSourceConfig;
  private embeddingService: EmbeddingService;
  private driveService: GoogleDriveService;
  private integrationHistory: Array<{
    timestamp: Date;
    source: string;
    result: IntegrationResult;
  }>;

  constructor(
    config: DataSourceConfig,
    embeddingService: EmbeddingService,
    driveService: GoogleDriveService
  ) {
    this.config = config;
    this.embeddingService = embeddingService;
    this.driveService = driveService;
    this.integrationHistory = [];
  }

  /**
   * 1. 로컬 파일 시스템 통합 (Level 1 요구사항)
   * 특정 디렉토리(C:/argo-sync)를 대상으로 수동 실행 스크립트를 통해
   * 파일의 메타데이터(파일명, 경로, 크기, 수정일)를 추출하고 BigQuery에 일괄 적재
   */
  async integrateLocalFileSystem(): Promise<IntegrationResult> {
    console.log('📁 로컬 파일 시스템 통합 시작...');
    
    const startTime = new Date();
    let processedCount = 0;
    let errorCount = 0;
    const errors: string[] = [];
    let totalSize = 0;

    try {
      // C:/argo-sync 디렉토리 확인 및 생성
      const targetDir = 'C:/argo-sync';
      await this.ensureDirectoryExists(targetDir);

      // 모든 파일 메타데이터 수집
      const fileMetadataList: FileMetadata[] = [];
      
      for (const directory of this.config.localDirectories) {
        try {
          const files = await this.scanDirectory(directory);
          fileMetadataList.push(...files);
          console.log(`✅ ${directory}: ${files.length}개 파일 스캔 완료`);
        } catch (error) {
          const errorMsg = `${directory} 스캔 실패: ${error instanceof Error ? error.message : String(error)}`;
          errors.push(errorMsg);
          errorCount++;
          console.warn(`⚠️ ${errorMsg}`);
        }
      }

      // BigQuery 적재 시뮬레이션 (실제 구현 시 BigQuery 클라이언트 사용)
      for (const metadata of fileMetadataList) {
        try {
          await this.simulateBigQueryIngest(metadata);
          processedCount++;
          totalSize += metadata.fileSize;
        } catch (error) {
          const errorMsg = `${metadata.filePath} 적재 실패: ${error instanceof Error ? error.message : String(error)}`;
          errors.push(errorMsg);
          errorCount++;
        }
      }

      const result: IntegrationResult = {
        success: errorCount === 0,
        processedCount,
        errorCount,
        errors,
        metadata: {
          startTime,
          endTime: new Date(),
          totalFiles: fileMetadataList.length,
          totalSize
        }
      };

      this.integrationHistory.push({
        timestamp: new Date(),
        source: 'local_file_system',
        result
      });

      console.log(`✅ 로컬 파일 시스템 통합 완료: ${processedCount}개 성공, ${errorCount}개 실패`);
      return result;

    } catch (error) {
      console.error('❌ 로컬 파일 시스템 통합 실패:', error);
      throw error;
    }
  }

  /**
   * 2. Google Drive 통합 (Level 1 요구사항)
   * 수동 실행 스크립트를 통해 전체 G-Drive 파일 목록 및 메타데이터를 조회하여
   * BigQuery에 일괄 적재 (읽기 전용)
   */
  async integrateGoogleDrive(): Promise<IntegrationResult> {
    console.log('☁️ Google Drive 통합 시작...');
    
    const startTime = new Date();
    let processedCount = 0;
    let errorCount = 0;
    const errors: string[] = [];

    try {
      if (!this.config.googleDriveEnabled) {
        console.log('⏸️ Google Drive 통합 비활성화됨');
        return {
          success: true,
          processedCount: 0,
          errorCount: 0,
          errors: [],
          metadata: {
            startTime,
            endTime: new Date(),
            totalFiles: 0,
            totalSize: 0
          }
        };
      }

      // Google Drive 파일 목록 조회
      const driveFiles = await this.driveService.searchFiles({
        query: '',
        mimeTypes: ['text/plain', 'text/markdown', 'application/pdf'],
        maxResults: 1000
      });
      
      // 메타데이터 추출 및 BigQuery 적재
      for (const file of driveFiles) {
        try {
          await this.simulateBigQueryIngest({
            fileName: file.name,
            filePath: `gdrive://${file.id}`,
            fileSize: parseInt(file.size || '0'),
            lastModified: new Date(file.modifiedTime || Date.now()),
            fileType: file.mimeType || 'unknown',
            checksum: file.id
          });
          processedCount++;
        } catch (error) {
          const errorMsg = `${file.name} 적재 실패: ${error instanceof Error ? error.message : String(error)}`;
          errors.push(errorMsg);
          errorCount++;
        }
      }

      const result: IntegrationResult = {
        success: errorCount === 0,
        processedCount,
        errorCount,
        errors,
        metadata: {
          startTime,
          endTime: new Date(),
          totalFiles: driveFiles.length,
          totalSize: driveFiles.reduce((sum: number, file: any) => sum + (parseInt(file.size || '0')), 0)
        }
      };

      this.integrationHistory.push({
        timestamp: new Date(),
        source: 'google_drive',
        result
      });

      console.log(`✅ Google Drive 통합 완료: ${processedCount}개 성공, ${errorCount}개 실패`);
      return result;

    } catch (error) {
      console.error('❌ Google Drive 통합 실패:', error);
      throw error;
    }
  }

  /**
   * 3. 웹 브라우징 기록 통합 (Level 1 요구사항)
   * 브라우저 확장 프로그램을 통해 방문한 URL과 페이지 제목을 수동으로 내보내기하여
   * BigQuery에 적재
   */
  async integrateBrowserHistory(): Promise<IntegrationResult> {
    console.log('🌐 웹 브라우징 기록 통합 시작...');
    
    const startTime = new Date();
    let processedCount = 0;
    let errorCount = 0;
    const errors: string[] = [];

    try {
      if (!this.config.browserHistoryEnabled) {
        console.log('⏸️ 웹 브라우징 기록 통합 비활성화됨');
        return {
          success: true,
          processedCount: 0,
          errorCount: 0,
          errors: [],
          metadata: {
            startTime,
            endTime: new Date(),
            totalFiles: 0,
            totalSize: 0
          }
        };
      }

      // 브라우저 기록 파일 읽기 (Chrome, Firefox 등)
      const browserHistoryFiles = [
        'C:/Users/Administrator/AppData/Local/Google/Chrome/User Data/Default/History',
        'C:/Users/Administrator/AppData/Local/Mozilla/Firefox/Profiles'
      ];

      for (const historyFile of browserHistoryFiles) {
        try {
          if (await this.fileExists(historyFile)) {
            const historyData = await this.extractBrowserHistory(historyFile);
            await this.simulateBigQueryIngest({
              fileName: 'browser_history',
              filePath: historyFile,
              fileSize: historyData.length,
              lastModified: new Date(),
              fileType: 'browser_history',
              checksum: 'browser_history'
            });
            processedCount++;
          }
        } catch (error) {
          const errorMsg = `${historyFile} 처리 실패: ${error instanceof Error ? error.message : String(error)}`;
          errors.push(errorMsg);
          errorCount++;
        }
      }

      const result: IntegrationResult = {
        success: errorCount === 0,
        processedCount,
        errorCount,
        errors,
        metadata: {
          startTime,
          endTime: new Date(),
          totalFiles: browserHistoryFiles.length,
          totalSize: 0
        }
      };

      this.integrationHistory.push({
        timestamp: new Date(),
        source: 'browser_history',
        result
      });

      console.log(`✅ 웹 브라우징 기록 통합 완료: ${processedCount}개 성공, ${errorCount}개 실패`);
      return result;

    } catch (error) {
      console.error('❌ 웹 브라우징 기록 통합 실패:', error);
      throw error;
    }
  }

  /**
   * 4. 캘린더 통합 (Level 1 요구사항)
   * 수동 실행 스크립트를 통해 모든 캘린더 일정(이벤트명, 시간, 참석자)을
   * BigQuery에 일괄 적재
   */
  async integrateCalendar(): Promise<IntegrationResult> {
    console.log('📅 캘린더 통합 시작...');
    
    const startTime = new Date();
    let processedCount = 0;
    let errorCount = 0;
    const errors: string[] = [];

    try {
      if (!this.config.calendarEnabled) {
        console.log('⏸️ 캘린더 통합 비활성화됨');
        return {
          success: true,
          processedCount: 0,
          errorCount: 0,
          errors: [],
          metadata: {
            startTime,
            endTime: new Date(),
            totalFiles: 0,
            totalSize: 0
          }
        };
      }

      // Google Calendar API를 통한 일정 조회 (실제 구현 시)
      const calendarEvents = await this.fetchCalendarEvents();
      
      for (const event of calendarEvents) {
        try {
          await this.simulateBigQueryIngest({
            fileName: event.summary,
            filePath: `calendar://${event.id}`,
            fileSize: JSON.stringify(event).length,
            lastModified: new Date(event.updated || Date.now()),
            fileType: 'calendar_event',
            checksum: event.id
          });
          processedCount++;
        } catch (error) {
          const errorMsg = `${event.summary} 적재 실패: ${error instanceof Error ? error.message : String(error)}`;
          errors.push(errorMsg);
          errorCount++;
        }
      }

      const result: IntegrationResult = {
        success: errorCount === 0,
        processedCount,
        errorCount,
        errors,
        metadata: {
          startTime,
          endTime: new Date(),
          totalFiles: calendarEvents.length,
          totalSize: 0
        }
      };

      this.integrationHistory.push({
        timestamp: new Date(),
        source: 'calendar',
        result
      });

      console.log(`✅ 캘린더 통합 완료: ${processedCount}개 성공, ${errorCount}개 실패`);
      return result;

    } catch (error) {
      console.error('❌ 캘린더 통합 실패:', error);
      throw error;
    }
  }

  /**
   * 5. 앱 API 통합 (Level 1 요구사항)
   * Notion 기준으로 특정 데이터베이스의 모든 페이지를 읽어와 BigQuery 일괄 적재
   */
  async integrateAppAPIs(): Promise<IntegrationResult> {
    console.log('🔌 앱 API 통합 시작...');
    
    const startTime = new Date();
    let processedCount = 0;
    let errorCount = 0;
    const errors: string[] = [];

    try {
      if (!this.config.notionEnabled) {
        console.log('⏸️ Notion API 통합 비활성화됨');
        return {
          success: true,
          processedCount: 0,
          errorCount: 0,
          errors: [],
          metadata: {
            startTime,
            endTime: new Date(),
            totalFiles: 0,
            totalSize: 0
          }
        };
      }

      // Notion 데이터베이스 페이지 조회 (실제 구현 시)
      const notionPages = await this.fetchNotionPages();
      
      for (const page of notionPages) {
        try {
          await this.simulateBigQueryIngest({
            fileName: page.title,
            filePath: `notion://${page.id}`,
            fileSize: JSON.stringify(page).length,
            lastModified: new Date(page.last_edited_time || Date.now()),
            fileType: 'notion_page',
            checksum: page.id
          });
          processedCount++;
        } catch (error) {
          const errorMsg = `${page.title} 적재 실패: ${error instanceof Error ? error.message : String(error)}`;
          errors.push(errorMsg);
          errorCount++;
        }
      }

      const result: IntegrationResult = {
        success: errorCount === 0,
        processedCount,
        errorCount,
        errors,
        metadata: {
          startTime,
          endTime: new Date(),
          totalFiles: notionPages.length,
          totalSize: 0
        }
      };

      this.integrationHistory.push({
        timestamp: new Date(),
        source: 'notion_api',
        result
      });

      console.log(`✅ 앱 API 통합 완료: ${processedCount}개 성공, ${errorCount}개 실패`);
      return result;

    } catch (error) {
      console.error('❌ 앱 API 통합 실패:', error);
      throw error;
    }
  }

  /**
   * 전체 데이터 소스 통합 실행
   */
  async integrateAllDataSources(): Promise<{
    localFiles: IntegrationResult;
    googleDrive: IntegrationResult;
    browserHistory: IntegrationResult;
    calendar: IntegrationResult;
    appAPIs: IntegrationResult;
    summary: {
      totalProcessed: number;
      totalErrors: number;
      overallSuccess: boolean;
    };
  }> {
    console.log('🚀 전체 데이터 소스 통합 시작...');
    
    const results = {
      localFiles: await this.integrateLocalFileSystem(),
      googleDrive: await this.integrateGoogleDrive(),
      browserHistory: await this.integrateBrowserHistory(),
      calendar: await this.integrateCalendar(),
      appAPIs: await this.integrateAppAPIs()
    };

    const totalProcessed = Object.values(results).reduce((sum, result) => sum + result.processedCount, 0);
    const totalErrors = Object.values(results).reduce((sum, result) => sum + result.errorCount, 0);
    const overallSuccess = totalErrors === 0;

    const summary = {
      totalProcessed,
      totalErrors,
      overallSuccess
    };

    console.log('\n📊 === 데이터 소스 통합 완료 요약 ===');
    console.log(`✅ 총 처리된 항목: ${totalProcessed}개`);
    console.log(`❌ 총 오류: ${totalErrors}개`);
    console.log(`🎯 전체 성공: ${overallSuccess ? '예' : '아니오'}`);
    console.log('========================================\n');

    return { ...results, summary };
  }

  // ======= Private Helper Methods =======

  private async ensureDirectoryExists(dirPath: string): Promise<void> {
    try {
      await fs.access(dirPath);
    } catch {
      await fs.mkdir(dirPath, { recursive: true });
      console.log(`📁 디렉토리 생성: ${dirPath}`);
    }
  }

  private async scanDirectory(dirPath: string): Promise<FileMetadata[]> {
    const files: FileMetadata[] = [];
    
    const scanRecursive = async (currentPath: string): Promise<void> => {
      try {
        const entries = await fs.readdir(currentPath, { withFileTypes: true });
        
        for (const entry of entries) {
          const fullPath = path.join(currentPath, entry.name);
          
          if (entry.isDirectory()) {
            await scanRecursive(fullPath);
          } else if (entry.isFile()) {
            try {
              const stats = await fs.stat(fullPath);
              const content = await fs.readFile(fullPath, 'utf8');
              const checksum = await this.calculateChecksum(content);
              
              files.push({
                fileName: entry.name,
                filePath: fullPath,
                fileSize: stats.size,
                lastModified: stats.mtime,
                fileType: path.extname(entry.name),
                checksum
              });
            } catch (error) {
              console.warn(`⚠️ 파일 읽기 실패: ${fullPath}`);
            }
          }
        }
      } catch (error) {
        console.warn(`⚠️ 디렉토리 스캔 실패: ${currentPath}`);
      }
    };

    await scanRecursive(dirPath);
    return files;
  }

  private async calculateChecksum(content: string): Promise<string> {
    // 간단한 해시 계산 (실제 구현 시 crypto 모듈 사용)
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 32bit 정수로 변환
    }
    return hash.toString(16);
  }

  private async simulateBigQueryIngest(metadata: FileMetadata): Promise<void> {
    // BigQuery 적재 시뮬레이션 (실제 구현 시 BigQuery 클라이언트 사용)
    await new Promise(resolve => setTimeout(resolve, 10)); // 10ms 지연
    console.log(`📊 BigQuery 적재: ${metadata.fileName}`);
  }

  private async fileExists(filePath: string): Promise<boolean> {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  private async extractBrowserHistory(filePath: string): Promise<any[]> {
    // 브라우저 기록 추출 시뮬레이션
    return [
      { url: 'https://example.com', title: 'Example Page', timestamp: new Date() }
    ];
  }

  private async fetchCalendarEvents(): Promise<any[]> {
    // 캘린더 이벤트 조회 시뮬레이션
    return [
      { id: '1', summary: 'Team Meeting', start: new Date(), end: new Date() }
    ];
  }

  private async fetchNotionPages(): Promise<any[]> {
    // Notion 페이지 조회 시뮬레이션
    return [
      { id: '1', title: 'Project Notes', last_edited_time: new Date() }
    ];
  }

  /**
   * 통합 히스토리 조회
   */
  getIntegrationHistory() {
    return this.integrationHistory;
  }

  /**
   * 통합 상태 요약
   */
  getIntegrationSummary() {
    const totalIntegrations = this.integrationHistory.length;
    const successfulIntegrations = this.integrationHistory.filter(h => h.result.success).length;
    const totalProcessed = this.integrationHistory.reduce((sum, h) => sum + h.result.processedCount, 0);
    const totalErrors = this.integrationHistory.reduce((sum, h) => sum + h.result.errorCount, 0);

    return {
      totalIntegrations,
      successfulIntegrations,
      successRate: totalIntegrations > 0 ? (successfulIntegrations / totalIntegrations) * 100 : 0,
      totalProcessed,
      totalErrors
    };
  }
}
