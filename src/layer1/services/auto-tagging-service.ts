/**
 * ARGO Layer 1 Phase 1: 자동 태깅 및 분류 시스템
 * 블루프린트: "컨텐츠 기반 지능적 분류 및 태깅"
 * 목표: OpenAI를 통한 의미론적 태깅 + 패턴 기반 자동 분류
 */

import { EmbeddingService } from './embedding-service.js';
import { GoogleDriveService, DriveFile } from './google-drive-service.js';
import * as fs from 'fs/promises';

interface TaggingResult {
  filePath: string;
  contentType: ContentType;
  tags: Tag[];
  categories: Category[];
  confidence: number;
  timestamp: Date;
}

interface Tag {
  name: string;
  weight: number;
  type: 'topic' | 'technology' | 'project' | 'person' | 'concept' | 'action';
  source: 'ai' | 'pattern' | 'manual' | 'inherited';
}

interface Category {
  name: string;
  confidence: number;
  subcategory?: string;
}

type ContentType = 
  | 'documentation' 
  | 'code' 
  | 'design' 
  | 'meeting_notes' 
  | 'planning' 
  | 'research' 
  | 'personal' 
  | 'reference'
  | 'unknown';

interface TaggingRule {
  id: string;
  name: string;
  condition: {
    filePattern?: RegExp;
    contentPattern?: RegExp;
    keywords?: string[];
    minConfidence?: number;
  };
  action: {
    addTags?: string[];
    setCategory?: string;
    setContentType?: ContentType;
  };
  priority: number;
}

interface TagAnalytics {
  mostUsedTags: Array<{tag: string, count: number, trend: 'rising' | 'stable' | 'declining'}>;
  categoryDistribution: Record<string, number>;
  contentTypeBreakdown: Record<ContentType, number>;
  tagCorrelations: Array<{tag1: string, tag2: string, correlation: number}>;
  temporalTrends: Array<{period: string, tags: Record<string, number>}>;
}

/**
 * AI-powered Auto-Tagging and Classification Service
 * Phase 1 핵심: 콘텐츠의 의미적 이해를 통한 자동 분류
 */
class AutoTaggingService {
  private embeddingService: EmbeddingService;
  private driveService: GoogleDriveService;
  private taggingRules: TaggingRule[];
  private tagHistory: TaggingResult[];
  private historyFile: string;
  private rulesFile: string;
  private tagVocabulary: Map<string, number>; // tag -> frequency
  private categoryPatterns: Map<ContentType, RegExp[]>;

  constructor(embeddingService: EmbeddingService, driveService: GoogleDriveService) {
    this.embeddingService = embeddingService;
    this.driveService = driveService;
    this.taggingRules = [];
    this.tagHistory = [];
    this.historyFile = 'C:\\Argo-813\\data\\tagging-history.json';
    this.rulesFile = 'C:\\Argo-813\\data\\tagging-rules.json';
    this.tagVocabulary = new Map();
    this.categoryPatterns = new Map();

    this.initializeDefaultRules();
    this.initializeCategoryPatterns();
    this.loadTaggingHistory();
    this.loadTaggingRules();
  }

