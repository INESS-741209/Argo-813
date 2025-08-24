#!/usr/bin/env node
/**
 * Layer 1 임베딩 서비스 테스트
 */

import { EmbeddingService } from './dist/layer1/services/embedding-service.js';

async function testEmbeddingService() {
    console.log('🚀 Layer 1 임베딩 서비스 테스트 시작\n');
    
    try {
        // 임베딩 서비스 초기화
        const embeddingService = new EmbeddingService();
        console.log('✅ 임베딩 서비스 초기화 완료');
        
        // 테스트 텍스트들
        const testTexts = [
            'AI neural networks for natural language processing',
            'Machine learning algorithms and deep learning',
            'Natural language understanding and generation',
            'Computer vision and image recognition',
            'Data science and analytics'
        ];
        
        console.log('\n📝 개별 임베딩 테스트:');
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
                
                console.log(`   ✅ 임베딩 생성 성공`);
                console.log(`   📊 차원: ${result.embedding.length}`);
                console.log(`   🏷️ 모델: ${result.model}`);
                console.log(`   💰 비용: $${(result.cost || 0).toFixed(6)}`);
                console.log(`   ⏱️ 실행 시간: ${endTime - startTime}ms`);
                console.log(`   🗄️ 캐시 사용: ${result.cached ? '예' : '아니오'}`);
                
                // 임베딩 품질 평가
                const quality = embeddingService.evaluateEmbeddingQuality(result.embedding);
                console.log(`   🎯 품질: ${quality.quality} (차원: ${quality.dimension}, 크기: ${quality.magnitude.toFixed(3)}, 희소성: ${(quality.sparsity * 100).toFixed(1)}%)`);
                
            } catch (error) {
                console.log(`   ❌ 임베딩 생성 실패: ${error.message}`);
            }
        }
        
        console.log('\n📦 배치 임베딩 테스트:');
        try {
            const startTime = Date.now();
            const batchResults = await embeddingService.getBatchEmbeddings(testTexts);
            const endTime = Date.now();
            
            console.log(`   ✅ 배치 임베딩 생성 성공`);
            console.log(`   📊 총 개수: ${batchResults.length}`);
            console.log(`   ⏱️ 총 실행 시간: ${endTime - startTime}ms`);
            console.log(`   📈 평균 실행 시간: ${((endTime - startTime) / batchResults.length).toFixed(2)}ms`);
            
            // 성공률 계산
            const successCount = batchResults.filter(r => r.embedding && r.embedding.length > 0).length;
            console.log(`   🎯 성공률: ${(successCount / batchResults.length * 100).toFixed(1)}%`);
            
        } catch (error) {
            console.log(`   ❌ 배치 임베딩 생성 실패: ${error.message}`);
        }
        
        console.log('\n🔍 유사도 검색 테스트:');
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
        
        console.log('\n📊 사용량 통계:');
        const usageStats = embeddingService.getUsageStats();
        console.log(`   📞 API 호출 횟수: ${usageStats.apiCalls}`);
        console.log(`   💰 총 비용: $${usageStats.totalCost}`);
        console.log(`   🗄️ 캐시 크기: ${usageStats.cacheSize}`);
        console.log(`   🎯 캐시 히트율: ${(usageStats.cacheHitRate * 100).toFixed(1)}%`);
        console.log(`   💸 평균 호출당 비용: $${usageStats.avgCostPerCall.toFixed(6)}`);
        
        console.log('\n✅ Layer 1 임베딩 서비스 테스트 완료');
        
    } catch (error) {
        console.error('❌ 테스트 중 오류 발생:', error);
    }
}

// 테스트 실행
testEmbeddingService().catch(console.error);
