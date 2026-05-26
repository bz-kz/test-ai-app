// ADR-0006 FE-015: Datadog Browser RUM 初期化モジュール。
//
// 本ファイル + components/_rum/RumInit.tsx の 2 ファイルだけが
// @datadog/browser-rum を import できる (security-check probe が isolation を grep で確認)。
//
// PHI 防衛は in-SDK scrub に全責任あり (DD Agent は path に居らず browser → Datadog SaaS 直送)。
// ADR-0006 §Egress contracts (Browser RUM) を実装する。

import { datadogRum } from "@datadog/browser-rum";
import { API_BASE_URL } from "@/lib/constants";

/**
 * PHI を含む可能性のある URL path セグメントを template 形式へ書き換えるカタログ。
 * 新規 PHI ルートを追加したら必ずここにも 1 行足す (G7 + G4 の二重失敗を防ぐ)。
 * 末尾の query string は別途 strip。
 */
const PHI_URL_SCRUB_PATTERNS: ReadonlyArray<readonly [RegExp, string]> = [
  [/\/patients\/[^/?#]+/g, "/patients/:patientId"],
  [/\/encounters\/[^/?#]+/g, "/encounters/:encounterId"],
  [/\/drafts\/[^/?#]+/g, "/drafts/:draftId"],
  [/\/finals\/[^/?#]+/g, "/finals/:finalId"],
] as const;

export function scrubUrl(url: string): string {
  let scrubbed = url;
  for (const [pattern, replacement] of PHI_URL_SCRUB_PATTERNS) {
    scrubbed = scrubbed.replace(pattern, replacement);
  }
  const qIdx = scrubbed.indexOf("?");
  return qIdx >= 0 ? scrubbed.substring(0, qIdx) : scrubbed;
}

/**
 * error.message / error.stack 内の 4 桁以上の連続数字を `?` に置換。
 * MRN / 患者 ID / 受診 ID 等が numeric な場合のリーク対策。
 */
export function scrubErrorMessage(msg: string): string {
  return msg.replace(/[0-9]{4,}/g, "?");
}

// RUM の event 型は @datadog/browser-rum の RumEvent union だが
// scrub 用途では narrow に絞らず unknown でアクセスしてフィールド有無を判定する。
function beforeSend(event: unknown): boolean {
  // 既知の event 形状: { type: 'view' | 'resource' | 'action' | 'error' | 'long_task', ... }
  const e = event as {
    type?: string;
    view?: { url?: string; name?: string; referrer?: string };
    resource?: { url?: string };
    error?: { message?: string; stack?: string };
  };

  if (e.view?.url) e.view.url = scrubUrl(e.view.url);
  if (e.view?.name) e.view.name = scrubUrl(e.view.name);
  if (e.view?.referrer) e.view.referrer = scrubUrl(e.view.referrer);
  if (e.resource?.url) e.resource.url = scrubUrl(e.resource.url);
  if (e.error?.message) e.error.message = scrubErrorMessage(e.error.message);
  if (e.error?.stack) e.error.stack = scrubErrorMessage(e.error.stack);

  return true;
}

export function initRum(): void {
  const applicationId = process.env.NEXT_PUBLIC_DD_RUM_APPLICATION_ID;
  const clientToken = process.env.NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN;

  // applicationId / clientToken が未設定なら no-op。
  // Datadog UI で RUM Application を作成して .env に転記するまではここで弾く。
  if (!applicationId || !clientToken) return;

  // 二重 init 防止。
  if (datadogRum.getInitConfiguration()) return;

  datadogRum.init({
    applicationId,
    clientToken,
    site: process.env.NEXT_PUBLIC_DD_SITE ?? "ap1.datadoghq.com",
    service: process.env.NEXT_PUBLIC_DD_RUM_SERVICE ?? "frontend-browser",
    env: process.env.NEXT_PUBLIC_DD_RUM_ENV ?? "local",
    version: process.env.NEXT_PUBLIC_DD_RUM_VERSION ?? "dev",
    sessionSampleRate: 100,
    // ADR-0006: 全 mask で session replay 有効化。defaultPrivacyLevel='mask' は
    // text 全要素 (user input に限らずラベル含む) を mask 対象にする。
    sessionReplaySampleRate: 20,
    defaultPrivacyLevel: "mask",
    // ADR-0006: long task に CPU stack frame 経由で PHI リテラルが混入する可能性が
    // あるため v1 では無効化。per-route audit 完了まで上げない。
    trackLongTasks: false,
    trackResources: true,
    trackUserInteractions: true,
    // backend (OTel) への trace context は W3C tracecontext (traceparent) のみ。
    // Datadog 専用ヘッダは backend OTel が読まないので無駄。
    allowedTracingUrls: [{ match: API_BASE_URL, propagatorTypes: ["tracecontext"] }],
    beforeSend,
  });

  // PHI を含まない anon ユーザでセッションを束ねる。
  // setUser を別文字列で呼ぶことは ADR-0006 §Egress contracts で禁止。
  datadogRum.setUser({ id: "anon" });

  // ADR-0006: sessionReplaySampleRate>0 なので録画開始。
  datadogRum.startSessionReplayRecording();
}
