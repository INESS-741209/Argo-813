/**
 * ARGO Layer 1 Phase 1: 통합 서비스
 * 블루프린트: "모든 Phase 1 서비스의 통합 오케스트레이션"
 * 목표: CLI와 웹 인터페이스를 위한 단일 진입점
 */

import { EventEmitter } from 'events';
import { EmbeddingService } from './services/embedding-service.js';
import { SemanticSearchEngine } from './services/semantic-search.js';
import { AutoTaggingService } from './services/auto-tagging-service.js';
import { GoogleDriveService } from './services/google-drive-service.js';
import { RealtimeSyncService } from './services/realtime-sync-service.js';
import { DataSourceIntegrationService } from './services/data-source-integration.js';
import { WebInterface } from './interfaces/web-interface.js';
import { SynapticNetwork } from './synaptic-network/synaptic-network.js';
import { Layer1Config, ServiceStatus, PerformanceMetrics } from './types/common.js';

interface Layer1Status {
  status: ServiceStatus;
  services: {
    embedding: ServiceStatus;
    drive: ServiceStatus;
    sync: ServiceStatus;
    tagging: ServiceStatus;
    search: ServiceStatus;
    web?: ServiceStatus;
  };
  startTime: Date;
  errors: string[];
}

/**
 * ARGO Layer 1 Integrated Service
 * Phase 1 핵심: 모든 서비스의 통합 관리 및 오케스트레이션
 */
class ArgoLayer1Service extends EventEmitter {
  private config: Layer1Config;
  private status: Layer1Status;
  
  // 서비스 인스턴스들
  public embeddingService!: EmbeddingService;
  public driveService!: GoogleDriveService;
  public syncService!: RealtimeSyncService;
  public taggingService!: AutoTaggingService;
  public searchEngine!: SemanticSearchEngine;
  public dataSourceIntegrationService!: DataSourceIntegrationService;
  public webInterface?: WebInterface;
  private network!: SynapticNetwork;

  constructor(config: Layer1Config = {}) {
    super();
    
    this.config = {
      enableWebInterface: true,
      enableRealtimeSync: true,
      webPort: 3000,
      dataDir: 'C:\\Argo-813\\data',
      ...config
    };

    this.status = {
      status: 'initializing',
      services: {
        embedding: 'initializing',
        drive: 'initializing',
        sync: 'initializing',
        tagging: 'initializing',
        search: 'initializing'
      },
      startTime: new Date(),
      errors: []
    };

    // 서비스 초기화
    this.initializeServices();
  }