  /**
   * 단일 파일 자동 태깅
   */
  async tagFile(filePath: string, content?: string): Promise<TaggingResult> {
    try {
      console.log(`🏷️  파일 태깅 시작: ${filePath}`);

      // 콘텐츠 로드
      if (!content) {
        try {
          content = await fs.readFile(filePath, 'utf-8');
        } catch (error) {
          console.warn(`파일 읽기 실패: ${filePath}`);
          content = '';
        }
      }

      // 콘텐츠 타입 결정
      const contentType = this.detectContentType(filePath, content);

      // AI 기반 태깅
      const aiTags = await this.generateAITags(content, filePath);

      // 패턴 기반 태깅
      const patternTags = this.generatePatternTags(filePath, content);

      // 규칙 기반 태깅
      const ruleTags = this.applyTaggingRules(filePath, content);

      // 태그 병합 및 정규화
      const allTags = [...aiTags, ...patternTags, ...ruleTags];
      const mergedTags = this.mergeTags(allTags);

      // 카테고리 결정
      const categories = this.determineCategories(contentType, mergedTags, content);

      // 전체 신뢰도 계산
      const confidence = this.calculateOverallConfidence(mergedTags, categories);

      const result: TaggingResult = {
        filePath,
        contentType,
        tags: mergedTags,
        categories,
        confidence,
        timestamp: new Date()
      };

      // 히스토리에 저장
      this.tagHistory.push(result);
      await this.saveTaggingHistory();

      // 태그 어휘 업데이트
      this.updateTagVocabulary(mergedTags);

      console.log(`✅ 파일 태깅 완료: ${mergedTags.length}개 태그, ${categories.length}개 카테고리 (신뢰도: ${(confidence * 100).toFixed(1)}%)`);

      return result;

    } catch (error) {
      console.error(`❌ 파일 태깅 실패 (${filePath}):`, error);
      
      return {
        filePath,
        contentType: 'unknown',
        tags: [],
        categories: [],
        confidence: 0,
        timestamp: new Date()
      };
    }
  }

  /**
   * 배치 태깅 (여러 파일)
   */
  async tagFiles(filePaths: string[]): Promise<TaggingResult[]> {
    console.log(`🏷️  배치 태깅 시작: ${filePaths.length}개 파일`);

    const results: TaggingResult[] = [];
    const batchSize = 10;

    for (let i = 0; i < filePaths.length; i += batchSize) {
      const batch = filePaths.slice(i, i + batchSize);
      console.log(`📦 배치 처리: ${i + 1}-${Math.min(i + batchSize, filePaths.length)}/${filePaths.length}`);

      const batchResults = await Promise.all(
        batch.map(filePath => this.tagFile(filePath))
      );

      results.push(...batchResults);

      // API 레이트 제한 고려
      if (i + batchSize < filePaths.length) {
        await this.sleep(1000);
      }
    }

    console.log(`✅ 배치 태깅 완료: ${results.length}개 파일 처리`);
    return results;
  }

  /**
   * 태그 기반 파일 검색
   */
  async searchByTags(tags: string[], options?: {
    matchAll?: boolean;
    minConfidence?: number;
    contentTypes?: ContentType[];
    dateRange?: { from: Date; to: Date };
  }): Promise<TaggingResult[]> {
    
    const { 
      matchAll = false, 
      minConfidence = 0.5, 
      contentTypes,
      dateRange 
    } = options || {};

    let results = this.tagHistory.filter(result => {
      // 신뢰도 필터
      if (result.confidence < minConfidence) return false;

      // 콘텐츠 타입 필터
      if (contentTypes && !contentTypes.includes(result.contentType)) return false;

      // 날짜 범위 필터
      if (dateRange) {
        const resultDate = new Date(result.timestamp);
        if (resultDate < dateRange.from || resultDate > dateRange.to) return false;
      }

      // 태그 매칭
      const resultTags = result.tags.map(t => t.name.toLowerCase());
      const searchTags = tags.map(t => t.toLowerCase());

      if (matchAll) {
        return searchTags.every(tag => resultTags.includes(tag));
      } else {
        return searchTags.some(tag => resultTags.includes(tag));
      }
    });

    // 관련성 순으로 정렬
    results.sort((a, b) => {
      const aScore = this.calculateTagRelevanceScore(a.tags, tags);
      const bScore = this.calculateTagRelevanceScore(b.tags, tags);
      return bScore - aScore;
    });

    return results;
  }

