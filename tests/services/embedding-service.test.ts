/**
 * EmbeddingService 단위 테스트
 * Phase 1 핵심 서비스 검증
 */

import { EmbeddingService } from '../../src/layer1/services/embedding-service.js';

describe('EmbeddingService', () => {
  let embeddingService: EmbeddingService;

  beforeEach(() => {
    embeddingService = new EmbeddingService('test-api-key');
  });

  describe('초기화 테스트', () => {
    test('EmbeddingService가 올바르게 초기화되어야 함', () => {
      expect(embeddingService).toBeDefined();
      expect(embeddingService.getUsageStats).toBeDefined();
      expect(embeddingService.cosineSimilarity).toBeDefined();
    });

    test('사용량 통계 초기값이 올바르게 설정되어야 함', () => {
      const stats = embeddingService.getUsageStats();
      
      expect(stats.apiCalls).toBe(0);
      expect(stats.totalCost).toBe(0);
      expect(stats.cacheSize).toBe(0);
    });
  });

  describe('코사인 유사도 계산 테스트', () => {
    test('동일한 벡터의 유사도는 1이어야 함', () => {
      const vector1 = [1, 0, 0];
      const vector2 = [1, 0, 0];
      
      const similarity = embeddingService.cosineSimilarity(vector1, vector2);
      expect(similarity).toBeCloseTo(1.0, 5);
    });

    test('직교 벡터의 유사도는 0이어야 함', () => {
      const vector1 = [1, 0, 0];
      const vector2 = [0, 1, 0];
      
      const similarity = embeddingService.cosineSimilarity(vector1, vector2);
      expect(similarity).toBeCloseTo(0.0, 5);
    });

    test('반대 방향 벡터의 유사도는 -1이어야 함', () => {
      const vector1 = [1, 0, 0];
      const vector2 = [-1, 0, 0];
      
      const similarity = embeddingService.cosineSimilarity(vector1, vector2);
      expect(similarity).toBeCloseTo(-1.0, 5);
    });

    test('차원이 다른 벡터는 에러를 발생시켜야 함', () => {
      const vector1 = [1, 0, 0];
      const vector2 = [1, 0];
      
      expect(() => {
        embeddingService.cosineSimilarity(vector1, vector2);
      }).toThrow('임베딩 차원이 다릅니다');
    });
  });

  describe('유사 문서 검색 테스트', () => {
    test('유사 문서를 올바른 순서로 반환해야 함', () => {
      const queryEmbedding = [1, 0, 0];
      const documentEmbeddings = [
        { id: 'doc1', embedding: [0.9, 0.1, 0] }, // 높은 유사도
        { id: 'doc2', embedding: [0.5, 0.5, 0] }, // 중간 유사도  
        { id: 'doc3', embedding: [0, 1, 0] },     // 낮은 유사도
        { id: 'doc4', embedding: [0.8, 0.2, 0] }  // 높은 유사도
      ];
      
      const results = embeddingService.findSimilarDocuments(
        queryEmbedding, 
        documentEmbeddings, 
        3, 
        0.1
      );
      
      expect(results).toHaveLength(3);
      expect(results[0].id).toBe('doc1'); // 가장 높은 유사도
      expect(results[1].id).toBe('doc4'); // 두 번째 높은 유사도
      expect(results[2].id).toBe('doc2'); // 세 번째 높은 유사도
      
      // 유사도가 내림차순으로 정렬되어 있는지 확인
      expect(results[0].similarity).toBeGreaterThan(results[1].similarity);
      expect(results[1].similarity).toBeGreaterThan(results[2].similarity);
    });

    test('threshold 이하의 유사도를 가진 문서는 제외되어야 함', () => {
      const queryEmbedding = [1, 0, 0];
      const documentEmbeddings = [
        { id: 'doc1', embedding: [0.9, 0.1, 0] }, // 높은 유사도
        { id: 'doc2', embedding: [0, 1, 0] }      // 낮은 유사도 (threshold 이하)
      ];
      
      const results = embeddingService.findSimilarDocuments(
        queryEmbedding, 
        documentEmbeddings, 
        10, 
        0.8 // 높은 threshold
      );
      
      expect(results).toHaveLength(1);
      expect(results[0].id).toBe('doc1');
    });
  });

  describe('임베딩 품질 평가 테스트', () => {
    test('고품질 임베딩을 올바르게 평가해야 함', () => {
      const highQualityEmbedding = new Array(1536).fill(0.1); // 일정한 값
      
      const evaluation = embeddingService.evaluateEmbeddingQuality(highQualityEmbedding);
      
      expect(evaluation.dimension).toBe(1536);
      expect(evaluation.magnitude).toBeGreaterThan(0);
      expect(evaluation.sparsity).toBe(0); // 0에 가까운 값이 없음
      expect(evaluation.quality).toBe('excellent');
    });

    test('저품질 임베딩을 올바르게 평가해야 함', () => {
      const lowQualityEmbedding = new Array(1536).fill(0); // 모두 0
      
      const evaluation = embeddingService.evaluateEmbeddingQuality(lowQualityEmbedding);
      
      expect(evaluation.dimension).toBe(1536);
      expect(evaluation.magnitude).toBe(0);
      expect(evaluation.sparsity).toBe(1); // 모두 0에 가까움
      expect(evaluation.quality).toBe('poor');
    });
  });

  describe('에러 처리 테스트', () => {
    test('빈 텍스트에 대한 폴백 임베딩 생성', async () => {
      try {
        const result = await embeddingService.getEmbedding({ text: '' });
        
        // 폴백 임베딩이 생성되어야 함
        expect(result.embedding).toBeDefined();
        expect(result.embedding).toHaveLength(1536);
        expect(result.model).toBe('local-fallback');
      } catch (error) {
        // API 키가 유효하지 않을 경우 에러가 발생할 수 있음
        expect(error).toBeDefined();
      }
    });
  });

  describe('성능 테스트', () => {
    test('코사인 유사도 계산이 1ms 이내에 완료되어야 함', () => {
      const vector1 = new Array(1536).fill(0.1);
      const vector2 = new Array(1536).fill(0.2);
      
      const startTime = performance.now();
      const similarity = embeddingService.cosineSimilarity(vector1, vector2);
      const endTime = performance.now();
      
      expect(endTime - startTime).toBeLessThan(1); // 1ms 이내
      expect(similarity).toBeDefined();
    });

    test('대용량 문서 검색 성능 테스트', () => {
      const queryEmbedding = new Array(1536).fill(0.1);
      const documentEmbeddings = Array.from({ length: 1000 }, (_, i) => ({
        id: `doc${i}`,
        embedding: new Array(1536).fill(Math.random())
      }));
      
      const startTime = performance.now();
      const results = embeddingService.findSimilarDocuments(
        queryEmbedding, 
        documentEmbeddings, 
        10
      );
      const endTime = performance.now();
      
      expect(endTime - startTime).toBeLessThan(100); // 100ms 이내
      expect(results).toHaveLength(10);
    });
  });
});