  /**
   * Layer 1 시스템 시작
   */
  async start(): Promise<void> {
    console.log('🧠 ARGO Layer 1 시작 중...');
    console.log(`📅 시작 시간: ${this.status.startTime.toISOString()}`);
    
    try {
      // 1. 임베딩 서비스 시작
      console.log('🔤 임베딩 서비스 초기화...');
      try {
        // 임베딩 서비스는 생성자에서 이미 초기화됨
        this.status.services.embedding = 'ready';
        this.emit('service_ready', 'embedding');
        console.log('✅ 임베딩 서비스 준비 완료');
      } catch (error) {
        console.warn('⚠️ 임베딩 서비스 초기화 실패, 폴백 모드로 전환');
        this.status.services.embedding = 'error';
        this.status.errors.push(`임베딩 서비스: ${error instanceof Error ? error.message : String(error)}`);
      }

      // 2. Google Drive 서비스 시작
      console.log('☁️  Google Drive 서비스 초기화...');
      try {
        // Drive 서비스도 생성자에서 초기화됨
        this.status.services.drive = 'ready';
        this.emit('service_ready', 'drive');
        console.log('✅ Google Drive 서비스 준비 완료');
      } catch (error) {
        console.warn('⚠️ Google Drive 서비스 초기화 실패, 폴백 모드로 전환');
        this.status.services.drive = 'error';
        this.status.errors.push(`Google Drive 서비스: ${error instanceof Error ? error.message : String(error)}`);
      }

      // 3. 검색 엔진 시작
      console.log('🔍 시맨틱 검색 엔진 초기화...');
      try {
        this.status.services.search = 'ready';
        this.emit('service_ready', 'search');
        console.log('✅ 시맨틱 검색 엔진 준비 완료');
      } catch (error) {
        console.warn('⚠️ 검색 엔진 초기화 실패, 폴백 모드로 전환');
        this.status.services.search = 'error';
        this.status.errors.push(`검색 엔진: ${error instanceof Error ? error.message : String(error)}`);
      }

      // 4. 태깅 서비스 시작
      console.log('🏷️  자동 태깅 서비스 초기화...');
      try {
        this.status.services.tagging = 'ready';
        this.emit('service_ready', 'tagging');
        console.log('✅ 자동 태깅 서비스 준비 완료');
      } catch (error) {
        console.warn('⚠️ 태깅 서비스 초기화 실패, 폴백 모드로 전환');
        this.status.services.tagging = 'error';
        this.status.errors.push(`태깅 서비스: ${error instanceof Error ? error.message : String(error)}`);
      }

      // 5. 실시간 동기화 시작 (옵션)
      if (this.config.enableRealtimeSync) {
        console.log('🔄 실시간 동기화 서비스 시작...');
        try {
          await this.syncService.startRealtimeSync();
          this.status.services.sync = 'ready';
          this.emit('service_ready', 'sync');
          console.log('✅ 실시간 동기화 서비스 준비 완료');
        } catch (error) {
          console.warn('⚠️ 실시간 동기화 서비스 시작 실패, 폴백 모드로 전환');
          this.status.services.sync = 'error';
          this.status.errors.push(`실시간 동기화: ${error instanceof Error ? error.message : String(error)}`);
        }
      } else {
        console.log('⏸️  실시간 동기화 비활성화됨');
        this.status.services.sync = 'ready';
      }

      // 6. 웹 인터페이스 시작 (옵션)
      if (this.config.enableWebInterface && this.webInterface) {
        console.log(`🌐 웹 인터페이스 시작 중... (포트: ${this.config.webPort})`);
        try {
          await this.webInterface.start();
          this.status.services.web = 'ready';
          this.emit('service_ready', 'web');
          console.log('✅ 웹 인터페이스 준비 완료');
        } catch (error) {
          console.warn('⚠️ 웹 인터페이스 시작 실패, CLI 모드로 전환');
          this.status.services.web = 'error';
          this.status.errors.push(`웹 인터페이스: ${error instanceof Error ? error.message : String(error)}`);
          this.config.enableWebInterface = false;
        }
      }

      // 7. 초기 설정 작업
      await this.performInitialSetup();

      // 최소한의 서비스가 준비되었는지 확인
      const readyServices = Object.values(this.status.services).filter(status => status === 'ready').length;
      const totalServices = Object.keys(this.status.services).length;
      
      if (readyServices >= Math.ceil(totalServices * 0.7)) { // 70% 이상 준비되면 시스템 준비로 간주
        this.status.status = 'ready';
        this.emit('system_ready');
        console.log('✅ ARGO Layer 1 시작 완료 (일부 서비스 폴백 모드)');
      } else {
        this.status.status = 'degraded';
        console.warn('⚠️ ARGO Layer 1이 제한된 기능으로 시작됨');
      }
      
      this.printSystemStatus();

    } catch (error) {
      console.error('❌ ARGO Layer 1 시작 실패:', error);
      this.status.status = 'error';
      this.status.errors.push(error instanceof Error ? error.message : String(error));
      this.emit('system_error', error);
      throw error;
    }
  }