  /**
   * 스마트 태그 추천
   */
  async suggestTags(filePath: string, content?: string): Promise<{
    suggested: Tag[];
    reasons: string[];
  }> {
    
    if (!content) {
      try {
        content = await fs.readFile(filePath, 'utf-8');
      } catch {
        return { suggested: [], reasons: ['파일을 읽을 수 없습니다'] };
      }
    }

    const suggestions: Tag[] = [];
    const reasons: string[] = [];

    // 1. 유사한 파일의 태그 분석
    const similarFiles = await this.findSimilarFiles(content);
    if (similarFiles.length > 0) {
      const commonTags = this.extractCommonTags(similarFiles);
      suggestions.push(...commonTags);
      reasons.push(`유사한 ${similarFiles.length}개 파일에서 공통 태그 추출`);
    }

    // 2. 콘텐츠 패턴 기반 추천
    const patternTags = this.generatePatternTags(filePath, content);
    suggestions.push(...patternTags);
    reasons.push('파일 경로 및 콘텐츠 패턴 분석');

    // 3. 트렌딩 태그 추천
    const trendingTags = this.getTrendingTags();
    const relevantTrending = trendingTags.filter(tag => 
      content.toLowerCase().includes(tag.name.toLowerCase())
    );
    suggestions.push(...relevantTrending);
    if (relevantTrending.length > 0) {
      reasons.push('최근 트렌딩 태그 중 관련성 높은 태그');
    }

    // 4. 중복 제거 및 정규화
    const uniqueSuggestions = this.mergeTags(suggestions).slice(0, 10);

    return {
      suggested: uniqueSuggestions,
      reasons
    };
  }

  /**
   * 태깅 통계 및 분석
   */
  getTagAnalytics(): TagAnalytics {
    const tagCounts = new Map<string, number>();
    const categoryCount = new Map<string, number>();
    const contentTypeCount = new Map<ContentType, number>();

    // 기본 통계 수집
    for (const result of this.tagHistory) {
      // 태그 빈도
      for (const tag of result.tags) {
        tagCounts.set(tag.name, (tagCounts.get(tag.name) || 0) + 1);
      }

      // 카테고리 분포
      for (const category of result.categories) {
        categoryCount.set(category.name, (categoryCount.get(category.name) || 0) + 1);
      }

      // 콘텐츠 타입 분포
      contentTypeCount.set(result.contentType, (contentTypeCount.get(result.contentType) || 0) + 1);
    }

    // 최다 사용 태그
    const mostUsedTags = Array.from(tagCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([tag, count]) => ({
        tag,
        count,
        trend: this.calculateTagTrend(tag) as 'rising' | 'stable' | 'declining'
      }));

    // 태그 상관관계
    const tagCorrelations = this.calculateTagCorrelations().slice(0, 10);

    return {
      mostUsedTags,
      categoryDistribution: Object.fromEntries(categoryCount),
      contentTypeBreakdown: this.createContentTypeBreakdown(contentTypeCount),
      tagCorrelations,
      temporalTrends: this.calculateTemporalTrends()
    };
  }

  // ======= Private Methods =======

  private async generateAITags(content: string, filePath: string): Promise<Tag[]> {
    if (!content.trim()) return [];

    try {
      // OpenAI를 이용한 태그 생성 (임베딩 기반)
      const embedding = await this.embeddingService.getEmbedding({ 
        text: content.substring(0, 4000) // 토큰 제한
      });

      // 기존 태그들과의 유사도를 통한 추천
      const existingTags = Array.from(this.tagVocabulary.keys());
      const similarTags: Tag[] = [];

      for (const existingTag of existingTags) {
        const tagEmbedding = await this.embeddingService.getEmbedding({ text: existingTag });
        const similarity = this.embeddingService.cosineSimilarity(
          embedding.embedding,
          tagEmbedding.embedding
        );

        if (similarity > 0.7) { // 높은 유사도
          similarTags.push({
            name: existingTag,
            weight: similarity,
            type: this.inferTagType(existingTag),
            source: 'ai'
          });
        }
      }

      // 콘텐츠에서 직접 키워드 추출
      const extractedTags = this.extractKeywords(content);
      
      return [...similarTags, ...extractedTags].slice(0, 8);

    } catch (error) {
      console.warn('AI 태깅 실패:', error);
      return this.extractKeywords(content);
    }
  }

