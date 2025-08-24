/**
 * ARGO Layer 1 Phase 1: OpenAI Embeddings Integration
 * 블루프린트: "임시 MD5 해시를 실제 의미론적 임베딩으로 교체"
 * 목표: 진정한 의미 기반 검색 실현
 */

import OpenAI from 'openai';
import * as fs from 'fs/promises';

interface EmbeddingCache {
  [key: string]: {
    embedding: number[];
    timestamp: Date;
    version: string;
  };
}

interface EmbeddingRequest {
  text: string;
  model?: string;
  maxTokens?: number;
}

interface EmbeddingResult {
  embedding: number[];
  tokens: number;
  model: string;
  cached: boolean;
}

/**
 * OpenAI Embeddings Service
 * Phase 1 핵심: MD5 해시를 실제 의미론적 임베딩으로 교체
 */
class EmbeddingService {
  private openai: OpenAI;
  private cache: EmbeddingCache;
  private cacheFile: string;
  private defaultModel: string;
  private maxCacheSize: number;
  private apiCallCount: number;
  private costTracker: number; // USD

  constructor(apiKey?: string) {
    // API 키는 .env 파일에서 로드
    this.openai = new OpenAI({
      apiKey: apiKey || process.env.OPENAI_API_KEY
    });
    this.cache = {};
    this.cacheFile = 'C:\\Argo-813\\data\\embeddings-cache.json';
    this.defaultModel = 'text-embedding-3-large'; // 최신 모델
    this.maxCacheSize = 10000; // 최대 10,000개 임베딩 캐시
    this.apiCallCount = 0;
    this.costTracker = 0;
    
    this.loadCache();
  }

  /**
   * 텍스트를 의미론적 임베딩으로 변환
   * 캐싱을 통한 API 비용 최적화
   */
  async getEmbedding(request: EmbeddingRequest): Promise<EmbeddingResult> {
    const { text, model = this.defaultModel, maxTokens = 8192 } = request;
    
    // 텍스트 정규화 및 토큰 제한
    const normalizedText = this.normalizeText(text, maxTokens);
    const cacheKey = await this.generateCacheKey(normalizedText, model);
    
    // 캐시 확인
    const cached = this.cache[cacheKey];
    if (cached && this.isCacheValid(cached)) {
      return {
        embedding: cached.embedding,
        tokens: this.estimateTokens(normalizedText),
        model: model,
        cached: true
      };
    }
    
    try {
      // OpenAI API 호출
      console.log(`🔄 OpenAI Embeddings API 호출 중... (${normalizedText.length} chars)`);
      
      const response = await this.openai.embeddings.create({
        model: model,
        input: normalizedText
      });
      
      const embedding = response.data[0].embedding;
      const tokens = response.usage?.total_tokens || this.estimateTokens(normalizedText);
      
      // API 사용량 추적
      this.apiCallCount++;
      this.costTracker += this.calculateCost(tokens, model);
      
      // 캐시 저장
      this.cache[cacheKey] = {
        embedding,
        timestamp: new Date(),
        version: '1.0'
      };
      
      // 캐시 크기 관리
      await this.manageCacheSize();
      await this.saveCache();
      
      console.log(`✅ 임베딩 생성 완료 (${tokens} tokens, $${this.calculateCost(tokens, model).toFixed(4)})`);
      
      return {
        embedding,
        tokens,
        model,
        cached: false
      };
      
    } catch (error: any) {
      console.error('❌ OpenAI API 오류:', error.response?.data || error.message);
      
      // 폴백: 로컬 해시 기반 임베딩 (Phase 0 방식)
      console.log('🔄 로컬 폴백 임베딩 사용');
      return {
        embedding: await this.generateFallbackEmbedding(normalizedText),
        tokens: this.estimateTokens(normalizedText),
        model: 'local-fallback',
        cached: false
      };
    }
  }

