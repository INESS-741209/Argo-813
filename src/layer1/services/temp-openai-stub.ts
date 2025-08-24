// 임시 OpenAI 스텁 - 실제 구현에서는 openai 패키지 설치 필요
export class Configuration {
  constructor(options: any) {}
}

export class OpenAIApi {
  constructor(config: Configuration) {}
  
  async createEmbedding(params: any): Promise<any> {
    // 모의 응답
    return {
      data: {
        data: [{ embedding: new Array(1536).fill(0).map(() => Math.random() * 2 - 1) }],
        usage: { total_tokens: Math.floor(params.input.length / 4) }
      }
    };
  }
}