  private generatePatternTags(filePath: string, content: string): Tag[] {
    const tags: Tag[] = [];

    // 파일 확장자 기반
    const ext = filePath.split('.').pop()?.toLowerCase();
    if (ext) {
      const techTags = {
        'md': ['markdown', 'documentation'],
        'ts': ['typescript', 'code', 'javascript'],
        'js': ['javascript', 'code'],
        'py': ['python', 'code'],
        'json': ['data', 'configuration'],
        'yaml': ['configuration', 'deployment'],
        'yml': ['configuration', 'deployment']
      };

      const extTags = techTags[ext as keyof typeof techTags] || [];
      tags.push(...extTags.map(tag => ({
        name: tag,
        weight: 0.8,
        type: 'technology' as const,
        source: 'pattern' as const
      })));
    }

    // 경로 기반 태깅
    const pathParts = filePath.toLowerCase().split(/[/\\]/);
    const pathKeywords = ['src', 'docs', 'test', 'config', 'lib', 'components', 'services', 'utils'];
    
    for (const keyword of pathKeywords) {
      if (pathParts.includes(keyword)) {
        tags.push({
          name: keyword,
          weight: 0.7,
          type: 'project',
          source: 'pattern'
        });
      }
    }

    // 콘텐츠 패턴 기반
    const contentPatterns = [
      { pattern: /TODO|FIXME|BUG/i, tag: 'todo', type: 'action' as const },
      { pattern: /API|endpoint|request/i, tag: 'api', type: 'technology' as const },
      { pattern: /test|spec|describe|it\(/i, tag: 'testing', type: 'technology' as const },
      { pattern: /meeting|agenda|discussion/i, tag: 'meeting', type: 'action' as const },
      { pattern: /design|mockup|wireframe/i, tag: 'design', type: 'concept' as const }
    ];

    for (const { pattern, tag, type } of contentPatterns) {
      if (pattern.test(content)) {
        tags.push({
          name: tag,
          weight: 0.6,
          type,
          source: 'pattern'
        });
      }
    }

    return tags;
  }

  private applyTaggingRules(filePath: string, content: string): Tag[] {
    const tags: Tag[] = [];

    for (const rule of this.taggingRules) {
      let matches = true;

      // 파일 패턴 체크
      if (rule.condition.filePattern && !rule.condition.filePattern.test(filePath)) {
        matches = false;
      }

      // 콘텐츠 패턴 체크
      if (rule.condition.contentPattern && !rule.condition.contentPattern.test(content)) {
        matches = false;
      }

      // 키워드 체크
      if (rule.condition.keywords) {
        const hasKeywords = rule.condition.keywords.some(keyword =>
          content.toLowerCase().includes(keyword.toLowerCase())
        );
        if (!hasKeywords) matches = false;
      }

      if (matches && rule.action.addTags) {
        tags.push(...rule.action.addTags.map(tag => ({
          name: tag,
          weight: 0.9,
          type: 'concept' as const,
          source: 'manual' as const
        })));
      }
    }

    return tags;
  }

  private detectContentType(filePath: string, content: string): ContentType {
    // 파일 확장자 기반
    if (filePath.match(/\.(md|txt|doc|docx)$/i)) {
      if (content.match(/# |## |### /)) return 'documentation';
      if (content.match(/meeting|agenda|minutes/i)) return 'meeting_notes';
      if (content.match(/plan|roadmap|strategy/i)) return 'planning';
      return 'documentation';
    }

    if (filePath.match(/\.(js|ts|py|java|cpp|c|h)$/i)) {
      return 'code';
    }

    if (filePath.match(/\.(json|yaml|yml|xml)$/i)) {
      return 'reference';
    }

    // 콘텐츠 기반
    for (const [type, patterns] of this.categoryPatterns) {
      if (patterns.some(pattern => pattern.test(content))) {
        return type;
      }
    }

    return 'unknown';
  }

  private mergeTags(tags: Tag[]): Tag[] {
    const tagMap = new Map<string, Tag>();

    for (const tag of tags) {
      const key = tag.name.toLowerCase();
      
      if (tagMap.has(key)) {
        const existing = tagMap.get(key)!;
        // 더 높은 가중치와 더 신뢰할 만한 소스를 선택
        if (tag.weight > existing.weight || 
           (tag.weight === existing.weight && this.getSourcePriority(tag.source) > this.getSourcePriority(existing.source))) {
          tagMap.set(key, tag);
        }
      } else {
        tagMap.set(key, tag);
      }
    }

    return Array.from(tagMap.values())
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 15); // 최대 15개 태그
  }

  private determineCategories(contentType: ContentType, tags: Tag[], content: string): Category[] {
    const categories: Category[] = [];

    // 주 카테고리 (콘텐츠 타입 기반)
    categories.push({
      name: contentType,
      confidence: 0.8
    });

    // 태그 기반 추가 카테고리
    const projectTags = tags.filter(t => t.type === 'project');
    if (projectTags.length > 0) {
      categories.push({
        name: 'project_specific',
        confidence: 0.7,
        subcategory: projectTags[0].name
      });
    }

    return categories;
  }

  private calculateOverallConfidence(tags: Tag[], categories: Category[]): number {
    if (tags.length === 0) return 0;

    const avgTagWeight = tags.reduce((sum, tag) => sum + tag.weight, 0) / tags.length;
    const avgCategoryConfidence = categories.reduce((sum, cat) => sum + cat.confidence, 0) / categories.length;

    return (avgTagWeight + avgCategoryConfidence) / 2;
  }

  private extractKeywords(content: string): Tag[] {
    // 간단한 키워드 추출 (실제로는 더 정교한 NLP 필요)
    const words = content.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(word => word.length > 3)
      .filter(word => !this.isStopWord(word));

    const wordFreq = new Map<string, number>();
    for (const word of words) {
      wordFreq.set(word, (wordFreq.get(word) || 0) + 1);
    }

    return Array.from(wordFreq.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([word, freq]) => ({
        name: word,
        weight: Math.min(freq / words.length * 10, 1),
        type: 'concept' as const,
        source: 'ai' as const
      }));
  }

  private isStopWord(word: string): boolean {
    const stopWords = new Set([
      'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
      'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
      'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'
    ]);
    return stopWords.has(word.toLowerCase());
  }

  private inferTagType(tag: string): Tag['type'] {
    const patterns = {
      technology: /^(javascript|typescript|python|react|node|api|database|sql|html|css)$/i,
      project: /^(argo|layer|phase|system|core)$/i,
      action: /^(todo|bug|fix|test|review|meeting)$/i,
      person: /^(developer|manager|user|client|team)$/i,
      concept: /^(architecture|design|pattern|strategy|plan)$/i
    };

    for (const [type, pattern] of Object.entries(patterns)) {
      if (pattern.test(tag)) {
        return type as Tag['type'];
      }
    }

    return 'topic';
  }

  private getSourcePriority(source: Tag['source']): number {
    const priorities = { manual: 4, ai: 3, pattern: 2, inherited: 1 };
    return priorities[source] || 0;
  }

  private calculateTagRelevanceScore(tags: Tag[], searchTags: string[]): number {
    const searchTagsLower = searchTags.map(t => t.toLowerCase());
    let score = 0;

    for (const tag of tags) {
      if (searchTagsLower.includes(tag.name.toLowerCase())) {
        score += tag.weight;
      }
    }

    return score / searchTags.length;
  }

  private async findSimilarFiles(content: string): Promise<TaggingResult[]> {
    // 임베딩 기반 유사 파일 찾기 (간소화된 구현)
    return this.tagHistory
      .filter(result => result.confidence > 0.6)
      .slice(0, 5);
  }

  private extractCommonTags(results: TaggingResult[]): Tag[] {
    const tagCounts = new Map<string, { count: number; avgWeight: number; types: Set<string> }>();

    for (const result of results) {
      for (const tag of result.tags) {
        const key = tag.name.toLowerCase();
        const current = tagCounts.get(key) || { count: 0, avgWeight: 0, types: new Set() };
        
        current.count++;
        current.avgWeight = (current.avgWeight * (current.count - 1) + tag.weight) / current.count;
        current.types.add(tag.type);
        
        tagCounts.set(key, current);
      }
    }

    return Array.from(tagCounts.entries())
      .filter(([, stats]) => stats.count >= Math.max(1, results.length * 0.3)) // 30% 이상의 파일에서 등장
      .sort((a, b) => b[1].avgWeight - a[1].avgWeight)
      .slice(0, 8)
      .map(([name, stats]) => ({
        name,
        weight: stats.avgWeight,
        type: Array.from(stats.types)[0] as Tag['type'], // 첫 번째 타입 사용
        source: 'inherited' as const
      }));
  }

  private getTrendingTags(): Tag[] {
    // 최근 1주일 데이터에서 트렌딩 태그 추출
    const oneWeekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const recentResults = this.tagHistory.filter(r => r.timestamp > oneWeekAgo);

    const tagFreq = new Map<string, number>();
    for (const result of recentResults) {
      for (const tag of result.tags) {
        tagFreq.set(tag.name, (tagFreq.get(tag.name) || 0) + 1);
      }
    }

    return Array.from(tagFreq.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, freq]) => ({
        name,
        weight: freq / recentResults.length,
        type: 'topic' as const,
        source: 'inherited' as const
      }));
  }

