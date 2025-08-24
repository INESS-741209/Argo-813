/**
 * ARGO Layer 1: CLI Interface Implementation
 * 사용자와 상호작용하는 명령줄 인터페이스
 */

import { SemanticSearchEngine } from '../services/semantic-search.js';
import { AutoTaggingService } from '../services/auto-tagging-service.js';
import { GoogleDriveService } from '../services/google-drive-service.js';
import { RealtimeSyncService } from '../services/realtime-sync-service.js';
import { IntelligentNode } from '../knowledge-mesh/intelligent-node.js';
import { FileContent, CommandResult, Layer1Config, PerformanceMetrics } from '../types/common.js';

export class ArgoCliInterface {
  private rl: any; // readline.Interface
  private layer1Service: any; // ArgoLayer1Service
  private isRunning: boolean;
  private currentSession: string;
  private commandHistory: string[];
  
  private searchEngine: SemanticSearchEngine;
  private taggingService: AutoTaggingService;
  private driveService: GoogleDriveService;
  private syncService: RealtimeSyncService;
  private network: any; // SynapticNetwork 인스턴스
  private predictiveEngine: any; // PredictiveEngine 인스턴스
  
  constructor(config?: Layer1Config) {
    this.isRunning = false;
    this.currentSession = this.generateSessionId();
    this.commandHistory = [];
    
    // 임시로 기본 인스턴스 생성 (실제로는 의존성 주입으로 처리)
    this.searchEngine = new SemanticSearchEngine({} as any, {} as any);
    this.taggingService = new AutoTaggingService({} as any, {} as any);
    this.driveService = new GoogleDriveService({} as any);
    this.syncService = new RealtimeSyncService({} as any, {} as any);
    this.network = {}; // 임시 초기화
    this.predictiveEngine = {}; // 임시 초기화
    
    this.setupEventHandlers();
  }

  /**
   * CLI 시작
   */
  async start(): Promise<void> {
    console.log('🚀 ARGO Layer 1: Neuromorphic Knowledge Mesh - Phase 1');
    console.log('✨ 블루프린트: "Phase 1 완전한 AI 지능 시스템"');
    console.log('🎯 Phase 1 목표: 시맨틱 검색 + 자동 태깅 + 실시간 동기화');
    console.log('');
    console.log('🔧 Layer 1 서비스 초기화 중...');
    
    try {
      // Layer 1 통합 서비스 시작
      await this.layer1Service.start();
      
      console.log('✅ Phase 1 모든 서비스 준비 완료!');
      console.log('');
      console.log('💡 도움말을 보려면 "help"를 입력하세요.');
      console.log('🌐 웹 인터페이스: http://localhost:3000');
      console.log('');
      
      this.isRunning = true;
      this.rl.prompt();
      
    } catch (error) {
      console.error('❌ Layer 1 서비스 시작 실패:', error);
      process.exit(1);
    }
  }

  /**
   * 서비스 이벤트 핸들러 설정
   */
  private setupServiceEvents(): void {
    this.layer1Service.on('system_ready', () => {
      console.log('🎉 모든 Phase 1 서비스가 준비되었습니다!');
    });

    this.layer1Service.on('service_ready', (serviceName: string) => {
      console.log(`✅ ${serviceName} 서비스 준비 완료`);
    });

    this.layer1Service.on('sync_started', () => {
      console.log('🔄 실시간 동기화가 시작되었습니다');
    });

    this.layer1Service.on('file_synced', (event: any) => {
      console.log(`📁 파일 동기화: ${event.filePath}`);
    });

    this.layer1Service.on('conflict_detected', (conflict: any) => {
      console.log(`⚠️  동기화 충돌 감지: ${conflict.filePath}`);
    });
  }

