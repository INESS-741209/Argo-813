/**
 * Jest 테스트 설정
 * 모든 테스트 파일에서 사용할 공통 설정
 */

// 환경 변수 설정 (테스트용)
process.env.NODE_ENV = 'test';
process.env.OPENAI_API_KEY = 'test-api-key';

// 콘솔 출력 줄이기 (테스트 중)
const originalConsoleLog = console.log;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

beforeAll(() => {
  console.log = jest.fn();
  console.warn = jest.fn();
  console.error = jest.fn();
});

afterAll(() => {
  console.log = originalConsoleLog;
  console.warn = originalConsoleWarn;
  console.error = originalConsoleError;
});

// 테스트 타임아웃 설정
jest.setTimeout(30000);

// 전역 테스트 유틸리티
global.testUtils = {
  delay: (ms: number) => new Promise(resolve => setTimeout(resolve, ms)),
  mockFile: {
    path: 'C:\\test\\test-file.md',
    content: '# Test File\nThis is a test file for ARGO Layer 1 testing.',
    size: 100
  }
};