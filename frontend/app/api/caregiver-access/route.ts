import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const ROLE_COOKIE = "amg_caregiver_role";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const intent = String(formData.get("intent") ?? "login");
  const nextPath = safeNextPath(String(formData.get("next") ?? "/caregiver"));

  if (intent === "logout") {
    const cookieStore = await cookies();
    cookieStore.delete(ROLE_COOKIE);
    return NextResponse.redirect(new URL("/caregiver/access", request.url), { status: 303 });
  }

  const passcode = String(formData.get("passcode") ?? "");
  if (!caregiverAccessEnabled()) {
    return NextResponse.redirect(new URL(nextPath, request.url), { status: 303 });
  }
  if (!caregiverPasscodeConfigured()) {
    return redirectWithError(request, "/caregiver/access", "not_configured");
  }
  if (passcode !== process.env.CAREGIVER_PASSCODE) {
    return redirectWithError(request, "/caregiver/access", "invalid");
  }

  const response = NextResponse.redirect(new URL(nextPath, request.url), { status: 303 });
  response.cookies.set({
    name: ROLE_COOKIE,
    value: "caregiver",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 8
  });
  return response;
}

function redirectWithError(request: NextRequest, nextPath: string, error: string): NextResponse {
  const url = new URL("/caregiver/access", request.url);
  if (nextPath) {
    url.searchParams.set("next", nextPath);
  }
  if (error) {
    url.searchParams.set("error", error);
  }
  return NextResponse.redirect(url, { status: 303 });
}

function safeNextPath(value: string): string {
  if (!value.startsWith("/") || value.startsWith("//")) {
    return "/caregiver";
  }
  if (value.startsWith("/api/")) {
    return "/caregiver";
  }
  return value;
}

function caregiverAccessEnabled(): boolean {
  return process.env.CAREGIVER_ACCESS_ENABLED === "true";
}

function caregiverPasscodeConfigured(): boolean {
  return Boolean(process.env.CAREGIVER_PASSCODE);
}