  /**
   * 이벤트 핸들러 설정
   */
  private setupEventHandlers(): void {
    this.rl.on('line', async (input: string) => {
      if (!this.isRunning) return;
      
      const trimmedInput = input.trim();
      if (trimmedInput === '') {
        this.rl.prompt();
        return;
      }
      
      this.commandHistory.push(trimmedInput);
      
      const startTime = Date.now();
      const result = await this.processCommand(trimmedInput);
      const executionTime = Date.now() - startTime;
      
      this.displayResult(result, executionTime);
      
      // 예측적 제안 표시
      await this.showPredictiveSuggestions(trimmedInput);
      
      this.rl.prompt();
    });
    
    this.rl.on('SIGINT', () => {
      console.log('\n👋 ARGO Layer 1을 종료합니다...');
      this.shutdown();
    });
  }

  /**
   * 명령어 처리
   */
  private async processCommand(input: string): Promise<CommandResult> {
    const [command, ...args] = input.split(' ');
    const argsString = args.join(' ');
    
    try {
      switch (command.toLowerCase()) {
        case 'help':
        case 'h':
          return this.showHelp();
          
        case 'find':
        case 'search':
          return await this.searchFiles(argsString);
          
        case 'semantic':
          return await this.semanticSearch(argsString);
          
        case 'tag':
          return await this.tagFile(argsString);
          
        case 'sync':
          return await this.syncFiles(argsString);
          
        case 'analyze':
          return await this.analyzeFile(argsString);
          
        case 'status':
          return this.showStatus();
          
        case 'insights':
          return await this.showInsights();
          
        case 'connections':
          return this.showConnections(argsString);
          
        case 'pattern':
          return this.showWorkPatterns();
          
        case 'clear':
          return this.clearScreen();
          
        case 'exit':
        case 'quit':
          return this.exit();
          
        default:
          return this.handleInvalidCommand(command);
      }
    } catch (error) {
      return this.handleError(error as Error, command);
    }
  }

  /**
   * 통합 검색 - Phase 1 하이브리드 검색
   */
  private async searchFiles(query: string): Promise<CommandResult> {
    if (!query) {
      return {
        success: false,
        message: '검색어를 입력해주세요. 예: find ARGO architecture',
        executionTime: 0,
        suggestions: ['semantic <query>', 'find <query>', 'analyze <filepath>'],
        timestamp: new Date()
      };
    }
    
    try {
      const results = await this.layer1Service.search(query, {
        mode: 'hybrid',
        maxResults: 10
      });
      
      return {
        success: true,
        message: `"${query}"에 대한 ${results.length}개 하이브리드 검색 결과를 찾았습니다.`,
        data: results,
        executionTime: 0,
        suggestions: [
          'semantic ' + query,
          'tag ' + (results[0]?.name || results[0]?.filePath || ''),
          'analyze ' + (results[0]?.name || results[0]?.filePath || '')
        ],
        timestamp: new Date()
      };
      
    } catch (error) {
      return this.handleError(error as Error, 'search');
    }
  }

  /**
   * 시맨틱 검색 - Phase 1 OpenAI 임베딩 기반
   */
  private async semanticSearch(query: string): Promise<CommandResult> {
    if (!query) {
      return {
        success: false,
        message: '시맨틱 검색어를 입력해주세요. 예: semantic "AI architecture patterns"',
        executionTime: 0,
        timestamp: new Date()
      };
    }
    
    try {
      const results = await this.layer1Service.search(query, {
        mode: 'semantic',
        maxResults: 10
      });
      
      return {
        success: true,
        message: `"${query}"에 대한 ${results.length}개 시맨틱 검색 결과를 찾았습니다.`,
        data: results,
        executionTime: 0,
        timestamp: new Date()
      };
      
    } catch (error) {
      return this.handleError(error as Error, 'semantic');
    }
  }

  /**
   * 파일 자동 태깅
   */
  private async tagFile(filePath: string): Promise<CommandResult> {
    if (!filePath) {
      return {
        success: false,
        message: '태깅할 파일 경로를 입력해주세요. 예: tag C:\\Argo-813\\README.md',
        executionTime: 0,
        timestamp: new Date()
      };
    }
    
    try {
      const result = await this.layer1Service.taggingService.tagFile(filePath);
      
      return {
        success: true,
        message: `"${filePath}" 파일 태깅 완료`,
        data: {
          contentType: result.contentType,
          tags: result.tags.slice(0, 10),
          categories: result.categories,
          confidence: (result.confidence * 100).toFixed(1) + '%'
        },
        executionTime: 0,
        suggestions: [
          'analyze ' + filePath,
          'semantic "' + result.tags.slice(0, 2).map((t: any) => t.name).join(' ') + '"'
        ],
        timestamp: new Date()
      };
      
    } catch (error) {
      return this.handleError(error as Error, 'tag');
    }
  }

