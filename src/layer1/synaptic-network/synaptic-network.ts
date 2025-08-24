/**
 * ARGO Layer 1: Synaptic Network Implementation
 * 신경망 구조를 모방한 지식 연결 네트워크
 */

import { IntelligentNode, NodeConnection } from '../knowledge-mesh/intelligent-node.js';
import { FileContent, Tag, Category } from '../types/common.js';

export interface NetworkMetrics {
  totalNodes: number;
  totalConnections: number;
  averageDegree: number;
  networkDensity: number;
  averagePathLength: number;
  clusteringCoefficient: number;
  modularity: number;
}

export interface NetworkAnalysis {
  communities: string[][];
  influentialNodes: string[];
  bridges: string[];
  bottlenecks: string[];
}

export interface InteractionQuality {
  satisfaction: number;
  timeSpent: number;
  contextRelevance: number;
  surpriseFactor: number;
}

export class SynapticNetwork {
  private nodes: Map<string, IntelligentNode>;
  private adjacencyMatrix: Map<string, Map<string, number>>;
  private globalMetrics: NetworkMetrics;
  private lastUpdate: Date;
  private networkId: string;
  private version: string;

  constructor(networkId: string = 'argo-knowledge-network', version: string = '1.0.0') {
    this.nodes = new Map();
    this.adjacencyMatrix = new Map();
    this.networkId = networkId;
    this.version = version;
    this.lastUpdate = new Date();
    this.globalMetrics = {
      totalNodes: 0,
      totalConnections: 0,
      averageDegree: 0,
      networkDensity: 0,
      averagePathLength: 0,
      clusteringCoefficient: 0,
      modularity: 0
    };
  }

  // 노드 관리
  public addNode(node: IntelligentNode): void {
    this.nodes.set(node.id, node);
    this.adjacencyMatrix.set(node.id, new Map());
    this.updateGlobalMetrics();
  }

  public removeNode(nodeId: string): boolean {
    if (this.nodes.has(nodeId)) {
      // 노드 제거
      this.nodes.delete(nodeId);
      
      // 인접 행렬에서 제거
      this.adjacencyMatrix.delete(nodeId);
      
      // 다른 노드들의 연결에서도 제거
      for (const [id, connections] of this.adjacencyMatrix) {
        connections.delete(nodeId);
      }
      
      this.updateGlobalMetrics();
      return true;
    }
    return false;
  }

  public getNode(nodeId: string): IntelligentNode | undefined {
    return this.nodes.get(nodeId);
  }

  public getAllNodes(): IntelligentNode[] {
    return Array.from(this.nodes.values());
  }

  // 연결 관리
  public addConnection(fromNodeId: string, toNodeId: string, strength: number = 1.0): boolean {
    if (this.nodes.has(fromNodeId) && this.nodes.has(toNodeId)) {
      // 양방향 연결 설정
      if (!this.adjacencyMatrix.has(fromNodeId)) {
        this.adjacencyMatrix.set(fromNodeId, new Map());
      }
      if (!this.adjacencyMatrix.has(toNodeId)) {
        this.adjacencyMatrix.set(toNodeId, new Map());
      }
      
      this.adjacencyMatrix.get(fromNodeId)!.set(toNodeId, strength);
      this.adjacencyMatrix.get(toNodeId)!.set(fromNodeId, strength);
      
      // 노드 간 연결 정보도 업데이트
      const fromNode = this.nodes.get(fromNodeId)!;
      const toNode = this.nodes.get(toNodeId)!;
      
      fromNode.addConnection(toNodeId, {
        targetNodeId: toNodeId,
        strength,
        type: 'semantic',
        metadata: { timestamp: new Date() }
      });
      
      toNode.addConnection(fromNodeId, {
        targetNodeId: fromNodeId,
        strength,
        type: 'semantic',
        metadata: { timestamp: new Date() }
      });
      
      this.updateGlobalMetrics();
      return true;
    }
    return false;
  }

