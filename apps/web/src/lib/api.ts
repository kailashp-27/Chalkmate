import { supabase } from "./supabase";

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const { data } = await supabase!.auth.getSession();
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      Authorization: `Bearer ${data.session?.access_token ?? ""}`,
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : "The request could not be completed. Review your entries and try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function downloadApi(path: string, filename: string) {
  const { data } = await supabase!.auth.getSession();
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    headers: { Authorization: `Bearer ${data.session?.access_token ?? ""}` },
  });
  if (!response.ok)
    throw new Error("The export could not be prepared. Try again.");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