  /**
   * 동기화 관련 명령어
   */
  private async syncFiles(action: string): Promise<CommandResult> {
    try {
      if (!action || action === 'status') {
        const state = this.layer1Service.syncService.getSyncState();
        const stats = this.layer1Service.syncService.getSyncStats();
        
        return {
          success: true,
          message: '동기화 상태',
          data: {
            status: state.status,
            lastSync: new Date(state.lastSync).toLocaleString(),
            syncedFiles: state.stats.syncedFiles,
            pendingFiles: state.stats.pendingFiles,
            conflicts: state.conflicts.length,
            uptime: Math.floor(stats.uptime / 1000 / 60) + '분'
          },
          executionTime: 0,
          suggestions: ['sync trigger', 'sync conflicts'],
          timestamp: new Date()
        };
        
      } else if (action === 'trigger') {
        const result = await this.layer1Service.syncService.triggerSync();
        
        return {
          success: true,
          message: '수동 동기화 완료',
          data: result,
          executionTime: 0,
          timestamp: new Date()
        };
        
      } else if (action === 'conflicts') {
        const state = this.layer1Service.syncService.getSyncState();
        
        return {
          success: true,
          message: `현재 ${state.conflicts.length}개의 동기화 충돌`,
          data: state.conflicts,
          executionTime: 0,
          timestamp: new Date()
        };
        
      } else {
        return {
          success: false,
          message: '잘못된 동기화 명령어입니다.',
          executionTime: 0,
          suggestions: ['sync status', 'sync trigger', 'sync conflicts'],
          timestamp: new Date()
        };
      }
      
    } catch (error) {
      return this.handleError(error as Error, 'sync');
    }
  }

  /**
   * 파일 종합 분석
   */
  private async analyzeFile(filePath: string): Promise<CommandResult> {
    if (!filePath) {
      return {
        success: false,
        message: '분석할 파일 경로를 입력해주세요. 예: analyze C:\\Argo-813\\README.md',
        executionTime: 0,
        timestamp: new Date()
      };
    }
    
    try {
      const result = await this.layer1Service.analyzeFile(filePath);
      
      return {
        success: true,
        message: `"${filePath}" 파일 종합 분석 완료`,
        data: {
          tags: result.tagging.tags.slice(0, 8),
          contentType: result.tagging.contentType,
          confidence: (result.tagging.confidence * 100).toFixed(1) + '%',
          embedding: result.embedding ? '생성됨' : '생성 안됨',
          synchronized: result.synchronized ? '동기화됨' : '대기 중'
        },
        executionTime: 0,
        suggestions: [
          'semantic "' + result.tagging.tags.slice(0, 2).map((t: any) => t.name).join(' ') + '"',
          'tag ' + filePath
        ],
        timestamp: new Date()
      };
      
    } catch (error) {
      return this.handleError(error as Error, 'analyze');
    }
  }

  /**
   * 시스템 상태 표시 - Phase 1 완전한 상태
   */
  private async showStatus(): Promise<CommandResult> {
    try {
      const healthCheck = await this.layer1Service.healthCheck();
      const systemStatus = this.layer1Service.getStatus();
      
      return {
        success: true,
        message: '🧠 ARGO Layer 1 Phase 1 시스템 상태',
        data: {
          systemStatus: systemStatus.status,
          services: systemStatus.services,
          healthy: healthCheck.healthy,
          uptime: Math.floor(healthCheck.performance.uptime / 1000 / 60) + '분',
          memoryUsage: Math.floor(healthCheck.performance.memoryUsage.rss / 1024 / 1024) + 'MB',
          statistics: healthCheck.statistics,
          sessionId: this.currentSession,
          commandHistory: this.commandHistory.length
        },
        executionTime: 0,
        suggestions: ['sync status', 'insights', 'help'],
        timestamp: new Date()
      };
      
    } catch (error) {
      return this.handleError(error as Error, 'status');
    }
  }