  public removeConnection(fromNodeId: string, toNodeId: string): boolean {
    if (this.adjacencyMatrix.has(fromNodeId) && this.adjacencyMatrix.has(toNodeId)) {
      const fromConnections = this.adjacencyMatrix.get(fromNodeId)!;
      const toConnections = this.adjacencyMatrix.get(toNodeId)!;
      
      const fromRemoved = fromConnections.delete(toNodeId);
      const toRemoved = toConnections.delete(fromNodeId);
      
      if (fromRemoved || toRemoved) {
        // 노드 간 연결 정보도 제거
        const fromNode = this.nodes.get(fromNodeId);
        const toNode = this.nodes.get(toNodeId);
        
        if (fromNode) fromNode.removeConnection(toNodeId);
        if (toNode) toNode.removeConnection(fromNodeId);
        
        this.updateGlobalMetrics();
        return true;
      }
    }
    return false;
  }

  public getConnectionStrength(fromNodeId: string, toNodeId: string): number {
    return this.adjacencyMatrix.get(fromNodeId)?.get(toNodeId) || 0;
  }

  // 네트워크 분석
  public analyzeNetwork(): NetworkAnalysis {
    const communities = this.detectCommunities();
    const influentialNodes = this.findInfluentialNodes();
    const bridges = this.findBridges();
    const bottlenecks = this.findBottlenecks();

    return {
      communities,
      influentialNodes,
      bridges,
      bottlenecks
    };
  }

  private detectCommunities(): string[][] {
    // 간단한 커뮤니티 감지 알고리즘 (Louvain 방법의 단순화된 버전)
    const visited = new Set<string>();
    const communities: string[][] = [];
    
    for (const [nodeId, _] of this.nodes) {
      if (!visited.has(nodeId)) {
        const community = this.dfsCommunity(nodeId, visited);
        if (community.length > 0) {
          communities.push(community);
        }
      }
    }
    
    return communities;
  }

  private dfsCommunity(startNodeId: string, visited: Set<string>): string[] {
    const community: string[] = [];
    const stack = [startNodeId];
    
    while (stack.length > 0) {
      const currentId = stack.pop()!;
      if (!visited.has(currentId)) {
        visited.add(currentId);
        community.push(currentId);
        
        const connections = this.adjacencyMatrix.get(currentId);
        if (connections) {
          for (const [neighborId, _] of connections) {
            if (!visited.has(neighborId)) {
              stack.push(neighborId);
            }
          }
        }
      }
    }
    
    return community;
  }

  private findInfluentialNodes(): string[] {
    // 연결 수 기반 영향력 노드 찾기
    const nodeDegrees = new Map<string, number>();
    
    for (const [nodeId, connections] of this.adjacencyMatrix) {
      nodeDegrees.set(nodeId, connections.size);
    }
    
    return Array.from(nodeDegrees.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, Math.min(10, nodeDegrees.size))
      .map(([nodeId, _]) => nodeId);
  }

  private findBridges(): string[] {
    // 간단한 브리지 노드 감지
    const bridges: string[] = [];
    
    for (const [nodeId, connections] of this.adjacencyMatrix) {
      if (connections.size === 1) {
        bridges.push(nodeId);
      }
    }
    
    return bridges;
  }

  private findBottlenecks(): string[] {
    // 병목 노드 감지 (높은 중심성, 낮은 클러스터링 계수)
    const bottlenecks: string[] = [];
    
    for (const [nodeId, node] of this.nodes) {
      const connections = this.adjacencyMatrix.get(nodeId);
      if (connections && connections.size > 2) {
        // 높은 연결 수를 가진 노드들을 병목으로 간주
        bottlenecks.push(nodeId);
      }
    }
    
    return bottlenecks.slice(0, 5); // 상위 5개만 반환
  }

  // 메트릭 업데이트
  private updateGlobalMetrics(): void {
    const totalNodes = this.nodes.size;
    let totalConnections = 0;
    
    for (const connections of this.adjacencyMatrix.values()) {
      totalConnections += connections.size;
    }
    
    // 양방향 연결이므로 2로 나눔
    totalConnections = Math.floor(totalConnections / 2);
    
    this.globalMetrics = {
      totalNodes,
      totalConnections,
      averageDegree: totalNodes > 0 ? (totalConnections * 2) / totalNodes : 0,
      networkDensity: totalNodes > 1 ? (totalConnections * 2) / (totalNodes * (totalNodes - 1)) : 0,
      averagePathLength: this.calculateAveragePathLength(),
      clusteringCoefficient: this.calculateClusteringCoefficient(),
      modularity: this.calculateModularity()
    };
    
    this.lastUpdate = new Date();
  }

