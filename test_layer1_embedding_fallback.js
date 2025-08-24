#!/usr/bin/env node
/**
 * Layer 1 임베딩 서비스 폴백 모드 테스트
 */

import { EmbeddingService } from './dist/layer1/services/embedding-service.js';

async function testEmbeddingServiceFallback() {
    console.log('🚀 Layer 1 임베딩 서비스 폴백 모드 테스트 시작\n');
    
    try {
        // 임베딩 서비스 초기화 (API 키 없이)
        const embeddingService = new EmbeddingService('dummy-key');
        console.log('✅ 임베딩 서비스 초기화 완료 (폴백 모드)');
        
        // 테스트 텍스트들
        const testTexts = [
            'AI neural networks for natural language processing',
            'Machine learning algorithms and deep learning',
            'Natural language understanding and generation',
            'Computer vision and image recognition',
            'Data science and analytics'
        ];
        
        console.log('\n📝 개별 임베딩 테스트 (폴백 모드):');
        for (let i = 0; i < testTexts.length; i++) {
            const text = testTexts[i];
            console.log(`\n${i + 1}. 텍스트: "${text}"`);
            
            try {
                const startTime = Date.now();
                const result = await embeddingService.getEmbedding({
                    text: text,
                    maxTokens: 8000
                });
                const endTime = Date.now();
                
                console.log(`   ✅ 임베딩 생성 성공 (폴백)`);
                console.log(`   📊 차원: ${result.embedding.length}`);
                console.log(`   🏷️ 모델: ${result.model}`);
                console.log(`   ⏱️ 실행 시간: ${endTime - startTime}ms`);
                console.log(`   🗄️ 캐시 사용: ${result.cached ? '예' : '아니오'}`);
                
                // 임베딩 품질 평가
                const quality = embeddingService.evaluateEmbeddingQuality(result.embedding);
                console.log(`   🎯 품질: ${quality.quality} (차원: ${quality.dimension}, 크기: ${quality.magnitude.toFixed(3)}, 희소성: ${(quality.sparsity * 100).toFixed(1)}%)`);
                
                // 임베딩 값 샘플 출력
                const sampleValues = result.embedding.slice(0, 5);
                console.log(`   📊 샘플 값: [${sampleValues.map(v => v.toFixed(3)).join(', ')}...]`);
                
            } catch (error) {
                console.log(`   ❌ 임베딩 생성 실패: ${error.message}`);
            }
        }
        
        console.log('\n🔍 유사도 검색 테스트 (폴백 모드):');
        try {
            // 첫 번째 텍스트를 쿼리로 사용
            const queryText = testTexts[0];
            const queryResult = await embeddingService.getEmbedding({ text: queryText });
            
            // 다른 텍스트들과 유사도 계산
            const similarities = [];
            for (let i = 1; i < testTexts.length; i++) {
                const targetResult = await embeddingService.getEmbedding({ text: testTexts[i] });
                const similarity = embeddingService.cosineSimilarity(
                    queryResult.embedding, 
                    targetResult.embedding
                );
                similarities.push({
                    text: testTexts[i],
                    similarity: similarity
                });
            }
            
            // 유사도 순으로 정렬
            similarities.sort((a, b) => b.similarity - a.similarity);
            
            console.log(`   🔍 쿼리: "${queryText}"`);
            console.log(`   📊 유사도 순위:`);
            similarities.forEach((item, index) => {
                console.log(`      ${index + 1}. ${(item.similarity * 100).toFixed(1)}% - "${item.text}"`);
            });
            
        } catch (error) {
            console.log(`   ❌ 유사도 검색 실패: ${error.message}`);
        }
        
        console.log('\n📊 사용량 통계 (폴백 모드):');
        const usageStats = embeddingService.getUsageStats();
        console.log(`   📞 API 호출 횟수: ${usageStats.apiCalls}`);
        console.log(`   💰 총 비용: $${usageStats.totalCost}`);
        console.log(`   🗄️ 캐시 크기: ${usageStats.cacheSize}`);
        console.log(`   🎯 캐시 히트율: ${(usageStats.cacheHitRate * 100).toFixed(1)}%`);
        console.log(`   💸 평균 호출당 비용: $${usageStats.avgCostPerCall.toFixed(6)}`);
        
        console.log('\n🔍 폴백 모드 분석:');
        console.log(`   📝 폴백 임베딩은 MD5 해시 기반으로 생성됨`);
        console.log(`   🔄 OpenAI API 연결 실패 시 자동으로 폴백 모드로 전환`);
        console.log(`   📊 1536차원 벡터로 OpenAI 임베딩과 동일한 구조 유지`);
        console.log(`   ⚠️ 실제 의미론적 유사도는 제공하지 않음 (Phase 0 수준)`);
        
        console.log('\n✅ Layer 1 임베딩 서비스 폴백 모드 테스트 완료');
        
    } catch (error) {
        console.error('❌ 테스트 중 오류 발생:', error);
    }
}

// 테스트 실행
testEmbeddingServiceFallback().catch(console.error);