  private calculateTagTrend(tag: string): 'rising' | 'stable' | 'declining' {
    // 간단한 트렌드 계산 (최근 vs 이전 기간 비교)
    const now = Date.now();
    const oneWeekAgo = now - 7 * 24 * 60 * 60 * 1000;
    const twoWeeksAgo = now - 14 * 24 * 60 * 60 * 1000;

    const recentCount = this.tagHistory
      .filter(r => r.timestamp.getTime() > oneWeekAgo)
      .reduce((count, r) => count + (r.tags.some(t => t.name === tag) ? 1 : 0), 0);

    const previousCount = this.tagHistory
      .filter(r => r.timestamp.getTime() > twoWeeksAgo && r.timestamp.getTime() <= oneWeekAgo)
      .reduce((count, r) => count + (r.tags.some(t => t.name === tag) ? 1 : 0), 0);

    if (recentCount > previousCount * 1.2) return 'rising';
    if (recentCount < previousCount * 0.8) return 'declining';
    return 'stable';
  }

  private calculateTagCorrelations(): Array<{tag1: string, tag2: string, correlation: number}> {
    const correlations: Array<{tag1: string, tag2: string, correlation: number}> = [];
    const tagNames = Array.from(this.tagVocabulary.keys());

    for (let i = 0; i < tagNames.length; i++) {
      for (let j = i + 1; j < tagNames.length; j++) {
        const tag1 = tagNames[i];
        const tag2 = tagNames[j];
        
        const cooccurrence = this.tagHistory.filter(r => 
          r.tags.some(t => t.name === tag1) && r.tags.some(t => t.name === tag2)
        ).length;

        const tag1Count = this.tagHistory.filter(r => r.tags.some(t => t.name === tag1)).length;
        const tag2Count = this.tagHistory.filter(r => r.tags.some(t => t.name === tag2)).length;

        if (tag1Count > 0 && tag2Count > 0) {
          const correlation = cooccurrence / Math.sqrt(tag1Count * tag2Count);
          
          if (correlation > 0.3) { // 의미있는 상관관계만
            correlations.push({ tag1, tag2, correlation });
          }
        }
      }
    }

    return correlations.sort((a, b) => b.correlation - a.correlation);
  }