  private calculateAveragePathLength(): number {
    // 간단한 평균 경로 길이 계산
    if (this.nodes.size <= 1) return 0;
    
    let totalPathLength = 0;
    let pathCount = 0;
    
    for (const [nodeId1, _] of this.nodes) {
      for (const [nodeId2, _] of this.nodes) {
        if (nodeId1 !== nodeId2) {
          const pathLength = this.findShortestPath(nodeId1, nodeId2);
          if (pathLength > 0) {
            totalPathLength += pathLength;
            pathCount++;
          }
        }
      }
    }
    
    return pathCount > 0 ? totalPathLength / pathCount : 0;
  }

  private findShortestPath(startId: string, endId: string): number {
    // BFS 기반 최단 경로 찾기
    const visited = new Set<string>();
    const queue: Array<{ id: string; distance: number }> = [{ id: startId, distance: 0 }];
    
    while (queue.length > 0) {
      const { id, distance } = queue.shift()!;
      
      if (id === endId) {
        return distance;
      }
      
      if (!visited.has(id)) {
        visited.add(id);
        const connections = this.adjacencyMatrix.get(id);
        
        if (connections) {
          for (const [neighborId, _] of connections) {
            if (!visited.has(neighborId)) {
              queue.push({ id: neighborId, distance: distance + 1 });
            }
          }
        }
      }
    }
    
    return -1; // 경로를 찾을 수 없음
  }

  private calculateClusteringCoefficient(): number {
    // 네트워크 전체 클러스터링 계수 계산
    if (this.nodes.size <= 2) return 0;
    
    let totalCoefficient = 0;
    let validNodes = 0;
    
    for (const [nodeId, connections] of this.adjacencyMatrix) {
      if (connections.size >= 2) {
        const localCoefficient = this.calculateLocalClusteringCoefficient(nodeId);
        totalCoefficient += localCoefficient;
        validNodes++;
      }
    }
    
    return validNodes > 0 ? totalCoefficient / validNodes : 0;
  }

  private calculateLocalClusteringCoefficient(nodeId: string): number {
    const connections = this.adjacencyMatrix.get(nodeId);
    if (!connections || connections.size < 2) return 0;
    
    const neighbors = Array.from(connections.keys());
    let triangles = 0;
    let possibleTriangles = (neighbors.length * (neighbors.length - 1)) / 2;
    
    if (possibleTriangles === 0) return 0;
    
    for (let i = 0; i < neighbors.length; i++) {
      for (let j = i + 1; j < neighbors.length; j++) {
        const neighbor1 = neighbors[i];
        const neighbor2 = neighbors[j];
        
        if (this.adjacencyMatrix.get(neighbor1)?.has(neighbor2)) {
          triangles++;
        }
      }
    }
    
    return triangles / possibleTriangles;
  }

  private calculateModularity(): number {
    // 간단한 모듈성 계산
    const communities = this.detectCommunities();
    if (communities.length <= 1) return 0;
    
    let modularity = 0;
    const totalEdges = this.globalMetrics.totalConnections;
    
    if (totalEdges === 0) return 0;
    
    for (const community of communities) {
      let internalEdges = 0;
      let totalDegree = 0;
      
      for (const nodeId of community) {
        const connections = this.adjacencyMatrix.get(nodeId);
        if (connections) {
          totalDegree += connections.size;
          
          for (const [neighborId, _] of connections) {
            if (community.includes(neighborId)) {
              internalEdges++;
            }
          }
        }
      }
      
      // 양방향 연결이므로 2로 나눔
      internalEdges = Math.floor(internalEdges / 2);
      
      const expectedEdges = (totalDegree * totalDegree) / (4 * totalEdges);
      modularity += (internalEdges - expectedEdges) / totalEdges;
    }
    
    return modularity;
  }

  // 네트워크 정보
  public getNetworkMetrics(): NetworkMetrics {
    return { ...this.globalMetrics };
  }