  /**
   * 태깅 분석 및 인사이트 표시
   */
  private async showInsights(): Promise<CommandResult> {
    try {
      const analytics = this.layer1Service.taggingService.getTagAnalytics();
      const systemHealth = await this.layer1Service.healthCheck();
      
      return {
        success: true,
        message: `🔮 태깅 시스템 분석 인사이트`,
        data: {
          mostUsedTags: analytics.mostUsedTags.slice(0, 10),
          categoryDistribution: analytics.categoryDistribution,
          contentTypeBreakdown: analytics.contentTypeBreakdown,
          tagCorrelations: analytics.tagCorrelations.slice(0, 5),
          systemPerformance: {
            embeddingCalls: systemHealth.statistics.embedding.apiCalls,
            totalCost: '$' + systemHealth.statistics.embedding.totalCost,
            cacheHitRate: (systemHealth.statistics.embedding.cacheHitRate * 100).toFixed(1) + '%'
          }
        },
        executionTime: 0,
        suggestions: ['status', 'sync status', 'semantic <trending_tag>'],
        timestamp: new Date()
      };
      
    } catch (error) {
      return this.handleError(error as Error, 'insights');
    }
  }

  /**
   * 연결 관계 표시
   */
  private showConnections(nodeIdOrQuery: string): CommandResult {
    if (!nodeIdOrQuery) {
      return {
        success: false,
        message: '노드 ID나 파일 경로를 입력해주세요.',
        executionTime: 0,
        timestamp: new Date()
      };
    }
    
    // 임시로 간단한 연결 정보 반환 (실제로는 네트워크에서 조회)
    return {
      success: true,
      message: `"${nodeIdOrQuery}"의 연결 관계 (시뮬레이션)`,
      data: {
        targetPath: nodeIdOrQuery,
        connections: [
          '관련 문서 1.md',
          '관련 문서 2.md',
          '연결된 파일.txt'
        ]
      },
      executionTime: 0,
      timestamp: new Date()
    };
  }

  /**
   * 작업 패턴 분석 표시
   */
  private showWorkPatterns(): CommandResult {
    const analysis = this.predictiveEngine.generateWorkPatternAnalysis();
    
    return {
      success: true,
      message: '📊 작업 패턴 분석 결과',
      data: analysis,
      executionTime: 0,
      timestamp: new Date()
    };
  }

  /**
   * 도움말 표시
   */
  private showHelp(): CommandResult {
    const helpText = `
🧠 ARGO Layer 1 - Neuromorphic Knowledge Mesh

📌 주요 명령어:
  find <검색어>     - 파일 검색 (예: find ARGO architecture)
  status            - 시스템 상태 확인
  insights          - 예측적 인사이트 보기
  connections <파일> - 파일 연결 관계 보기
  pattern           - 작업 패턴 분석
  help              - 이 도움말 보기
  clear             - 화면 지우기
  exit              - 종료

🎯 Phase 0 성공 기준: "find ARGO architecture files" 명령이 동작합니다!

💡 블루프린트 핵심 기능:
  • 🔍 지능형 파일 검색 (키워드 매칭을 넘어선 맥락적 이해)
  • 🧠 자기학습 연결망 (사용할수록 더 똑똑해짐)
  • 🔮 예측적 통찰 제공 (필요한 정보를 미리 제안)
  • 📊 작업 패턴 학습 (Director의 업무 스타일 학습)
`;
    
    return {
      success: true,
      message: helpText,
      executionTime: 0,
      timestamp: new Date()
    };
  }