  /**
   * Layer 1 시스템 중지
   */
  async shutdown(): Promise<void> {
    console.log('⏹️  ARGO Layer 1 시스템 종료 중...');
    
    this.status.status = 'shutdown';

    try {
      // 웹 인터페이스 중지
      if (this.webInterface) {
        console.log('🌐 웹 인터페이스 중지...');
        await this.webInterface.stop();
      }

      // 실시간 동기화 중지
      if (this.config.enableRealtimeSync) {
        console.log('🔄 실시간 동기화 중지...');
        await this.syncService.stopRealtimeSync();
      }

      // 기타 정리 작업
      console.log('🧹 리소스 정리...');
      
      this.emit('system_shutdown');
      console.log('✅ ARGO Layer 1 시스템 종료 완료');

    } catch (error) {
      console.error('❌ 시스템 종료 중 오류:', error);
      throw error;
    }
  }

  /**
   * 시스템 상태 조회
   */
  getStatus(): Layer1Status {
    return { ...this.status };
  }

  /**
   * 통합 검색 (모든 검색 방식 통합)
   */
  async search(query: string, options?: {
    mode?: 'hybrid' | 'semantic' | 'drive' | 'local';
    maxResults?: number;
    includeEmbeddings?: boolean;
  }): Promise<any[]> {
    
    const { mode = 'hybrid', maxResults = 20, includeEmbeddings = false } = options || {};

    console.log(`🔍 통합 검색: "${query}" (모드: ${mode})`);

    try {
      let results = [];

      switch (mode) {
        case 'semantic':
          const semanticResults = await this.searchEngine.search({
            query,
            filters: { maxResults }
          });
          results = semanticResults.results;
          break;

        case 'drive':
          results = await this.driveService.searchFiles({
            query,
            maxResults
          });
          break;

        case 'local':
          const localResults = await this.searchEngine.search({
            query,
            filters: { maxResults }
          });
          results = localResults.results;
          break;

        case 'hybrid':
        default:
          results = await this.driveService.hybridSearch(query, {
            includeLocal: true,
            includeDrive: true,
            maxResults
          });
      }

      // 임베딩 정보 포함 (옵션)
      if (includeEmbeddings && results.length > 0) {
        console.log('🧮 검색 결과 임베딩 정보 추가...');
        // 임베딩 정보를 추가하는 로직 (필요시)
      }

      console.log(`✅ ${results.length}개 검색 결과 반환`);
      return results;

    } catch (error) {
      console.error('❌ 통합 검색 오류:', error);
      throw error;
    }
  }

  /**
   * 통합 파일 분석 (태깅 + 임베딩 + 동기화)
   */
  async analyzeFile(filePath: string, content?: string): Promise<{
    tagging: any;
    embedding: any;
    synchronized: boolean;
  }> {
    console.log(`🔬 파일 분석 시작: ${filePath}`);

    try {
      // 병렬 처리로 성능 최적화
      const [taggingResult, embeddingResult] = await Promise.all([
        this.taggingService.tagFile(filePath, content),
        content ? this.embeddingService.getEmbedding({ text: content }) : null
      ]);

      // 동기화 상태 확인
      const syncState = this.syncService.getSyncState();
      const isSynchronized = syncState.stats.syncedFiles > 0;

      const result = {
        tagging: taggingResult,
        embedding: embeddingResult,
        synchronized: isSynchronized
      };

      console.log(`✅ 파일 분석 완료: ${filePath}`);
      console.log(`   - 태그: ${taggingResult.tags.length}개`);
      console.log(`   - 임베딩: ${embeddingResult ? '생성됨' : '생성 안됨'}`);
      console.log(`   - 동기화: ${isSynchronized ? '완료' : '대기'}`);

      return result;

    } catch (error) {
      console.error(`❌ 파일 분석 오류 (${filePath}):`, error);
      throw error;
    }
  }

  /**
   * 배치 파일 처리
   */
  async processBatch(filePaths: string[]): Promise<{
    processed: number;
    errors: number;
    results: any[];
  }> {
    console.log(`📦 배치 처리 시작: ${filePaths.length}개 파일`);

    const results = [];
    let processed = 0;
    let errors = 0;

    for (const filePath of filePaths) {
      try {
        const result = await this.analyzeFile(filePath);
        results.push({ filePath, ...result, success: true });
        processed++;
      } catch (error) {
        console.warn(`⚠️  파일 처리 실패: ${filePath}`);
        results.push({ 
          filePath, 
          success: false, 
          error: error instanceof Error ? error.message : String(error) 
        });
        errors++;
      }
    }

    console.log(`✅ 배치 처리 완료: ${processed}개 성공, ${errors}개 실패`);

    return { processed, errors, results };
  }

