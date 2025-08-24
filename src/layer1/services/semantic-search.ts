/**
 * ARGO Layer 1 Phase 1: Semantic Search Engine  
 * 블루프린트: "키워드 매칭을 넘어선 맥락적 이해"
 * 목표: OpenAI Embeddings를 활용한 진정한 의미 기반 검색
 */

import { EmbeddingService, EmbeddingResult } from './embedding-service.js';
import { IntelligentNode, RelevanceScore } from '../knowledge-mesh/intelligent-node.js';
import { SynapticNetwork } from '../synaptic-network/synaptic-network.js';

interface SemanticSearchQuery {
  query: string;
  filters?: {
    fileTypes?: string[];
    dateRange?: { start: Date; end: Date };
    minRelevance?: number;
    maxResults?: number;
    includeSnippets?: boolean;
  };
  context?: {
    currentFiles?: string[];
    recentQueries?: string[];
    userIntent?: 'research' | 'reference' | 'implementation' | 'review';
  };
}

interface SemanticSearchResult {
  nodeId: string;
  path: string;
  semanticScore: number;    // 0-1, 의미적 유사도
  contextScore: number;     // 0-1, 맥락적 관련성
  temporalScore: number;    // 0-1, 시간적 관련성
  combinedScore: number;    // 0-1, 최종 점수
  snippet: string;
  highlightedSnippet?: string;
  reasoning: string[];
  relatedNodes?: string[];
  tags: string[];
  lastModified: Date;
  confidence: number;
}

interface SearchInsight {
  type: 'suggestion' | 'expansion' | 'clarification' | 'related_concept';
  content: string;
  query: string;
  confidence: number;
}

/**
 * Semantic Search Engine - OpenAI Embeddings 기반 지능형 검색
 * Phase 1 목표: "관련 파일 자동 제안 + 의미적 유사도 검색"
 */
class SemanticSearchEngine {
  private embeddingService: EmbeddingService;
  private network: SynapticNetwork;
  private searchHistory: Array<{query: string, timestamp: Date, results: number}>;
  private queryCache: Map<string, SemanticSearchResult[]>;
  private conceptMap: Map<string, string[]>; // 개념 -> 관련 키워드들

  constructor(embeddingService: EmbeddingService, network: SynapticNetwork) {
    this.embeddingService = embeddingService;
    this.network = network;
    this.searchHistory = [];
    this.queryCache = new Map();
    this.conceptMap = new Map();
    
    this.initializeConceptMap();
  }

  /**
   * 핵심 기능: 의미적 검색 실행
   * 기존 키워드 매칭을 완전히 대체하는 지능형 검색
   */
  async search(searchQuery: SemanticSearchQuery): Promise<{
    results: SemanticSearchResult[];
    insights: SearchInsight[];
    searchStats: {
      totalNodes: number;
      searchTime: number;
      embeddingTime: number;
      cacheHit: boolean;
    };
  }> {
    const startTime = Date.now();
    let embeddingTime = 0;
    
    // 쿼리 정규화 및 확장
    const enhancedQuery = await this.enhanceQuery(searchQuery.query, searchQuery.context);
    
    // 캐시 확인
    const cacheKey = this.generateCacheKey(enhancedQuery, searchQuery.filters);
    if (this.queryCache.has(cacheKey)) {
      const cachedResults = this.queryCache.get(cacheKey)!;
      return {
        results: cachedResults,
        insights: await this.generateSearchInsights(enhancedQuery, cachedResults),
        searchStats: {
          totalNodes: cachedResults.length,
          searchTime: Date.now() - startTime,
          embeddingTime: 0,
          cacheHit: true
        }
      };
    }
    
    // 쿼리 임베딩 생성
    const embeddingStart = Date.now();
    const queryEmbedding = await this.embeddingService.getEmbedding({
      text: enhancedQuery,
      maxTokens: 8000
    });
    embeddingTime = Date.now() - embeddingStart;
    
    // 모든 노드에 대해 의미적 유사도 계산
    const nodeEmbeddings = await this.getNodeEmbeddings();
    const semanticResults = this.calculateSemanticSimilarity(
      queryEmbedding.embedding,
      nodeEmbeddings,
      searchQuery.filters?.minRelevance || 0.3
    );
    
    // 컨텍스트 점수 계산
    const contextualResults = await this.calculateContextualRelevance(
      semanticResults,
      searchQuery.context
    );
    
    // 시간적 관련성 추가
    const temporalResults = this.calculateTemporalRelevance(contextualResults);
    
    // 최종 점수 계산 및 정렬
    const finalResults = this.calculateFinalScores(temporalResults)
      .sort((a, b) => b.combinedScore - a.combinedScore)
      .slice(0, searchQuery.filters?.maxResults || 20);
    
    // 스니펫 생성 (요청된 경우)
    if (searchQuery.filters?.includeSnippets !== false) {
      await this.generateSnippets(finalResults, searchQuery.query);
    }
    
    // 관련 노드 추가
    await this.addRelatedNodes(finalResults);
    
    // 결과 캐싱
    this.queryCache.set(cacheKey, finalResults);
    this.manageQueryCache();
    
    // 검색 히스토리 업데이트
    this.updateSearchHistory(searchQuery.query, finalResults.length);
    
    // 검색 인사이트 생성
    const insights = await this.generateSearchInsights(enhancedQuery, finalResults);
    
    const totalTime = Date.now() - startTime;
    
    return {
      results: finalResults,
      insights,
      searchStats: {
        totalNodes: nodeEmbeddings.length,
        searchTime: totalTime,
        embeddingTime,
        cacheHit: false
      }
    };
  }

