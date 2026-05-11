/**
 * PHI マスキングユーティリティ。
 *
 * バックエンドの app/domain/phi.py の mask_phi() と同じ意図を持つ。
 * ログ出力前に PHI 値をこの関数に通すことで、生の個人情報がログに残るのを防ぐ。
 *
 * 出力形式: "[PHI len=N]"
 *   N は元の文字列の長さ (non-string は JSON 文字列化後の長さ)。
 *   長さのヒントだけ残し、内容は完全に除去する。
 *
 * 使用例:
 *   maskPhi("MRN-0001-2024")  // => "[PHI len=13]"
 *   maskPhi(12345)            // => "[PHI len=5]"
 *   maskPhi(null)             // => "[PHI len=4]"
 */
export function maskPhi(value: unknown): string {
  if (typeof value === "string") {
    return `[PHI len=${value.length}]`;
  }
  // 文字列以外は String() で変換してから長さを計算する。
  // null/undefined は String() がそれぞれ "null"/"undefined" に変換するので ?? は使わない。
  const str = String(value);
  return `[PHI len=${str.length}]`;
}
