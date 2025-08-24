/**
 * ARGO Layer 1: Intelligent Node Implementation
 * 지식 메시의 핵심 노드 클래스
 */

import { FileContent, Tag, Category, ContentType } from '../types/common.js';

export interface NodeConnection {
  targetNodeId: string;
  strength: number;
  type: 'semantic' | 'temporal' | 'spatial' | 'causal';
  metadata: Record<string, any>;
}

export interface NodeMetrics {
  centrality: number;
  clusteringCoefficient: number;
  betweenness: number;
  pagerank: number;
}

export interface RelevanceScore {
  score: number;
  factors: string[];
  confidence: number;
  timestamp: Date;
}

export class IntelligentNode {
  public id: string;
  public content: FileContent;
  public tags: Tag[];
  public categories: Category[];
  public connections: Map<string, NodeConnection>;
  public metrics: NodeMetrics;
  public lastModified: Date;
  public accessCount: number;
  public confidence: number;

  constructor(
    id: string,
    content: FileContent,
    tags: Tag[] = [],
    categories: Category[] = []
  ) {
    this.id = id;
    this.content = content;
    this.tags = tags;
    this.categories = categories;
    this.connections = new Map();
    this.metrics = {
      centrality: 0,
      clusteringCoefficient: 0,
      betweenness: 0,
      pagerank: 0
    };
    this.lastModified = new Date();
    this.accessCount = 0;
    this.confidence = 1.0;
  }

  // 노드 연결 관리
  public addConnection(targetNodeId: string, connection: NodeConnection): void {
    this.connections.set(targetNodeId, connection);
  }

  public removeConnection(targetNodeId: string): boolean {
    return this.connections.delete(targetNodeId);
  }

  public getConnection(targetNodeId: string): NodeConnection | undefined {
    return this.connections.get(targetNodeId);
  }

  public getConnectedNodes(minStrength: number = 0): string[] {
    return Array.from(this.connections.entries())
      .filter(([_, connection]) => connection.strength >= minStrength)
      .map(([targetId, _]) => targetId);
  }

  // 태그 및 카테고리 관리
  public addTag(tag: Tag): void {
    if (!this.tags.find(t => t.name === tag.name)) {
      this.tags.push(tag);
    }
  }

  public removeTag(tagName: string): boolean {
    const index = this.tags.findIndex(t => t.name === tagName);
    if (index !== -1) {
      this.tags.splice(index, 1);
      return true;
    }
    return false;
  }

  public addCategory(category: Category): void {
    if (!this.categories.find(c => c.name === category.name)) {
      this.categories.push(category);
    }
  }

  // 메트릭 업데이트
  public updateMetrics(newMetrics: Partial<NodeMetrics>): void {
    this.metrics = { ...this.metrics, ...newMetrics };
  }

  // 접근 기록
  public recordAccess(): void {
    this.accessCount++;
    this.lastModified = new Date();
  }

  // 신뢰도 조정
  public adjustConfidence(delta: number): void {
    this.confidence = Math.max(0, Math.min(1, this.confidence + delta));
  }

  // 관련성 예측
  public predictRelevance(task: string): RelevanceScore {
    // 간단한 관련성 예측 로직
    const relevantTags = this.tags.filter(tag => 
      task.toLowerCase().includes(tag.name.toLowerCase())
    );
    
    const score = relevantTags.length > 0 ? 
      Math.min(0.9, 0.3 + (relevantTags.length * 0.2)) : 0.1;
    
    return {
      score,
      factors: relevantTags.map(t => t.name),
      confidence: this.confidence,
      timestamp: new Date()
    };
  }

  // 노드 정보 직렬화
  public toJSON(): any {
    return {
      id: this.id,
      content: this.content,
      tags: this.tags,
      categories: this.categories,
      connections: Array.from(this.connections.entries()),
      metrics: this.metrics,
      lastModified: this.lastModified.toISOString(),
      accessCount: this.accessCount,
      confidence: this.confidence
    };
  }

  // 노드 정보 역직렬화
  public static fromJSON(data: any): IntelligentNode {
    const node = new IntelligentNode(data.id, data.content, data.tags, data.categories);
    node.connections = new Map(data.connections);
    node.metrics = data.metrics;
    node.lastModified = new Date(data.lastModified);
    node.accessCount = data.accessCount;
    node.confidence = data.confidence;
    return node;
  }
}