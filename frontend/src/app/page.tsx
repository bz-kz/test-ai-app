import Link from "next/link";
import Button from "@/components/atoms/Button";

/**
 * ルートランディングページ — サーバーコンポーネント。
 * PHI なし、フェッチなし、クライアント状態なし。
 * 臨床スタッフがシステムの主要機能を把握し、患者検索へ移動できる。
 */
export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="font-display text-3xl font-bold text-navy">AI カルテ生成システム</h1>

      <p className="mt-4 text-base leading-relaxed text-slate">
        ローカル LLM による SOAP カルテ下書き生成。患者情報はローカルネットワーク外へ送信しません。
      </p>

      <ul className="mt-8 space-y-3 text-base text-navy" role="list" aria-label="主な機能">
        <li className="flex items-start gap-3">
          <span className="mt-0.5 text-sage" aria-hidden="true">
            ●
          </span>
          <span>患者検索 — 診察番号 (MRN) で即時検索</span>
        </li>
        <li className="flex items-start gap-3">
          <span className="mt-0.5 text-sage" aria-hidden="true">
            ●
          </span>
          <span>下書きを AI 生成 — ストリーミングでリアルタイム表示</span>
        </li>
        <li className="flex items-start gap-3">
          <span className="mt-0.5 text-sage" aria-hidden="true">
            ●
          </span>
          <span>音声入力で口述転記 — マイクで臨床叙述をテキスト化</span>
        </li>
        <li className="flex items-start gap-3">
          <span className="mt-0.5 text-sage" aria-hidden="true">
            ●
          </span>
          <span>編集・承認・訂正で監査可能なチェーン管理</span>
        </li>
      </ul>

      <div className="mt-10">
        <Link href="/patients">
          <Button variant="primary" size="lg">
            患者検索を開く
          </Button>
        </Link>
      </div>

      <p className="mt-8 text-sm text-slate">
        ローカル専用 PoC — すべてのデータは開発者のローカル環境内で処理されます。
      </p>
    </main>
  );
}
