/**
 * ARGO Layer 1 성능 프로파일링 도구
 * 시스템 병목 지점 식별 및 성능 최적화를 위한 분석 도구
 */

interface PerformanceMetric {
  name: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  metadata?: Record<string, any>;
}

interface SystemProfile {
  timestamp: Date;
  totalDuration: number;
  metrics: PerformanceMetric[];
  memoryUsage: NodeJS.MemoryUsage;
  cpuUsage: NodeJS.CpuUsage;
  bottlenecks: BottleneckAnalysis[];
}

interface BottleneckAnalysis {
  component: string;
  averageTime: number;
  maxTime: number;
  callCount: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  recommendations: string[];
}

/**
 * 성능 프로파일링 클래스
 */
class PerformanceProfiler {
  private metrics: Map<string, PerformanceMetric[]> = new Map();
  private activeTimers: Map<string, number> = new Map();
  private cpuStartUsage?: NodeJS.CpuUsage;
  private profilingStartTime: number = 0;

  /**
   * 프로파일링 시작
   */
  startProfiling(): void {
    this.profilingStartTime = performance.now();
    this.cpuStartUsage = process.cpuUsage();
    this.metrics.clear();
    this.activeTimers.clear();
    
    console.log('🔍 성능 프로파일링 시작됨');
  }

  /**
   * 개별 작업 측정 시작
   */
  startTimer(name: string, metadata?: Record<string, any>): void {
    const startTime = performance.now();
    
    this.activeTimers.set(name, startTime);
    
    if (!this.metrics.has(name)) {
      this.metrics.set(name, []);
    }
    
    this.metrics.get(name)!.push({
      name,
      startTime,
      metadata
    });
  }

  /**
   * 개별 작업 측정 종료
   */
  endTimer(name: string): number {
    const endTime = performance.now();
    const startTime = this.activeTimers.get(name);
    
    if (!startTime) {
      console.warn(`⚠️ 타이머 '${name}'이 시작되지 않았습니다`);
      return 0;
    }
    
    const duration = endTime - startTime;
    const metrics = this.metrics.get(name);
    
    if (metrics) {
      const lastMetric = metrics[metrics.length - 1];
      lastMetric.endTime = endTime;
      lastMetric.duration = duration;
    }
    
    this.activeTimers.delete(name);
    
    return duration;
  }

  /**
   * 비동기 작업 측정
   */
  async measureAsync<T>(name: string, task: () => Promise<T>, metadata?: Record<string, any>): Promise<T> {
    this.startTimer(name, metadata);
    
    try {
      const result = await task();
      this.endTimer(name);
      return result;
    } catch (error) {
      this.endTimer(name);
      throw error;
    }
  }

  /**
   * 동기 작업 측정
   */
  measureSync<T>(name: string, task: () => T, metadata?: Record<string, any>): T {
    this.startTimer(name, metadata);
    
    try {
      const result = task();
      this.endTimer(name);
      return result;
    } catch (error) {
      this.endTimer(name);
      throw error;
    }
  }

  /**
   * 메모리 사용량 측정
   */
  measureMemoryUsage(label: string): NodeJS.MemoryUsage {
    const memUsage = process.memoryUsage();
    
    console.log(`📊 메모리 사용량 (${label}):`);
    console.log(`  - RSS: ${(memUsage.rss / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  - Heap Used: ${(memUsage.heapUsed / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  - Heap Total: ${(memUsage.heapTotal / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  - External: ${(memUsage.external / 1024 / 1024).toFixed(2)} MB`);
    
    return memUsage;
  }

  /**
   * 프로파일링 종료 및 분석
   */
  generateProfile(): SystemProfile {
    const endTime = performance.now();
    const totalDuration = endTime - this.profilingStartTime;
    const memoryUsage = process.memoryUsage();
    const cpuUsage = this.cpuStartUsage ? process.cpuUsage(this.cpuStartUsage) : process.cpuUsage();
    
    // 모든 메트릭을 평면 배열로 변환
    const allMetrics: PerformanceMetric[] = [];
    for (const metrics of this.metrics.values()) {
      allMetrics.push(...metrics);
    }
    
    // 병목 지점 분석
    const bottlenecks = this.analyzeBottlenecks();
    
    const profile: SystemProfile = {
      timestamp: new Date(),
      totalDuration,
      metrics: allMetrics,
      memoryUsage,
      cpuUsage,
      bottlenecks
    };
    
    this.printProfileSummary(profile);
    
    return profile;
  }