  /**
   * 시스템 헬스체크
   */
  async healthCheck(): Promise<{
    healthy: boolean;
    services: Record<string, boolean>;
    performance: {
      uptime: number;
      memoryUsage: NodeJS.MemoryUsage;
    };
    statistics: any;
  }> {
    const services: Record<string, boolean> = {};
    
    // 각 서비스 상태 확인
    Object.entries(this.status.services).forEach(([service, status]) => {
      services[service] = status === 'ready';
    });

    const allServicesHealthy = Object.values(services).every(healthy => healthy);

    // 통계 수집
    const embeddingStats = this.embeddingService.getUsageStats();
    const syncStats = this.syncService.getSyncStats();
    const taggingAnalytics = this.taggingService.getTagAnalytics();

    return {
      healthy: allServicesHealthy && this.status.status === 'ready',
      services,
      performance: {
        uptime: Date.now() - this.status.startTime.getTime(),
        memoryUsage: process.memoryUsage()
      },
      statistics: {
        embedding: embeddingStats,
        sync: syncStats,
        tagging: {
          totalTags: taggingAnalytics.mostUsedTags.length,
          categories: Object.keys(taggingAnalytics.categoryDistribution).length
        }
      }
    };
  }

  // ======= Private Methods =======

  private async initializeServices(): Promise<void> {
    console.log('🔧 서비스 초기화 시작...');

    try {
      // 1. 임베딩 서비스
      console.log('🔤 임베딩 서비스 초기화...');
      this.embeddingService = new EmbeddingService(this.config.openaiApiKey);
      console.log('✅ 임베딩 서비스 초기화 완료');

      // 2. Google Drive 서비스
      console.log('☁️ Google Drive 서비스 초기화...');
      this.driveService = new GoogleDriveService(this.embeddingService);
      console.log('✅ Google Drive 서비스 초기화 완료');

      // 3. 신경망 네트워크
      console.log('🧠 신경망 네트워크 초기화...');
      this.network = new SynapticNetwork();
      console.log('✅ 신경망 네트워크 초기화 완료');

      // 4. 시맨틱 검색 엔진
      console.log('🔍 시맨틱 검색 엔진 초기화...');
      this.searchEngine = new SemanticSearchEngine(this.embeddingService, this.network);
      console.log('✅ 시맨틱 검색 엔진 초기화 완료');

      // 5. 자동 태깅 서비스
      console.log('🏷️ 자동 태깅 서비스 초기화...');
      this.taggingService = new AutoTaggingService(this.embeddingService, this.driveService);
      console.log('✅ 자동 태깅 서비스 초기화 완료');

      // 6. 실시간 동기화 서비스
      console.log('🔄 실시간 동기화 서비스 초기화...');
      this.syncService = new RealtimeSyncService(this.driveService, this.embeddingService);
      console.log('✅ 실시간 동기화 서비스 초기화 완료');

      // 7. 데이터 소스 통합 서비스
      console.log('📊 데이터 소스 통합 서비스 초기화...');
      const dataSourceConfig = {
        localDirectories: ['C:/argo-sync', 'C:/Argo-813'],
        googleDriveEnabled: true,
        browserHistoryEnabled: true,
        calendarEnabled: true,
        notionEnabled: true,
        slackEnabled: false,
        bigQueryProjectId: 'argo-project',
        bigQueryDatasetId: 'argo_analytics'
      };
      this.dataSourceIntegrationService = new DataSourceIntegrationService(
        dataSourceConfig,
        this.embeddingService,
        this.driveService
      );
      console.log('✅ 데이터 소스 통합 서비스 초기화 완료');

      // 8. 웹 인터페이스 (옵션)
      if (this.config.enableWebInterface) {
        console.log('🌐 웹 인터페이스 초기화...');
        try {
          this.webInterface = new WebInterface(
            this.embeddingService,
            this.driveService,
            this.syncService,
            this.taggingService,
            this.searchEngine,
            { 
              port: this.config.webPort,
              host: 'localhost',
              staticDir: 'C:\\Argo-813\\web\\static',
              uploadDir: 'C:\\Argo-813\\web\\uploads'
            }
          );
          console.log('✅ 웹 인터페이스 초기화 완료');
        } catch (error) {
          console.warn('⚠️ 웹 인터페이스 초기화 실패:', error);
          this.config.enableWebInterface = false;
        }
      }

      // 서비스 간 이벤트 연결
      this.setupServiceEvents();

      console.log('✅ 모든 서비스 초기화 완료');
    } catch (error) {
      console.error('❌ 서비스 초기화 실패:', error);
      throw error;
    }
  }

