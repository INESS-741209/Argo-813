/**
 * ARGO Layer 1: Predictive Engine - 예측적 통찰 제공
 * 블루프린트: "Director가 요청하기 전에 필요한 정보를 미리 준비"
 * 
 * 핵심 혁신: Temporal Pattern Recognition + Context Anticipation + Proactive Loading
 */

import { EventEmitter } from 'events';
import { IntelligentNode } from '../knowledge-mesh/intelligent-node.js';
import { SynapticNetwork, InteractionQuality } from '../synaptic-network/synaptic-network.js';

interface WorkContext {
  currentTask: string;
  activeFiles: string[]; // 현재 열린 파일들
  recentQueries: string[]; // 최근 질의들
  timeOfDay: 'morning' | 'afternoon' | 'evening' | 'night';
  dayOfWeek: string;
  currentProject?: string;
}

interface PredictiveInsight {
  type: 'proactive_suggestion' | 'context_expansion' | 'missing_link' | 'optimization_opportunity';
  content: string;
  relevantNodes: string[];
  confidence: number; // 0-1
  priority: 'low' | 'medium' | 'high' | 'critical';
  reasoningChain: string[];
  suggestedAction: string;
  estimatedValue: number; // 예상 시간 절약(분)
}

interface PreloadManifest {
  nodeIds: string[];
  priority: number;
  estimatedLoadTime: number; // ms
  cacheKey: string;
  validUntil: Date;
}

interface TemporalPattern {
  timePattern: string; // "09:00-11:00" 같은 시간대
  dayPattern: string; // "Monday,Tuesday" 같은 요일 패턴  
  associatedTasks: string[];
  frequency: number;
  avgDuration: number; // 분 단위
  typicalFiles: string[];
  confidence: number;
}

/**
 * Predictive Engine - Director의 미래 니즈를 예측하는 지능 시스템
 * 블루프린트: "선제적 정보 제안 + 맥락 예측 및 선제적 정보 서피싱"
 */
class PredictiveEngine extends EventEmitter {
  private network: SynapticNetwork;
  private currentContext: WorkContext | null;
  private temporalPatterns: Map<string, TemporalPattern>;
  private preloadCache: Map<string, any>;
  private insightHistory: PredictiveInsight[];
  private predictionAccuracy: Map<string, number>; // 예측 정확도 추적
  
  constructor(network: SynapticNetwork) {
    super();
    this.network = network;
    this.currentContext = null;
    this.temporalPatterns = new Map();
    this.preloadCache = new Map();
    this.insightHistory = [];
    this.predictionAccuracy = new Map();
    
    // 정기적 예측 업데이트 (5분마다)
    setInterval(() => this.updatePredictions(), 5 * 60 * 1000);
    
    // 캐시 정리 (30분마다)
    setInterval(() => this.cleanupCache(), 30 * 60 * 1000);
  }

  /**
   * 현재 작업 컨텍스트 업데이트
   */
  updateContext(context: WorkContext): void {
    const previousContext = this.currentContext;
    this.currentContext = context;
    
    // 시간적 패턴 학습
    this.learnTemporalPattern(context);
    
    // 컨텍스트 변화 감지 및 예측 업데이트
    if (this.hasSignificantContextChange(previousContext, context)) {
      this.triggerPredictionUpdate();
    }
    
    this.emit('contextUpdated', { previous: previousContext, current: context });
  }

  /**
   * 핵심 기능: 선제적 통찰 생성
   * Director의 현재 상황을 분석하여 필요할 정보를 미리 제안
   */
  generateProactiveInsights(): PredictiveInsight[] {
    if (!this.currentContext) return [];

    const insights: PredictiveInsight[] = [];
    
    // 1. 현재 작업 기반 확장 제안
    insights.push(...this.generateContextExpansion());
    
    // 2. 누락된 연결 고리 식별
    insights.push(...this.identifyMissingLinks());
    
    // 3. 시간 기반 작업 예측
    insights.push(...this.generateTimeBasedSuggestions());
    
    // 4. 최적화 기회 발견
    insights.push(...this.identifyOptimizationOpportunities());
    
    // 5. 정확도 기반 정렬 및 필터링
    const rankedInsights = insights
      .sort((a, b) => b.confidence * b.estimatedValue - a.confidence * a.estimatedValue)
      .slice(0, 10); // 상위 10개만
    
    // 6. 인사이트 히스토리 업데이트
    this.insightHistory.push(...rankedInsights);
    this.insightHistory = this.insightHistory.slice(-100); // 최근 100개만 유지
    
    return rankedInsights;
  }

