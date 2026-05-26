// ADR-0006 FE-015: Datadog Browser RUM の唯一の mount point。
// layout.tsx から <RumInit /> を 1 回だけ呼ぶ。layout 自体は Server Component
// のまま、本 client island だけ hydration する。
//
// Atomic Design の atoms/molecules/organisms ではない infrastructure mount
// のため _rum/ 配下に隔離 (Next.js の private folder 規約 = _ prefix で route 化されない)。

"use client";

import { useEffect } from "react";

import { RUM_ENABLED } from "@/lib/constants";
import { initRum } from "@/lib/datadog-rum";

export function RumInit() {
  useEffect(() => {
    if (RUM_ENABLED) initRum();
  }, []);
  return null;
}