  public getNetworkInfo(): any {
    return {
      networkId: this.networkId,
      version: this.version,
      lastUpdate: this.lastUpdate.toISOString(),
      metrics: this.globalMetrics,
      nodeCount: this.nodes.size,
      connectionCount: this.globalMetrics.totalConnections
    };
  }

  // 네트워크 통계
  public getNetworkStats(): any {
    return {
      nodeCount: this.nodes.size,
      connectionCount: this.globalMetrics.totalConnections,
      averageDegree: this.globalMetrics.averageDegree,
      density: this.globalMetrics.networkDensity
    };
  }

  // 경로 강화
  public reinforcePath(path: string[], interactionQuality: number): void {
    if (path.length < 2) return;
    
    for (let i = 0; i < path.length - 1; i++) {
      const fromId = path[i];
      const toId = path[i + 1];
      
      if (this.nodes.has(fromId) && this.nodes.has(toId)) {
        const currentStrength = this.getConnectionStrength(fromId, toId);
        const newStrength = Math.min(1.0, currentStrength + (interactionQuality * 0.1));
        this.addConnection(fromId, toId, newStrength);
      }
    }
  }

  // 네트워크 인사이트 생성
  public generateNetworkInsights(): any[] {
    const insights: any[] = [];
    
    // 허브 노드 감지
    const hubNodes = Array.from(this.nodes.entries())
      .filter(([_, node]) => node.metrics.centrality > 3)
      .map(([id, node]) => ({
        type: 'hub',
        nodeId: id,
        centrality: node.metrics.centrality,
        description: `높은 중심성을 가진 허브 노드`
      }));
    
    insights.push(...hubNodes);
    
    // 브리지 노드 감지
    const bridgeNodes = Array.from(this.nodes.entries())
      .filter(([_, node]) => node.metrics.betweenness > 0.5)
      .map(([id, node]) => ({
        type: 'bridge',
        nodeId: id,
        betweenness: node.metrics.betweenness,
        description: `높은 중간 중심성을 가진 브리지 노드`
      }));
    
    insights.push(...bridgeNodes);
    
    // 커뮤니티 감지
    const communities = this.detectCommunities();
    communities.forEach((community, index) => {
      insights.push({
        type: 'community',
        communityId: index,
        size: community.length,
        description: `${community.length}개 노드로 구성된 커뮤니티`
      });
    });
    
    return insights;
  }

  // 다음 노드 예측
  public predictNextNodes(currentNodeId: string, context: string[] = []): string[] {
    if (!this.nodes.has(currentNodeId)) return [];
    
    const currentNode = this.nodes.get(currentNodeId)!;
    const connections = Array.from(currentNode.connections.entries())
      .sort((a, b) => b[1].strength - a[1].strength);
    
    // 강한 연결을 가진 노드들을 우선적으로 반환
    return connections
      .slice(0, 5)
      .map(([targetId, _]) => targetId);
  }

  // 네트워크 직렬화
  public toJSON(): any {
    return {
      networkId: this.networkId,
      version: this.version,
      lastUpdate: this.lastUpdate.toISOString(),
      nodes: Array.from(this.nodes.entries()),
      adjacencyMatrix: Array.from(this.adjacencyMatrix.entries()).map(([key, value]) => [
        key,
        Array.from(value.entries())
      ]),
      globalMetrics: this.globalMetrics
    };
  }

  // 네트워크 역직렬화
  public static fromJSON(data: any): SynapticNetwork {
    const network = new SynapticNetwork(data.networkId, data.version);
    
    // 노드 복원
    for (const [nodeId, nodeData] of data.nodes) {
      const node = IntelligentNode.fromJSON(nodeData);
      network.nodes.set(nodeId, node);
    }
    
    // 인접 행렬 복원
    for (const [nodeId, connections] of data.adjacencyMatrix) {
      const connectionMap = new Map();
      for (const [targetId, strength] of connections) {
        connectionMap.set(targetId, strength);
      }
      network.adjacencyMatrix.set(nodeId, connectionMap);
    }
    
    // 메트릭 복원
    network.globalMetrics = data.globalMetrics;
    network.lastUpdate = new Date(data.lastUpdate);
    
    return network;
  }
}