  /**
   * 결과 표시
   */
  private displayResult(result: CommandResult, executionTime: number): void {
    if (result.success) {
      console.log(`✅ ${result.message}`);
      
      if (result.data) {
        if (Array.isArray(result.data)) {
          // 검색 결과 등 배열 데이터
          result.data.forEach((item: any, index: number) => {
            if (item.path && item.relevanceScore) {
              // 검색 결과 형식
              console.log(`\n${index + 1}. ${item.path}`);
              console.log(`   관련성: ${(item.relevanceScore * 100).toFixed(1)}%`);
              console.log(`   이유: ${item.reasoning}`);
              if (item.snippet) {
                console.log(`   미리보기: ${item.snippet}`);
              }
            } else if (item.type && item.content) {
              // 인사이트 형식
              console.log(`\n💡 ${item.type.toUpperCase()}: ${item.content}`);
              console.log(`   신뢰도: ${(item.confidence * 100).toFixed(1)}%`);
              console.log(`   예상 절약: ${item.estimatedValue}분`);
              console.log(`   제안: ${item.suggestedAction}`);
            }
          });
        } else {
          // 객체 데이터
          console.log(JSON.stringify(result.data, null, 2));
        }
      }
      
      if (result.suggestions) {
        console.log(`\n💡 제안: ${result.suggestions.join(', ')}`);
      }
      
    } else {
      console.log(`❌ ${result.message}`);
      
      if (result.suggestions) {
        console.log(`💡 다음을 시도해보세요: ${result.suggestions.join(', ')}`);
      }
    }
    
    console.log(`⏱️  실행 시간: ${executionTime}ms`);
  }

  /**
   * 예측적 제안 표시
   */
  private async showPredictiveSuggestions(lastCommand: string): Promise<void> {
    if (lastCommand.startsWith('find')) {
      const suggestions = [
        '💡 관련 파일들의 연결 관계를 보려면: connections <파일명>',
        '📊 현재 작업 패턴을 분석하려면: pattern',
        '🔮 추가 인사이트를 보려면: insights'
      ];
      
      const randomSuggestion = suggestions[Math.floor(Math.random() * suggestions.length)];
      console.log(`\n${randomSuggestion}`);
    }
  }

  // ======= Utility Methods =======

  private async scanDirectory(dirPath: string): Promise<string[]> {
    const files: string[] = [];
    
    try {
      const fs = await import('fs/promises');
      const path = await import('path');
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        
        if (entry.isDirectory()) {
          // 재귀적으로 하위 디렉토리 스캔
          const subFiles = await this.scanDirectory(fullPath);
          files.push(...subFiles);
        } else if (entry.isFile()) {
          // 파일 필터링 (텍스트 파일만)
          if (await this.isTextFile(entry.name)) {
            files.push(fullPath);
          }
        }
      }
    } catch (error) {
      console.warn(`디렉토리 스캔 실패: ${dirPath} - ${error}`);
    }
    
