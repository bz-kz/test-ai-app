/* jsdom 環境で jest-dom マッチャーを全テストへ適用するためのセットアップ。 */
import "@testing-library/jest-dom";
import { vi } from "vitest";

/* next/navigation は AppRouter コンテキスト外で hook を呼ぶと throw するため、
   ページ/コンポーネントテストで安全に render できるようグローバルにスタブする。
   個別テストで挙動を上書きしたい場合は vi.mocked(useRouter).mockReturnValue(...) で対応する。 */
vi.mock("next/navigation", () => ({
  /* useRouter は vi.fn() で包み個別テストから mockReturnValueOnce で上書きできるようにする。 */
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })),
  usePathname: vi.fn(() => "/"),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  useParams: vi.fn(() => ({})),
  redirect: vi.fn(),
  notFound: vi.fn(),
}));