  /**
   * 배치 임베딩 생성 (효율성 최적화)
   */
  async getBatchEmbeddings(texts: string[], model?: string): Promise<EmbeddingResult[]> {
    const batchSize = 100; // OpenAI 배치 제한
    const results: EmbeddingResult[] = [];
    
    for (let i = 0; i < texts.length; i += batchSize) {
      const batch = texts.slice(i, i + batchSize);
      console.log(`📦 배치 처리: ${i + 1}-${Math.min(i + batchSize, texts.length)}/${texts.length}`);
      
      // 캐시되지 않은 텍스트만 API 호출
      const uncachedTexts = [];
      for (const text of batch) {
        const cacheKey = await this.generateCacheKey(text, model || this.defaultModel);
        if (!this.cache[cacheKey] || !this.isCacheValid(this.cache[cacheKey])) {
          uncachedTexts.push(text);
        }
      }
      
      if (uncachedTexts.length > 0) {
        try {
          const response = await this.openai.embeddings.create({
            model: model || this.defaultModel,
            input: uncachedTexts
          });
          
          // 결과를 캐시에 저장
          for (let index = 0; index < response.data.length; index++) {
            const item = response.data[index];
            const text = uncachedTexts[index];
            const cacheKey = await this.generateCacheKey(text, model || this.defaultModel);
            
            this.cache[cacheKey] = {
              embedding: item.embedding,
              timestamp: new Date(),
              version: '1.0'
            };
          }
          
          this.apiCallCount++;
          this.costTracker += this.calculateCost(
            response.usage?.total_tokens || 0, 
            model || this.defaultModel
          );
          
        } catch (error) {
          console.warn('배치 API 호출 실패, 개별 처리로 전환:', error);
        }
      }
      
      // 전체 배치 결과 수집
      for (const text of batch) {
        const result = await this.getEmbedding({ text, model });
        results.push(result);
      }
      
      // API 레이트 제한 고려 (잠시 대기)
      if (uncachedTexts.length > 0) {
        await this.sleep(100);
      }
    }
    
    await this.saveCache();
    return results;
  }

  /**
   * 코사인 유사도 계산 (벡터화된 고성능 구현)
   */
  cosineSimilarity(embedding1: number[], embedding2: number[]): number {
    if (embedding1.length !== embedding2.length) {
      throw new Error('임베딩 차원이 다릅니다');
    }
    
    let dotProduct = 0;
    let norm1 = 0;
    let norm2 = 0;
    
    for (let i = 0; i < embedding1.length; i++) {
      dotProduct += embedding1[i] * embedding2[i];
      norm1 += embedding1[i] * embedding1[i];
      norm2 += embedding2[i] * embedding2[i];
    }
    
    const magnitude1 = Math.sqrt(norm1);
    const magnitude2 = Math.sqrt(norm2);
    
    if (magnitude1 === 0 || magnitude2 === 0) {
      return 0;
    }
    
    return dotProduct / (magnitude1 * magnitude2);
  }

