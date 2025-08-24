/**
 * AutoTaggingService 단위 테스트
 * AI 기반 자동 태깅 시스템 검증
 */

import { AutoTaggingService } from '../../src/layer1/services/auto-tagging-service.js';
import { EmbeddingService } from '../../src/layer1/services/embedding-service.js';
import { GoogleDriveService } from '../../src/layer1/services/google-drive-service.js';

describe('AutoTaggingService', () => {
  let taggingService: AutoTaggingService;
  let embeddingService: EmbeddingService;
  let driveService: GoogleDriveService;

  beforeEach(() => {
    embeddingService = new EmbeddingService('test-api-key');
    driveService = new GoogleDriveService(embeddingService);
    taggingService = new AutoTaggingService(embeddingService, driveService);
  });

  describe('초기화 테스트', () => {
    test('AutoTaggingService가 올바르게 초기화되어야 함', () => {
      expect(taggingService).toBeDefined();
      expect(taggingService.tagFile).toBeDefined();
      expect(taggingService.searchByTags).toBeDefined();
      expect(taggingService.getTagAnalytics).toBeDefined();
    });
  });

  describe('콘텐츠 타입 감지 테스트', () => {
    test('마크다운 파일을 documentation으로 분류해야 함', async () => {
      const markdownContent = `# ARGO Architecture
      This is a documentation about ARGO system architecture.
      ## Overview
      The system consists of multiple layers.`;

      const result = await taggingService.tagFile('test.md', markdownContent);
      
      expect(result.contentType).toBe('documentation');
      expect(result.confidence).toBeGreaterThan(0);
    });

    test('TypeScript 파일을 code로 분류해야 함', async () => {
      const codeContent = `interface TestInterface {
        name: string;
        value: number;
      }
      
      class TestClass implements TestInterface {
        constructor(public name: string, public value: number) {}
      }`;

      const result = await taggingService.tagFile('test.ts', codeContent);
      
      expect(result.contentType).toBe('code');
    });

    test('회의록을 meeting_notes로 분류해야 함', async () => {
      const meetingContent = `# Weekly Team Meeting
      Date: 2024-01-15
      Attendees: John, Jane, Bob
      
      ## Agenda
      1. Project update
      2. Action items
      
      ## Discussion
      We discussed the current progress...`;

      const result = await taggingService.tagFile('meeting.md', meetingContent);
      
      expect(result.contentType).toBe('meeting_notes');
    });
  });

  describe('태그 생성 테스트', () => {
    test('기술 관련 콘텐츠에서 적절한 태그를 추출해야 함', async () => {
      const techContent = `# React TypeScript Application
      This application uses React with TypeScript for building a modern web interface.
      We are using OpenAI for AI functionality and Google Drive for cloud storage.`;

      const result = await taggingService.tagFile('app.md', techContent);
      
      const tagNames = result.tags.map(tag => tag.name.toLowerCase());
      
      expect(tagNames).toContain('react');
      expect(tagNames).toContain('typescript');
      expect(result.tags.length).toBeGreaterThan(0);
      expect(result.confidence).toBeGreaterThan(0);
    });

    test('프로젝트 관련 태그를 식별해야 함', async () => {
      const projectContent = `# ARGO Layer 1 Development
      This document describes the ARGO project architecture and implementation details.
      The system is designed to be a neuromorphic knowledge mesh.`;

      const result = await taggingService.tagFile('argo.md', projectContent);
      
      const tagNames = result.tags.map(tag => tag.name.toLowerCase());
      
      expect(tagNames.some(name => name.includes('argo'))).toBe(true);
      expect(tagNames.some(name => name.includes('project') || name.includes('architecture'))).toBe(true);
    });
  });

  describe('태그 기반 검색 테스트', () => {
    test('태그로 파일을 검색할 수 있어야 함', async () => {
      // 먼저 몇 개 파일에 태그를 생성
      await taggingService.tagFile('react-app.md', 'React application with TypeScript');
      await taggingService.tagFile('vue-app.md', 'Vue.js application');
      await taggingService.tagFile('node-server.md', 'Node.js server with TypeScript');

      // TypeScript 태그로 검색
      const results = await taggingService.searchByTags(['typescript'], {
        matchAll: false,
        minConfidence: 0.1
      });

      expect(results.length).toBeGreaterThan(0);
      expect(results.some(r => r.filePath.includes('react-app.md'))).toBe(true);
    });

    test('여러 태그를 AND 조건으로 검색할 수 있어야 함', async () => {
      await taggingService.tagFile('fullstack.md', 'React TypeScript Node.js full-stack application');
      
      const results = await taggingService.searchByTags(['react', 'typescript'], {
        matchAll: true, // AND 조건
        minConfidence: 0.1
      });

      // fullstack.md는 react와 typescript 태그를 모두 가져야 함
      const matchingResult = results.find(r => r.filePath.includes('fullstack.md'));
      expect(matchingResult).toBeDefined();
    });
  });

  describe('태그 추천 테스트', () => {
    test('유사한 파일 기반으로 태그를 추천해야 함', async () => {
      // 기존 파일들에 태그 생성
      await taggingService.tagFile('existing1.md', 'React application with modern UI');
      await taggingService.tagFile('existing2.md', 'React component library documentation');
      
      // 새로운 유사한 파일에 대한 태그 추천
      const suggestions = await taggingService.suggestTags(
        'new-react-app.md', 
        'Building a new React application with components'
      );

      expect(suggestions.suggested.length).toBeGreaterThan(0);
      expect(suggestions.reasons.length).toBeGreaterThan(0);
      
      const tagNames = suggestions.suggested.map(tag => tag.name.toLowerCase());
      expect(tagNames.some(name => name.includes('react'))).toBe(true);
    });
  });

  describe('태그 분석 테스트', () => {
    test('태그 통계를 올바르게 생성해야 함', async () => {
      // 여러 파일에 태그 생성
      await taggingService.tagFile('file1.md', 'React TypeScript application');
      await taggingService.tagFile('file2.md', 'React JavaScript application');
      await taggingService.tagFile('file3.md', 'Vue TypeScript application');

      const analytics = taggingService.getTagAnalytics();

      expect(analytics.mostUsedTags).toBeDefined();
      expect(analytics.categoryDistribution).toBeDefined();
      expect(analytics.contentTypeBreakdown).toBeDefined();
      expect(analytics.tagCorrelations).toBeDefined();
      
      // React가 가장 많이 사용된 태그 중 하나여야 함
      const reactTag = analytics.mostUsedTags.find(tag => 
        tag.tag.toLowerCase().includes('react')
      );
      expect(reactTag).toBeDefined();
    });

    test('태그 상관관계를 계산해야 함', async () => {
      // React와 TypeScript가 함께 나타나는 파일들 생성
      for (let i = 0; i < 5; i++) {
        await taggingService.tagFile(`react-ts-${i}.md`, 'React TypeScript application');
      }
      
      const analytics = taggingService.getTagAnalytics();
      
      // React와 TypeScript 간의 상관관계가 있어야 함
      const correlation = analytics.tagCorrelations.find(corr => 
        (corr.tag1.toLowerCase().includes('react') && corr.tag2.toLowerCase().includes('typescript')) ||
        (corr.tag1.toLowerCase().includes('typescript') && corr.tag2.toLowerCase().includes('react'))
      );
      
      if (correlation) {
        expect(correlation.correlation).toBeGreaterThan(0);
      }
    });
  });

  describe('성능 테스트', () => {
    test('단일 파일 태깅이 5초 이내에 완료되어야 함', async () => {
      const content = 'Simple test content for performance testing.';
      
      const startTime = Date.now();
      const result = await taggingService.tagFile('performance-test.md', content);
      const endTime = Date.now();
      
      expect(endTime - startTime).toBeLessThan(5000); // 5초 이내
      expect(result).toBeDefined();
      expect(result.tags).toBeDefined();
    }, 10000);

    test('배치 태깅 성능 테스트', async () => {
      const files = Array.from({ length: 10 }, (_, i) => 
        `test-file-${i}.md`
      );
      
      const startTime = Date.now();
      const results = await taggingService.tagFiles(files);
      const endTime = Date.now();
      
      expect(endTime - startTime).toBeLessThan(30000); // 30초 이내
      expect(results).toHaveLength(10);
    }, 35000);
  });

  describe('에러 처리 테스트', () => {
    test('존재하지 않는 파일에 대한 오류 처리', async () => {
      const result = await taggingService.tagFile('non-existent-file.md');
      
      expect(result.tags).toHaveLength(0);
      expect(result.confidence).toBe(0);
      expect(result.contentType).toBe('unknown');
    });

    test('빈 콘텐츠에 대한 처리', async () => {
      const result = await taggingService.tagFile('empty.md', '');
      
      expect(result).toBeDefined();
      expect(result.contentType).toBe('unknown');
    });

    test('매우 긴 콘텐츠 처리', async () => {
      const longContent = 'A'.repeat(50000); // 50KB 콘텐츠
      
      const result = await taggingService.tagFile('long-file.md', longContent);
      
      expect(result).toBeDefined();
      expect(result.tags).toBeDefined();
    }, 15000);
  });
});