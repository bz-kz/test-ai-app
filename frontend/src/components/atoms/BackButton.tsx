"use client";
import { useRouter } from "next/navigation";

interface BackButtonProps {
  label?: string;
}

export default function BackButton({ label = "← 戻る" }: BackButtonProps) {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.back()}
      className="text-sm text-sage hover:underline"
    >
      {label}
    </button>
  );
}