  /**
   * 병목 지점 분석
   */
  private analyzeBottlenecks(): BottleneckAnalysis[] {
    const bottlenecks: BottleneckAnalysis[] = [];
    
    for (const [component, metrics] of this.metrics.entries()) {
      const durations = metrics
        .filter(m => m.duration !== undefined)
        .map(m => m.duration!) as number[];
      
      if (durations.length === 0) continue;
      
      const totalTime = durations.reduce((sum, d) => sum + d, 0);
      const averageTime = totalTime / durations.length;
      const maxTime = Math.max(...durations);
      const callCount = durations.length;
      
      // 심각도 판정
      let severity: BottleneckAnalysis['severity'] = 'low';
      const recommendations: string[] = [];
      
      if (averageTime > 5000) {
        severity = 'critical';
        recommendations.push('5초 이상의 평균 응답시간은 심각한 성능 문제입니다');
        recommendations.push('알고리즘 최적화 또는 캐싱 전략 도입 필요');
      } else if (averageTime > 2000) {
        severity = 'high';
        recommendations.push('2초 이상의 응답시간 개선 필요');
        recommendations.push('비동기 처리 또는 배치 처리 고려');
      } else if (averageTime > 1000) {
        severity = 'medium';
        recommendations.push('1초 이상의 응답시간 모니터링 필요');
      }
      
      if (maxTime > averageTime * 3) {
        recommendations.push('최대 응답시간이 평균의 3배 이상: 성능 변동성 큼');
        recommendations.push('일관된 성능을 위한 리소스 할당 검토 필요');
      }
      
      if (callCount > 100 && averageTime > 100) {
        recommendations.push('높은 호출 빈도와 응답시간: 캐싱 전략 고려');
      }
      
      bottlenecks.push({
        component,
        averageTime,
        maxTime,
        callCount,
        severity,
        recommendations
      });
    }
    
    // 심각도와 평균시간으로 정렬
    bottlenecks.sort((a, b) => {
      const severityOrder = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1 };
      const severityDiff = severityOrder[b.severity] - severityOrder[a.severity];
      if (severityDiff !== 0) return severityDiff;
      return b.averageTime - a.averageTime;
    });
    
    return bottlenecks;
  }

  /**
   * 프로파일 요약 출력
   */
  private printProfileSummary(profile: SystemProfile): void {
    console.log('\n🔍 ===== ARGO Layer 1 성능 프로파일 =====');
    console.log(`📅 측정 시간: ${profile.timestamp.toISOString()}`);
    console.log(`⏱️ 총 소요시간: ${profile.totalDuration.toFixed(2)}ms`);
    
    console.log('\n📊 메모리 사용량:');
    console.log(`  - RSS: ${(profile.memoryUsage.rss / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  - Heap Used: ${(profile.memoryUsage.heapUsed / 1024 / 1024).toFixed(2)} MB`);
    
    console.log('\n💻 CPU 사용량:');
    console.log(`  - User CPU: ${(profile.cpuUsage.user / 1000).toFixed(2)}ms`);
    console.log(`  - System CPU: ${(profile.cpuUsage.system / 1000).toFixed(2)}ms`);
    
    if (profile.bottlenecks.length > 0) {
      console.log('\n🚨 병목 지점 분석:');
      
      profile.bottlenecks.slice(0, 5).forEach((bottleneck, index) => {
        const emoji = {
          'critical': '🔴',
          'high': '🟡',
          'medium': '🟠',
          'low': '🟢'
        };
        
        console.log(`\n${index + 1}. ${emoji[bottleneck.severity]} ${bottleneck.component}`);
        console.log(`   평균 시간: ${bottleneck.averageTime.toFixed(2)}ms`);
        console.log(`   최대 시간: ${bottleneck.maxTime.toFixed(2)}ms`);
        console.log(`   호출 횟수: ${bottleneck.callCount}회`);
        console.log(`   심각도: ${bottleneck.severity.toUpperCase()}`);
        
        if (bottleneck.recommendations.length > 0) {
          console.log('   📝 권장사항:');
          bottleneck.recommendations.forEach(rec => {
            console.log(`      - ${rec}`);
          });
        }
      });
    }
    
    console.log('\n🎯 성능 지표 요약:');
    const components = Array.from(this.metrics.keys());
    
    components.forEach(component => {
      const metrics = this.metrics.get(component)!;
      const durations = metrics
        .filter(m => m.duration !== undefined)
        .map(m => m.duration!) as number[];
      
      if (durations.length > 0) {
        const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length;
        console.log(`  ${component}: ${avg.toFixed(2)}ms (${durations.length}회 호출)`);
      }
    });
    
    console.log('\n=========================================\n');
  }

  /**
   * 성능 지표를 JSON으로 내보내기
   */
  exportToJSON(filePath: string): Promise<void> {
    const profile = this.generateProfile();
    
    return require('fs').promises.writeFile(
      filePath, 
      JSON.stringify(profile, null, 2)
    );
  }

  /**
   * 시스템 리소스 모니터링 시작
   */
  startResourceMonitoring(intervalMs: number = 5000): NodeJS.Timeout {
    console.log(`🔍 시스템 리소스 모니터링 시작 (${intervalMs}ms 간격)`);
    
    return setInterval(() => {
      const memUsage = process.memoryUsage();
      const cpuUsage = process.cpuUsage();
      
      console.log(`📊 [${new Date().toISOString()}] 시스템 상태:`);
      console.log(`   메모리: ${(memUsage.heapUsed / 1024 / 1024).toFixed(2)} MB`);
      console.log(`   CPU: ${(cpuUsage.user / 1000).toFixed(2)}ms user, ${(cpuUsage.system / 1000).toFixed(2)}ms system`);
    }, intervalMs);
  }

  /**
   * 특정 함수의 성능을 지속적으로 모니터링
   */
  createMonitoredFunction<T extends (...args: any[]) => any>(
    name: string,
    originalFunction: T
  ): T {
    return ((...args: any[]) => {
      this.startTimer(name);
      
      try {
        const result = originalFunction(...args);
        
        if (result instanceof Promise) {
          return result.finally(() => this.endTimer(name));
        } else {
          this.endTimer(name);
          return result;
        }
      } catch (error) {
        this.endTimer(name);
        throw error;
      }
    }) as T;
  }
}

// 전역 인스턴스
const globalProfiler = new PerformanceProfiler();

export {
  PerformanceProfiler,
  SystemProfile,
  BottleneckAnalysis,
  PerformanceMetric,
  globalProfiler
};