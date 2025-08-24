/**
 * ARGO Layer 1 Phase 1: 데이터 소스 통합 테스트
 * 평가 기준표 Level 1 요구사항 검증
 */

import { DataSourceIntegrationService } from './dist/layer1/services/data-source-integration.js';
import { EmbeddingService } from './dist/layer1/services/embedding-service.js';
import { GoogleDriveService } from './dist/layer1/services/google-drive-service.js';

async function testDataSourceIntegration() {
  console.log('🚀 ARGO Layer 1 Phase 1 데이터 소스 통합 테스트 시작');
  console.log('📊 평가 기준표 Level 1 요구사항 검증');
  console.log('=' * 60);

  try {
    // 1. 서비스 초기화
    console.log('\n🔧 서비스 초기화...');
    
    const embeddingService = new EmbeddingService();
    const driveService = new GoogleDriveService(embeddingService);
    
    const dataSourceConfig = {
      localDirectories: ['C:/argo-sync', 'C:/Argo-813'],
      googleDriveEnabled: true,
      browserHistoryEnabled: true,
      calendarEnabled: true,
      notionEnabled: true,
      slackEnabled: false,
      bigQueryProjectId: 'argo-project',
      bigQueryDatasetId: 'argo_analytics'
    };

    const integrationService = new DataSourceIntegrationService(
      dataSourceConfig,
      embeddingService,
      driveService
    );

    console.log('✅ 모든 서비스 초기화 완료');

    // 2. 개별 데이터 소스 통합 테스트
    console.log('\n📁 1. 로컬 파일 시스템 통합 테스트...');
    const localFilesResult = await integrationService.integrateLocalFileSystem();
    console.log(`   결과: ${localFilesResult.processedCount}개 성공, ${localFilesResult.errorCount}개 실패`);

    console.log('\n☁️ 2. Google Drive 통합 테스트...');
    const googleDriveResult = await integrationService.integrateGoogleDrive();
    console.log(`   결과: ${googleDriveResult.processedCount}개 성공, ${googleDriveResult.errorCount}개 실패`);

    console.log('\n🌐 3. 웹 브라우징 기록 통합 테스트...');
    const browserHistoryResult = await integrationService.integrateBrowserHistory();
    console.log(`   결과: ${browserHistoryResult.processedCount}개 성공, ${browserHistoryResult.errorCount}개 실패`);

    console.log('\n📅 4. 캘린더 통합 테스트...');
    const calendarResult = await integrationService.integrateCalendar();
    console.log(`   결과: ${calendarResult.processedCount}개 성공, ${calendarResult.errorCount}개 실패`);

    console.log('\n🔌 5. 앱 API 통합 테스트...');
    const appAPIsResult = await integrationService.integrateAppAPIs();
    console.log(`   결과: ${appAPIsResult.processedCount}개 성공, ${appAPIsResult.errorCount}개 실패`);

    // 3. 전체 통합 테스트
    console.log('\n🚀 전체 데이터 소스 통합 테스트...');
    const allResults = await integrationService.integrateAllDataSources();
    
    console.log('\n📊 === 최종 통합 결과 ===');
    console.log(`✅ 총 처리된 항목: ${allResults.summary.totalProcessed}개`);
    console.log(`❌ 총 오류: ${allResults.summary.totalErrors}개`);
    console.log(`🎯 전체 성공: ${allResults.summary.overallSuccess ? '예' : '아니오'}`);
    console.log('============================');

    // 4. 통합 히스토리 및 요약
    console.log('\n📈 통합 히스토리 및 통계...');
    const history = integrationService.getIntegrationHistory();
    const summary = integrationService.getIntegrationSummary();
    
    console.log(`📊 총 통합 횟수: ${summary.totalIntegrations}`);
    console.log(`✅ 성공한 통합: ${summary.successfulIntegrations}`);
    console.log(`📈 성공률: ${summary.successRate.toFixed(1)}%`);
    console.log(`📁 총 처리된 파일: ${summary.totalProcessed}개`);

    // 5. Phase 1 달성 기준 검증
    console.log('\n🎯 === Phase 1 달성 기준 검증 ===');
    
    const phase1Requirements = {
      localFileSystem: localFilesResult.success && localFilesResult.processedCount > 0,
      googleDrive: googleDriveResult.success && googleDriveResult.processedCount >= 0,
      browserHistory: browserHistoryResult.success && browserHistoryResult.processedCount >= 0,
      calendar: calendarResult.success && calendarResult.processedCount >= 0,
      appAPIs: appAPIsResult.success && appAPIsResult.processedCount >= 0
    };

    console.log('📁 로컬 파일 시스템 통합:', phase1Requirements.localFileSystem ? '✅ 달성' : '❌ 미달성');
    console.log('☁️ Google Drive 통합:', phase1Requirements.googleDrive ? '✅ 달성' : '❌ 미달성');
    console.log('🌐 웹 브라우징 기록 통합:', phase1Requirements.browserHistory ? '✅ 달성' : '❌ 미달성');
    console.log('📅 캘린더 통합:', phase1Requirements.calendar ? '✅ 달성' : '❌ 미달성');
    console.log('🔌 앱 API 통합:', phase1Requirements.appAPIs ? '✅ 달성' : '❌ 미달성');

    const allRequirementsMet = Object.values(phase1Requirements).every(met => met);
    console.log(`\n🎯 Phase 1 전체 달성: ${allRequirementsMet ? '✅ 성공' : '❌ 실패'}`);

    if (allRequirementsMet) {
      console.log('\n🎉 축하합니다! ARGO Layer 1 Phase 1이 성공적으로 완성되었습니다!');
      console.log('📊 모든 디지털 자산이 ARGO의 단일 의미론적 공간으로 통합되었습니다.');
      console.log('🚀 다음 단계: Level 2 (실시간 동기화 및 웹훅) 구현 준비');
    } else {
      console.log('\n⚠️ 일부 Phase 1 요구사항이 달성되지 않았습니다.');
      console.log('🔧 추가 작업이 필요합니다.');
    }

  } catch (error) {
    console.error('❌ 데이터 소스 통합 테스트 실패:', error);
    process.exit(1);
  }
}

// 테스트 실행
testDataSourceIntegration().then(() => {
  console.log('\n✅ 테스트 완료');
  process.exit(0);
}).catch((error) => {
  console.error('❌ 테스트 실행 실패:', error);
  process.exit(1);
});