  /**
   * 백그라운드 리소스 사전 로딩
   * Director가 요청하기 전에 필요할 파일들을 미리 캐시
   */
  async preloadResources(currentNodeId: string): Promise<PreloadManifest> {
    const predictedNodes = this.network.predictNextNodes(
      currentNodeId, 
      this.currentContext?.currentTask ? [this.currentContext.currentTask] : []
    );
    
    const prioritizedNodes = this.prioritizePreloadTargets(predictedNodes);
    const cacheKey = this.generateCacheKey(currentNodeId, prioritizedNodes);
    
    // 이미 캐시된 경우 기존 매니페스트 반환
    if (this.preloadCache.has(cacheKey)) {
      return this.preloadCache.get(cacheKey);
    }
    
    const manifest: PreloadManifest = {
      nodeIds: prioritizedNodes,
      priority: this.calculateOverallPriority(prioritizedNodes),
      estimatedLoadTime: prioritizedNodes.length * 50, // 노드당 평균 50ms 가정
      cacheKey,
      validUntil: new Date(Date.now() + 30 * 60 * 1000) // 30분 유효
    };
    
    // 백그라운드에서 비동기 로딩 시작
    this.backgroundLoad(prioritizedNodes);
    
    this.preloadCache.set(cacheKey, manifest);
    return manifest;
  }

  /**
   * 예측 정확도 피드백 처리
   * Director의 실제 행동과 예측을 비교하여 모델 개선
   */
  recordPredictionFeedback(predictionId: string, actualOutcome: 'helpful' | 'irrelevant' | 'harmful'): void {
    const accuracy = this.predictionAccuracy.get(predictionId) || 0.5;
    
    let newAccuracy: number;
    switch (actualOutcome) {
      case 'helpful':
        newAccuracy = Math.min(accuracy + 0.1, 1.0);
        break;
      case 'irrelevant':
        newAccuracy = accuracy * 0.9;
        break;
      case 'harmful':
        newAccuracy = Math.max(accuracy - 0.2, 0.0);
        break;
    }
    
    this.predictionAccuracy.set(predictionId, newAccuracy);
    
    // 전체 시스템 학습에 반영
    this.adjustPredictionModel(predictionId, actualOutcome);
    
    this.emit('feedbackProcessed', {
      predictionId,
      outcome: actualOutcome,
      newAccuracy,
      timestamp: new Date()
    });
  }

  /**
   * Director의 작업 패턴 분석 리포트
   */
  generateWorkPatternAnalysis() {
    const patterns = Array.from(this.temporalPatterns.values())
      .sort((a, b) => b.confidence - a.confidence);
    
    const mostProductiveTime = this.findMostProductiveTimeSlot();
    const commonWorkflows = this.identifyCommonWorkflows();
    const improvementSuggestions = this.generateImprovementSuggestions();
    
    return {
      temporalPatterns: patterns.slice(0, 5), // 상위 5개 패턴
      mostProductiveTime,
      commonWorkflows,
      improvementSuggestions,
      predictionAccuracy: this.calculateOverallAccuracy(),
      generatedAt: new Date()
    };
  }

  // ======= Private Methods =======

  private generateContextExpansion(): PredictiveInsight[] {
    if (!this.currentContext) return [];

    const insights: PredictiveInsight[] = [];
    const currentTask = this.currentContext.currentTask;
    
    // 현재 작업과 관련된 추가 리소스 제안
    const relatedNodes = this.findRelatedResources(currentTask);
    
    if (relatedNodes.length > 0) {
      insights.push({
        type: 'context_expansion',
        content: `현재 작업 "${currentTask}"와 관련된 ${relatedNodes.length}개의 추가 리소스를 발견했습니다.`,
        relevantNodes: relatedNodes,
        confidence: 0.7,
        priority: 'medium',
        reasoningChain: [
          '현재 작업 컨텍스트 분석',
          '의미적 유사성 기반 검색',
          '관련성 스코어링 및 필터링'
        ],
        suggestedAction: '관련 파일들을 검토하여 작업 품질을 높이세요.',
        estimatedValue: relatedNodes.length * 5 // 파일당 5분 절약 추정
      });
    }

    return insights;
  }

