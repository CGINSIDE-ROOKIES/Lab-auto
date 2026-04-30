/**
 * 범용 파일 다운로드 프록시
 *
 * 브라우저가 크로스-오리진 URL 다운로드 시 파일명을 제어할 수 없는 문제를 해결.
 * 허용된 호스트의 파일을 서버에서 받아 올바른 Content-Disposition 헤더로 응답.
 *
 * 요청 형태: GET /api/download?url=<encoded_url>&filename=<encoded_filename>
 */

import { NextRequest, NextResponse } from "next/server";

function allowedHosts(): Set<string> {
  const hosts = new Set(["file.scourt.go.kr"]);
  try {
    const supabaseHost = new URL(process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").hostname;
    if (supabaseHost) hosts.add(supabaseHost);
  } catch {}
  return hosts;
}

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get("url") ?? "";
  const filename = req.nextUrl.searchParams.get("filename") ?? "download";

  if (!url) {
    return new NextResponse("url 파라미터 필요", { status: 400 });
  }

  let fetchUrl = url;

  if (url.startsWith("/")) {
    // 상대 경로(예: /api/ekt-download?...) → 같은 origin으로 구성
    fetchUrl = `${req.nextUrl.origin}${url}`;
  } else {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      return new NextResponse("유효하지 않은 URL", { status: 400 });
    }
    if (!allowedHosts().has(parsed.hostname)) {
      return new NextResponse("허용되지 않은 도메인", { status: 403 });
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(fetchUrl);
  } catch (e) {
    return new NextResponse(`파일 요청 실패: ${e}`, { status: 502 });
  }

  if (!upstream.ok) {
    return new NextResponse(`업스트림 오류: ${upstream.status}`, { status: 502 });
  }

  const contentType =
    upstream.headers.get("content-type") ?? "application/octet-stream";
  const safeFilename = filename.replace(/[/\\:*?"<>|]/g, "_");

  return new NextResponse(upstream.body, {
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(safeFilename)}`,
      "Cache-Control": "no-store",
    },
  });
}
