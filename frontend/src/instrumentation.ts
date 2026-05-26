// ADR-0006: Next.js Node runtime (SSR / Server Actions / route handlers) を
// @vercel/otel で自動計装する。Next.js 15.3 は app root の instrumentation.ts を
// 自動検出するので next.config.ts の experimental フラグは不要。
//
// OTLP 送信先・サンプリング・リソース属性は compose の OTEL_* env vars (lines 67-92)
// から runtime に注入されるため、ここでは serviceName だけ明示する。
import { registerOTel } from "@vercel/otel";

export function register() {
  registerOTel({
    serviceName: process.env.OTEL_SERVICE_NAME ?? "frontend",
  });
}