  private identifyMissingLinks(): PredictiveInsight[] {
    const insights: PredictiveInsight[] = [];
    
    if (!this.currentContext || this.currentContext.activeFiles.length < 2) return insights;
    
    // 현재 활성 파일들 간의 약한 연결 찾기
    const activeNodes = this.currentContext.activeFiles;
    const weakConnections = this.findWeakConnections(activeNodes);
    
    if (weakConnections.length > 0) {
      insights.push({
        type: 'missing_link',
        content: `현재 작업 중인 파일들 사이에 놓치고 있는 연결고리가 있을 수 있습니다.`,
        relevantNodes: weakConnections,
        confidence: 0.6,
        priority: 'medium',
        reasoningChain: [
          '활성 파일들 간의 연결성 분석',
          '약한 연결 또는 누락된 연결 식별',
          '잠재적 연결 가치 평가'
        ],
        suggestedAction: '추천된 파일들을 검토하여 통합적 관점을 얻으세요.',
        estimatedValue: 15 // 통합적 사고로 15분 절약
      });
    }

    return insights;
  }

  private generateTimeBasedSuggestions(): PredictiveInsight[] {
    const insights: PredictiveInsight[] = [];
    
    if (!this.currentContext) return insights;
    
    const currentTime = new Date();
    const timeSlot = this.getTimeSlot(currentTime);
    const dayOfWeek = this.currentContext.dayOfWeek;
    
    // 시간대별 일반적인 작업 패턴 찾기
    const typicalTasks = this.getTypicalTasksForTime(timeSlot, dayOfWeek);
    
    if (typicalTasks.length > 0) {
      insights.push({
        type: 'proactive_suggestion',
        content: `${timeSlot} 시간대에 보통 ${typicalTasks[0]}를 작업하시는데, 관련 파일들을 미리 준비했습니다.`,
        relevantNodes: this.getFilesForTasks(typicalTasks),
        confidence: 0.8,
        priority: 'high',
        reasoningChain: [
          `${timeSlot} 시간대 패턴 분석`,
          '과거 작업 이력 기반 예측',
          '관련 파일 식별 및 준비'
        ],
        suggestedAction: '준비된 파일들을 활용하여 효율적으로 작업을 시작하세요.',
        estimatedValue: 10 // 준비 시간 10분 절약
      });
    }

    return insights;
  }

  private identifyOptimizationOpportunities(): PredictiveInsight[] {
    const insights: PredictiveInsight[] = [];
    
    // 네트워크 인사이트를 활용한 최적화 기회 찾기
    const networkInsights = this.network.generateNetworkInsights();
    
    networkInsights.forEach(insight => {
      if (insight.importance > 0.7) {
        insights.push({
          type: 'optimization_opportunity',
          content: insight.description,
          relevantNodes: [insight.nodeId],
          confidence: insight.importance,
          priority: insight.importance > 0.8 ? 'high' : 'medium',
          reasoningChain: [
            '네트워크 구조 분석',
            `${insight.type} 노드 식별`,
            '최적화 기회 평가'
          ],
          suggestedAction: insight.suggestedAction,
          estimatedValue: Math.floor(insight.importance * 20) // 중요도에 비례한 시간 절약
        });
      }
    });

    return insights;
  }

  private learnTemporalPattern(context: WorkContext): void {
    const now = new Date();
    const timeSlot = this.getTimeSlot(now);
    const patternKey = `${timeSlot}_${context.dayOfWeek}`;
    
    const existing = this.temporalPatterns.get(patternKey);
    
    if (existing) {
      // 기존 패턴 업데이트
      existing.frequency += 1;
      existing.associatedTasks.push(context.currentTask);
      existing.typicalFiles.push(...context.activeFiles);
      existing.confidence = Math.min(existing.confidence + 0.01, 1.0);
      
      // 중복 제거
      existing.associatedTasks = [...new Set(existing.associatedTasks)];
      existing.typicalFiles = [...new Set(existing.typicalFiles)];
    } else {
      // 새 패턴 생성
      this.temporalPatterns.set(patternKey, {
        timePattern: timeSlot,
        dayPattern: context.dayOfWeek,
        associatedTasks: [context.currentTask],
        frequency: 1,
        avgDuration: 60, // 기본값 60분
        typicalFiles: [...context.activeFiles],
        confidence: 0.1
      });
    }
  }

