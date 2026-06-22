import { NextResponse, type NextRequest } from "next/server";

const ROLE_COOKIE = "amg_caregiver_role";

export function middleware(request: NextRequest) {
  if (!caregiverAccessEnabled()) {
    return NextResponse.next();
  }

  const isCaregiverRoute = request.nextUrl.pathname.startsWith("/caregiver");
  const isAccessRoute = request.nextUrl.pathname.startsWith("/caregiver/access");
  if (!isCaregiverRoute || isAccessRoute) {
    return NextResponse.next();
  }

  const role = request.cookies.get(ROLE_COOKIE)?.value;
  if (role === "caregiver") {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/caregiver/access";
  url.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/caregiver/:path*"]
};

function caregiverAccessEnabled(): boolean {
  return process.env.CAREGIVER_ACCESS_ENABLED === "true";
}
