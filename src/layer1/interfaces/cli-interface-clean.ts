/**
 * ARGO Layer 1: CLI Interface - Clean Version
 * 블루프린트 목표: "타입 안전하고 깔끔한 Phase 1 CLI"
 * 목표: 모든 타입 에러 해결 및 사용하지 않는 코드 제거
 */

import * as readline from 'readline';
import { ArgoLayer1Service } from '../argo-layer1-service.js';
import { 
  CommandResult, 
  SearchResult, 
  Layer1Config
} from '../types/common.js';

/**
 * Clean CLI Interface for ARGO Layer 1 Phase 1
 * 모든 타입 에러 해결 및 핵심 기능만 유지
 */
class ArgoCliInterface {
  private rl: readline.Interface;
  private layer1Service: ArgoLayer1Service;
  private isRunning: boolean;
  private currentSession: string;
  private commandHistory: string[];
  
  constructor(config?: Layer1Config) {
    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      prompt: '🧠 ARGO Layer-1 Phase-1 > '
    });
    
    this.layer1Service = new ArgoLayer1Service(config);
    this.isRunning = false;
    this.currentSession = this.generateSessionId();
    this.commandHistory = [];
    
    this.setupEventHandlers();
    this.setupServiceEvents();
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
      console.log(`⚠️ 동기화 충돌 감지: ${conflict.filePath}`);
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
          return await this.showStatus();
          
        case 'insights':
          return await this.showInsights();
          
        case 'clear':
          console.clear();
          return { 
            success: true, 
            message: '화면을 지웠습니다.', 
            executionTime: 0, 
            timestamp: new Date() 
          };
          
        case 'exit':
        case 'quit':
          await this.shutdown();
          return { 
            success: true, 
            message: '종료 중...', 
            executionTime: 0, 
            timestamp: new Date() 
          };
          
        default:
          return {
            success: false,
            message: `알 수 없는 명령어: ${command}. 도움말은 'help'를 입력하세요.`,
            executionTime: 0,
            timestamp: new Date(),
            suggestions: ['help', 'find <query>', 'semantic <query>', 'tag <filepath>', 'sync status']
          };
      }
    } catch (error) {
      return {
        success: false,
        message: `명령어 실행 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
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
        timestamp: new Date(),
        suggestions: ['semantic <query>', 'find <query>', 'analyze <filepath>']
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
        timestamp: new Date(),
        suggestions: [
          'semantic ' + query,
          'analyze ' + (results[0]?.name || results[0]?.path || ''),
          'tag ' + (results[0]?.name || results[0]?.path || '')
        ]
      };
      
    } catch (error) {
      return {
        success: false,
        message: `검색 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
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
      return {
        success: false,
        message: `시맨틱 검색 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
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
        timestamp: new Date(),
        suggestions: [
          'analyze ' + filePath,
          'semantic "' + result.tags.slice(0, 2).map(t => t.name).join(' ') + '"'
        ]
      };
      
    } catch (error) {
      return {
        success: false,
        message: `파일 태깅 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
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
          timestamp: new Date(),
          suggestions: ['sync trigger', 'sync conflicts']
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
        
      } else {
        return {
          success: false,
          message: '잘못된 동기화 명령어입니다.',
          executionTime: 0,
          timestamp: new Date(),
          suggestions: ['sync status', 'sync trigger']
        };
      }
      
    } catch (error) {
      return {
        success: false,
        message: `동기화 작업 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
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
        timestamp: new Date(),
        suggestions: [
          'semantic "' + result.tagging.tags.slice(0, 2).map((t: any) => t.name).join(' ') + '"',
          'tag ' + filePath
        ]
      };
      
    } catch (error) {
      return {
        success: false,
        message: `파일 분석 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
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
        timestamp: new Date(),
        suggestions: ['sync status', 'insights', 'help']
      };
      
    } catch (error) {
      return {
        success: false,
        message: `상태 조회 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
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
        message: '🔮 태깅 시스템 분석 인사이트',
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
        timestamp: new Date(),
        suggestions: ['status', 'sync status', 'semantic <trending_tag>']
      };
      
    } catch (error) {
      return {
        success: false,
        message: `인사이트 생성 중 오류: ${error}`,
        executionTime: 0,
        timestamp: new Date()
      };
    }
  }

  /**
   * 도움말 표시 - Phase 1 완전한 기능 가이드
   */
  private showHelp(): CommandResult {
    const helpText = `
🧠 ARGO Layer 1 Phase 1 - Neuromorphic Knowledge Mesh

📌 검색 명령어:
  find <검색어>       - 하이브리드 검색 (로컬 + 클라우드)
  semantic <검색어>   - AI 시맨틱 검색 (OpenAI 임베딩)
  
🏷️ 태깅 및 분석:
  tag <파일경로>      - 자동 AI 태깅
  analyze <파일경로>  - 종합 파일 분석 (태깅 + 임베딩)
  insights           - 태깅 통계 및 인사이트
  
🔄 동기화 관리:
  sync status        - 동기화 상태 확인
  sync trigger       - 수동 동기화 실행
  
⚙️ 시스템 관리:
  status            - 시스템 전체 상태 (모든 서비스)
  help              - 이 도움말 보기
  clear             - 화면 지우기
  exit              - 종료

🎯 Phase 1 핵심 기능:
  • 🧠 OpenAI 기반 시맨틱 검색
  • 🏷️ AI 자동 태깅 및 분류 시스템
  • ☁️ Google Drive 통합 검색
  • 🔄 실시간 파일 동기화 (CRDT)
  • 🌐 웹 인터페이스 (http://localhost:3000)
  • 📊 종합적인 시스템 분석

💡 사용 예시:
  semantic "ARGO Layer 1 architecture design"
  tag C:\\Argo-813\\README.md
  analyze C:\\Argo-813\\ARGO_needs.md
  sync trigger
`;
    
    return {
      success: true,
      message: helpText,
      executionTime: 0,
      timestamp: new Date()
    };
  }

  /**
   * 결과 표시 - 깔끔한 출력
   */
  private displayResult(result: CommandResult, executionTime: number): void {
    if (result.success) {
      console.log(`✅ ${result.message}`);
      
      if (result.data) {
        if (Array.isArray(result.data)) {
          // 검색 결과 등 배열 데이터
          result.data.forEach((item: any, index: number) => {
            if (item.path || item.name) {
              console.log(`\n${index + 1}. ${item.name || item.path}`);
              if (item.relevanceScore || item.similarity) {
                console.log(`   관련성: ${((item.relevanceScore || item.similarity) * 100).toFixed(1)}%`);
              }
              if (item.source) {
                console.log(`   소스: ${item.source}`);
              }
            }
          });
        } else {
          // 객체 데이터 - 중요한 정보만 표시
          if (result.data.tags) {
            console.log(`\n📊 분석 결과:`);
            console.log(`   태그: ${result.data.tags.map((t: any) => t.name || t).join(', ')}`);
            if (result.data.contentType) {
              console.log(`   유형: ${result.data.contentType}`);
            }
            if (result.data.confidence) {
              console.log(`   신뢰도: ${result.data.confidence}`);
            }
          } else if (result.data.systemStatus) {
            console.log(`\n📊 시스템 상태:`);
            console.log(`   상태: ${result.data.systemStatus}`);
            console.log(`   메모리: ${result.data.memoryUsage}`);
            console.log(`   가동시간: ${result.data.uptime}`);
          } else {
            console.log('\n📊 결과:');
            console.log(JSON.stringify(result.data, null, 2));
          }
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
    
    console.log(`⏱️ 실행 시간: ${executionTime}ms`);
  }

  // ======= Utility Methods =======

  private generateSessionId(): string {
    return `session_${Date.now()}`;
  }

  private formatUptime(): string {
    const uptime = process.uptime() * 1000;
    const minutes = Math.floor(uptime / 60000);
    return `${minutes}분`;
  }

  private async shutdown(): Promise<void> {
    this.isRunning = false;
    
    console.log('🎯 Phase 1 세션 통계:');
    console.log(`   명령어 실행: ${this.commandHistory.length}개`);
    
    try {
      const healthCheck = await this.layer1Service.healthCheck();
      console.log(`   임베딩 호출: ${healthCheck.statistics.embedding.apiCalls}회`);
      console.log(`   총 비용: $${healthCheck.statistics.embedding.totalCost}`);
      console.log(`   캐시 적중률: ${(healthCheck.statistics.embedding.cacheHitRate * 100).toFixed(1)}%`);
      
      await this.layer1Service.shutdown();
      
    } catch (error) {
      console.warn('⚠️ 서비스 종료 중 일부 오류:', error);
    }
    
    console.log('');
    console.log('✨ "Phase 1 지능형 연결"이 완성되었습니다...');
    
    this.rl.close();
    process.exit(0);
  }
}

// CLI 실행 - Phase 1 통합 설정
if (require.main === module) {
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

export { ArgoCliInterface };