  private hasSignificantContextChange(prev: WorkContext | null, current: WorkContext): boolean {
    if (!prev) return true;
    
    return (
      prev.currentTask !== current.currentTask ||
      prev.currentProject !== current.currentProject ||
      prev.activeFiles.length !== current.activeFiles.length ||
      prev.activeFiles.some(file => !current.activeFiles.includes(file))
    );
  }

  private triggerPredictionUpdate(): void {
    // 컨텍스트 변화에 따른 예측 재계산
    setTimeout(() => {
      const insights = this.generateProactiveInsights();
      this.emit('predictionsUpdated', { insights, timestamp: new Date() });
    }, 100); // 100ms 디바운싱
  }

  private updatePredictions(): void {
    if (this.currentContext) {
      const insights = this.generateProactiveInsights();
      this.emit('predictionsGenerated', { insights });
    }
  }

  private cleanupCache(): void {
    const now = new Date();
    
    this.preloadCache.forEach((manifest, key) => {
      if (manifest.validUntil < now) {
        this.preloadCache.delete(key);
      }
    });
  }

  // 더 많은 유틸리티 메소드들...
  private getTimeSlot(date: Date): string {
    const hour = date.getHours();
    if (hour < 6) return 'night';
    if (hour < 12) return 'morning';
    if (hour < 18) return 'afternoon';
    return 'evening';
  }

  private findRelatedResources(task: string): string[] {
    // 작업명을 기반으로 관련 리소스 찾기 (실제 구현에서는 더 정교한 검색)
    const relatedNodes: string[] = [];
    
    this.network['nodes'].forEach((node, nodeId) => {
      const relevance = node.predictRelevance(task);
      if (relevance.score > 0.6) {
        relatedNodes.push(nodeId);
      }
    });
    
    return relatedNodes.slice(0, 5);
  }

  private findWeakConnections(activeNodes: string[]): string[] {
    // 활성 노드들 사이의 약한 연결 찾기
    const suggestions: string[] = [];
    // 구현 로직...
    return suggestions;
  }

  private getTypicalTasksForTime(timeSlot: string, dayOfWeek: string): string[] {
    const pattern = this.temporalPatterns.get(`${timeSlot}_${dayOfWeek}`);
    return pattern ? pattern.associatedTasks.slice(0, 3) : [];
  }

  private getFilesForTasks(tasks: string[]): string[] {
    const files: string[] = [];
    // 작업에 관련된 파일들 찾기
    return files;
  }

  private prioritizePreloadTargets(nodes: string[]): string[] {
    // 사전 로딩 대상 우선순위 결정
    return nodes.slice(0, 5); // 상위 5개
  }

  private calculateOverallPriority(nodes: string[]): number {
    // 전체 우선순위 계산
    return nodes.length * 0.2;
  }

  private generateCacheKey(currentNode: string, predictedNodes: string[]): string {
    return `${currentNode}:${predictedNodes.join(',')}`;
  }

  private async backgroundLoad(nodeIds: string[]): Promise<void> {
    // 백그라운드에서 비동기 로딩
    // 실제 구현에서는 파일 내용을 미리 읽어서 캐시
  }

  private adjustPredictionModel(predictionId: string, outcome: string): void {
    // 예측 모델 조정 로직
  }

  private findMostProductiveTimeSlot(): string {
    // 가장 생산적인 시간대 찾기
    return 'morning';
  }

  private identifyCommonWorkflows(): string[] {
    // 일반적인 워크플로우 식별
    return [];
  }

  private generateImprovementSuggestions(): string[] {
    // 개선 제안 생성
    return [];
  }

  private calculateOverallAccuracy(): number {
    const accuracyValues = Array.from(this.predictionAccuracy.values());
    return accuracyValues.length > 0 
      ? accuracyValues.reduce((sum, acc) => sum + acc, 0) / accuracyValues.length 
      : 0.5;
  }
}

export {
  PredictiveEngine,
  WorkContext,
  PredictiveInsight,
  PreloadManifest,
  TemporalPattern
};