/**
 * 日時フォーマットユーティリティ。
 *
 * ロケールは `ja-JP` 固定 (UI 文言が日本語のため)。タイムゾーンはブラウザの
 * ローカル TZ に従う (ISO 文字列の UTC 解釈 → JST 変換)。
 *
 * PHI ではないが、表示専用のためログには出力しない (呼び出し元の規約に従う)。
 */

/**
 * ISO 日時文字列を「YYYY年M月D日」形式に変換する (時刻なし)。
 * 患者・受診の詳細画面で日付のみを表示する際に使用する。
 */
export const formatJpDate = (iso: string): string =>
  new Date(iso).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

/**
 * ISO 日時文字列を「YYYY年M月D日 HH:mm」形式に変換する。
 * 患者・受診の詳細画面で登録日時を表示する際に使用する。
 */
export const formatJpDateTime = (iso: string): string =>
  new Date(iso).toLocaleString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

/**
 * ISO 日時文字列を「YYYY/MM/DD HH:mm」形式に変換する (コンパクト)。
 * リストやチェーン表示など、横幅を抑えたい場面で使用する。
 */
export const formatJpDateTimeCompact = (iso: string): string =>
  new Date(iso).toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