  private calculateTemporalTrends(): Array<{period: string, tags: Record<string, number>}> {
    // 주별 태그 트렌드
    const trends: Array<{period: string, tags: Record<string, number>}> = [];
    const now = new Date();
    
    for (let week = 0; week < 8; week++) {
      const weekStart = new Date(now.getTime() - (week + 1) * 7 * 24 * 60 * 60 * 1000);
      const weekEnd = new Date(now.getTime() - week * 7 * 24 * 60 * 60 * 1000);
      
      const weekResults = this.tagHistory.filter(r => 
        r.timestamp >= weekStart && r.timestamp < weekEnd
      );

      const weekTags: Record<string, number> = {};
      for (const result of weekResults) {
        for (const tag of result.tags) {
          weekTags[tag.name] = (weekTags[tag.name] || 0) + 1;
        }
      }

      trends.unshift({
        period: `${weekStart.toISOString().split('T')[0]} ~ ${weekEnd.toISOString().split('T')[0]}`,
        tags: weekTags
      });
    }

    return trends;
  }

  private updateTagVocabulary(tags: Tag[]): void {
    for (const tag of tags) {
      this.tagVocabulary.set(tag.name, (this.tagVocabulary.get(tag.name) || 0) + 1);
    }
  }

  private initializeDefaultRules(): void {
    this.taggingRules = [
      {
        id: 'argo-project',
        name: 'ARGO Project Files',
        condition: {
          filePattern: /ARGO/i,
          keywords: ['argo', 'layer', 'blueprint']
        },
        action: {
          addTags: ['argo', 'project', 'core'],
          setCategory: 'project_specific'
        },
        priority: 10
      },
      {
        id: 'documentation',
        name: 'Documentation Files',
        condition: {
          filePattern: /\.(md|txt|doc)$/i,
          contentPattern: /^#\s/m
        },
        action: {
          addTags: ['documentation'],
          setContentType: 'documentation'
        },
        priority: 5
      }
    ];
  }

