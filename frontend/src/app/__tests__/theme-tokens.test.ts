/**
 * @theme トークン × Tailwind 4 ユーティリティの名前空間衝突ガード。
 *
 * Tailwind 4 の `max-w-2xl` / `gap-2xl` / `p-2xl` 等は `--spacing-Nxl`
 * トークンから値を引きます。`@theme` で `--spacing-2xl: 48px` を定義すると
 * `max-w-2xl` が黙って 48px になり、全ページの main コンテナが潰れます。
 *
 * 過去事故: commit d785f12 — `--spacing-2xl: 48px` と `--spacing-3xl: 64px`
 * の登録により `max-w-2xl` (本来 42rem) が 48px に縮み、日本語テキストが
 * 一文字一行に折り返されていた。G1/G2/G3 では検知できず、Item 4 の
 * Playwright スクリーンショットで初めて視覚的に判明。
 *
 * 本テストはその回帰を防ぐ。globals.css の `@theme` ブロック内に
 * 危険トークンが追加されたら即座に G3 で失敗させる。
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

describe("@theme tokens vs Tailwind 4 namespace", () => {
  const cssPath = join(__dirname, "../globals.css");
  const css = readFileSync(cssPath, "utf-8");

  // Tailwind 4 の組み込みスケール (2xl..9xl) と衝突する `--spacing-Nxl` を禁止する。
  // 例: `--spacing-2xl` は `max-w-2xl` / `gap-2xl` / `p-2xl` 等をすべて上書きする。
  it("does not define --spacing-Nxl (collides with max-w-Nxl / gap-Nxl)", () => {
    const matches = Array.from(css.matchAll(/--spacing-([2-9])xl\s*:/g)).map((m) => m[0]);
    expect(matches).toEqual([]);
  });

  // 同じ理由で `--text-Nxl` / `--font-size-Nxl` も将来追加されたら警告する。
  // (現状はゼロだが、Tailwind 4 の text-2xl ユーティリティと衝突しうる名前空間)
  it("does not define --text-Nxl / --font-size-Nxl (collides with text-Nxl)", () => {
    const reservedText = /--(?:text|font-size)-([2-9])xl\s*:/g;
    const matches = Array.from(css.matchAll(reservedText)).map((m) => m[0]);
    expect(matches).toEqual([]);
  });
});
