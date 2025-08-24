/**
 * ARGO Layer 1 전체 시스템 통합 테스트
 * 모든 서비스가 함께 동작하는지 검증
 */

import { ArgoLayer1Service } from '../../src/layer1/argo-layer1-service.js';
import { Layer1Config } from '../../src/layer1/types/common.js';
import * as fs from 'fs/promises';
import * as path from 'path';

describe('ARGO Layer 1 Full System Integration', () => {
  let layer1Service: ArgoLayer1Service;
  const testConfig: Layer1Config = {
    enableWebInterface: false, // 통합 테스트에서는 웹 비활성화
    enableRealtimeSync: false, // 통합 테스트에서는 동기화 비활성화
    openaiApiKey: 'test-api-key',
    dataDir: './test-data'
  };

  beforeAll(async () => {
    // 테스트 데이터 디렉토리 생성
    try {
      await fs.mkdir('./test-data', { recursive: true });
    } catch (error) {
      // 이미 존재할 수 있음
    }
    
    layer1Service = new ArgoLayer1Service(testConfig);
  });

  afterAll(async () => {
    try {
      if (layer1Service) {
        await layer1Service.shutdown();
      }
      
      // 테스트 데이터 정리
      await fs.rmdir('./test-data', { recursive: true });
    } catch (error) {
      console.warn('테스트 정리 중 오류:', error);
    }
  });

  describe('시스템 초기화 테스트', () => {
    test('Layer 1 서비스가 올바르게 초기화되어야 함', async () => {
      await expect(layer1Service.start()).resolves.not.toThrow();
      
      const status = layer1Service.getStatus();
      expect(status.status).toBe('ready');
      expect(status.services.embedding).toBe('ready');
      expect(status.services.tagging).toBe('ready');
      expect(status.services.search).toBe('ready');
    }, 30000);

    test('헬스체크가 정상적으로 작동해야 함', async () => {
      const healthCheck = await layer1Service.healthCheck();
      
      expect(healthCheck.healthy).toBe(true);
      expect(healthCheck.services).toBeDefined();
      expect(healthCheck.performance).toBeDefined();
      expect(healthCheck.statistics).toBeDefined();
    });
  });

  describe('통합 검색 워크플로우 테스트', () => {
    const testFiles = [
      {
        name: 'react-guide.md',
        content: `# React Development Guide
        This guide covers modern React development with TypeScript.
        It includes hooks, components, and state management patterns.`
      },
      {
        name: 'vue-tutorial.md',
        content: `# Vue.js Tutorial
        Learn Vue.js framework for building interactive web applications.
        Covers Vue 3 composition API and reactive programming.`
      },
      {
        name: 'argo-architecture.md',
        content: `# ARGO System Architecture
        The ARGO Layer 1 implements a neuromorphic knowledge mesh.
        It uses AI embeddings for semantic search and auto-tagging.`
      }
    ];

    beforeAll(async () => {
      // 테스트 파일들 생성
      for (const file of testFiles) {
        const filePath = path.join('./test-data', file.name);
        await fs.writeFile(filePath, file.content);
      }
    });

    test('하이브리드 검색이 관련 파일을 찾아야 함', async () => {
      const results = await layer1Service.search('React development', {
        mode: 'hybrid',
        maxResults: 5
      });

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
      
      if (results.length > 0) {
        expect(results.some((r: any) => 
          r.name?.includes('react') || r.path?.includes('react')
        )).toBe(true);
      }
    });

    test('시맨틱 검색이 의미적으로 관련된 파일을 찾아야 함', async () => {
      const results = await layer1Service.search('web framework tutorial', {
        mode: 'semantic',
        maxResults: 3
      });

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('파일 분석 워크플로우 테스트', () => {
    test('파일 분석이 태깅, 임베딩, 동기화 정보를 모두 제공해야 함', async () => {
      const testFilePath = path.join('./test-data', 'analysis-test.md');
      const content = `# Machine Learning Guide
      This document explains machine learning concepts and AI implementation.
      It covers neural networks, deep learning, and practical applications.`;
      
      await fs.writeFile(testFilePath, content);

      const analysisResult = await layer1Service.analyzeFile(testFilePath);

      expect(analysisResult).toBeDefined();
      expect(analysisResult.tagging).toBeDefined();
      expect(analysisResult.tagging.tags).toBeDefined();
      expect(analysisResult.tagging.contentType).toBeDefined();
      expect(analysisResult.tagging.confidence).toBeGreaterThan(0);
      
      // 임베딩 상태 확인
      expect(analysisResult.embedding).toBeDefined();
      
      // 동기화 상태 확인
      expect(typeof analysisResult.synchronized).toBe('boolean');
    });

    test('배치 파일 처리가 성공적으로 동작해야 함', async () => {
      const batchFiles = [
        './test-data/batch1.md',
        './test-data/batch2.md',
        './test-data/batch3.md'
      ];

      // 배치 파일들 생성
      for (let i = 0; i < batchFiles.length; i++) {
        await fs.writeFile(batchFiles[i], `# Batch File ${i + 1}\nTest content for batch processing.`);
      }

      const batchResult = await layer1Service.processBatch(batchFiles);

      expect(batchResult.processed).toBe(3);
      expect(batchResult.results).toHaveLength(3);
      expect(batchResult.results.every(r => r.success)).toBe(true);
    }, 20000);
  });

  describe('태깅 시스템 통합 테스트', () => {
    test('자동 태깅과 검색이 연동되어 작동해야 함', async () => {
      const taggedFilePath = path.join('./test-data', 'tagged-file.md');
      const content = `# Database Design Patterns
      This document covers database design patterns for scalable applications.
      Topics include normalization, indexing, and query optimization.`;
      
      await fs.writeFile(taggedFilePath, content);

      // 1. 파일 태깅
      const taggingResult = await layer1Service.taggingService.tagFile(taggedFilePath);
      
      expect(taggingResult.tags.length).toBeGreaterThan(0);
      
      // 2. 태그 기반 검색
      const firstTag = taggingResult.tags[0].name;
      const tagSearchResults = await layer1Service.taggingService.searchByTags([firstTag]);
      
      expect(tagSearchResults.some(r => r.filePath === taggedFilePath)).toBe(true);
    });

    test('태그 분석이 의미 있는 인사이트를 제공해야 함', async () => {
      // 여러 파일에 태그 생성
      const files = [
        { name: 'web-dev-1.md', content: 'HTML CSS JavaScript web development' },
        { name: 'web-dev-2.md', content: 'React Vue Angular frontend frameworks' },
        { name: 'backend-1.md', content: 'Node.js Express API server development' }
      ];

      for (const file of files) {
        const filePath = path.join('./test-data', file.name);
        await fs.writeFile(filePath, file.content);
        await layer1Service.taggingService.tagFile(filePath);
      }

      const analytics = layer1Service.taggingService.getTagAnalytics();
      
      expect(analytics.mostUsedTags.length).toBeGreaterThan(0);
      expect(Object.keys(analytics.categoryDistribution).length).toBeGreaterThan(0);
    });
  });

  describe('시스템 성능 테스트', () => {
    test('동시 검색 요청 처리 성능', async () => {
      const queries = [
        'JavaScript development',
        'React components',
        'database design',
        'API architecture',
        'frontend frameworks'
      ];

      const startTime = Date.now();
      
      const results = await Promise.all(
        queries.map(query => 
          layer1Service.search(query, { mode: 'hybrid', maxResults: 3 })
        )
      );

      const endTime = Date.now();
      
      expect(endTime - startTime).toBeLessThan(10000); // 10초 이내
      expect(results).toHaveLength(queries.length);
    }, 15000);

    test('메모리 사용량 모니터링', async () => {
      const initialMemory = process.memoryUsage();
      
      // 여러 작업 수행
      await layer1Service.search('test query');
      const healthCheck = await layer1Service.healthCheck();
      
      const finalMemory = process.memoryUsage();
      
      // 메모리 증가가 합리적인 범위 내에 있는지 확인
      const memoryIncrease = finalMemory.heapUsed - initialMemory.heapUsed;
      expect(memoryIncrease).toBeLessThan(100 * 1024 * 1024); // 100MB 미만
      
      expect(healthCheck.performance.memoryUsage).toBeDefined();
    });
  });

  describe('에러 복구 테스트', () => {
    test('서비스 오류 후 복구 능력', async () => {
      const healthCheckBefore = await layer1Service.healthCheck();
      expect(healthCheckBefore.healthy).toBe(true);

      // 의도적으로 오류 유발 (존재하지 않는 파일 분석)
      try {
        await layer1Service.analyzeFile('non-existent-file.md');
      } catch (error) {
        // 예상된 오류
      }

      // 시스템이 여전히 작동하는지 확인
      const healthCheckAfter = await layer1Service.healthCheck();
      expect(healthCheckAfter.healthy).toBe(true);

      // 다른 기능들이 정상 작동하는지 확인
      const searchResult = await layer1Service.search('test');
      expect(searchResult).toBeDefined();
    });

    test('부분적 서비스 실패 시 시스템 안정성', async () => {
      // 태깅 서비스가 일시적으로 실패하더라도 검색은 작동해야 함
      const searchResult = await layer1Service.search('resilience test', {
        mode: 'local',
        maxResults: 1
      });

      expect(searchResult).toBeDefined();
      expect(Array.isArray(searchResult)).toBe(true);
    });
  });

  describe('데이터 일관성 테스트', () => {
    test('여러 서비스 간 데이터 일관성 유지', async () => {
      const testFile = path.join('./test-data', 'consistency-test.md');
      const content = 'Consistency test for ARGO Layer 1 system integration';
      
      await fs.writeFile(testFile, content);

      // 1. 태깅 수행
      const taggingResult = await layer1Service.taggingService.tagFile(testFile);
      
      // 2. 분석 수행  
      const analysisResult = await layer1Service.analyzeFile(testFile);
      
      // 3. 검색 수행
      const searchResults = await layer1Service.search('consistency test');

      // 데이터 일관성 확인
      expect(taggingResult.filePath).toBe(testFile);
      expect(analysisResult.tagging.filePath).toBe(testFile);
      
      if (searchResults.length > 0) {
        const matchingResult = searchResults.find((r: any) => 
          r.path === testFile || r.filePath === testFile
        );
        expect(matchingResult).toBeDefined();
      }
    });
  });
});