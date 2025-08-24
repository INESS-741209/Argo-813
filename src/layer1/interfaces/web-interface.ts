/**
 * ARGO Layer 1 Phase 1: 기본 웹 인터페이스
 * 블루프린트: "CLI를 넘어선 시각적 지식 탐색 인터페이스"
 * 목표: Phase 1 모든 기능의 웹 기반 접근점
 */

import express from 'express';
import cors from 'cors';
import multer from 'multer';
import * as fs from 'fs/promises';
import * as path from 'path';

import { EmbeddingService } from '../services/embedding-service.js';
import { GoogleDriveService } from '../services/google-drive-service.js';
import { RealtimeSyncService } from '../services/realtime-sync-service.js';
import { AutoTaggingService } from '../services/auto-tagging-service.js';
import { SemanticSearchEngine } from '../services/semantic-search.js';

interface WebInterfaceConfig {
  port: number;
  host: string;
  staticDir: string;
  uploadDir: string;
  enableCors: boolean;
  enableFileUpload: boolean;
}

interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
}

/**
 * ARGO Layer 1 Web Interface
 * Phase 1 핵심: 모든 서비스의 통합 웹 접근점
 */
class WebInterface {
  private app: express.Application;
  private config: WebInterfaceConfig;
  private embeddingService: EmbeddingService;
  private driveService: GoogleDriveService;
  private syncService: RealtimeSyncService;
  private taggingService: AutoTaggingService;
  private searchEngine: SemanticSearchEngine;
  private upload!: multer.Multer;

  constructor(
    embeddingService: EmbeddingService,
    driveService: GoogleDriveService,
    syncService: RealtimeSyncService,
    taggingService: AutoTaggingService,
    searchEngine: SemanticSearchEngine,
    config?: Partial<WebInterfaceConfig>
  ) {
    this.embeddingService = embeddingService;
    this.driveService = driveService;
    this.syncService = syncService;
    this.taggingService = taggingService;
    this.searchEngine = searchEngine;

    this.config = {
      port: 3000,
      host: 'localhost',
      staticDir: 'C:\\Argo-813\\web\\static',
      uploadDir: 'C:\\Argo-813\\web\\uploads',
      enableCors: true,
      enableFileUpload: true,
      ...config
    };

    this.app = express();
    this.setupUpload();
    this.setupMiddleware();
    this.setupRoutes();
    this.setupStaticFiles();
    this.setupErrorHandling();
  }

  /**
   * 웹 서버 시작
   */
  async start(): Promise<void> {
    try {
      // 필요한 디렉토리 생성
      await this.ensureDirectories();

      // HTML 파일이 없으면 생성
      await this.generateDefaultHTML();

      this.app.listen(this.config.port, this.config.host, () => {
        console.log(`🌐 ARGO Layer 1 웹 인터페이스 시작됨: http://${this.config.host}:${this.config.port}`);
        console.log(`📁 정적 파일: ${this.config.staticDir}`);
        console.log(`📤 업로드 디렉토리: ${this.config.uploadDir}`);
      });

    } catch (error) {
      console.error('❌ 웹 서버 시작 실패:', error);
      throw error;
    }
  }

  /**
   * 웹 서버 중지
   */
  async stop(): Promise<void> {
    console.log('⏹️  웹 서버 중지 중...');
    // Express 서버 중지 로직 (실제 구현에서는 server.close() 사용)
    console.log('✅ 웹 서버 중지됨');
  }

  // ======= Private Setup Methods =======

  private setupUpload(): void {
    if (this.config.enableFileUpload) {
      this.upload = multer({
        dest: this.config.uploadDir,
        limits: {
          fileSize: 10 * 1024 * 1024, // 10MB
          files: 5
        },
        fileFilter: (req, file, cb) => {
          // 허용된 파일 형식만
          const allowedTypes = /\.(md|txt|json|js|ts|py|yaml|yml|doc|docx)$/i;
          if (allowedTypes.test(file.originalname)) {
            cb(null, true);
          } else {
            cb(new Error('지원하지 않는 파일 형식입니다'));
          }
        }
      });
    }
  }