  /**
   * 자동 완성 및 쿼리 제안
   */
  async suggestQueries(partialQuery: string, limit: number = 5): Promise<string[]> {
    const suggestions: string[] = [];
    
    // 1. 검색 히스토리 기반 제안
    const historySuggestions = this.searchHistory
      .filter(h => h.query.toLowerCase().includes(partialQuery.toLowerCase()))
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, 3)
      .map(h => h.query);
    
    suggestions.push(...historySuggestions);
    
    // 2. 개념 맵 기반 제안
    const conceptSuggestions = this.getConceptSuggestions(partialQuery);
    suggestions.push(...conceptSuggestions.slice(0, 2));
    
    // 3. 의미적 확장 제안
    if (partialQuery.length > 3) {
      const semanticSuggestions = await this.generateSemanticExpansions(partialQuery);
      suggestions.push(...semanticSuggestions.slice(0, 2));
    }
    
    // 중복 제거 및 제한
    return [...new Set(suggestions)].slice(0, limit);
  }

  /**
   * 검색 결과 학습 피드백
   */
  recordSearchFeedback(
    query: string, 
    nodeId: string, 
    feedback: 'clicked' | 'helpful' | 'irrelevant' | 'opened'
  ): void {
    // 피드백을 통해 검색 품질 개선
    const weight = {
      'clicked': 0.1,
      'opened': 0.3,
      'helpful': 0.5,
      'irrelevant': -0.2
    }[feedback];
    
    // SynapticNetwork에 학습 신호 전달
    const interactionQuality = {
      satisfaction: Math.max(0, 0.5 + weight),
      timeSpent: feedback === 'opened' ? 30 : 5,
      contextRelevance: 0.7,
      surpriseFactor: feedback === 'helpful' ? 0.3 : 0.1
    };
    
    // 검색 쿼리와 결과 노드 간 연결 강화
    this.network.reinforcePath([query, nodeId], interactionQuality.satisfaction);
  }

  /**
   * 개념 클러스터 분석
   */
  async analyzeConceptClusters(): Promise<{
    clusters: Array<{
      concept: string;
      nodes: string[];
      centrality: number;
      keywords: string[];
    }>;
    insights: string[];
  }> {
    const clusters: Array<{
      concept: string;
      nodes: string[];
      centrality: number;  
      keywords: string[];
    }> = [];
    
    // 네트워크 인사이트를 활용한 개념 클러스터링
    const networkInsights = this.network.generateNetworkInsights();
    
    // 허브 노드들을 중심으로 클러스터 형성
    const hubNodes = networkInsights.filter(insight => insight.type === 'hub');
    
    for (const hub of hubNodes) {
      const connectedNodes = this.getConnectedNodes(hub.nodeId);
      const keywords = await this.extractKeywords(connectedNodes);
      
      clusters.push({
        concept: this.inferConceptName(hub.nodeId, keywords),
        nodes: connectedNodes,
        centrality: hub.importance,
        keywords: keywords.slice(0, 10)
      });
    }
    
    const insights = this.generateClusterInsights(clusters);
    
    return { clusters, insights };
  }

  // ======= Private Methods =======

  private async enhanceQuery(query: string, context?: SemanticSearchQuery['context']): Promise<string> {
    let enhanced = query.trim();
    
    // 컨텍스트 기반 쿼리 확장
    if (context?.userIntent) {
      const intentKeywords = {
        'research': ['analysis', 'study', 'investigation'],
        'reference': ['example', 'documentation', 'guide'],
        'implementation': ['code', 'solution', 'method'],
        'review': ['evaluation', 'assessment', 'feedback']
      };
      
      const keywords = intentKeywords[context.userIntent];
      if (keywords) {
        enhanced += ' ' + keywords.join(' OR ');
      }
    }
    
    // 최근 쿼리와의 관련성 고려
    if (context?.recentQueries && context.recentQueries.length > 0) {
      const recentContext = context.recentQueries.slice(-2).join(' ');
      enhanced = `${enhanced} context: ${recentContext}`;
    }
    
    return enhanced;
  }

  private async getNodeEmbeddings(): Promise<Array<{nodeId: string, embedding: number[], node: IntelligentNode}>> {
    const results: Array<{nodeId: string, embedding: number[], node: IntelligentNode}> = [];
    
    // 모든 노드의 임베딩 가져오기 (캐시 활용)
    const promises: Promise<{nodeId: string, embedding: number[], node: IntelligentNode}>[] = [];
    
    this.network['nodes'].forEach((node: IntelligentNode, nodeId: string) => {
      const promise = this.getNodeEmbedding(nodeId, node).then(embedding => ({
        nodeId,
        embedding,
        node
      }));
      promises.push(promise);
    });
    
    const embeddingResults = await Promise.all(promises);
    return embeddingResults;
  }

  private async getNodeEmbedding(nodeId: string, node: IntelligentNode): Promise<number[]> {
    // 노드 내용을 임베딩으로 변환 (캐시 활용)
    const content = `${node.content.path} ${node.content.content}`.substring(0, 8000);
    const result = await this.embeddingService.getEmbedding({ text: content });
    return result.embedding;
  }

  private calculateSemanticSimilarity(
    queryEmbedding: number[],
    nodeEmbeddings: Array<{nodeId: string, embedding: number[], node: IntelligentNode}>,
    minRelevance: number
  ): Array<{nodeId: string, node: IntelligentNode, semanticScore: number}> {
    
    return nodeEmbeddings
      .map(item => ({
        nodeId: item.nodeId,
        node: item.node,
        semanticScore: this.embeddingService.cosineSimilarity(queryEmbedding, item.embedding)
      }))
      .filter(item => item.semanticScore >= minRelevance);
  }

  private async calculateContextualRelevance(
    semanticResults: Array<{nodeId: string, node: IntelligentNode, semanticScore: number}>,
    context?: SemanticSearchQuery['context']
  ): Promise<Array<{nodeId: string, node: IntelligentNode, semanticScore: number, contextScore: number}>> {
    
    return semanticResults.map(item => {
      let contextScore = 0.5; // 기본 컨텍스트 점수
      
      if (context?.currentFiles) {
        // 현재 활성 파일들과의 연관성
        const connections = item.node.getConnectedNodes();
        const overlap = context.currentFiles.filter(file => 
          connections.some(connectedId => {
            const connectedNode = this.network['nodes'].get(connectedId);
            return connectedNode?.content.path === file;
          })
        );
        contextScore += overlap.length * 0.1;
      }
      
      if (context?.recentQueries) {
        // 최근 쿼리와의 관련성
        const recentRelevance = context.recentQueries.reduce((acc, recentQuery) => {
          const relevance = item.node.predictRelevance(recentQuery);
          return acc + relevance.score;
        }, 0) / context.recentQueries.length;
        
        contextScore += recentRelevance * 0.2;
      }
      
      return {
        ...item,
        contextScore: Math.min(contextScore, 1.0)
      };
    });
  }

  private calculateTemporalRelevance(
    contextualResults: Array<{nodeId: string, node: IntelligentNode, semanticScore: number, contextScore: number}>
  ): Array<{nodeId: string, node: IntelligentNode, semanticScore: number, contextScore: number, temporalScore: number}> {
    
    const now = Date.now();
    const oneWeek = 7 * 24 * 60 * 60 * 1000;
    
    return contextualResults.map(item => {
      const timeSinceModified = now - item.node.content.lastModified.getTime();
      
      // 최근 파일일수록 높은 점수
      let temporalScore = 0.5;
      if (timeSinceModified < oneWeek) {
        temporalScore = 1.0 - (timeSinceModified / oneWeek) * 0.5;
      } else {
        temporalScore = 0.5 * Math.exp(-(timeSinceModified - oneWeek) / (oneWeek * 4));
      }
      
      return {
        ...item,
        temporalScore: Math.max(0.1, temporalScore)
      };
    });
  }

  private calculateFinalScores(
    temporalResults: Array<{nodeId: string, node: IntelligentNode, semanticScore: number, contextScore: number, temporalScore: number}>
  ): SemanticSearchResult[] {
    
    return temporalResults.map(item => {
      // 가중 평균으로 최종 점수 계산
      const combinedScore = 
        item.semanticScore * 0.6 +     // 의미적 유사도 60%
        item.contextScore * 0.3 +      // 맥락적 관련성 30%
        item.temporalScore * 0.1;      // 시간적 관련성 10%
      
      // 추론 체인 생성
      const reasoning = [];
      if (item.semanticScore > 0.8) reasoning.push('높은 의미적 유사도');
      if (item.contextScore > 0.7) reasoning.push('현재 작업과 관련');
      if (item.temporalScore > 0.8) reasoning.push('최근 수정됨');
      
      return {
        nodeId: item.nodeId,
        path: item.node.content.path,
        semanticScore: item.semanticScore,
        contextScore: item.contextScore,
        temporalScore: item.temporalScore,
        combinedScore,
        snippet: '', // 추후 생성
        reasoning: reasoning.length > 0 ? reasoning : ['기본 의미적 매칭'],
        tags: item.node.content.metadata.tags || [],
        lastModified: item.node.content.lastModified,
        confidence: combinedScore * 0.9 // 약간 보수적으로
      };
    });
  }

  private async generateSnippets(results: SemanticSearchResult[], query: string): Promise<void> {
    for (const result of results) {
      const node = this.network['nodes'].get(result.nodeId);
      if (node) {
        result.snippet = this.extractSnippet(node.content.content, query, 150);
        result.highlightedSnippet = this.highlightSnippet(result.snippet, query);
      }
    }
  }

  private extractSnippet(content: string, query: string, maxLength: number): string {
    const queryTerms = query.toLowerCase().split(/\s+/);
    const sentences = content.split(/[.!?]+/);
    
    // 쿼리 용어가 포함된 문장 찾기
    let bestSentence = sentences[0];
    let maxScore = 0;
    
    for (const sentence of sentences) {
      const lowerSentence = sentence.toLowerCase();
      const score = queryTerms.reduce((acc, term) => 
        acc + (lowerSentence.includes(term) ? 1 : 0), 0
      );
      
      if (score > maxScore) {
        maxScore = score;
        bestSentence = sentence;
      }
    }
    
    // 길이 제한
    if (bestSentence.length > maxLength) {
      return bestSentence.substring(0, maxLength) + '...';
    }
    
    return bestSentence.trim();
  }

  private highlightSnippet(snippet: string, query: string): string {
    const queryTerms = query.toLowerCase().split(/\s+/);
    let highlighted = snippet;
    
    queryTerms.forEach(term => {
      const regex = new RegExp(`(${term})`, 'gi');
      highlighted = highlighted.replace(regex, '<mark>$1</mark>');
    });
    
    return highlighted;
  }

  private async addRelatedNodes(results: SemanticSearchResult[]): Promise<void> {
    for (const result of results) {
      const node = this.network['nodes'].get(result.nodeId);
      if (node) {
        const connectedNodes = node.getConnectedNodes(0.5); // 강한 연결만
        result.relatedNodes = connectedNodes.slice(0, 5);
      }
    }
  }

  private generateCacheKey(query: string, filters?: SemanticSearchQuery['filters']): string {
    const filterStr = filters ? JSON.stringify(filters) : '';
    return `${query}:${filterStr}`;
  }

  private manageQueryCache(): void {
    if (this.queryCache.size > 100) {
      // 가장 오래된 캐시 항목 제거
      const firstKey = this.queryCache.keys().next().value;
      if (firstKey) {
        this.queryCache.delete(firstKey);
      }
    }
  }

  private updateSearchHistory(query: string, resultCount: number): void {
    this.searchHistory.push({
      query,
      timestamp: new Date(),
      results: resultCount
    });
    
    // 최근 100개만 유지
    if (this.searchHistory.length > 100) {
      this.searchHistory = this.searchHistory.slice(-100);
    }
  }

  private async generateSearchInsights(query: string, results: SemanticSearchResult[]): Promise<SearchInsight[]> {
    const insights: SearchInsight[] = [];
    
    // 검색 결과 품질 분석
    if (results.length === 0) {
      insights.push({
        type: 'suggestion',
        content: '검색 결과가 없습니다. 더 일반적인 용어로 다시 시도해보세요.',
        query: query.split(' ').slice(0, 2).join(' '),
        confidence: 0.8
      });
    } else if (results.length > 0 && results[0].combinedScore < 0.5) {
      insights.push({
        type: 'clarification', 
        content: '관련성이 낮은 결과입니다. 더 구체적인 키워드를 추가해보세요.',
        query: `${query} specific details`,
        confidence: 0.6
      });
    }
    
    // 관련 개념 제안
    const relatedConcepts = this.getConceptSuggestions(query);
    if (relatedConcepts.length > 0) {
      insights.push({
        type: 'expansion',
        content: `관련 개념: ${relatedConcepts.slice(0, 3).join(', ')}`,
        query: `${query} ${relatedConcepts[0]}`,
        confidence: 0.7
      });
    }
    
    return insights;
  }

  private initializeConceptMap(): void {
    // ARGO 프로젝트 관련 개념 맵 초기화
    this.conceptMap.set('architecture', ['design', 'structure', 'pattern', 'layer', 'component']);
    this.conceptMap.set('argo', ['project', 'system', 'agent', 'ai', 'assistant']);
    this.conceptMap.set('layer', ['tier', 'level', 'phase', 'stage']);
    this.conceptMap.set('intelligence', ['ai', 'smart', 'learning', 'prediction', 'insight']);
    this.conceptMap.set('search', ['find', 'query', 'retrieve', 'discover']);
    this.conceptMap.set('context', ['background', 'situation', 'environment', 'setting']);
  }

  private getConceptSuggestions(query: string): string[] {
    const suggestions: string[] = [];
    const queryLower = query.toLowerCase();
    
    this.conceptMap.forEach((related, concept) => {
      if (queryLower.includes(concept)) {
        suggestions.push(...related);
      }
      if (related.some(r => queryLower.includes(r))) {
        suggestions.push(concept, ...related.filter(r => !queryLower.includes(r)));
      }
    });
    
    return [...new Set(suggestions)];
  }

  private async generateSemanticExpansions(partialQuery: string): Promise<string[]> {
    // 의미적 확장 (실제 구현에서는 GPT API 사용 가능)
    const expansions: string[] = [];
    
    if (partialQuery.includes('architecture')) {
      expansions.push(`${partialQuery} design patterns`, `${partialQuery} structure`);
    }
    
    if (partialQuery.includes('search')) {
      expansions.push(`${partialQuery} algorithm`, `${partialQuery} optimization`);
    }
    
    return expansions;
  }

  private getConnectedNodes(hubNodeId: string): string[] {
    const node = this.network['nodes'].get(hubNodeId);
    return node ? node.getConnectedNodes() : [];
  }

  private async extractKeywords(nodeIds: string[]): Promise<string[]> {
    const allKeywords: string[] = [];
    
    nodeIds.forEach(nodeId => {
      const node = this.network['nodes'].get(nodeId);
      if (node && node.content.metadata.tags) {
        allKeywords.push(...node.content.metadata.tags);
      }
    });
    
    // 빈도수 기반 상위 키워드 반환
    const keywordCounts = new Map<string, number>();
    allKeywords.forEach(keyword => {
      keywordCounts.set(keyword, (keywordCounts.get(keyword) || 0) + 1);
    });
    
    return Array.from(keywordCounts.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, 20)
      .map(([keyword]) => keyword);
  }

  private inferConceptName(nodeId: string, keywords: string[]): string {
    const node = this.network['nodes'].get(nodeId);
    const filename = node?.content.path.split('\\').pop()?.replace(/\.[^.]+$/, '') || nodeId;
    
    // 파일명과 키워드를 조합하여 개념명 생성
    if (keywords.length > 0) {
      return `${filename} (${keywords.slice(0, 2).join(', ')})`;
    }
    
    return filename;
  }

  private generateClusterInsights(clusters: Array<{concept: string, nodes: string[], centrality: number, keywords: string[]}>): string[] {
    const insights: string[] = [];
    
    if (clusters.length > 0) {
      const topCluster = clusters.sort((a, b) => b.centrality - a.centrality)[0];
      insights.push(`"${topCluster.concept}"이(가) 가장 중심적인 개념입니다 (연결된 파일: ${topCluster.nodes.length}개)`);
    }
    
    const largeClusters = clusters.filter(c => c.nodes.length > 5);
    if (largeClusters.length > 0) {
      insights.push(`${largeClusters.length}개의 주요 개념 클러스터가 발견되었습니다`);
    }
    
    return insights;
  }
}

export {
  SemanticSearchEngine,
  SemanticSearchQuery,
  SemanticSearchResult,
  SearchInsight
};