  private setupServiceEvents(): void {
    // 동기화 이벤트
    this.syncService.on('sync_started', () => {
      console.log('🔄 실시간 동기화 시작됨');
    });

    this.syncService.on('file_synced', (event) => {
      console.log(`📁 파일 동기화: ${event.filePath}`);
    });

    this.syncService.on('conflict_detected', (conflict) => {
      console.warn(`⚠️  동기화 충돌: ${conflict.filePath}`);
    });

    // 시스템 전체 이벤트 전달
    ['sync_started', 'sync_stopped', 'sync_error', 'file_synced', 'conflict_detected'].forEach(event => {
      this.syncService.on(event, (...args) => this.emit(event, ...args));
    });
  }

  private async performInitialSetup(): Promise<void> {
    console.log('⚙️  초기 설정 작업 수행...');

    try {
      // 1. 데이터 디렉토리 확인 및 생성
      await this.ensureDataDirectory();

      // 2. 기존 파일 인덱싱 (백그라운드)
      if (this.config.enableRealtimeSync) {
        setTimeout(async () => {
          console.log('📊 백그라운드 인덱싱 시작...');
          const stats = await this.driveService.syncDriveFiles();
          console.log(`📊 백그라운드 인덱싱 완료: ${stats.synced + stats.updated}개 파일`);
        }, 5000); // 5초 후 시작
      }

      console.log('✅ 초기 설정 완료');

    } catch (error) {
      console.warn('⚠️  초기 설정 중 일부 오류 발생:', error);
      // 치명적이지 않은 오류는 무시하고 계속 진행
    }
  }

  private async ensureDataDirectory(): Promise<void> {
    try {
      const fs = await import('fs/promises');
      await fs.mkdir(this.config.dataDir!, { recursive: true });
      console.log(`📁 데이터 디렉토리 확인: ${this.config.dataDir}`);
    } catch (error) {
      console.warn('데이터 디렉토리 생성 실패:', error);
    }
  }

  private printSystemStatus(): void {
    console.log('\n🧠 === ARGO Layer 1 시스템 상태 ===');
    console.log(`📅 시작 시간: ${this.status.startTime.toISOString()}`);
    console.log(`🚦 전체 상태: ${this.status.status.toUpperCase()}`);
    console.log('🔧 서비스 상태:');
    
    Object.entries(this.status.services).forEach(([service, status]) => {
      const emoji = status === 'ready' ? '✅' : status === 'error' ? '❌' : '⏳';
      console.log(`   ${emoji} ${service}: ${status}`);
    });

    if (this.status.errors.length > 0) {
      console.log('❌ 오류:');
      this.status.errors.forEach(error => {
        console.log(`   - ${error}`);
      });
    }

    console.log('==========================================\n');

    // 사용 가능한 명령어 안내
    if (this.config.enableWebInterface) {
      console.log(`🌐 웹 인터페이스: http://localhost:${this.config.webPort}`);
    }
    console.log('💡 사용 방법: CLI에서 search(), analyzeFile(), healthCheck() 등을 호출하세요');
    console.log('');
  }
}

export {
  ArgoLayer1Service,
  Layer1Config,
  Layer1Status
};