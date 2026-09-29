import { LoginForm } from "@/components/login/LoginForm";
import { devLoginEnabled } from "@/lib/server/config";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; next?: string }>;
}) {
  const { error, next } = await searchParams;
  return <LoginForm devLogin={devLoginEnabled()} error={error ?? null} next={next ?? null} />;
}