  private initializeCategoryPatterns(): void {
    this.categoryPatterns.set('code', [
      /function\s+\w+/,
      /class\s+\w+/,
      /import\s+.*from/,
      /const\s+\w+\s*=/
    ]);

    this.categoryPatterns.set('meeting_notes', [
      /meeting|agenda|minutes/i,
      /attendees?:|participants?:/i,
      /action\s+items?/i
    ]);

    this.categoryPatterns.set('planning', [
      /roadmap|timeline|milestone/i,
      /phase\s+\d+/i,
      /week\s+\d+/i,
      /goals?|objectives?/i
    ]);
  }

  private async loadTaggingHistory(): Promise<void> {
    try {
      await fs.mkdir('C:\\Argo-813\\data', { recursive: true });
      
      const data = await fs.readFile(this.historyFile, 'utf-8');
      this.tagHistory = JSON.parse(data);
      
      // Date 객체 복원
      this.tagHistory.forEach(result => {
        result.timestamp = new Date(result.timestamp);
      });

      // 태그 어휘 재구성
      for (const result of this.tagHistory) {
        this.updateTagVocabulary(result.tags);
      }
      
      console.log(`📂 태깅 히스토리 로드: ${this.tagHistory.length}개 결과`);

    } catch (error) {
      console.log('📝 새로운 태깅 히스토리 생성');
      this.tagHistory = [];
    }
  }

  private async saveTaggingHistory(): Promise<void> {
    try {
      await fs.writeFile(this.historyFile, JSON.stringify(this.tagHistory, null, 2));
    } catch (error) {
      console.warn('태깅 히스토리 저장 실패:', error);
    }
  }

  private async loadTaggingRules(): Promise<void> {
    try {
      const data = await fs.readFile(this.rulesFile, 'utf-8');
      const rules = JSON.parse(data);
      
      // RegExp 객체 복원
      this.taggingRules = rules.map((rule: any) => ({
        ...rule,
        condition: {
          ...rule.condition,
          filePattern: rule.condition.filePattern ? new RegExp(rule.condition.filePattern.source, rule.condition.filePattern.flags) : undefined,
          contentPattern: rule.condition.contentPattern ? new RegExp(rule.condition.contentPattern.source, rule.condition.contentPattern.flags) : undefined
        }
      }));
      
      console.log(`📂 태깅 규칙 로드: ${this.taggingRules.length}개 규칙`);

    } catch (error) {
      console.log('📝 기본 태깅 규칙 사용');
      // 기본 규칙은 이미 초기화됨
    }
  }

  private createContentTypeBreakdown(contentTypeCount: Map<string, number>): Record<ContentType, number> {
    const breakdown: Record<ContentType, number> = {
      documentation: 0,
      code: 0,
      design: 0,
      meeting_notes: 0,
      planning: 0,
      research: 0,
      personal: 0,
      reference: 0,
      unknown: 0
    };

    contentTypeCount.forEach((count, type) => {
      if (type in breakdown) {
        breakdown[type as ContentType] = count;
      } else {
        breakdown.unknown += count;
      }
    });

    return breakdown;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export {
  AutoTaggingService,
  TaggingResult,
  Tag,
  Category,
  ContentType,
  TaggingRule,
  TagAnalytics
};