    return files;
  }

  private async createIntelligentNode(filePath: string): Promise<IntelligentNode> {
    try {
      const fs = await import('fs/promises');
      const content = await fs.readFile(filePath, 'utf-8');
      
      const fileContent: FileContent = {
        path: filePath,
        content,
        metadata: {
          size: content.length,
          type: 'text',
          encoding: 'utf-8',
          tags: [],
          importance: 1,
          lastModified: new Date()
        },
        lastModified: new Date()
      };

      const node = new IntelligentNode(filePath, fileContent);
      return node;
    } catch (error) {
      throw new Error(`파일을 읽을 수 없습니다: ${error}`);
    }
  }

  private async getNodeInfo(nodeId: string): Promise<CommandResult> {
    try {
      // 간단한 노드 정보 조회 (실제로는 네트워크에서 조회해야 함)
      const nodeInfo = {
        id: nodeId,
        type: 'file',
        path: nodeId,
        lastModified: new Date().toISOString(),
        connections: 0
      };

      return {
        success: true,
        message: '노드 정보를 조회했습니다.',
        data: nodeInfo,
        executionTime: 0,
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'node');
    }
  }

  private async analyzeWorkPatterns(): Promise<CommandResult> {
    try {
      // 간단한 작업 패턴 분석 (실제로는 예측 엔진에서 분석해야 함)
      const analysis = {
        patterns: [
          { type: 'search', frequency: 0.4, trend: 'increasing' },
          { type: 'tagging', frequency: 0.3, trend: 'stable' },
          { type: 'sync', frequency: 0.2, trend: 'decreasing' },
          { type: 'analysis', frequency: 0.1, trend: 'stable' }
        ],
        recommendations: [
          '검색 패턴을 더 효율적으로 만들기',
          '자동 태깅 정확도 향상',
          '동기화 성능 최적화'
        ]
      };

      return {
        success: true,
        message: '📊 작업 패턴 분석 결과',
        data: analysis,
        executionTime: 0,
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'patterns');
    }
  }

  private async isTextFile(fileName: string): Promise<boolean> {
    const textExtensions = ['.md', '.txt', '.json', '.js', '.ts', '.py', '.yaml', '.yml'];
    const path = await import('path');
    const ext = path.extname(fileName).toLowerCase();
    return textExtensions.includes(ext);
  }

  private extractTags(content: string): string[] {
    // 간단한 태그 추출 로직
    const words = content.toLowerCase().match(/\b\w+\b/g) || [];
    const commonWords = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'];
    
    const tagCounts = new Map<string, number>();
    words.forEach(word => {
      if (word.length > 3 && !commonWords.includes(word)) {
        tagCounts.set(word, (tagCounts.get(word) || 0) + 1);
      }
    });
    
    return Array.from(tagCounts.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10)
      .map(([word]) => word);
  }

  private generateSnippet(content: FileContent, query: string): string {
    const text = content.content.toLowerCase();
    const queryLower = query.toLowerCase();
    
    const index = text.indexOf(queryLower);
    if (index === -1) {
      return content.content.substring(0, 100) + '...';
    }
    
    const start = Math.max(0, index - 50);
    const end = Math.min(content.content.length, index + query.length + 50);
    
    return '...' + content.content.substring(start, end) + '...';
  }

  private recordSearchInteraction(query: string, results: any[]): void {
    // 검색 상호작용 기록 (향후 학습 개선용)
    const quality: any = {
      satisfaction: results.length > 0 ? 0.7 : 0.3,
      timeSpent: 0,
      contextRelevance: 0.6,
      surpriseFactor: 0.1
    };
    
    // 실제 구현에서는 더 정교한 상호작용 품질 측정
  }

  private getTimeOfDay(): 'morning' | 'afternoon' | 'evening' | 'night' {
    const hour = new Date().getHours();
    if (hour < 6) return 'night';
    if (hour < 12) return 'morning';
    if (hour < 18) return 'afternoon';
    return 'evening';
  }

  private formatUptime(): string {
    const startTime = Date.now() - (process.uptime() * 1000);
    const uptime = Date.now() - startTime;
    const minutes = Math.floor(uptime / 60000);
    return `${minutes}분`;
  }

  private generateSessionId(): string {
    return `session_${Date.now()}`;
  }

  private shutdown(): void {
    console.log('🔄 시스템 종료 중...');
    this.isRunning = false;
    process.exit(0);
  }

  private clearScreen(): CommandResult {
    console.clear();
    return { 
      success: true, 
      message: '화면을 지웠습니다.', 
      executionTime: 0,
      timestamp: new Date()
    };
  }

  private exit(): CommandResult {
    return { 
      success: true, 
      message: '종료 중...', 
      executionTime: 0,
      timestamp: new Date()
    };
  }

  private handleError(error: Error, command: string): CommandResult {
    console.error(`명령어 실행 중 오류 발생: ${error.message}`);
    return {
      success: false,
      message: `명령어 실행 실패: ${error.message}`,
      executionTime: 0,
      suggestions: ['명령어 구문을 확인하세요', '도움말을 참조하세요'],
      timestamp: new Date()
    };
  }

  private handleInvalidCommand(command: string): CommandResult {
    return {
      success: false,
      message: `알 수 없는 명령어: ${command}`,
      executionTime: 0,
      timestamp: new Date()
    };
  }

  private async handleSearch(query: string): Promise<CommandResult> {
    try {
      const startTime = Date.now();
      const results = await this.searchEngine.search({
        query,
        filters: { maxResults: 10 }
      });
      const executionTime = Date.now() - startTime;

      if (results.results.length === 0) {
        return {
          success: false,
          message: '검색 결과가 없습니다.',
          executionTime,
          suggestions: ['다른 키워드로 검색해보세요', '검색 범위를 넓혀보세요'],
          timestamp: new Date()
        };
      }

      return {
        success: true,
        message: `${results.results.length}개의 결과를 찾았습니다.`,
        data: results.results,
        executionTime,
        suggestions: ['더 구체적인 검색어를 사용하세요', '필터를 적용해보세요'],
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'search');
    }
  }

  private async handleSemanticSearch(query: string): Promise<CommandResult> {
    try {
      const startTime = Date.now();
      const results = await this.searchEngine.search({
        query,
        filters: { maxResults: 10 }
      });
      const executionTime = Date.now() - startTime;

      if (results.results.length === 0) {
        return {
          success: false,
          message: '시맨틱 검색 결과가 없습니다.',
          executionTime,
          timestamp: new Date()
        };
      }

      return {
        success: true,
        message: `${results.results.length}개의 시맨틱 검색 결과를 찾았습니다.`,
        data: results.results,
        executionTime,
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'semantic');
    }
  }

  private async handleTagFile(filePath: string): Promise<CommandResult> {
    try {
      const startTime = Date.now();
      const result = await this.taggingService.tagFile(filePath);
      const executionTime = Date.now() - startTime;

      return {
        success: true,
        message: '파일 태깅이 완료되었습니다.',
        data: {
          contentType: result.contentType,
          tags: result.tags,
          categories: result.categories,
          confidence: result.confidence.toString()
        },
        executionTime,
        suggestions: ['태그를 수정하려면 edit 명령어를 사용하세요'],
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'tag');
    }
  }

  private async handleAnalyzeFile(filePath: string): Promise<CommandResult> {
    try {
      const startTime = Date.now();
      const analysis = await this.taggingService.tagFile(filePath);
      const executionTime = Date.now() - startTime;

      return {
        success: true,
        message: '파일 분석이 완료되었습니다.',
        data: analysis,
        executionTime,
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'analyze');
    }
  }

  private async handleSyncStatus(): Promise<CommandResult> {
    try {
      const startTime = Date.now();
      const status = await this.syncService.getSyncState();
      const executionTime = Date.now() - startTime;

      return {
        success: true,
        message: '동기화 상태를 확인했습니다.',
        data: status,
        executionTime,
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'sync');
    }
  }

  private async handleInsights(): Promise<CommandResult> {
    try {
      const startTime = Date.now();
      const insights = await this.taggingService.getTagAnalytics();
      const executionTime = Date.now() - startTime;

      return {
        success: true,
        message: '태깅 인사이트를 생성했습니다.',
        data: insights,
        executionTime,
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'insights');
    }
  }

  private async handleStatus(): Promise<CommandResult> {
    try {
      const startTime = Date.now();
      const status = await this.layer1Service.getStatus(); // Assuming getSystemStatus is part of ArgoLayer1Service
      const executionTime = Date.now() - startTime;

      return {
        success: true,
        message: '시스템 상태를 확인했습니다.',
        data: status,
        executionTime,
        timestamp: new Date()
      };
    } catch (error) {
      return this.handleError(error as Error, 'status');
    }
  }
}

// CLI 실행 - Phase 1 통합 설정
// ES 모듈에서는 import.meta.url을 사용하여 메인 모듈 확인
const isMainModule = import.meta.url === `file://${process.argv[1]}`;

if (isMainModule) {
  const config: Layer1Config = {
    enableWebInterface: true,
    enableRealtimeSync: true,
    webPort: 3000,
    openaiApiKey: process.env.OPENAI_API_KEY
  };
  
  const cli = new ArgoCliInterface(config);
  cli.start().catch(error => {
    console.error('ARGO Layer 1 Phase 1 시작 실패:', error);
    process.exit(1);
  });
}