  private setupMiddleware(): void {
    // CORS
    if (this.config.enableCors) {
      this.app.use(cors({
        origin: [`http://${this.config.host}:${this.config.port}`, 'http://localhost:*'],
        methods: ['GET', 'POST', 'PUT', 'DELETE'],
        allowedHeaders: ['Content-Type', 'Authorization']
      }));
    }

    // JSON 파싱
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true }));

    // 요청 로깅
    this.app.use((req, res, next) => {
      console.log(`🌐 ${req.method} ${req.path} - ${new Date().toISOString()}`);
      next();
    });
  }

  private setupRoutes(): void {
    const router = express.Router();

    // ======= Search API =======
    
    // 통합 검색
    router.get('/api/search', async (req, res) => {
      try {
        const { q: query, type, limit = 20, source } = req.query;

        if (!query || typeof query !== 'string') {
          return this.sendError(res, 'query 매개변수가 필요합니다', 400);
        }

        let results;

        switch (source) {
          case 'drive':
            results = await this.driveService.searchFiles({
              query,
              maxResults: parseInt(limit as string)
            });
            break;
          
          case 'local':
            results = await this.searchEngine.search({
              query,
              filters: { maxResults: parseInt(limit as string) }
            });
            break;
          
          default:
            // 하이브리드 검색 (기본)
            results = await this.driveService.hybridSearch(query, {
              includeLocal: true,
              includeDrive: true,
              maxResults: parseInt(limit as string)
            });
        }

        this.sendSuccess(res, results);

      } catch (error) {
        console.error('검색 API 오류:', error);
        this.sendError(res, '검색 중 오류가 발생했습니다');
      }
    });

    // 시맨틱 검색
    router.get('/api/search/semantic', async (req, res) => {
      try {
        const { query, mode = 'semantic', maxResults = 10 } = req.query;

        if (!query || typeof query !== 'string') {
          return this.sendError(res, 'query 매개변수가 필요합니다', 400);
        }

        const results = await this.searchEngine.search({
          query,
          filters: { maxResults: parseInt(maxResults as string) }
        });

        this.sendSuccess(res, results);

      } catch (error) {
        console.error('시맨틱 검색 오류:', error);
        this.sendError(res, '시맨틱 검색 중 오류가 발생했습니다');
      }
    });

    // ======= Tagging API =======
    
    // 파일 태깅
    router.post('/api/tags/file', async (req, res) => {
      try {
        const { filePath, content } = req.body;

        if (!filePath) {
          return this.sendError(res, 'filePath가 필요합니다', 400);
        }

        const result = await this.taggingService.tagFile(filePath, content);
        this.sendSuccess(res, result);

      } catch (error) {
        console.error('파일 태깅 오류:', error);
        this.sendError(res, '파일 태깅 중 오류가 발생했습니다');
      }
    });

    // 태그 기반 검색
    router.get('/api/search/tags', async (req, res) => {
      try {
        const { tags, matchAll = false, minConfidence = 0.5 } = req.query;

        if (!tags) {
          return this.sendError(res, 'tags 매개변수가 필요합니다', 400);
        }

        const tagArray = Array.isArray(tags) ? tags : [tags];
        const results = await this.taggingService.searchByTags(tagArray as string[], {
          matchAll: matchAll === 'true',
          minConfidence: parseFloat(minConfidence as string)
        });

        this.sendSuccess(res, results);

      } catch (error) {
        console.error('태그 검색 오류:', error);
        this.sendError(res, '태그 검색 중 오류가 발생했습니다');
      }
    });

    // 태그 추천
    router.post('/api/tags/suggest', async (req, res) => {
      try {
        const { filePath, content } = req.body;

        if (!filePath && !content) {
          return this.sendError(res, 'filePath 또는 content가 필요합니다', 400);
        }

        const suggestions = await this.taggingService.suggestTags(filePath, content);
        this.sendSuccess(res, suggestions);

      } catch (error) {
        console.error('태그 추천 오류:', error);
        this.sendError(res, '태그 추천 중 오류가 발생했습니다');
      }
    });

    // 태깅 통계
    router.get('/api/tags/analytics', async (req, res) => {
      try {
        const analytics = this.taggingService.getTagAnalytics();
        this.sendSuccess(res, analytics);
      } catch (error) {
        console.error('태깅 통계 오류:', error);
        this.sendError(res, '태깅 통계 조회 중 오류가 발생했습니다');
      }
    });

    // ======= Sync API =======
    
    // 동기화 상태 조회
    router.get('/api/sync/status', async (req, res) => {
      try {
        const state = this.syncService.getSyncState();
        const stats = this.syncService.getSyncStats();
        
        this.sendSuccess(res, { state, stats });
      } catch (error) {
        console.error('동기화 상태 조회 오류:', error);
        this.sendError(res, '동기화 상태 조회 중 오류가 발생했습니다');
      }
    });

    // 수동 동기화 실행
    router.post('/api/sync/trigger', async (req, res) => {
      try {
        const result = await this.syncService.triggerSync();
        this.sendSuccess(res, result);
      } catch (error) {
        console.error('수동 동기화 오류:', error);
        this.sendError(res, '수동 동기화 중 오류가 발생했습니다');
      }
    });

    // 충돌 해결
    router.post('/api/sync/resolve-conflict', async (req, res) => {
      try {
        const { conflictId, resolution } = req.body;

        if (!conflictId || !resolution) {
          return this.sendError(res, 'conflictId와 resolution이 필요합니다', 400);
        }

        const success = await this.syncService.resolveConflict(conflictId, resolution);
        this.sendSuccess(res, { resolved: success });

      } catch (error) {
        console.error('충돌 해결 오류:', error);
        this.sendError(res, '충돌 해결 중 오류가 발생했습니다');
      }
    });

    // ======= File Upload API =======
    
    if (this.config.enableFileUpload) {
      router.post('/api/files/upload', this.upload.array('files', 5), async (req, res) => {
        try {
          const files = req.files as Express.Multer.File[];
          
          if (!files || files.length === 0) {
            return this.sendError(res, '업로드할 파일이 없습니다', 400);
          }

          const results = [];

          for (const file of files) {
            // 파일 내용 읽기
            const content = await fs.readFile(file.path, 'utf-8');
            
            // 자동 태깅
            const taggingResult = await this.taggingService.tagFile(file.originalname, content);
            
            // 임베딩 생성
            const embedding = await this.embeddingService.getEmbedding({ text: content });
            
            results.push({
              filename: file.originalname,
              path: file.path,
              size: file.size,
              tags: taggingResult.tags,
              contentType: taggingResult.contentType,
              confidence: taggingResult.confidence,
              embeddingGenerated: true
            });
          }

          this.sendSuccess(res, results);

        } catch (error) {
          console.error('파일 업로드 오류:', error);
          this.sendError(res, '파일 업로드 중 오류가 발생했습니다');
        }
      });
    }

    // ======= System API =======
    
    // 시스템 상태
    router.get('/api/system/status', async (req, res) => {
      try {
        const embeddingStats = this.embeddingService.getUsageStats();
        const syncState = this.syncService.getSyncState();
        const taggingAnalytics = this.taggingService.getTagAnalytics();

        const systemStatus = {
          status: 'healthy',
          uptime: process.uptime(),
          memory: process.memoryUsage(),
          services: {
            embedding: {
              status: 'active',
              stats: embeddingStats
            },
            sync: {
              status: syncState.status,
              stats: syncState.stats
            },
            tagging: {
              status: 'active',
              totalTags: taggingAnalytics.mostUsedTags.length
            }
          },
          timestamp: new Date().toISOString()
        };

        this.sendSuccess(res, systemStatus);

      } catch (error) {
        console.error('시스템 상태 조회 오류:', error);
        this.sendError(res, '시스템 상태 조회 중 오류가 발생했습니다');
      }
    });

    // 헬스체크
    router.get('/api/health', (req, res) => {
      this.sendSuccess(res, { 
        status: 'healthy', 
        timestamp: new Date().toISOString(),
        version: '1.0.0'
      });
    });

    this.app.use('/', router);
  }

  private setupStaticFiles(): void {
    // 정적 파일 서빙
    this.app.use('/static', express.static(this.config.staticDir));
    
    // 루트 경로에서 index.html 서빙
    this.app.get('/', (req, res) => {
      res.sendFile(path.join(this.config.staticDir, 'index.html'));
    });
  }

  private setupErrorHandling(): void {
    // 404 핸들러
    this.app.use((req, res) => {
      this.sendError(res, '페이지를 찾을 수 없습니다', 404);
    });

    // 전역 에러 핸들러
    this.app.use((error: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
      console.error('웹 인터페이스 오류:', error);
      
      if (!res.headersSent) {
        this.sendError(res, '서버 내부 오류가 발생했습니다', 500);
      }
    });
  }

  // ======= Utility Methods =======

  private sendSuccess<T>(res: express.Response, data: T): void {
    const response: APIResponse<T> = {
      success: true,
      data,
      timestamp: new Date().toISOString()
    };
    res.json(response);
  }

  private sendError(res: express.Response, message: string, statusCode: number = 500): void {
    const response: APIResponse = {
      success: false,
      error: message,
      timestamp: new Date().toISOString()
    };
    res.status(statusCode).json(response);
  }

  private async ensureDirectories(): Promise<void> {
    await fs.mkdir(this.config.staticDir, { recursive: true });
    if (this.config.enableFileUpload) {
      await fs.mkdir(this.config.uploadDir, { recursive: true });
    }
  }

  private async generateDefaultHTML(): Promise<void> {
    const indexPath = path.join(this.config.staticDir, 'index.html');
    
    try {
      await fs.access(indexPath);
      console.log('기존 index.html 파일 사용');
      return;
    } catch {
      // 파일이 없으면 생성
    }

    const htmlContent = `
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ARGO Layer 1 - Neuromorphic Knowledge Mesh</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .header {
            text-align: center;
            margin-bottom: 3rem;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(45deg, #fff, #64b5f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
            margin-bottom: 2rem;
        }
        
        .search-section {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 2rem;
            margin-bottom: 2rem;
        }
        
        .search-input {
            width: 100%;
            padding: 1rem 1.5rem;
            font-size: 1.1rem;
            border: none;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.9);
            color: #333;
            margin-bottom: 1rem;
        }
        
        .search-buttons {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95rem;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            text-align: center;
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #42a5f5, #1976d2);
            color: white;
        }
        
        .btn-secondary {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        
        .results-section {
            background: rgba(255, 255, 255, 0.95);
            color: #333;
            border-radius: 15px;
            padding: 2rem;
            min-height: 200px;
            display: none;
        }
        
        .results-section.show {
            display: block;
        }
        
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }
        
        .feature-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 1.5rem;
            transition: transform 0.3s ease;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
        }
        
        .feature-icon {
            font-size: 2rem;
            margin-bottom: 1rem;
        }
        
        .status-bar {
            background: rgba(0,0,0,0.2);
            padding: 1rem;
            border-radius: 10px;
            margin-top: 2rem;
            font-family: monospace;
        }
        
        .loading {
            display: inline-block;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 ARGO Layer 1</h1>
            <p class="subtitle">Neuromorphic Knowledge Mesh</p>
            <p>구슬을 꿰는 직관적 연결 시스템</p>
        </div>
        
        <div class="search-section">
            <h2>🔍 통합 검색</h2>
            <input type="text" id="searchInput" class="search-input" placeholder="검색어를 입력하세요 (예: ARGO architecture, Layer 1 design)">
            
            <div class="search-buttons">
                <button class="btn btn-primary" onclick="search('hybrid')">🔍 하이브리드 검색</button>
                <button class="btn btn-secondary" onclick="search('semantic')">🧠 시맨틱 검색</button>
                <button class="btn btn-secondary" onclick="search('drive')">☁️ Drive 검색</button>
                <button class="btn btn-secondary" onclick="search('local')">💻 로컬 검색</button>
            </div>
        </div>
        
        <div id="resultsSection" class="results-section">
            <div id="resultsContent">
                검색 결과가 여기에 표시됩니다...
            </div>
        </div>
        
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon">🏷️</div>
                <h3>스마트 태깅</h3>
                <p>AI 기반 자동 태깅으로 파일을 지능적으로 분류합니다.</p>
                <button class="btn btn-primary" onclick="showTagAnalytics()">태그 분석 보기</button>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">🔄</div>
                <h3>실시간 동기화</h3>
                <p>로컬과 클라우드 파일을 완벽하게 동기화합니다.</p>
                <button class="btn btn-primary" onclick="showSyncStatus()">동기화 상태</button>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <h3>시스템 상태</h3>
                <p>전체 시스템의 상태와 성능을 모니터링합니다.</p>
                <button class="btn btn-primary" onclick="showSystemStatus()">시스템 상태</button>
            </div>
        </div>
        
        <div id="statusBar" class="status-bar">
            <div id="statusText">✅ 시스템 준비 완료</div>
        </div>
    </div>

    <script>
        let currentRequest = null;
        
        // 검색 함수
        async function search(type) {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) {
                alert('검색어를 입력하세요');
                return;
            }
            
            setStatus('🔍 검색 중...', true);
            showResults('');
            
            try {
                let url;
                switch (type) {
                    case 'semantic':
                        url = '/api/search/semantic?query=' + encodeURIComponent(query);
                        break;
                    case 'drive':
                        url = '/api/search?q=' + encodeURIComponent(query) + '&source=drive';
                        break;
                    case 'local':
                        url = '/api/search?q=' + encodeURIComponent(query) + '&source=local';
                        break;
                    default:
                        url = '/api/search?q=' + encodeURIComponent(query);
                }
                
                if (currentRequest) {
                    currentRequest.abort();
                }
                
                currentRequest = new AbortController();
                const response = await fetch(url, { signal: currentRequest.signal });
                const data = await response.json();
                
                if (data.success) {
                    displaySearchResults(data.data, type);
                    setStatus(\`✅ \${data.data.length}개 결과 찾음\`);
                } else {
                    showResults('❌ 오류: ' + data.error);
                    setStatus('❌ 검색 실패');
                }
            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.error('검색 오류:', error);
                    showResults('❌ 검색 중 오류가 발생했습니다: ' + error.message);
                    setStatus('❌ 검색 오류');
                }
            } finally {
                currentRequest = null;
            }
        }
        
        // 검색 결과 표시
        function displaySearchResults(results, type) {
            if (!results || results.length === 0) {
                showResults('📭 검색 결과가 없습니다.');
                return;
            }
            
            let html = \`<h3>🔍 \${type.toUpperCase()} 검색 결과 (\${results.length}개)</h3><div style="margin-top: 1rem;">\`;
            
            results.forEach((result, index) => {
                const title = result.name || result.title || result.filePath || '제목 없음';
                const preview = (result.content || '').substring(0, 150) + '...';
                const source = result.source || 'unknown';
                const similarity = result.similarity ? (result.similarity * 100).toFixed(1) + '%' : '';
                
                html += \`
                    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; background: #f9f9f9;">
                        <h4 style="color: #1976d2; margin-bottom: 0.5rem;">\${index + 1}. \${title}</h4>
                        \${similarity ? \`<div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">유사도: \${similarity}</div>\` : ''}
                        \${preview ? \`<p style="color: #666; margin-bottom: 0.5rem;">\${preview}</p>\` : ''}
                        <div style="font-size: 0.8rem; color: #999;">
                            소스: \${source} | 
                            \${result.modifiedTime ? '수정일: ' + new Date(result.modifiedTime).toLocaleDateString() : ''}
                            \${result.webViewLink ? \`| <a href="\${result.webViewLink}" target="_blank">열기</a>\` : ''}
                        </div>
                    </div>
                \`;
            });
            
            html += '</div>';
            showResults(html);
        }
        
        // 결과 표시
        function showResults(content) {
            const resultsSection = document.getElementById('resultsSection');
            const resultsContent = document.getElementById('resultsContent');
            
            resultsContent.innerHTML = content;
            resultsSection.classList.add('show');
        }
        
        // 상태 표시
        function setStatus(text, loading = false) {
            const statusText = document.getElementById('statusText');
            statusText.innerHTML = loading ? \`<span class="loading">⏳</span> \${text}\` : text;
        }
        
        // 태그 분석 표시
        async function showTagAnalytics() {
            setStatus('📊 태그 분석 불러오는 중...', true);
            
            try {
                const response = await fetch('/api/tags/analytics');
                const data = await response.json();
                
                if (data.success) {
                    const analytics = data.data;
                    let html = '<h3>🏷️ 태그 분석</h3>';
                    
                    html += '<h4>인기 태그 TOP 10</h4><ul>';
                    analytics.mostUsedTags.slice(0, 10).forEach(tag => {
                        html += \`<li>\${tag.tag} (\${tag.count}회, \${tag.trend})</li>\`;
                    });
                    html += '</ul>';
                    
                    html += '<h4>카테고리 분포</h4><ul>';
                    Object.entries(analytics.categoryDistribution).forEach(([category, count]) => {
                        html += \`<li>\${category}: \${count}개</li>\`;
                    });
                    html += '</ul>';
                    
                    showResults(html);
                    setStatus('✅ 태그 분석 완료');
                } else {
                    showResults('❌ 태그 분석 실패: ' + data.error);
                    setStatus('❌ 분석 실패');
                }
            } catch (error) {
                console.error('태그 분석 오류:', error);
                showResults('❌ 태그 분석 중 오류 발생');
                setStatus('❌ 분석 오류');
            }
        }
        
        // 동기화 상태 표시
        async function showSyncStatus() {
            setStatus('🔄 동기화 상태 확인 중...', true);
            
            try {
                const response = await fetch('/api/sync/status');
                const data = await response.json();
                
                if (data.success) {
                    const { state, stats } = data.data;
                    
                    let html = '<h3>🔄 동기화 상태</h3>';
                    html += \`<p><strong>상태:</strong> \${state.status}</p>\`;
                    html += \`<p><strong>마지막 동기화:</strong> \${new Date(state.lastSync).toLocaleString()}</p>\`;
                    html += \`<p><strong>동기화된 파일:</strong> \${state.stats.syncedFiles}개</p>\`;
                    html += \`<p><strong>대기 중인 파일:</strong> \${state.stats.pendingFiles}개</p>\`;
                    html += \`<p><strong>오류 파일:</strong> \${state.stats.errorFiles}개</p>\`;
                    
                    if (state.conflicts.length > 0) {
                        html += \`<h4>⚠️ 충돌 (\${state.conflicts.length}개)</h4><ul>\`;
                        state.conflicts.forEach(conflict => {
                            html += \`<li>\${conflict.filePath} - \${conflict.conflictType}</li>\`;
                        });
                        html += '</ul>';
                    }
                    
                    html += '<button class="btn btn-primary" onclick="triggerSync()">🔄 수동 동기화 실행</button>';
                    
                    showResults(html);
                    setStatus('✅ 동기화 상태 조회 완료');
                } else {
                    showResults('❌ 동기화 상태 조회 실패: ' + data.error);
                    setStatus('❌ 상태 조회 실패');
                }
            } catch (error) {
                console.error('동기화 상태 오류:', error);
                showResults('❌ 동기화 상태 조회 중 오류 발생');
                setStatus('❌ 상태 조회 오류');
            }
        }
        
        // 수동 동기화 실행
        async function triggerSync() {
            setStatus('🔄 동기화 실행 중...', true);
            
            try {
                const response = await fetch('/api/sync/trigger', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    const result = data.data;
                    showResults(\`
                        <h3>✅ 동기화 완료</h3>
                        <p>동기화된 파일: \${result.synced}개</p>
                        <p>충돌: \${result.conflicts}개</p>
                        <p>오류: \${result.errors}개</p>
                    \`);
                    setStatus('✅ 동기화 완료');
                } else {
                    showResults('❌ 동기화 실패: ' + data.error);
                    setStatus('❌ 동기화 실패');
                }
            } catch (error) {
                console.error('동기화 실행 오류:', error);
                showResults('❌ 동기화 실행 중 오류 발생');
                setStatus('❌ 동기화 오류');
            }
        }
        
        // 시스템 상태 표시
        async function showSystemStatus() {
            setStatus('📊 시스템 상태 확인 중...', true);
            
            try {
                const response = await fetch('/api/system/status');
                const data = await response.json();
                
                if (data.success) {
                    const status = data.data;
                    
                    let html = '<h3>📊 시스템 상태</h3>';
                    html += \`<p><strong>상태:</strong> \${status.status}</p>\`;
                    html += \`<p><strong>가동 시간:</strong> \${Math.floor(status.uptime / 3600)}시간 \${Math.floor((status.uptime % 3600) / 60)}분</p>\`;
                    html += \`<p><strong>메모리 사용량:</strong> \${Math.floor(status.memory.used / 1024 / 1024)}MB</p>\`;
                    
                    html += '<h4>서비스 상태</h4><ul>';
                    Object.entries(status.services).forEach(([service, info]) => {
                        html += \`<li><strong>\${service}:</strong> \${info.status}\`;
                        if (info.stats) {
                            html += \` (통계: \${JSON.stringify(info.stats)})\`;
                        }
                        html += '</li>';
                    });
                    html += '</ul>';
                    
                    showResults(html);
                    setStatus('✅ 시스템 상태 조회 완료');
                } else {
                    showResults('❌ 시스템 상태 조회 실패: ' + data.error);
                    setStatus('❌ 상태 조회 실패');
                }
            } catch (error) {
                console.error('시스템 상태 오류:', error);
                showResults('❌ 시스템 상태 조회 중 오류 발생');
                setStatus('❌ 상태 조회 오류');
            }
        }
        
        // 엔터 키 검색
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                search('hybrid');
            }
        });
        
        // 초기 시스템 상태 확인
        window.onload = async function() {
            try {
                const response = await fetch('/api/health');
                const data = await response.json();
                if (data.success) {
                    setStatus('✅ 시스템 준비 완료 - ' + data.data.timestamp);
                } else {
                    setStatus('⚠️ 시스템 상태 확인 필요');
                }
            } catch (error) {
                setStatus('❌ 시스템 연결 오류');
            }
        };
    </script>
</body>
</html>
    `.trim();

    await fs.writeFile(indexPath, htmlContent);
    console.log('✅ 기본 index.html 파일 생성됨');
  }
}

export {
  WebInterface,
  WebInterfaceConfig,
  APIResponse
};