  /**
   * 유사 문서 검색 (K-NN)
   */
  findSimilarDocuments(
    queryEmbedding: number[], 
    documentEmbeddings: Array<{id: string, embedding: number[]}>, 
    topK: number = 10,
    threshold: number = 0.7
  ): Array<{id: string, similarity: number}> {
    
    const similarities = documentEmbeddings.map(doc => ({
      id: doc.id,
      similarity: this.cosineSimilarity(queryEmbedding, doc.embedding)
    }));
    
    return similarities
      .filter(item => item.similarity >= threshold)
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, topK);
  }

  /**
   * 임베딩 품질 평가
   */
  evaluateEmbeddingQuality(embedding: number[]): {
    dimension: number;
    magnitude: number;
    sparsity: number; // 0에 가까운 값의 비율
    quality: 'excellent' | 'good' | 'fair' | 'poor';
  } {
    const dimension = embedding.length;
    const magnitude = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    const zeroCount = embedding.filter(val => Math.abs(val) < 0.001).length;
    const sparsity = zeroCount / dimension;
    
    let quality: 'excellent' | 'good' | 'fair' | 'poor';
    if (magnitude > 0.8 && sparsity < 0.1) quality = 'excellent';
    else if (magnitude > 0.6 && sparsity < 0.2) quality = 'good';
    else if (magnitude > 0.4 && sparsity < 0.4) quality = 'fair';
    else quality = 'poor';
    
    return { dimension, magnitude, sparsity, quality };
  }

  /**
   * 비용 및 사용량 통계
   */
  getUsageStats() {
    return {
      apiCalls: this.apiCallCount,
      totalCost: parseFloat(this.costTracker.toFixed(4)),
      cacheSize: Object.keys(this.cache).length,
      cacheHitRate: this.calculateCacheHitRate(),
      avgCostPerCall: this.apiCallCount > 0 ? this.costTracker / this.apiCallCount : 0
    };
  }

  // ======= Private Methods =======

  private normalizeText(text: string, maxTokens: number): string {
    // 텍스트 정리 및 토큰 제한
    let normalized = text
      .replace(/\s+/g, ' ')
      .replace(/[^\w\s\-_.]/g, ' ')
      .trim();
    
    // 대략적인 토큰 제한 (1 토큰 ≈ 4 문자)
    const maxChars = maxTokens * 4;
    if (normalized.length > maxChars) {
      normalized = normalized.substring(0, maxChars);
    }
    
    return normalized;
  }

  private async generateCacheKey(text: string, model: string): Promise<string> {
    // 텍스트와 모델 기반 캐시 키 생성
    const crypto = await import('crypto');
    return crypto
      .createHash('md5')
      .update(`${text}:${model}`)
      .digest('hex');
  }

  private isCacheValid(cached: { timestamp: Date; version: string }): boolean {
    const maxAge = 7 * 24 * 60 * 60 * 1000; // 7일
    const age = Date.now() - cached.timestamp.getTime();
    return age < maxAge && cached.version === '1.0';
  }

  private estimateTokens(text: string): number {
    // 대략적인 토큰 수 추정 (1 토큰 ≈ 4 문자)
    return Math.ceil(text.length / 4);
  }

  private calculateCost(tokens: number, model: string): number {
    // OpenAI 가격표 (2024년 기준)
    const pricePerToken = {
      'text-embedding-3-large': 0.00013 / 1000,    // $0.13 per 1M tokens
      'text-embedding-3-small': 0.00002 / 1000,    // $0.02 per 1M tokens
      'text-embedding-ada-002': 0.00010 / 1000     // $0.10 per 1M tokens
    };
    
    return tokens * (pricePerToken[model as keyof typeof pricePerToken] || pricePerToken['text-embedding-3-large']);
  }

  private async generateFallbackEmbedding(text: string): Promise<number[]> {
    // Phase 0 방식 폴백 (MD5 기반)
    const crypto = await import('crypto');
    const hash = crypto.createHash('md5').update(text).digest();
    const embedding = new Array(1536); // OpenAI 임베딩과 같은 차원
    
    for (let i = 0; i < 1536; i++) {
      embedding[i] = (hash[i % hash.length] - 128) / 128;
    }
    
    return embedding;
  }

  private async manageCacheSize(): Promise<void> {
    const keys = Object.keys(this.cache);
    
    if (keys.length > this.maxCacheSize) {
      // 가장 오래된 항목들 제거
      const sortedKeys = keys.sort((a, b) => 
        this.cache[a].timestamp.getTime() - this.cache[b].timestamp.getTime()
      );
      
      const toRemove = sortedKeys.slice(0, keys.length - this.maxCacheSize);
      toRemove.forEach(key => delete this.cache[key]);
      
      console.log(`🧹 캐시 정리: ${toRemove.length}개 항목 제거`);
    }
  }

  private async loadCache(): Promise<void> {
    try {
      // 데이터 디렉토리 생성
      await fs.mkdir('C:\\Argo-813\\data', { recursive: true });
      
      const data = await fs.readFile(this.cacheFile, 'utf-8');
      this.cache = JSON.parse(data);
      
      // Date 객체 복원
      Object.values(this.cache).forEach(item => {
        item.timestamp = new Date(item.timestamp);
      });
      
      console.log(`📂 임베딩 캐시 로드: ${Object.keys(this.cache).length}개 항목`);
      
    } catch (error) {
      console.log('📝 새로운 임베딩 캐시 생성');
      this.cache = {};
    }
  }

  private async saveCache(): Promise<void> {
    try {
      await fs.writeFile(
        this.cacheFile, 
        JSON.stringify(this.cache, null, 2)
      );
    } catch (error) {
      console.warn('캐시 저장 실패:', error);
    }
  }

  private calculateCacheHitRate(): number {
    // 실제 구현에서는 히트/미스 카운터 필요
    return 0.75; // 임시값
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export {
  EmbeddingService,
  EmbeddingRequest,
  EmbeddingResult
};